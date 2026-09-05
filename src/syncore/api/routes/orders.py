"""Order endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ... import orders_store
from ...db import repositories as repo
from ...db.base import session_scope

router = APIRouter(prefix="/api/v1", tags=["orders"])


def _order_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "external_order_id": row.external_order_id,
        "status": row.status,
        "marketplace": row.marketplace,
        "vendor": row.vendor,
        "total": row.total,
        "currency": row.currency,
        "delivery_eta_minutes": row.delivery_eta_minutes,
        "items": row.items,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _store_order_to_dict(o: dict) -> dict:
    """Map a wallet (in-memory) order to the same shape the UI expects."""
    placed = o.get("placed_at")
    return {
        "id": o["order_id"],
        "external_order_id": o["order_id"],
        "status": o.get("payment_status", "PAID"),
        "marketplace": o.get("payment_method", "SynCore Wallet"),
        "vendor": "wallet",
        "total": o.get("total", 0),
        "currency": o.get("currency", "INR"),
        "delivery_eta_minutes": None,
        "items": o.get("items", []),
        "created_at": (datetime.fromtimestamp(placed, tz=UTC).isoformat()
                       if placed else None),
    }


@router.get("/orders")
def list_orders(limit: int = 50) -> list[dict]:
    with session_scope() as s:
        db_orders = [_order_row_to_dict(r) for r in repo.list_orders(s, limit=limit)]
    # Wallet checkout orders live in the in-memory store — merge them in.
    store_orders = [_store_order_to_dict(o) for o in orders_store.list_orders(limit=limit)]
    combined = store_orders + db_orders
    combined.sort(key=lambda o: o.get("created_at") or "", reverse=True)
    return combined[:limit]


@router.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    store = orders_store.get_order(order_id)
    if store is not None:
        return _store_order_to_dict(store)
    with session_scope() as s:
        row = repo.get_order_row(s, order_id)
        if row is None:
            raise HTTPException(status_code=404, detail="order not found")
        return _order_row_to_dict(row)
