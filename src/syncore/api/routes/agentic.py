"""Agentic checkout API — the AP2 "one door".

POST /api/v1/agentic/checkout  run agent -> AP2 mandates -> CAN_PAY gate -> (order)
POST /api/v1/agentic/confirm   verify hosted-checkout result -> settle -> receipt
GET  /api/v1/agentic/config    surface provider + whether live checkout is on
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import get_settings
from ...payments.agentic_checkout import AgenticCheckoutError, get_agentic_checkout

router = APIRouter(prefix="/api/v1/agentic", tags=["agentic-checkout"])


class CheckoutRequest(BaseModel):
    text: str = Field(..., examples=["₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar"])
    user_id: str | None = None
    # Optional delegation limits (in paise). Set a low per_txn to demo a BLOCK.
    per_txn_paise: int | None = Field(default=None, ge=0)
    daily_paise: int | None = Field(default=None, ge=0)
    monthly_paise: int | None = Field(default=None, ge=0)
    human_present: bool = True
    payment_method: str = "UPI"


class ConfirmRequest(BaseModel):
    intent_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.get("/config")
def agentic_config() -> dict[str, Any]:
    s = get_settings()
    key_id = (s.razorpay_key_id or "").strip()
    secret = (s.razorpay_key_secret or "").strip()
    live = s.payment_provider == "razorpay" and bool(key_id and secret)
    return {
        "provider": "razorpay" if s.payment_provider == "razorpay" else "mock",
        "live_checkout": live,
        "key_id": key_id if live else "",
        "currency": s.default_currency,
    }


@router.post("/checkout")
def agentic_checkout(body: CheckoutRequest) -> dict[str, Any]:
    try:
        return get_agentic_checkout().checkout(
            text=body.text,
            user_id=body.user_id,
            per_txn_paise=body.per_txn_paise,
            daily_paise=body.daily_paise,
            monthly_paise=body.monthly_paise,
            human_present=body.human_present,
            payment_method=body.payment_method,
        )
    except AgenticCheckoutError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/confirm")
def agentic_confirm(body: ConfirmRequest) -> dict[str, Any]:
    try:
        return get_agentic_checkout().confirm(
            intent_id=body.intent_id,
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        )
    except AgenticCheckoutError as exc:
        raise HTTPException(422, str(exc)) from exc
