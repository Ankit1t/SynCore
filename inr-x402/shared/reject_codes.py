"""Machine-readable reject codes.

Every rejection in the protocol returns one of these exact strings so agents
can branch programmatically (e.g. never retry on replay_detected).
"""
from __future__ import annotations

from enum import Enum


class RejectCode(str, Enum):
    BAD_SIGNATURE = "bad_signature"
    UNKNOWN_AGENT = "unknown_agent"
    MANDATE_NOT_FOUND = "mandate_not_found"
    MANDATE_EXPIRED = "mandate_expired"
    OVER_PER_TXN_LIMIT = "over_per_txn_limit"
    OVER_DAILY_CAP = "over_daily_cap"
    CATEGORY_BLOCKED = "category_blocked"
    VELOCITY_EXCEEDED = "velocity_exceeded"
    REPLAY_DETECTED = "replay_detected"
    INTENT_EXPIRED = "intent_expired"
    BANK_DECLINED = "bank_declined"
    BANK_TIMEOUT = "bank_timeout"

    def __str__(self) -> str:  # so f-strings / json give the bare value
        return self.value
