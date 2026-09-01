"""Phase 2 delegated-payment domain models (integer paise, pydantic v2).

Kept separate from the Phase-1 domain models so existing flows are untouched.
All money is integer paise; carts carry a deterministic cart_hash used to bind
an authorization to exactly one transaction.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from ..domain.enums import DelegationStatus, PaymentTxnState, PolicyOutcome, RiskLevel
from ..domain.models import new_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(BaseModel):
    model_config = {"use_enum_values": False}


class SpendingLimits(Base):
    per_txn_paise: int
    daily_paise: int
    monthly_paise: int


class Delegation(Base):
    id: str = Field(default_factory=lambda: "dlg_" + new_id()[:22])
    user_id: str
    agent_id: str
    purpose: str = "GROCERY"
    allowed_categories: list[str] = Field(default_factory=lambda: ["GROCERY"])
    allowed_merchants: list[str] = Field(default_factory=list)  # empty = category-scoped
    currency: str = "INR"
    limits: SpendingLimits
    substitution: str = "ASK"
    status: DelegationStatus = DelegationStatus.ACTIVE
    version: int = 1
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime = Field(default_factory=lambda: _utcnow() + timedelta(days=30))


class CartLine(Base):
    sku: str
    name: str
    quantity: int
    unit_price_paise: int
    line_total_paise: int
    category: str = "GROCERY"


class Cart(Base):
    id: str = Field(default_factory=lambda: "cart_" + new_id()[:16])
    merchant_id: str
    merchant_category: str = "GROCERY"
    currency: str = "INR"
    lines: list[CartLine] = Field(default_factory=list)
    subtotal_paise: int = 0
    delivery_paise: int = 0
    platform_fee_paise: int = 0
    handling_fee_paise: int = 0
    tax_paise: int = 0
    discount_paise: int = 0
    final_total_paise: int = 0
    cart_hash: str = ""
    observed_at: datetime = Field(default_factory=_utcnow)


class DelegatedPaymentIntent(Base):
    id: str = Field(default_factory=lambda: "pi_" + new_id()[:22])
    user_id: str
    agent_id: str
    delegation_id: str
    order_id: str | None = None
    merchant_id: str
    merchant_category: str = "GROCERY"
    amount_paise: int
    currency: str = "INR"
    purpose: str = "GROCERY"
    cart_hash: str
    idempotency_key: str
    status: str = "CREATED"
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime = Field(default_factory=lambda: _utcnow() + timedelta(minutes=10))


class RiskDecision(Base):
    level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    signals: dict = Field(default_factory=dict)


class PolicyCheck(Base):
    name: str
    passed: bool
    outcome: PolicyOutcome | None = None
    detail: str = ""


class PolicyDecision(Base):
    outcome: PolicyOutcome
    rule_fired: str | None = None
    checks: list[PolicyCheck] = Field(default_factory=list)
    risk: RiskDecision | None = None
    reasons: list[str] = Field(default_factory=list)


class PaymentTransaction(Base):
    id: str = Field(default_factory=lambda: "ptx_" + new_id()[:18])
    intent_id: str
    delegation_id: str
    state: PaymentTxnState = PaymentTxnState.PENDING
    provider: str = ""
    provider_ref: str | None = None
    amount_paise: int = 0
    currency: str = "INR"
    idempotency_key: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Receipt(Base):
    receipt_id: str = Field(default_factory=lambda: "rcpt_" + new_id()[:16])
    order_id: str | None
    merchant_id: str
    lines: list[CartLine]
    subtotal_paise: int
    delivery_paise: int
    fees_paise: int
    tax_paise: int
    discount_paise: int
    final_total_paise: int
    currency: str
    payment_status: str
    payment_reference: str | None
    order_status: str
    cart_hash: str
    issued_at: datetime = Field(default_factory=_utcnow)
