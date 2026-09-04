"""Razorpay (TEST mode) payment endpoints.

A real payment-gateway integration for the demo. In TEST mode no real money
moves — you use Razorpay test keys and test cards/UPI. If keys are not
configured the endpoints degrade gracefully (`enabled: false`) so the rest of
the app keeps working.

Env:
  RAZORPAY_KEY_ID       (test key id, e.g. rzp_test_XXXX)
  RAZORPAY_KEY_SECRET   (test key secret)

We never store card/UPI data — Razorpay's hosted checkout handles that. We only
create an order and verify the returned signature (HMAC-SHA256).
"""

from __future__ import annotations

import hashlib
import hmac
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/pay", tags=["payments"])

_RZP_ORDERS_URL = "https://api.razorpay.com/v1/orders"


def _keys() -> tuple[str, str]:
    return os.getenv("RAZORPAY_KEY_ID", "").strip(), os.getenv("RAZORPAY_KEY_SECRET", "").strip()


class CreateOrderRequest(BaseModel):
    amount_inr: float = Field(..., gt=0, examples=[530])
    receipt: str = Field(default="syncore-demo", max_length=40)


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.get("/config")
def payment_config() -> dict:
    key_id, secret = _keys()
    return {"enabled": bool(key_id and secret), "key_id": key_id}


@router.post("/create-order")
def create_order(body: CreateOrderRequest) -> dict:
    key_id, secret = _keys()
    if not (key_id and secret):
        return {"enabled": False, "reason": "Razorpay test keys not configured on the server."}

    amount_paise = int(round(body.amount_inr * 100))
    try:
        resp = httpx.post(
            _RZP_ORDERS_URL,
            auth=(key_id, secret),
            json={
                "amount": amount_paise,
                "currency": "INR",
                "receipt": body.receipt,
                "payment_capture": 1,
            },
            timeout=20,
        )
        resp.raise_for_status()
        order = resp.json()
    except httpx.HTTPError as exc:
        return {"enabled": True, "ok": False, "error": f"order creation failed: {exc}"}

    return {
        "enabled": True,
        "ok": True,
        "order_id": order.get("id"),
        "amount": order.get("amount"),
        "currency": order.get("currency", "INR"),
        "key_id": key_id,
    }


@router.post("/verify")
def verify_payment(body: VerifyRequest) -> dict:
    _, secret = _keys()
    if not secret:
        return {"verified": False, "reason": "server not configured"}

    expected = hmac.new(
        secret.encode(),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    verified = hmac.compare_digest(expected, body.razorpay_signature)
    return {"verified": verified}
