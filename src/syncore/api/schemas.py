"""API request/response schemas (kept separate from domain models)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateShoppingRequest(BaseModel):
    text: str = Field(..., examples=["₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar."])
    auto_execute: bool = True


class ParsedItemOut(BaseModel):
    canonical_name: str
    requested_quantity: str
    raw_text: str


class ShoppingRequestOut(BaseModel):
    id: str
    user_id: str
    raw_text: str
    budget_limit: float | None
    currency: str
    items: list[ParsedItemOut]


class BasketItemOut(BaseModel):
    canonical_name: str
    title: str
    packs: int
    unit_price: float
    line_total: float
    reasons: list[str]


class BasketOut(BaseModel):
    marketplace: str
    objective: str
    items: list[BasketItemOut]
    items_subtotal: float
    delivery_fee: float
    platform_fee: float
    discount: float
    total: float
    currency: str
    within_budget: bool
    missing_items: list[str]
    explanation: list[str]


class StepOut(BaseModel):
    index: int
    state: str
    message: str
    data: dict


class OrderOut(BaseModel):
    id: str
    external_order_id: str | None
    status: str
    marketplace: str
    vendor: str
    total: float
    currency: str
    delivery_eta_minutes: int | None
    items: list[dict]


class AgentRunOut(BaseModel):
    id: str
    request_id: str
    user_id: str
    state: str
    checkpoint_reason: str | None
    error: dict | None
    steps: list[StepOut]
    basket: BasketOut | None
    order: OrderOut | None


class OfferOut(BaseModel):
    marketplace: str
    title: str
    brand: str | None
    price: float
    mrp: float | None
    quantity: str
    rating: float | None
    review_count: int
    availability: str
    delivery_eta_minutes: int | None


class OptimizeRequest(BaseModel):
    text: str


class HealthOut(BaseModel):
    status: str
    checks: dict
