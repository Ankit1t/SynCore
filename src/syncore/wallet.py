"""In-memory prepaid wallet (UPI-Lite style).

The user tops up a balance once (via a real Razorpay test-mode payment) and
after that the agent settles each order by deducting from the wallet — no
payment step per order. Money math is integer paise; every movement is logged.

Storage is process-memory (thread-safe). On a fresh start the demo user is
seeded with a default balance so the demo always has funds. For real
persistence, swap this store for the DB layer without changing the API.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any

_LOCK = threading.RLock()
DEMO_USER = "demo"
DEFAULT_BALANCE_INR = float(os.getenv("WALLET_DEMO_BALANCE", "10000"))
_MAX_TXNS = 50

_balance_paise: dict[str, int] = {}
_txns: dict[str, list[dict[str, Any]]] = {}


def _to_paise(inr: float) -> int:
    return int(round(float(inr) * 100))


def _to_inr(paise: int) -> float:
    return round(paise / 100, 2)


def _ensure(user_id: str) -> None:
    if user_id not in _balance_paise:
        _balance_paise[user_id] = _to_paise(DEFAULT_BALANCE_INR)
        _txns[user_id] = [{
            "id": f"seed-{uuid.uuid4().hex[:8]}",
            "type": "credit",
            "amount_inr": DEFAULT_BALANCE_INR,
            "note": "Welcome balance",
            "balance_after_inr": DEFAULT_BALANCE_INR,
            "at": int(time.time()),
        }]


def _record(user_id: str, kind: str, amount_inr: float, note: str) -> dict[str, Any]:
    txn = {
        "id": f"txn-{uuid.uuid4().hex[:10]}",
        "type": kind,
        "amount_inr": round(amount_inr, 2),
        "note": note,
        "balance_after_inr": _to_inr(_balance_paise[user_id]),
        "at": int(time.time()),
    }
    _txns[user_id].insert(0, txn)
    del _txns[user_id][_MAX_TXNS:]
    return txn


def snapshot(user_id: str = DEMO_USER) -> dict[str, Any]:
    with _LOCK:
        _ensure(user_id)
        return {
            "balance_inr": _to_inr(_balance_paise[user_id]),
            "currency": "INR",
            "transactions": list(_txns[user_id]),
        }


def credit(user_id: str, amount_inr: float, note: str = "Top-up") -> dict[str, Any]:
    with _LOCK:
        _ensure(user_id)
        _balance_paise[user_id] += _to_paise(amount_inr)
        txn = _record(user_id, "credit", amount_inr, note)
        return {"ok": True, "balance_inr": _to_inr(_balance_paise[user_id]), "txn": txn}


def debit(user_id: str, amount_inr: float, note: str = "Order") -> dict[str, Any]:
    """Deduct if funds suffice; otherwise leave the balance untouched."""
    with _LOCK:
        _ensure(user_id)
        need = _to_paise(amount_inr)
        if need <= 0:
            return {"ok": False, "reason": "invalid amount", "balance_inr": _to_inr(_balance_paise[user_id])}
        if _balance_paise[user_id] < need:
            return {
                "ok": False,
                "reason": "insufficient balance",
                "balance_inr": _to_inr(_balance_paise[user_id]),
                "shortfall_inr": _to_inr(need - _balance_paise[user_id]),
            }
        _balance_paise[user_id] -= need
        txn = _record(user_id, "debit", amount_inr, note)
        return {"ok": True, "balance_inr": _to_inr(_balance_paise[user_id]), "txn": txn}
