"""AP2-aligned mandate models + mappers from Syncore's Phase-2 artifacts.

Money is presented in AP2 mandates as human-readable rupee strings (e.g.
``"89.24"``) for interoperability/readability, while the authoritative integer
paise are preserved alongside so nothing is lost in translation. All hashing is
done over the paise fields, never the display strings.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from ..domain.enums import PaymentTxnState, PolicyOutcome
from ..domain.models import new_id
from ..domain.money import from_paise
from ..payments.models import (
    Cart,
    DelegatedPaymentIntent,
    Delegation,
    PaymentTransaction,
    PolicyDecision,
)
from .signing import KeyManager, get_key_manager, signing_alg


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _rupees(paise: int) -> str:
    """Display amount as a plain decimal string (AP2-style money)."""
    return str(from_paise(paise))


def _digest(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 over a canonical JSON payload (AP2 evidence hash)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# AP2 mandate models
# --------------------------------------------------------------------------- #
class MandateBase(BaseModel):
    model_config = {"use_enum_values": True}

    # Content hash (set by each mandate's compute_digest) + Ed25519 signature.
    content_digest: str = ""
    signature_alg: str = ""
    signer_id: str = ""
    signer_pubkey: str = ""
    signature: str = ""

    def compute_digest(self) -> str:  # overridden by each mandate
        raise NotImplementedError

    def sign_with(self, km: KeyManager, signer_id: str) -> MandateBase:
        """Sign this mandate's content digest with the party's Ed25519 key."""
        if not self.content_digest:
            self.content_digest = self.compute_digest()
        self.signer_id = signer_id
        self.signer_pubkey = km.public_key_hex(signer_id)
        self.signature_alg = signing_alg()
        self.signature = km.sign(signer_id, self.content_digest)
        return self

    def signature_valid(self) -> bool:
        """True if the stored signature verifies against the recomputed digest."""
        if not self.signature or not self.signer_pubkey:
            return False
        expected = self.compute_digest()
        if self.content_digest != expected:
            return False  # content was tampered after signing
        return KeyManager.verify(self.signer_pubkey, self.content_digest, self.signature)


class IntentMandate(MandateBase):
    """AP2 IntentMandate — the user's authorization and the rules of engagement.

    Maps from a Syncore ``Delegation``. In AP2 terms this is the pre-authorized
    proof that scopes what an agent may buy, from whom, and up to what limit.
    """

    mandate_type: str = "IntentMandate"
    mandate_id: str = Field(default_factory=lambda: "im_" + new_id()[:20])
    delegation_id: str
    user_id: str
    agent_id: str
    # AP2: natural-language expression of intent + machine-checkable constraints.
    natural_language_intent: str
    merchants: list[str] = Field(default_factory=list)  # empty = any merchant in category
    allowed_categories: list[str] = Field(default_factory=list)
    currency: str = "INR"
    # Spend constraints (authoritative paise + readable rupees).
    max_amount_per_txn: str = "0"
    max_amount_daily: str = "0"
    max_amount_monthly: str = "0"
    per_txn_paise: int = 0
    daily_paise: int = 0
    monthly_paise: int = 0
    # AP2: for delegated (human-not-present) tasks the user pre-signs this.
    human_present: bool = False
    user_cart_confirmation_required: bool = True
    created_at: str = Field(default_factory=_utcnow_iso)
    expires_at: str | None = None
    status: str = "ACTIVE"
    content_digest: str = ""

    def compute_digest(self) -> str:
        return _digest({
            "type": self.mandate_type,
            "delegation_id": self.delegation_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "merchants": sorted(self.merchants),
            "categories": sorted(self.allowed_categories),
            "currency": self.currency,
            "per_txn_paise": self.per_txn_paise,
            "daily_paise": self.daily_paise,
            "monthly_paise": self.monthly_paise,
            "expires_at": self.expires_at,
        })


class CartMandateItem(MandateBase):
    sku: str
    name: str
    quantity: int
    unit_price: str
    total_price: str
    unit_price_paise: int
    total_price_paise: int
    category: str = "GROCERY"


class CartMandate(MandateBase):
    """AP2 CartMandate — the exact, immutable contents and price of the cart.

    Maps from a Syncore ``Cart`` + ``DelegatedPaymentIntent``. The ``cart_hash``
    is the same deterministic hash the policy gate binds the payment to, so the
    AP2 cart mandate and the internal binding are provably the same cart.
    """

    mandate_type: str = "CartMandate"
    mandate_id: str = Field(default_factory=lambda: "cm_" + new_id()[:20])
    cart_id: str
    intent_id: str
    intent_mandate_ref: str = ""  # digest of the IntentMandate above it
    merchant_id: str
    merchant_category: str = "GROCERY"
    currency: str = "INR"
    items: list[CartMandateItem] = Field(default_factory=list)
    subtotal: str = "0"
    delivery: str = "0"
    fees: str = "0"
    tax: str = "0"
    discount: str = "0"
    total_amount: str = "0"
    total_paise: int = 0
    cart_hash: str = ""
    user_cart_confirmation_required: bool = True
    created_at: str = Field(default_factory=_utcnow_iso)
    content_digest: str = ""

    def compute_digest(self) -> str:
        return _digest({
            "type": self.mandate_type,
            "cart_id": self.cart_id,
            "intent_id": self.intent_id,
            "intent_mandate_ref": self.intent_mandate_ref,
            "merchant_id": self.merchant_id,
            "merchant_category": self.merchant_category,
            "currency": self.currency,
            "total_paise": self.total_paise,
            "cart_hash": self.cart_hash,
            "items": sorted(
                [
                    {"sku": it.sku, "qty": it.quantity, "unit_paise": it.unit_price_paise}
                    for it in self.items
                ],
                key=lambda x: x["sku"],
            ),
        })


class PaymentMandate(MandateBase):
    """AP2 PaymentMandate — binds a payment method to the verified cart.

    Maps from a Syncore ``PaymentTransaction`` (+ the policy decision). Captures
    the payment rail (e.g. UPI/card via Razorpay), the settlement reference, and
    the deterministic policy verdict that authorized it.
    """

    mandate_type: str = "PaymentMandate"
    mandate_id: str = Field(default_factory=lambda: "pm_" + new_id()[:20])
    cart_mandate_ref: str = ""  # digest of the CartMandate above it
    intent_id: str
    delegation_id: str
    merchant_id: str
    payment_method: str = "UPI"  # UPI | CARD | NETBANKING | WALLET (rail via PSP)
    payment_processor: str = "razorpay"
    amount: str = "0"
    amount_paise: int = 0
    currency: str = "INR"
    # Deterministic authorization result from CAN_PAY().
    policy_outcome: str = PolicyOutcome.DENY.value
    policy_rule_fired: str | None = None
    transaction_id: str | None = None
    transaction_state: str = PaymentTxnState.PENDING.value
    provider_reference: str | None = None
    created_at: str = Field(default_factory=_utcnow_iso)
    content_digest: str = ""

    def compute_digest(self) -> str:
        return _digest({
            "type": self.mandate_type,
            "cart_mandate_ref": self.cart_mandate_ref,
            "intent_id": self.intent_id,
            "delegation_id": self.delegation_id,
            "merchant_id": self.merchant_id,
            "payment_method": self.payment_method,
            "amount_paise": self.amount_paise,
            "currency": self.currency,
            "policy_outcome": self.policy_outcome,
            "provider_reference": self.provider_reference,
        })


class MandateChain(BaseModel):
    """The full AP2 evidence chain: intent -> cart -> payment."""

    model_config = {"use_enum_values": True}

    intent_mandate: IntentMandate
    cart_mandate: CartMandate
    payment_mandate: PaymentMandate | None = None

    def verify_report(self) -> dict[str, Any]:
        """Per-mandate evidence check: digest integrity, chain link, signature."""
        im, cm, pm = self.intent_mandate, self.cart_mandate, self.payment_mandate
        report: dict[str, Any] = {
            "intent_mandate": {
                "digest_ok": im.content_digest == im.compute_digest(),
                "link_ok": True,  # top of the chain
                "signature_ok": im.signature_valid(),
                "signer_id": im.signer_id,
            },
            "cart_mandate": {
                "digest_ok": cm.content_digest == cm.compute_digest(),
                "link_ok": cm.intent_mandate_ref == im.content_digest,
                "signature_ok": cm.signature_valid(),
                "signer_id": cm.signer_id,
            },
        }
        if pm is not None:
            report["payment_mandate"] = {
                "digest_ok": pm.content_digest == pm.compute_digest(),
                "link_ok": pm.cart_mandate_ref == cm.content_digest,
                "signature_ok": pm.signature_valid(),
                "signer_id": pm.signer_id,
            }
        ok = all(all(v is True for v in m.values() if isinstance(v, bool)) for m in report.values())
        report["chain_valid"] = ok
        return report

    def verify(self) -> bool:
        """True only if every mandate's digest, chain link and signature hold."""
        return bool(self.verify_report()["chain_valid"])


# --------------------------------------------------------------------------- #
# Mappers
# --------------------------------------------------------------------------- #
def intent_mandate_from_delegation(
    delegation: Delegation,
    *,
    natural_language_intent: str = "",
    human_present: bool = False,
) -> IntentMandate:
    nli = natural_language_intent or f"Purchase {delegation.purpose.lower()} items on my behalf"
    status = (delegation.status.value if hasattr(delegation.status, "value")
              else str(delegation.status))
    im = IntentMandate(
        delegation_id=delegation.id,
        user_id=delegation.user_id,
        agent_id=delegation.agent_id,
        natural_language_intent=nli,
        merchants=list(delegation.allowed_merchants),
        allowed_categories=list(delegation.allowed_categories),
        currency=delegation.currency,
        per_txn_paise=delegation.limits.per_txn_paise,
        daily_paise=delegation.limits.daily_paise,
        monthly_paise=delegation.limits.monthly_paise,
        max_amount_per_txn=_rupees(delegation.limits.per_txn_paise),
        max_amount_daily=_rupees(delegation.limits.daily_paise),
        max_amount_monthly=_rupees(delegation.limits.monthly_paise),
        human_present=human_present,
        status=status,
        expires_at=delegation.expires_at.isoformat() if delegation.expires_at else None,
    )
    im.content_digest = im.compute_digest()
    return im


def cart_mandate_from_cart(
    cart: Cart,
    intent: DelegatedPaymentIntent,
    *,
    intent_mandate: IntentMandate | None = None,
    user_cart_confirmation_required: bool = True,
) -> CartMandate:
    items = [
        CartMandateItem(
            sku=ln.sku,
            name=ln.name,
            quantity=ln.quantity,
            unit_price=_rupees(ln.unit_price_paise),
            total_price=_rupees(ln.line_total_paise),
            unit_price_paise=ln.unit_price_paise,
            total_price_paise=ln.line_total_paise,
            category=ln.category,
        )
        for ln in cart.lines
    ]
    cm = CartMandate(
        cart_id=cart.id,
        intent_id=intent.id,
        intent_mandate_ref=intent_mandate.content_digest if intent_mandate else "",
        merchant_id=cart.merchant_id,
        merchant_category=cart.merchant_category,
        currency=cart.currency,
        items=items,
        subtotal=_rupees(cart.subtotal_paise),
        delivery=_rupees(cart.delivery_paise),
        fees=_rupees(cart.platform_fee_paise + cart.handling_fee_paise),
        tax=_rupees(cart.tax_paise),
        discount=_rupees(cart.discount_paise),
        total_amount=_rupees(cart.final_total_paise),
        total_paise=cart.final_total_paise,
        cart_hash=cart.cart_hash,
        user_cart_confirmation_required=user_cart_confirmation_required,
    )
    cm.content_digest = cm.compute_digest()
    return cm


def payment_mandate_from_txn(
    intent: DelegatedPaymentIntent,
    decision: PolicyDecision,
    *,
    cart_mandate: CartMandate | None = None,
    txn: PaymentTransaction | None = None,
    payment_method: str = "UPI",
    payment_processor: str = "razorpay",
) -> PaymentMandate:
    outcome = (decision.outcome.value if hasattr(decision.outcome, "value")
               else str(decision.outcome))
    pm = PaymentMandate(
        cart_mandate_ref=cart_mandate.content_digest if cart_mandate else "",
        intent_id=intent.id,
        delegation_id=intent.delegation_id,
        merchant_id=intent.merchant_id,
        payment_method=payment_method,
        payment_processor=payment_processor,
        amount=_rupees(intent.amount_paise),
        amount_paise=intent.amount_paise,
        currency=intent.currency,
        policy_outcome=outcome,
        policy_rule_fired=decision.rule_fired,
        transaction_id=txn.id if txn else None,
        transaction_state=(txn.state.value if txn and hasattr(txn.state, "value")
                           else (str(txn.state) if txn else PaymentTxnState.PENDING.value)),
        provider_reference=txn.provider_ref if txn else None,
    )
    pm.content_digest = pm.compute_digest()
    return pm


def verify_mandate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Verify a posted AP2 mandate (full chain or a single CartMandate).

    Used by the merchant SDK / endpoint: reconstruct the signed models and
    re-check digest integrity, chain links and Ed25519 signatures. No secrets
    are needed — verification uses only the public keys embedded in the mandate.
    """
    try:
        if "cart_mandate" in payload and "intent_mandate" in payload:
            chain = MandateChain.model_validate(payload)
            report = chain.verify_report()
            return {
                "ok": bool(report["chain_valid"]),
                "kind": "chain",
                "report": report,
                "cart_hash": chain.cart_mandate.cart_hash,
                "total_amount": chain.cart_mandate.total_amount,
            }
        # Single CartMandate case (merchant received only the cart).
        cm = CartMandate.model_validate(payload)
        digest_ok = cm.content_digest == cm.compute_digest()
        sig_ok = cm.signature_valid()
        return {
            "ok": bool(digest_ok and sig_ok),
            "kind": "cart_mandate",
            "report": {
                "cart_mandate": {
                    "digest_ok": digest_ok,
                    "signature_ok": sig_ok,
                    "signer_id": cm.signer_id,
                },
            },
            "cart_hash": cm.cart_hash,
            "total_amount": cm.total_amount,
        }
    except Exception as exc:  # noqa: BLE001 - any malformed input => not verified
        return {"ok": False, "kind": "invalid", "error": str(exc)}


def build_mandate_chain(
    *,
    delegation: Delegation,
    cart: Cart,
    intent: DelegatedPaymentIntent,
    decision: PolicyDecision,
    natural_language_intent: str = "",
    human_present: bool = False,
    txn: PaymentTransaction | None = None,
    payment_method: str = "UPI",
    payment_processor: str = "razorpay",
) -> MandateChain:
    """Build the full intent -> cart -> payment AP2 chain from Syncore objects."""
    km = get_key_manager()
    im = intent_mandate_from_delegation(
        delegation, natural_language_intent=natural_language_intent, human_present=human_present
    )
    # IntentMandate is authorized by the USER (their delegation signature).
    im.sign_with(km, delegation.user_id)

    cm = cart_mandate_from_cart(
        cart, intent, intent_mandate=im,
        user_cart_confirmation_required=not human_present,
    )
    # CartMandate is asserted by the AGENT (exact items + price it will pay).
    cm.sign_with(km, delegation.agent_id)

    pm = payment_mandate_from_txn(
        intent, decision, cart_mandate=cm, txn=txn,
        payment_method=payment_method, payment_processor=payment_processor,
    )
    # PaymentMandate is signed by the AGENT binding the method to the cart.
    pm.sign_with(km, delegation.agent_id)

    return MandateChain(intent_mandate=im, cart_mandate=cm, payment_mandate=pm)
