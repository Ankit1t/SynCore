"""Order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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


@router.get("/orders")
def list_orders(limit: int = 50) -> list[dict]:
    with session_scope() as s:
        return [_order_row_to_dict(r) for r in repo.list_orders(s, limit=limit)]


@router.get("/orders/{order_id}")
def get_order(order_id: str) -> dict:
    with session_scope() as s:
        row = repo.get_order_row(s, order_id)
        if row is None:
            raise HTTPException(status_code=404, detail="order not found")
        return _order_row_to_dict(row)
