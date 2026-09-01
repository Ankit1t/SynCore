"""Core domain models (pydantic v2).

These are the in-memory / API representations. Persistence tables in
syncore.db.tables mirror a subset of these. Canonical product data (Product)
is intentionally kept separate from marketplace-specific data (Offer).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator

from .enums import (
    Availability,
    ConstraintType,
    HumanCheckpointReason,
    OptimizationObjective,
    OrderStatus,
    PaymentStatus,
    Role,
    SubstitutionPolicy,
    Unit,
)


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(BaseModel):
    model_config = {"use_enum_values": False, "validate_assignment": True}


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
class Quantity(Base):
    """A normalized measurable quantity."""

    value: float
    unit: Unit

    @field_validator("value")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity value must be positive")
        return v

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        if self.unit == Unit.PIECE:
            n = int(self.value) if self.value.is_integer() else self.value
            return f"{n} piece" + ("s" if self.value != 1 else "")
        return f"{self.value:g}{self.unit.value}"


# --------------------------------------------------------------------------- #
# Users & preferences
# --------------------------------------------------------------------------- #
class User(Base):
    id: str = Field(default_factory=new_id)
    email: str
    display_name: str = ""
    role: Role = Role.USER
    created_at: datetime = Field(default_factory=utcnow)


class UserPreference(Base):
    user_id: str
    preferred_brands: list[str] = Field(default_factory=list)
    avoided_brands: list[str] = Field(default_factory=list)
    minimum_rating: float = 0.0
    vegetarian_only: bool = False
    organic_preference: bool = False
    price_weight: float = 0.5  # 0 = quality-first, 1 = price-first
    quality_threshold: float = 0.0
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ASK_BEFORE_SUBSTITUTION
    default_budget: float | None = None
    updated_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Shopping request / plan
# --------------------------------------------------------------------------- #
class ShoppingItem(Base):
    """One line item extracted from the request."""

    id: str = Field(default_factory=new_id)
    raw_text: str
    canonical_name: str
    requested_quantity: Quantity
    brand_preference: str | None = None
    minimum_rating: float | None = None
    optional: bool = False
    notes: str | None = None


class BudgetPolicy(Base):
    limit: float | None = None
    currency: str = "INR"
    constraint_type: ConstraintType = ConstraintType.HARD


class ShoppingPolicy(Base):
    objective: OptimizationObjective = OptimizationObjective.BEST_VALUE
    minimum_rating: float = 0.0
    substitution_policy: SubstitutionPolicy = SubstitutionPolicy.ASK_BEFORE_SUBSTITUTION
    delivery_deadline_minutes: int | None = None


class ShoppingRequest(Base):
    id: str = Field(default_factory=new_id)
    user_id: str
    raw_text: str
    items: list[ShoppingItem] = Field(default_factory=list)
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)
    policy: ShoppingPolicy = Field(default_factory=ShoppingPolicy)
    created_at: datetime = Field(default_factory=utcnow)


class ShoppingPlan(Base):
    """Structured plan derived from the request (search queries per item)."""

    id: str = Field(default_factory=new_id)
    request_id: str
    queries: list[SearchQuery] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class SearchQuery(Base):
    item_id: str
    text: str
    canonical_name: str
    target_quantity: Quantity
    brand_preference: str | None = None


# --------------------------------------------------------------------------- #
# Products & offers (canonical vs marketplace-specific)
# --------------------------------------------------------------------------- #
class Product(Base):
    """Canonical, marketplace-agnostic product identity."""

    id: str = Field(default_factory=new_id)
    canonical_name: str
    title: str
    brand: str | None = None
    category: str = "grocery"
    quantity: Quantity | None = None
    rating: float | None = None
    review_count: int = 0
    images: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    vegetarian: bool | None = None
    organic: bool = False
    last_seen_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Seller(Base):
    id: str = Field(default_factory=new_id)
    name: str
    reliability: float = 0.8  # 0..1
    marketplace: str = "mock-bazaar"


class Offer(Base):
    """A marketplace-specific purchasable offer for a Product.

    Data lineage fields make every price traceable and debuggable.
    """

    id: str = Field(default_factory=new_id)
    product: Product
    seller: Seller
    marketplace: str
    source_product_id: str
    price: float
    mrp: float | None = None
    currency: str = "INR"
    quantity: Quantity
    shipping_fee: float = 0.0
    platform_fee: float = 0.0
    availability: Availability = Availability.IN_STOCK
    delivery_eta_minutes: int | None = None
    coupon_code: str | None = None
    discount: float = 0.0
    # Data lineage / quality
    source: str = "mock"
    extracted_at: datetime = Field(default_factory=utcnow)
    parser_version: str = "1.0.0"
    normalization_version: str = "1.0.0"
    confidence: float = 1.0

    @property
    def discount_pct(self) -> float:
        if not self.mrp or self.mrp <= 0:
            return 0.0
        return max(0.0, round((self.mrp - self.price) / self.mrp * 100, 2))

    @property
    def effective_price(self) -> float:
        """Item price after per-offer discount (excludes basket-level fees)."""
        return round(max(0.0, self.price - self.discount), 2)


class RankedOffer(Base):
    offer: Offer
    score: float
    unit_price: float  # price per canonical base unit (e.g. per kg / per piece)
    reasons: list[str] = Field(default_factory=list)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Basket (optimizer output) - advisory, pre-execution
# --------------------------------------------------------------------------- #
class BasketItem(Base):
    item_id: str
    canonical_name: str
    offer: Offer
    packs: int = 1  # number of offer units required to meet requested quantity
    line_total: float
    unit_price: float
    is_substitute: bool = False
    reasons: list[str] = Field(default_factory=list)


class Basket(Base):
    id: str = Field(default_factory=new_id)
    request_id: str
    marketplace: str
    items: list[BasketItem] = Field(default_factory=list)
    items_subtotal: float = 0.0
    delivery_fee: float = 0.0
    platform_fee: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    currency: str = "INR"
    objective: OptimizationObjective = OptimizationObjective.BEST_VALUE
    within_budget: bool = True
    missing_items: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Execution: cart / checkout (re-validated against live state)
# --------------------------------------------------------------------------- #
class CartItem(Base):
    sku: str
    title: str
    unit_price: float
    quantity: int
    line_total: float


class Cart(Base):
    id: str = Field(default_factory=new_id)
    marketplace: str
    session_id: str
    items: list[CartItem] = Field(default_factory=list)
    items_subtotal: float = 0.0
    delivery_fee: float = 0.0
    platform_fee: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    currency: str = "INR"
    verified: bool = False


class CheckoutSession(Base):
    id: str = Field(default_factory=new_id)
    cart_id: str
    marketplace: str
    vendor: str
    final_total: float
    currency: str = "INR"
    delivery_eta_minutes: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Payments
# --------------------------------------------------------------------------- #
class PaymentIntent(Base):
    id: str = Field(default_factory=new_id)
    checkout_session_id: str
    user_id: str
    amount: float
    currency: str = "INR"
    vendor: str
    idempotency_key: str
    status: PaymentStatus = PaymentStatus.CREATED
    requires_user_action: bool = False
    checkpoint_reason: HumanCheckpointReason | None = None
    created_at: datetime = Field(default_factory=utcnow)


class PaymentAttempt(Base):
    id: str = Field(default_factory=new_id)
    intent_id: str
    status: PaymentStatus
    provider_reference: str | None = None
    message: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
class OrderItem(Base):
    sku: str
    title: str
    quantity: int
    unit_price: float
    line_total: float


class Order(Base):
    id: str = Field(default_factory=new_id)
    user_id: str
    request_id: str
    marketplace: str
    vendor: str
    items: list[OrderItem] = Field(default_factory=list)
    total: float = 0.0
    currency: str = "INR"
    status: OrderStatus = OrderStatus.PENDING
    payment_intent_id: str | None = None
    external_order_id: str | None = None
    delivery_eta_minutes: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Agent observability
# --------------------------------------------------------------------------- #
class AgentStep(Base):
    id: str = Field(default_factory=new_id)
    run_id: str
    index: int
    state: str
    message: str
    data: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class AgentDecision(Base):
    id: str = Field(default_factory=new_id)
    run_id: str
    kind: str
    summary: str
    evidence: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


class AgentRun(Base):
    id: str = Field(default_factory=new_id)
    request_id: str
    user_id: str
    state: str
    steps: list[AgentStep] = Field(default_factory=list)
    decisions: list[AgentDecision] = Field(default_factory=list)
    basket: Basket | None = None
    order: Order | None = None
    checkpoint_reason: HumanCheckpointReason | None = None
    error: dict | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class AuditEvent(Base):
    id: str = Field(default_factory=new_id)
    event: str
    user_id: str | None = None
    run_id: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)


# Resolve forward references
ShoppingPlan.model_rebuild()
