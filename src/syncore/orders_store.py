"""In-memory order store for the demo checkout.

When an order is settled from the wallet we mint an order_id and keep an
itemized receipt so the UI can display and re-download it. Swap for the DB
layer for persistence without changing the API.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()
_orders: dict[str, dict[str, Any]] = {}
_MAX = 200


def _new_id() -> str:
    return "SYN-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()


def create_order(items: list[dict[str, Any]], total: float, wallet_balance_after: float) -> dict[str, Any]:
    with _LOCK:
        order_id = _new_id()
        order = {
            "order_id": order_id,
            "placed_at": int(time.time()),
            "currency": "INR",
            "items": items,
            "subtotal": round(total, 2),
            "total": round(total, 2),
            "payment_method": "SynCore Wallet (prepaid)",
            "payment_status": "PAID",
            "wallet_balance_after": round(wallet_balance_after, 2),
        }
        _orders[order_id] = order
        if len(_orders) > _MAX:
            for k in list(_orders)[:-_MAX]:
                del _orders[k]
        return order


def get_order(order_id: str) -> dict[str, Any] | None:
    with _LOCK:
        return _orders.get(order_id)
