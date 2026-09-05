"""Core bank logic.

`debit()` is THE function boundary. To go live, swap its body for a real UPI
Autopay recurring-charge call and keep the same signature + return shape; the
facilitator never needs to change. Everything else here (mandates, ledger,
idempotency) is bank-side bookkeeping a real PSP would own too.
"""
from __future__ import annotations

import json
import os
import random
import secrets
import uuid
from typing import Optional

from shared.models import now_utc, iso, parse_iso
from mock_bank import db

# Internal account that receives settled funds (the merchant's nostro at bank).
MERCHANT_SETTLEMENT = "merchant_settlement"
OPENING_BALANCE_PAISE = 10_000_00  # ₹10,000 seeded per onboarded user

# --- Failure injection state -------------------------------------------------
# Seeded RNG so declines are deterministic for demos/tests. FAIL_RATE=0.2 means
# ~20% of NEW debits are declined. Set at import from env; overridable at runtime.
_fail_rate = float(os.environ.get("FAIL_RATE", "0.0"))
_rng = random.Random(int(os.environ.get("FAIL_SEED", "42")))


def set_fail_rate(rate: float, seed: Optional[int] = None) -> None:
    """Adjust decline probability (and optionally reseed) at runtime."""
    global _fail_rate, _rng
    _fail_rate = max(0.0, min(1.0, rate))
    if seed is not None:
        _rng = random.Random(seed)


def get_fail_rate() -> float:
    return _fail_rate


# --- Accounts ----------------------------------------------------------------
def onboard(user_id: Optional[str] = None,
            balance_paise: int = OPENING_BALANCE_PAISE) -> dict:
    uid = user_id or f"user_{uuid.uuid4().hex[:8]}"
    conn = db.connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO users(user_id, balance_paise) VALUES (?, ?)",
            (uid, balance_paise),
        )
        conn.commit()
    finally:
        conn.close()
    return {"user_id": uid, "balance_paise": balance_paise}


def get_balance(user_id: str) -> Optional[int]:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT balance_paise FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["balance_paise"] if row else None
    finally:
        conn.close()


# --- Mandates (UPI Autopay e-mandate) ----------------------------------------
def create_mandate(user_id: str, per_txn_max_paise: int, daily_max_paise: int,
                   categories: list[str], expires_at: str) -> dict:
    token = f"mdt_{uuid.uuid4().hex[:16]}"
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO mandates(mandate_token, user_id, per_txn_max_paise,
               daily_max_paise, categories, expires_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token, user_id, per_txn_max_paise, daily_max_paise,
             json.dumps(categories), expires_at, iso(now_utc())),
        )
        conn.commit()
    finally:
        conn.close()
    return get_mandate(token)


def get_mandate(mandate_token: str) -> Optional[dict]:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM mandates WHERE mandate_token = ?", (mandate_token,)
        ).fetchone()
        if not row:
            return None
        return {
            "mandate_token": row["mandate_token"],
            "user_id": row["user_id"],
            "per_txn_max_paise": row["per_txn_max_paise"],
            "daily_max_paise": row["daily_max_paise"],
            "categories": json.loads(row["categories"]),
            "expires_at": row["expires_at"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


# --- Ledger helpers ----------------------------------------------------------
def _write_ledger(conn, from_acct: str, to_acct: str, amount: int,
                  nonce: Optional[str], utrn: Optional[str], entry_type: str) -> None:
    conn.execute(
        """INSERT INTO ledger(from_acct, to_acct, amount_paise, nonce, utrn, ts, type)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (from_acct, to_acct, amount, nonce, utrn, iso(now_utc()), entry_type),
    )


def get_ledger(nonce: Optional[str] = None) -> list[dict]:
    conn = db.connect()
    try:
        if nonce:
            rows = conn.execute(
                "SELECT * FROM ledger WHERE nonce = ? ORDER BY id", (nonce,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM ledger ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _new_utrn() -> str:
    return "BK" + "".join(secrets.choice("0123456789") for _ in range(12))


# --- THE BOUNDARY ------------------------------------------------------------
def debit(mandate_token: str, amount_paise: int, idempotency_key: str) -> dict:
    """Charge a mandate. Returns {status, utrn, balance_after, reason?}.

    Swap the body of THIS function to call a real UPI Autopay charge API.
    Contract kept stable:
      status in {"settled", "declined"}
      idempotency_key -> identical response on replay, never a second debit.
    """
    conn = db.connect()
    try:
        # IDEMPOTENCY: if we've seen this key, replay the stored response.
        # WHY: bank debits are fallible + retried; the same key must never
        # move money twice (double-charge protection).
        existing = conn.execute(
            "SELECT response_json FROM debit_idempotency WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            return json.loads(existing["response_json"])

        mandate = get_mandate(mandate_token)
        if not mandate:
            return _finalize(conn, idempotency_key,
                             {"status": "declined", "utrn": None,
                              "balance_after": None, "reason": "mandate_not_found"})

        user_id = mandate["user_id"]
        balance = get_balance(user_id)
        if balance is None:
            return _finalize(conn, idempotency_key,
                             {"status": "declined", "utrn": None,
                              "balance_after": None, "reason": "user_not_found"})

        # Failure injection (seeded, deterministic). Simulates a real bank
        # declining sporadically so the agent's retry path gets exercised.
        if _rng.random() < _fail_rate:
            return _finalize(conn, idempotency_key,
                             {"status": "declined", "utrn": None,
                              "balance_after": balance, "reason": "fail_injection"})

        if balance < amount_paise:
            return _finalize(conn, idempotency_key,
                             {"status": "declined", "utrn": None,
                              "balance_after": balance, "reason": "insufficient_funds"})

        # Move money + write the double-entry pair atomically.
        utrn = _new_utrn()
        new_balance = balance - amount_paise
        conn.execute("UPDATE users SET balance_paise = ? WHERE user_id = ?",
                     (new_balance, user_id))
        # debit leg (user's cash out) + credit leg (merchant's cash in).
        _write_ledger(conn, user_id, MERCHANT_SETTLEMENT, amount_paise,
                      idempotency_key, utrn, "debit")
        _write_ledger(conn, user_id, MERCHANT_SETTLEMENT, amount_paise,
                      idempotency_key, utrn, "credit")
        return _finalize(conn, idempotency_key,
                         {"status": "settled", "utrn": utrn,
                          "balance_after": new_balance, "reason": None})
    finally:
        conn.close()


def _finalize(conn, idempotency_key: str, response: dict) -> dict:
    """Persist idempotency record + commit, then return the response."""
    conn.execute(
        "INSERT OR IGNORE INTO debit_idempotency(idempotency_key, response_json, created_at) VALUES (?, ?, ?)",
        (idempotency_key, json.dumps(response), iso(now_utc())),
    )
    conn.commit()
    return response


def reverse(nonce: str, reversal_key: str) -> dict:
    """Credit money back for a prior debit identified by its nonce.

    Idempotent on reversal_key. Returns {status, reversed_amount_paise?, reason?}.
    """
    conn = db.connect()
    try:
        existing = conn.execute(
            "SELECT response_json FROM debit_idempotency WHERE idempotency_key = ?",
            (reversal_key,),
        ).fetchone()
        if existing:
            return json.loads(existing["response_json"])

        debit_row = conn.execute(
            "SELECT * FROM ledger WHERE nonce = ? AND type = 'debit' ORDER BY id LIMIT 1",
            (nonce,),
        ).fetchone()
        if not debit_row:
            return _finalize(conn, reversal_key,
                             {"status": "declined", "reason": "original_debit_not_found"})

        user_id = debit_row["from_acct"]
        amount = debit_row["amount_paise"]
        utrn = debit_row["utrn"]
        balance = get_balance(user_id) or 0
        conn.execute("UPDATE users SET balance_paise = ? WHERE user_id = ?",
                     (balance + amount, user_id))
        _write_ledger(conn, MERCHANT_SETTLEMENT, user_id, amount, nonce, utrn, "reversal")
        return _finalize(conn, reversal_key,
                         {"status": "reversed", "reversed_amount_paise": amount,
                          "balance_after": balance + amount, "reason": None})
    finally:
        conn.close()
