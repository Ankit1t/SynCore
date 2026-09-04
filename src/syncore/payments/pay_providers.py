"""Phase-2 payment provider abstraction + adapters (Blueprint STEP 16/17/45/46).

Providers declare capabilities; the broker discovers them before executing.
MockDelegatedProvider is a deterministic sandbox (no real money). RazorpayProvider
is a real adapter whose structure follows Razorpay's documented Orders/Payments
API, but it refuses to act without configured credentials (never fabricates a
production call). No provider method is invented beyond documented behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from ..config import get_settings
from ..domain.models import new_id
from ..observability.logging import get_logger

logger = get_logger("syncore.payments.pay_providers")

_RZP_API_BASE = "https://api.razorpay.com/v1"


@dataclass
class ProviderExecResult:
    state: str  # "SUCCESS" | "FAILED" | "UNKNOWN"
    provider_ref: str | None
    detail: str = ""


@dataclass
class RefundResult:
    ok: bool
    provider_ref: str | None
    detail: str = ""


class PaymentProvider2(Protocol):
    name: str

    def available(self) -> bool: ...
    def capabilities(self) -> dict: ...
    def execute_payment(self, *, amount_paise: int, currency: str, merchant_id: str,
                        idempotency_key: str) -> ProviderExecResult: ...
    def get_status(self, provider_ref: str) -> str: ...
    def refund(self, *, provider_ref: str, amount_paise: int) -> RefundResult: ...


class MockDelegatedProvider:
    """Deterministic sandbox. Idempotent: same key -> same outcome, one charge."""

    name = "mock"

    def __init__(self) -> None:
        self._by_key: dict[str, ProviderExecResult] = {}
        self._truth: dict[str, str] = {}
        self._charges: list[str] = []
        self._script: list[str] = []

    def script(self, *states: str) -> None:
        self._script.extend(states)

    def available(self) -> bool:
        return True

    def capabilities(self) -> dict:
        return {
            "delegated_payment": True, "user_present_required": False,
            "merchant_binding": True, "amount_binding": True,
            "refund": True, "reconciliation": True, "sandbox": True,
        }

    def execute_payment(self, *, amount_paise: int, currency: str, merchant_id: str,
                        idempotency_key: str) -> ProviderExecResult:
        if idempotency_key in self._by_key:
            return self._by_key[idempotency_key]
        state = self._script.pop(0) if self._script else "SUCCESS"
        ref = "pay_" + new_id()[:14]
        if state in ("SUCCESS", "UNKNOWN"):  # UNKNOWN => money likely moved
            self._charges.append(ref)
            self._truth[ref] = "SUCCESS"
        else:
            self._truth[ref] = "FAILED"
        res = ProviderExecResult(state=state, provider_ref=ref, detail=f"sandbox {state}")
        self._by_key[idempotency_key] = res
        return res

    def get_status(self, provider_ref: str) -> str:
        return self._truth.get(provider_ref, "FAILED")

    def refund(self, *, provider_ref: str, amount_paise: int) -> RefundResult:
        if self._truth.get(provider_ref) == "SUCCESS":
            return RefundResult(ok=True, provider_ref="rfnd_" + new_id()[:12],
                                detail="sandbox refund")
        return RefundResult(ok=False, provider_ref=None, detail="nothing to refund")

    def total_charges(self) -> int:
        return len(self._charges)


class RazorpayProvider:
    """Real Razorpay adapter (TEST mode). Requires RAZORPAY_KEY_ID / SECRET.

    Honest boundary for delegated payments: this adapter CREATES a real Razorpay
    Order (documented Orders API) and returns ``UNKNOWN`` with the order id as the
    provider reference — the money has NOT moved yet. The actual charge is
    authorized by the user through Razorpay's hosted checkout (test UPI/card),
    after which ``get_status`` reads the live order status ("paid" => SUCCESS) and
    the broker's reconciliation promotes the transaction to SETTLED.

    We never fabricate a server-side capture and never touch UPI PIN/OTP/CVV —
    those stay inside Razorpay's PCI-compliant hosted checkout. Server-side
    delegated capture (Razorpay AutoPay) needs a pre-registered mandate token and
    is the documented next integration step, not faked here.
    """

    name = "razorpay"

    def __init__(self) -> None:
        s = get_settings()
        self._key_id = (getattr(s, "razorpay_key_id", None) or "").strip() or None
        self._key_secret = (getattr(s, "razorpay_key_secret", None) or "").strip() or None
        self._timeout = 20.0

    # -- helpers -----------------------------------------------------------
    def _auth(self) -> tuple[str, str]:
        return (self._key_id or "", self._key_secret or "")

    def available(self) -> bool:
        return bool(self._key_id and self._key_secret)

    def capabilities(self) -> dict:
        return {
            # server-side AutoPay capture not enabled (needs a mandate token)
            "delegated_payment": False,
            "hosted_checkout": True,
            "user_present_required": True,
            "merchant_binding": True, "amount_binding": True,
            "refund": True, "reconciliation": True,
            "requires_credentials": True, "configured": self.available(),
            "test_mode": bool(self._key_id and self._key_id.startswith("rzp_test_")),
        }

    # -- lifecycle ---------------------------------------------------------
    def execute_payment(self, *, amount_paise: int, currency: str, merchant_id: str,
                        idempotency_key: str) -> ProviderExecResult:
        if not self.available():
            return ProviderExecResult(
                "FAILED", None,
                "PROVIDER_ACCESS_RESTRICTED: set RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET",
            )
        # Create a real Razorpay Order (test mode). Receipt max length is 40.
        receipt = idempotency_key[:40]
        try:
            resp = httpx.post(
                f"{_RZP_API_BASE}/orders",
                auth=self._auth(),
                json={
                    "amount": int(amount_paise),
                    "currency": currency,
                    "receipt": receipt,
                    "payment_capture": 1,
                    "notes": {"merchant_id": merchant_id, "source": "syncore-agentic-checkout"},
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            order = resp.json()
        except httpx.HTTPError as exc:
            logger.error("razorpay order creation failed: %s", exc)
            return ProviderExecResult("FAILED", None, f"order creation failed: {exc}")

        order_id = order.get("id")
        # Order created but not yet authorized by the user => money not moved.
        return ProviderExecResult(
            "UNKNOWN", order_id,
            f"ORDER_CREATED_AWAITING_AUTH:{order_id}",
        )

    def get_status(self, provider_ref: str) -> str:
        """Read live order status. 'paid' => SUCCESS; anything else => FAILED."""
        if not self.available() or not provider_ref:
            return "FAILED"
        try:
            resp = httpx.get(
                f"{_RZP_API_BASE}/orders/{provider_ref}",
                auth=self._auth(),
                timeout=self._timeout,
            )
            resp.raise_for_status()
            order = resp.json()
        except httpx.HTTPError as exc:
            logger.error("razorpay order status failed: %s", exc)
            return "FAILED"
        return "SUCCESS" if order.get("status") == "paid" else "FAILED"

    def refund(self, *, provider_ref: str, amount_paise: int) -> RefundResult:
        """Refund the captured payment for an order (best-effort, real call)."""
        if not self.available() or not provider_ref:
            return RefundResult(ok=False, provider_ref=None, detail="provider unavailable")
        try:
            # Find the captured payment on this order, then refund it.
            resp = httpx.get(
                f"{_RZP_API_BASE}/orders/{provider_ref}/payments",
                auth=self._auth(), timeout=self._timeout,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            captured = next(
                (p for p in items if p.get("status") in ("captured", "authorized")), None
            )
            if not captured:
                return RefundResult(ok=False, provider_ref=None,
                                    detail="no captured payment to refund")
            payment_id = captured["id"]
            r = httpx.post(
                f"{_RZP_API_BASE}/payments/{payment_id}/refund",
                auth=self._auth(), json={"amount": int(amount_paise)}, timeout=self._timeout,
            )
            r.raise_for_status()
            refund = r.json()
        except httpx.HTTPError as exc:
            logger.error("razorpay refund failed: %s", exc)
            return RefundResult(ok=False, provider_ref=None, detail=f"refund failed: {exc}")
        return RefundResult(ok=True, provider_ref=refund.get("id"), detail="refund initiated")


def get_delegated_provider() -> PaymentProvider2:
    s = get_settings()
    if getattr(s, "payment_provider", "mock") == "razorpay":
        rp = RazorpayProvider()
        if rp.available():
            return rp
    return MockDelegatedProvider()
