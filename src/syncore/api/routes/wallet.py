"""Prepaid wallet endpoints.

Flow:
  1. Top up once  -> Razorpay test payment credits the wallet.
  2. Every order  -> settled by deducting from the wallet (no payment step).

Deduction is server-authoritative; the client cannot move money it doesn't
have. Top-ups require a Razorpay-signed payment (verified here).
"""

from __future__ import annotations

import hashlib
import hmac

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from ... import orders_store
from ... import wallet as wallet_store
from .payments_rzp import _RZP_ORDERS_URL, _keys

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


class OrderLine(BaseModel):
    name: str = Field(..., max_length=140)
    quantity: float = 1
    unit: str = Field(default="unit", max_length=20)
    unit_price: float = 0
    line_total: float = 0


class PlaceOrderRequest(BaseModel):
    items: list[OrderLine] = Field(..., min_length=1)


class PayRequest(BaseModel):
    amount_inr: float = Field(..., gt=0)
    note: str = Field(default="Order", max_length=80)


class TopupOrderRequest(BaseModel):
    amount_inr: float = Field(..., gt=0, le=100000)


class TopupConfirmRequest(BaseModel):
    amount_inr: float = Field(..., gt=0, le=100000)
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.get("")
def get_wallet() -> dict:
    return wallet_store.snapshot()


@router.post("/pay")
def wallet_pay(body: PayRequest) -> dict:
    """Settle an order straight from the wallet — no gateway, no user step."""
    result = wallet_store.debit(wallet_store.DEMO_USER, body.amount_inr, body.note)
    return {
        "paid": result["ok"],
        "balance_inr": result["balance_inr"],
        "reason": result.get("reason"),
        "shortfall_inr": result.get("shortfall_inr"),
        "txn_id": result.get("txn", {}).get("id") if result["ok"] else None,
    }


@router.post("/order")
def place_order(body: PlaceOrderRequest) -> dict:
    """Settle an itemized order from the wallet and mint a downloadable receipt."""
    total = round(sum(max(0.0, li.line_total) for li in body.items), 2)
    if total <= 0:
        return {"paid": False, "reason": "empty order"}
    result = wallet_store.debit(wallet_store.DEMO_USER, total, note="SynCore order")
    if not result["ok"]:
        return {
            "paid": False,
            "reason": result.get("reason"),
            "balance_inr": result["balance_inr"],
            "shortfall_inr": result.get("shortfall_inr"),
        }
    order = orders_store.create_order(
        items=[li.model_dump() for li in body.items],
        total=total,
        wallet_balance_after=result["balance_inr"],
    )
    return {"paid": True, "order_id": order["order_id"], "balance_inr": result["balance_inr"], "receipt": order}


@router.get("/order/{order_id}")
def get_order(order_id: str) -> dict:
    o = orders_store.get_order(order_id)
    return o if o else {"found": False, "order_id": order_id}


@router.post("/topup-order")
def topup_order(body: TopupOrderRequest) -> dict:
    key_id, secret = _keys()
    if not (key_id and secret):
        return {"enabled": False, "reason": "Razorpay test keys not configured on the server."}
    try:
        resp = httpx.post(
            _RZP_ORDERS_URL,
            auth=(key_id, secret),
            json={
                "amount": int(round(body.amount_inr * 100)),
                "currency": "INR",
                "receipt": "wallet-topup",
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


@router.post("/topup-confirm")
def topup_confirm(body: TopupConfirmRequest) -> dict:
    _, secret = _keys()
    if not secret:
        return {"ok": False, "reason": "server not configured"}
    expected = hmac.new(
        secret.encode(),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        return {"ok": False, "reason": "signature verification failed"}
    credited = wallet_store.credit(
        wallet_store.DEMO_USER, body.amount_inr, note="Wallet top-up (Razorpay test)"
    )
    return {"ok": True, "balance_inr": credited["balance_inr"]}
