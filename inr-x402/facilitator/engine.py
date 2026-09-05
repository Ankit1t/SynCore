"""The settle pipeline + policy engine + reversal.

Order of checks is NON-NEGOTIABLE (per protocol spec):
  signature -> agent registered -> mandate exists & not expired -> per-txn limit
  -> daily cap -> category allowed -> velocity -> nonce replay -> intent expiry
  -> bank debit.

Two reliability invariants are enforced here and commented WHY inline:
  * the nonce is persisted BEFORE the bank debit call (crash-safe ordering);
  * the bank idempotency_key IS the intent nonce (no double charge on retry).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional, Tuple

from shared.crypto import verify_obj, sign_obj
from shared.models import (
    PaymentIntent, Receipt, now_utc, iso, parse_iso, REVERSAL_WINDOW_SECONDS,
)
from shared.reject_codes import RejectCode
from facilitator import db, keys, config
from facilitator.bank_client import BankClient, BankTimeout


class Facilitator:
    def __init__(self):
        self.cfg = config.load()
        self.facilitator_id = self.cfg["facilitator_id"]
        self.key = keys.ensure_facilitator_key(self.facilitator_id)
        self.bank = BankClient(
            self.cfg["bank_url"], timeout=self.cfg.get("bank_timeout_seconds", 5.0)
        )

    # --- decision logging ----------------------------------------------------
    def _log(self, nonce: Optional[str], agent_id: Optional[str], step: str,
             decision: str, reason: Optional[str] = None) -> None:
        conn = db.connect()
        try:
            conn.execute(
                "INSERT INTO decision_log(nonce, agent_id, step, decision, reason, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (nonce, agent_id, step, decision, reason, iso(now_utc())),
            )
            conn.commit()
        finally:
            conn.close()

    def _reject(self, nonce, agent_id, step, code: RejectCode) -> dict:
        self._log(nonce, agent_id, step, "reject", code.value)
        return {"ok": False, "reason": code.value}

    # --- policy helpers ------------------------------------------------------
    def _daily_settled_paise(self, mandate_ref: str) -> int:
        start_of_day = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        conn = db.connect()
        try:
            row = conn.execute(
                """SELECT COALESCE(SUM(amount_paise), 0) AS total FROM receipts
                   WHERE mandate_ref = ? AND status = 'settled' AND settled_at >= ?""",
                (mandate_ref, iso(start_of_day)),
            ).fetchone()
            return int(row["total"])
        finally:
            conn.close()

    def _velocity_count(self, mandate_ref: str) -> int:
        window = int(self.cfg.get("velocity_window_seconds", 60))
        since = iso(now_utc() - timedelta(seconds=window))
        conn = db.connect()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM nonces WHERE mandate_ref = ? AND created_at >= ?",
                (mandate_ref, since),
            ).fetchone()
            return int(row["n"])
        finally:
            conn.close()

    def _nonce_exists(self, nonce: str) -> bool:
        conn = db.connect()
        try:
            row = conn.execute("SELECT 1 FROM nonces WHERE nonce = ?", (nonce,)).fetchone()
            return row is not None
        finally:
            conn.close()

    def _persist_nonce(self, nonce: str, agent_id: str, mandate_ref: str) -> None:
        conn = db.connect()
        try:
            conn.execute(
                "INSERT INTO nonces(nonce, agent_id, mandate_ref, created_at) VALUES (?, ?, ?, ?)",
                (nonce, agent_id, mandate_ref, iso(now_utc())),
            )
            conn.commit()
        finally:
            conn.close()

    def _sign_and_store_receipt(self, receipt: Receipt, agent_id: str,
                                resource: str) -> Tuple[Receipt, str]:
        signature = sign_obj(self.key["signing_key_hex"], receipt.signing_payload())
        conn = db.connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO receipts(nonce, status, amount_paise, utrn,
                   settled_at, agent_id, mandate_ref, resource, receipt_json, signature, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (receipt.nonce, receipt.status, receipt.amountPaise, receipt.utrn,
                 receipt.settledAt, agent_id, None, resource,
                 receipt.model_dump_json(), signature, iso(now_utc())),
            )
            conn.commit()
        finally:
            conn.close()
        return receipt, signature

    # --- the pipeline --------------------------------------------------------
    def settle(self, intent: PaymentIntent, signature: str, agent_id: str) -> dict:
        nonce = intent.nonce

        # (1) SIGNATURE. Ed25519 verify needs the agent's registered pubkey, so
        # key lookup necessarily precedes crypto verify (see DECISIONS.md). A
        # registered agent with a bad signature fails HERE as bad_signature.
        pubkey = keys.get_agent_pubkey(agent_id)
        if intent.agentId != agent_id:
            return self._reject(nonce, agent_id, "signature", RejectCode.BAD_SIGNATURE)
        if pubkey is not None:
            if not verify_obj(pubkey, intent.signing_payload(), signature):
                return self._reject(nonce, agent_id, "signature", RejectCode.BAD_SIGNATURE)
            self._log(nonce, agent_id, "signature", "pass")

        # (2) AGENT REGISTERED.
        if pubkey is None:
            return self._reject(nonce, agent_id, "agent_registered", RejectCode.UNKNOWN_AGENT)
        self._log(nonce, agent_id, "agent_registered", "pass")

        # (3) MANDATE exists & not expired (fetched from the bank over HTTP).
        try:
            mandate = self.bank.get_mandate(intent.mandateRef)
        except BankTimeout:
            return self._reject(nonce, agent_id, "mandate", RejectCode.BANK_TIMEOUT)
        if not mandate:
            return self._reject(nonce, agent_id, "mandate", RejectCode.MANDATE_NOT_FOUND)
        if now_utc() > parse_iso(mandate["expires_at"]):
            return self._reject(nonce, agent_id, "mandate", RejectCode.MANDATE_EXPIRED)
        self._log(nonce, agent_id, "mandate", "pass")

        # (4) PER-TXN LIMIT.
        if intent.amountPaise > mandate["per_txn_max_paise"]:
            return self._reject(nonce, agent_id, "per_txn_limit", RejectCode.OVER_PER_TXN_LIMIT)
        self._log(nonce, agent_id, "per_txn_limit", "pass")

        # (5) DAILY CAP (sum of today's settled for this mandate + this amount).
        if self._daily_settled_paise(intent.mandateRef) + intent.amountPaise > mandate["daily_max_paise"]:
            return self._reject(nonce, agent_id, "daily_cap", RejectCode.OVER_DAILY_CAP)
        self._log(nonce, agent_id, "daily_cap", "pass")

        # (6) CATEGORY ALLOWED (facilitator maps resource -> category).
        category = config.category_for(self.cfg, intent.resource)
        if category not in mandate["categories"]:
            return self._reject(nonce, agent_id, "category", RejectCode.CATEGORY_BLOCKED)
        self._log(nonce, agent_id, "category", "pass")

        # (7) VELOCITY (rolling window count per mandate).
        if self._velocity_count(intent.mandateRef) >= int(self.cfg["velocity_max_txn"]):
            return self._reject(nonce, agent_id, "velocity", RejectCode.VELOCITY_EXCEEDED)
        self._log(nonce, agent_id, "velocity", "pass")

        # (8) NONCE REPLAY.
        if self._nonce_exists(nonce):
            return self._reject(nonce, agent_id, "replay", RejectCode.REPLAY_DETECTED)
        self._log(nonce, agent_id, "replay", "pass")

        # (9) INTENT EXPIRY (stale signed intents are worthless; 5 min TTL).
        if intent.is_expired():
            return self._reject(nonce, agent_id, "intent_expiry", RejectCode.INTENT_EXPIRED)
        self._log(nonce, agent_id, "intent_expiry", "pass")

        # Persist the nonce BEFORE debiting. WHY: if we crash after the bank
        # moves money, the nonce is already burned, so a replay can't double
        # charge; the client recovers the receipt via GET /receipt/{nonce}.
        self._persist_nonce(nonce, agent_id, intent.mandateRef)

        # (10) BANK DEBIT. idempotency_key = nonce. WHY: a retried debit for the
        # same intent hits the same key and never charges twice.
        try:
            result = self.bank.debit(intent.mandateRef, intent.amountPaise, nonce)
        except BankTimeout:
            return self._reject(nonce, agent_id, "bank_debit", RejectCode.BANK_TIMEOUT)

        if result.get("status") != "settled":
            self._log(nonce, agent_id, "bank_debit", "reject",
                      f"{RejectCode.BANK_DECLINED.value}:{result.get('reason')}")
            return {"ok": False, "reason": RejectCode.BANK_DECLINED.value}

        receipt = Receipt(
            nonce=nonce, status="settled", amountPaise=intent.amountPaise,
            utrn=result["utrn"], settledAt=iso(now_utc()),
            facilitatorId=self.facilitator_id,
        )
        receipt, sig = self._sign_and_store_receipt(receipt, agent_id, intent.resource)
        # mandate_ref is needed for daily-cap accounting; patch it in.
        self._set_receipt_mandate(nonce, intent.mandateRef)
        self._log(nonce, agent_id, "bank_debit", "pass", f"utrn={result['utrn']}")
        return {"ok": True, "receipt": receipt.model_dump(), "receiptSignature": sig}

    def _set_receipt_mandate(self, nonce: str, mandate_ref: str) -> None:
        conn = db.connect()
        try:
            conn.execute("UPDATE receipts SET mandate_ref = ? WHERE nonce = ?",
                         (mandate_ref, nonce))
            conn.commit()
        finally:
            conn.close()

    # --- receipt recovery ----------------------------------------------------
    def get_receipt(self, nonce: str) -> Optional[dict]:
        conn = db.connect()
        try:
            row = conn.execute("SELECT * FROM receipts WHERE nonce = ?", (nonce,)).fetchone()
            if not row:
                return None
            return {"receipt": Receipt.model_validate_json(row["receipt_json"]).model_dump(),
                    "receiptSignature": row["signature"]}
        finally:
            conn.close()

    # --- reversal (bounded window, idempotent) -------------------------------
    def reverse(self, nonce: str) -> dict:
        conn = db.connect()
        try:
            row = conn.execute("SELECT * FROM receipts WHERE nonce = ?", (nonce,)).fetchone()
        finally:
            conn.close()

        if not row:
            return {"ok": False, "reason": "receipt_not_found"}

        # Idempotent: already reversed -> return current receipt, no bank call.
        if row["status"] == "reversed":
            self._log(nonce, row["agent_id"], "reverse", "info", "already_reversed")
            return {"ok": True, "receipt": Receipt.model_validate_json(row["receipt_json"]).model_dump(),
                    "receiptSignature": row["signature"], "note": "already_reversed"}

        if row["status"] != "settled":
            return {"ok": False, "reason": "not_settled"}

        # Enforce the 10-minute reversal window.
        settled_at = parse_iso(row["settled_at"])
        if now_utc() > settled_at + timedelta(seconds=REVERSAL_WINDOW_SECONDS):
            self._log(nonce, row["agent_id"], "reverse", "reject", "window_expired")
            return {"ok": False, "reason": "reversal_window_expired"}

        try:
            bank_res = self.bank.reverse(nonce, reversal_key=f"rev_{nonce}")
        except BankTimeout:
            return {"ok": False, "reason": RejectCode.BANK_TIMEOUT.value}
        if bank_res.get("status") != "reversed":
            return {"ok": False, "reason": bank_res.get("reason", "bank_reverse_failed")}

        reversed_receipt = Receipt(
            nonce=nonce, status="reversed", amountPaise=row["amount_paise"],
            utrn=row["utrn"], settledAt=row["settled_at"],
            facilitatorId=self.facilitator_id,
        )
        signature = sign_obj(self.key["signing_key_hex"], reversed_receipt.signing_payload())
        conn = db.connect()
        try:
            conn.execute(
                "UPDATE receipts SET status='reversed', receipt_json=?, signature=? WHERE nonce=?",
                (reversed_receipt.model_dump_json(), signature, nonce),
            )
            conn.commit()
        finally:
            conn.close()
        self._log(nonce, row["agent_id"], "reverse", "pass")
        return {"ok": True, "receipt": reversed_receipt.model_dump(),
                "receiptSignature": signature}
