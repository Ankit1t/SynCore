"""Agent client core."""
from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Optional

import httpx

from shared.canonical import canonical_json
from shared.crypto import sign_obj, verify_obj
from shared.models import (
    PaymentIntent, now_utc, iso, INTENT_TTL_SECONDS,
)


class ReplayHardStop(Exception):
    """Raised when the facilitator reports replay_detected. Never retry."""


@dataclass
class AgentConfig:
    agent_id: str
    signing_key_hex: str
    mandate_ref: str
    merchant_base: str = "http://localhost:8001"
    budget_paise: int = 10_000_00
    receipts_path: str = "agent_receipts.jsonl"
    config_path: Optional[str] = None  # where to persist budget updates

    @classmethod
    def load(cls, path: str) -> "AgentConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        allowed = {"agent_id", "signing_key_hex", "mandate_ref", "merchant_base",
                   "budget_paise", "receipts_path"}
        kwargs = {k: v for k, v in data.items() if k in allowed}
        kwargs["config_path"] = path
        return cls(**kwargs)


@dataclass
class PayResult:
    ok: bool
    status: str                     # settled | rejected | recovered | budget_exceeded | error
    reason: Optional[str] = None
    data: Optional[dict] = None
    receipt: Optional[dict] = None
    receipt_signature: Optional[str] = None
    nonce: Optional[str] = None
    attempts: int = 0
    receipt_verified: Optional[bool] = None


class Agent:
    def __init__(self, cfg: AgentConfig, timeout: float = 15.0):
        self.cfg = cfg
        self.timeout = timeout
        self._facilitator_pubkey: Optional[str] = None

    # --- persistence ---------------------------------------------------------
    def _persist_receipt(self, receipt: dict, signature: Optional[str]) -> None:
        """Append every receipt to a local JSONL expense log."""
        line = json.dumps({"receipt": receipt, "receiptSignature": signature,
                           "loggedAt": iso(now_utc())})
        path = self.cfg.receipts_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _persist_budget(self) -> None:
        if not self.cfg.config_path or not os.path.exists(self.cfg.config_path):
            return
        with open(self.cfg.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["budget_paise"] = self.cfg.budget_paise
        with open(self.cfg.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # --- receipt verification -----------------------------------------------
    def _get_facilitator_pubkey(self, facilitator_url: str) -> Optional[str]:
        if self._facilitator_pubkey:
            return self._facilitator_pubkey
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(f"{facilitator_url}/facilitator/pubkey")
                self._facilitator_pubkey = r.json()["verify_key_hex"]
        except Exception:
            self._facilitator_pubkey = None
        return self._facilitator_pubkey

    def _verify_receipt(self, facilitator_url: str, receipt: dict,
                        signature: Optional[str]) -> Optional[bool]:
        if not signature:
            return None
        pubkey = self._get_facilitator_pubkey(facilitator_url)
        if not pubkey:
            return None
        # Receipt is verified over the same signing payload the facilitator used.
        payload = {
            "nonce": receipt["nonce"], "status": receipt["status"],
            "amountPaise": receipt["amountPaise"], "utrn": receipt.get("utrn"),
            "settledAt": receipt.get("settledAt"),
            "facilitatorId": receipt["facilitatorId"],
        }
        return verify_obj(pubkey, payload, signature)

    # --- intent building -----------------------------------------------------
    def _build_intent(self, invoice: dict) -> PaymentIntent:
        return PaymentIntent(
            nonce=str(uuid.uuid4()),
            resource=invoice["resource"],
            amountPaise=invoice["pricePaise"],
            payTo=invoice["payTo"],
            mandateRef=self.cfg.mandate_ref,
            agentId=self.cfg.agent_id,
            issuedAt=iso(now_utc()),
            expiresAt=iso(now_utc() + timedelta(seconds=INTENT_TTL_SECONDS)),
        )

    def _payment_header(self, intent: PaymentIntent) -> str:
        signature = sign_obj(self.cfg.signing_key_hex, intent.signing_payload())
        envelope = {
            "intent": intent.model_dump(),
            "signature": signature,
            "agentId": self.cfg.agent_id,
        }
        return base64.b64encode(canonical_json(envelope).encode("utf-8")).decode("ascii")

    # --- receipt recovery ----------------------------------------------------
    def _poll_receipt(self, facilitator_url: str, nonce: str) -> Optional[dict]:
        """After a post-submit timeout, check if the debit actually succeeded."""
        try:
            with httpx.Client(timeout=self.timeout) as c:
                r = c.get(f"{facilitator_url}/receipt/{nonce}")
                if r.status_code == 200:
                    return r.json()
        except Exception:
            return None
        return None

    # --- main flow -----------------------------------------------------------
    def pay(self, path: str, simulate_timeout_once: bool = False) -> PayResult:
        url = f"{self.cfg.merchant_base}{path}"

        # Step 1: GET -> expect 402 + invoice.
        with httpx.Client(timeout=self.timeout) as c:
            first = c.get(url)
        if first.status_code == 200:
            return PayResult(ok=True, status="settled", data=first.json(),
                             reason="free_resource")
        if first.status_code != 402:
            return PayResult(ok=False, status="error",
                             reason=f"unexpected_status_{first.status_code}")

        invoice = first.json()
        facilitator_url = invoice["facilitatorUrl"]
        price = invoice["pricePaise"]

        # Step 2: local budget check BEFORE signing/spending.
        if price > self.cfg.budget_paise:
            return PayResult(ok=False, status="budget_exceeded",
                             reason=f"price {price} > budget {self.cfg.budget_paise}")

        attempts = 0
        max_attempts = 2  # allow ONE retry on bank_declined
        pending_timeout = simulate_timeout_once
        while attempts < max_attempts:
            attempts += 1
            intent = self._build_intent(invoice)
            header = self._payment_header(intent)

            # Step 3: retry GET with X-PAYMENT.
            try:
                with httpx.Client(timeout=self.timeout) as c:
                    if pending_timeout:
                        # Simulate a dropped response AFTER the debit committed:
                        # fire the settle request, then pretend we never saw it.
                        pending_timeout = False
                        c.get(url, headers={"X-PAYMENT": header})
                        raise httpx.ReadTimeout("simulated post-submit timeout")
                    resp = c.get(url, headers={"X-PAYMENT": header})
            except (httpx.TimeoutException, httpx.TransportError):
                # Post-submit timeout: poll the receipt endpoint before retrying.
                recovered = self._poll_receipt(facilitator_url, intent.nonce)
                if recovered and recovered.get("receipt", {}).get("status") == "settled":
                    receipt = recovered["receipt"]
                    sig = recovered.get("receiptSignature")
                    self._persist_receipt(receipt, sig)
                    self.cfg.budget_paise -= receipt["amountPaise"]
                    self._persist_budget()
                    verified = self._verify_receipt(facilitator_url, receipt, sig)
                    return PayResult(ok=True, status="recovered", data=None,
                                     receipt=receipt, receipt_signature=sig,
                                     nonce=intent.nonce, attempts=attempts,
                                     receipt_verified=verified)
                # No receipt -> debit didn't land; retry with a fresh nonce.
                continue

            if resp.status_code == 200:
                data = resp.json()
                receipt, sig = self._extract_receipt(resp)
                if receipt:
                    self._persist_receipt(receipt, sig)
                    self.cfg.budget_paise -= receipt["amountPaise"]
                    self._persist_budget()
                verified = self._verify_receipt(facilitator_url, receipt, sig) if receipt else None
                return PayResult(ok=True, status="settled", data=data,
                                 receipt=receipt, receipt_signature=sig,
                                 nonce=intent.nonce, attempts=attempts,
                                 receipt_verified=verified)

            # 402 (or other) -> a rejection with a machine-readable reason.
            reason = None
            try:
                reason = resp.json().get("reason")
            except Exception:
                pass

            if reason == "replay_detected":
                # NEVER retry a replay. Hard stop.
                return PayResult(ok=False, status="rejected", reason=reason,
                                 nonce=intent.nonce, attempts=attempts)
            if reason == "bank_declined" and attempts < max_attempts:
                # Retry ONCE with a fresh nonce (loop continues).
                continue
            return PayResult(ok=False, status="rejected", reason=reason,
                             nonce=intent.nonce, attempts=attempts)

        return PayResult(ok=False, status="rejected", reason="bank_declined",
                         attempts=attempts)

    @staticmethod
    def _extract_receipt(resp: httpx.Response):
        header = resp.headers.get("X-PAYMENT-RESPONSE")
        if header:
            try:
                env = json.loads(base64.b64decode(header))
                return env.get("receipt"), env.get("receiptSignature")
            except Exception:
                pass
        # Fallback: receipt is also embedded in the JSON body.
        try:
            body = resp.json()
            return body.get("receipt"), None
        except Exception:
            return None, None
