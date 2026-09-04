"""Agentic checkout — the "one door" that ties Syncore end to end.

Flow (AP2-aligned):

    natural-language request
        -> shopping agent builds an optimized, budget-checked basket   (Zone 0)
        -> basket becomes a priced, hash-bound Cart                    (binding)
        -> AP2 IntentMandate + CartMandate are minted                  (ap2)
        -> deterministic CAN_PAY() gate decides ALLOW/DENY/CHALLENGE   (Zone 1)
        -> on ALLOW: payment executes via the broker
             * mock provider  -> settled instantly (sandbox, no real money)
             * razorpay        -> a real TEST-mode order is created for the
                                   user to authorize via hosted UPI checkout
        -> AP2 PaymentMandate records the settlement + policy verdict

Nothing the agent "says" can move a rupee without passing CAN_PAY(): the gate is
pure deterministic code, evaluated fresh against the bound cart.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from ..ap2 import build_mandate_chain
from ..config import get_settings
from ..domain.enums import OrderStatus, PolicyOutcome
from ..domain.money import to_paise
from ..observability.logging import get_logger
from .control_plane import get_control_plane
from .models import CartLine, SpendingLimits

logger = get_logger("syncore.payments.agentic_checkout")

_AGENT_ID = "syncore_agent"


class AgenticCheckoutError(Exception):
    """Raised when the agent cannot produce a payable basket."""


class AgenticCheckoutService:
    """Stateless orchestration over the shopping agent + control plane."""

    def __init__(self) -> None:
        self.settings = get_settings()

    # -- public API --------------------------------------------------------
    def checkout(
        self,
        *,
        text: str,
        user_id: str | None = None,
        per_txn_paise: int | None = None,
        daily_paise: int | None = None,
        monthly_paise: int | None = None,
        human_present: bool = True,
        payment_method: str = "UPI",
    ) -> dict[str, Any]:
        # 1. Run the shopping agent (Zone 0) to build a basket — no execution.
        from ..api.service import get_service

        svc = get_service()
        request = svc.parse(text, user_id=user_id)
        orch = svc.new_orchestrator()
        run = orch.run(request, auto_execute=False)
        basket = run.basket

        if basket is None or basket.missing_items or not basket.within_budget:
            return {
                "stage": "BASKET_NOT_PAYABLE",
                "reason": self._basket_reason(basket),
                "agent_state": run.state,
                "basket": svc.to_basket_out(run).model_dump(mode="json") if basket else None,
            }

        # 2. Turn the basket into a priced, hash-bound Cart (integer paise).
        lines = self._basket_to_cart_lines(basket)
        cp = get_control_plane()
        cart = cp.build_cart(
            merchant_id=basket.marketplace,
            merchant_category="GROCERY",
            lines=lines,
            delivery_paise=to_paise(basket.delivery_fee),
            platform_fee_paise=to_paise(basket.platform_fee),
            discount_paise=to_paise(basket.discount),
        )

        # 3. Ensure a delegation (the user's signed authority + rules).
        budget_paise = to_paise(request.budget.limit) if request.budget.limit else 0
        default_per_txn = max(budget_paise, cart.final_total_paise, 50_000)
        limits = SpendingLimits(
            per_txn_paise=default_per_txn if per_txn_paise is None else per_txn_paise,
            daily_paise=(max(default_per_txn * 5, 150_000)
                         if daily_paise is None else daily_paise),
            monthly_paise=(max(default_per_txn * 30, 1_500_000)
                           if monthly_paise is None else monthly_paise),
        )
        delegation = cp.create_delegation(
            user_id=request.user_id,
            agent_id=_AGENT_ID,
            limits=limits,
            allowed_categories=["GROCERY"],
            allowed_merchants=[],  # category-scoped: any grocery merchant
            currency=self.settings.default_currency,
        )

        # 4. Create the payment intent and run CAN_PAY() (evaluate only).
        idempotency_key = f"agentic:{request.id}"
        intent, result = cp.create_payment_intent(
            user_id=request.user_id, agent_id=_AGENT_ID, delegation_id=delegation.id,
            cart=cart, idempotency_key=idempotency_key,
        )
        decision = result.decision

        # 5. Mint the AP2 mandate chain (pre-execution).
        chain = build_mandate_chain(
            delegation=delegation, cart=cart, intent=intent, decision=decision,
            natural_language_intent=text, human_present=human_present,
            payment_method=payment_method, payment_processor=self._processor_name(),
        )

        response: dict[str, Any] = {
            "stage": "GATE_EVALUATED",
            "agent_state": run.state,
            "request_id": request.id,
            "intent_id": intent.id,
            "delegation_id": delegation.id,
            "basket": svc.to_basket_out(run).model_dump(mode="json"),
            "cart": cart.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
            "ap2_mandates": chain.model_dump(mode="json"),
            "provider": self._processor_name(),
        }

        # 6. Fail closed: only ALLOW proceeds to execution.
        if decision.outcome != PolicyOutcome.ALLOW:
            response["stage"] = "BLOCKED"
            response["blocked_by"] = decision.rule_fired
            return response

        # 7. Execute through the broker (the single financial boundary).
        exec_result = cp.execute(intent.id)
        txn = exec_result.txn
        chain = build_mandate_chain(
            delegation=delegation, cart=cart, intent=intent, decision=exec_result.decision,
            natural_language_intent=text, human_present=human_present, txn=txn,
            payment_method=payment_method, payment_processor=self._processor_name(),
        )
        response["ap2_mandates"] = chain.model_dump(mode="json")
        response["txn"] = txn.model_dump(mode="json") if txn else None

        if txn is None:
            response["stage"] = "BLOCKED"
            response["blocked_by"] = exec_result.decision.rule_fired
            return response

        # 8a. Autonomous settle (mock provider / AutoPay) — no user step needed.
        if str(txn.state) in ("SETTLED", "PaymentTxnState.SETTLED"):
            response["stage"] = "SETTLED"
            response["checkout_required"] = False
            return response

        # 8b. Real Razorpay order created — user authorizes via hosted checkout.
        if txn.provider_ref and self._processor_name() == "razorpay":
            response["stage"] = "CHECKOUT_REQUIRED"
            response["checkout_required"] = True
            response["checkout"] = {
                "provider": "razorpay",
                "order_id": txn.provider_ref,
                "amount": intent.amount_paise,
                "currency": intent.currency,
                "key_id": (self.settings.razorpay_key_id or "").strip(),
                "name": "Syncore Grocery",
                "description": f"AP2 agentic order · {len(cart.lines)} item(s)",
                "txn_id": txn.id,
                "intent_id": intent.id,
            }
            return response

        # 8c. Parked (UNKNOWN) without a checkout handle — reconcile later.
        response["stage"] = "PENDING_RECONCILE"
        response["checkout_required"] = False
        return response

    def confirm(
        self,
        *,
        intent_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> dict[str, Any]:
        """Verify a hosted-checkout result and settle the parked transaction."""
        secret = (self.settings.razorpay_key_secret or "").strip()
        if not secret:
            raise AgenticCheckoutError("razorpay secret not configured on server")

        expected = hmac.new(
            secret.encode(),
            f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            return {"verified": False, "stage": "SIGNATURE_INVALID"}

        cp = get_control_plane()
        txn = next(
            (t for t in cp.broker._txns.values()  # noqa: SLF001
             if t.intent_id == intent_id),
            None,
        )
        if txn is None:
            raise AgenticCheckoutError("no transaction for this intent")

        # Reconcile against the live order status ('paid' => SETTLED).
        settled = cp.broker.reconcile(txn.id)
        receipt = cp.receipt(intent_id, merchant_confirmed=True)
        return {
            "verified": True,
            "stage": "SETTLED" if str(settled.state).endswith("SETTLED") else "RECONCILE_FAILED",
            "txn": settled.model_dump(mode="json"),
            "receipt": receipt.model_dump(mode="json") if receipt else None,
            "order_status": OrderStatus.CONFIRMED.value,
        }

    # -- helpers -----------------------------------------------------------
    def _processor_name(self) -> str:
        return "razorpay" if self.settings.payment_provider == "razorpay" else "mock"

    @staticmethod
    def _basket_reason(basket: Any) -> str:
        if basket is None:
            return "agent could not build a basket for this request"
        if basket.missing_items:
            return f"missing items: {', '.join(basket.missing_items)}"
        if not basket.within_budget:
            return "basket exceeds the hard budget"
        return "basket not payable"

    @staticmethod
    def _basket_to_cart_lines(basket: Any) -> list[CartLine]:
        lines: list[CartLine] = []
        for bi in basket.items:
            unit_paise = to_paise(bi.unit_price)
            lines.append(CartLine(
                sku=str(bi.offer.source_product_id),
                name=bi.offer.product.title,
                quantity=int(bi.packs),
                unit_price_paise=unit_paise,
                line_total_paise=unit_paise * int(bi.packs),
                category="GROCERY",
            ))
        return lines


_service: AgenticCheckoutService | None = None


def get_agentic_checkout() -> AgenticCheckoutService:
    global _service
    if _service is None:
        _service = AgenticCheckoutService()
    return _service
