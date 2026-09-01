"""Phase-2 delegated-payment API (Blueprint STEP 34/54)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ...domain.money import line_total_paise
from ...payments.control_plane import get_control_plane
from ...payments.models import CartLine, SpendingLimits

router = APIRouter(prefix="/api/v1", tags=["payments-cp"])


# ------------------------------------------------------------------ schemas --
class CreateDelegation(BaseModel):
    user_id: str
    agent_id: str = "syncore_agent"
    per_txn_paise: int = 50000
    daily_paise: int = 150000
    monthly_paise: int = 1500000
    allowed_categories: list[str] = Field(default_factory=lambda: ["GROCERY"])
    allowed_merchants: list[str] = Field(default_factory=list)
    currency: str = "INR"


class CartLineIn(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_price_paise: int
    category: str = "GROCERY"


class CreatePaymentIntent(BaseModel):
    user_id: str
    agent_id: str = "syncore_agent"
    delegation_id: str
    merchant_id: str
    merchant_category: str = "GROCERY"
    idempotency_key: str
    lines: list[CartLineIn]
    delivery_paise: int = 0
    platform_fee_paise: int = 0
    handling_fee_paise: int = 0
    tax_paise: int = 0
    discount_paise: int = 0
    order_id: str | None = None


class UserRef(BaseModel):
    user_id: str


# --------------------------------------------------------------- delegations -
@router.post("/delegations")
def create_delegation(body: CreateDelegation) -> dict[str, Any]:
    cp = get_control_plane()
    d = cp.create_delegation(
        user_id=body.user_id, agent_id=body.agent_id,
        limits=SpendingLimits(per_txn_paise=body.per_txn_paise, daily_paise=body.daily_paise,
                              monthly_paise=body.monthly_paise),
        allowed_categories=body.allowed_categories, allowed_merchants=body.allowed_merchants,
        currency=body.currency,
    )
    return d.model_dump(mode="json")


@router.get("/delegations")
def list_delegations(user_id: str) -> list[dict[str, Any]]:
    cp = get_control_plane()
    return [d.model_dump(mode="json") for d in cp.delegations.list_for_user(user_id)]


@router.post("/delegations/{delegation_id}/revoke")
def revoke_delegation(delegation_id: str) -> dict[str, Any]:
    try:
        return get_control_plane().delegations.revoke(delegation_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/delegations/{delegation_id}/pause")
def pause_delegation(delegation_id: str) -> dict[str, Any]:
    try:
        return get_control_plane().delegations.pause(delegation_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/delegations/{delegation_id}/resume")
def resume_delegation(delegation_id: str) -> dict[str, Any]:
    try:
        return get_control_plane().delegations.resume(delegation_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


# --------------------------------------------------------------- kill switch -
@router.post("/agent/pause-payments")
def pause_payments(body: UserRef) -> dict[str, Any]:
    n = get_control_plane().delegations.pause_all_for_user(body.user_id)
    return {"paused": n, "user_id": body.user_id}


@router.post("/agent/resume-payments")
def resume_payments(body: UserRef) -> dict[str, Any]:
    n = get_control_plane().delegations.resume_all_for_user(body.user_id)
    return {"resumed": n, "user_id": body.user_id}


# ------------------------------------------------------------ payment intents -
def _to_lines(lines: list[CartLineIn]) -> list[CartLine]:
    out: list[CartLine] = []
    for ln in lines:
        out.append(CartLine(
            sku=ln.sku, name=ln.name, quantity=ln.quantity, unit_price_paise=ln.unit_price_paise,
            line_total_paise=line_total_paise(ln.unit_price_paise, ln.quantity), category=ln.category,
        ))
    return out


@router.post("/payment-intents")
def create_payment_intent(body: CreatePaymentIntent) -> dict[str, Any]:
    cp = get_control_plane()
    cart = cp.build_cart(
        merchant_id=body.merchant_id, merchant_category=body.merchant_category,
        lines=_to_lines(body.lines), delivery_paise=body.delivery_paise,
        platform_fee_paise=body.platform_fee_paise, handling_fee_paise=body.handling_fee_paise,
        tax_paise=body.tax_paise, discount_paise=body.discount_paise,
    )
    intent, result = cp.create_payment_intent(
        user_id=body.user_id, agent_id=body.agent_id, delegation_id=body.delegation_id,
        cart=cart, idempotency_key=body.idempotency_key, order_id=body.order_id,
    )
    return {
        "intent": intent.model_dump(mode="json"),
        "cart": cart.model_dump(mode="json"),
        "decision": result.decision.model_dump(mode="json"),
    }


@router.post("/payment-intents/{intent_id}/authorize")
def authorize_intent(intent_id: str) -> dict[str, Any]:
    cp = get_control_plane()
    try:
        intent, cart = cp._require_intent(intent_id)  # noqa: SLF001
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    decision, _ = cp.broker.evaluate(intent=intent, cart=cart)
    return {"intent_id": intent_id, "decision": decision.model_dump(mode="json")}


@router.post("/payment-intents/{intent_id}/execute")
def execute_intent(intent_id: str) -> dict[str, Any]:
    cp = get_control_plane()
    try:
        result = cp.execute(intent_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "decision": result.decision.model_dump(mode="json"),
        "txn": result.txn.model_dump(mode="json") if result.txn else None,
        "executed": result.executed,
    }


@router.get("/payment-intents/{intent_id}/receipt")
def get_receipt(intent_id: str, merchant_confirmed: bool = True) -> dict[str, Any]:
    r = get_control_plane().receipt(intent_id, merchant_confirmed=merchant_confirmed)
    if r is None:
        raise HTTPException(404, "no receipt (intent/txn not found)")
    return r.model_dump(mode="json")


# ------------------------------------------------------------------ payments -
@router.get("/payments/{txn_id}")
def get_payment(txn_id: str) -> dict[str, Any]:
    txn = get_control_plane().broker.get_txn(txn_id)
    if txn is None:
        raise HTTPException(404, "txn not found")
    return txn.model_dump(mode="json")


@router.post("/payments/{txn_id}/reconcile")
def reconcile_payment(txn_id: str) -> dict[str, Any]:
    try:
        return get_control_plane().broker.reconcile(txn_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/payments/{txn_id}/refund")
def refund_payment(txn_id: str) -> dict[str, Any]:
    try:
        return get_control_plane().broker.refund(txn_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


# ------------------------------------------------------------------ webhooks -
@router.post("/webhooks/payments")
async def payments_webhook(request: Request) -> dict[str, Any]:
    body = await request.body()
    ok, reason = get_control_plane().webhooks.process(
        payload=body,
        signature=request.headers.get("x-syncore-signature", ""),
        timestamp=request.headers.get("x-syncore-timestamp", ""),
        event_id=request.headers.get("x-syncore-event-id", ""),
        event_type=request.headers.get("x-syncore-event-type", "unknown"),
    )
    if not ok:
        raise HTTPException(400, f"webhook rejected: {reason}")
    return {"accepted": True}
