"""Webhook security (Blueprint STEP 22).

Verifies HMAC-SHA256 signature over `timestamp.payload`, enforces a timestamp
freshness window, and deduplicates by provider event id (replay protection).
Payloads are never trusted before verification.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from ..observability.logging import get_logger

logger = get_logger("syncore.payments.webhooks")


def sign_payload(secret: str, timestamp: str, payload: bytes) -> str:
    msg = timestamp.encode() + b"." + payload
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str, payload: bytes, signature: str, timestamp: str, *, tolerance_s: int = 300
) -> tuple[bool, str]:
    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False, "bad timestamp"
    if abs(time.time() - ts) > tolerance_s:
        return False, "timestamp outside tolerance"
    expected = sign_payload(secret, timestamp, payload)
    if not hmac.compare_digest(expected, signature or ""):
        return False, "signature mismatch"
    return True, "ok"


class WebhookProcessor:
    """Idempotent, replay-protected webhook intake."""

    def __init__(self, secret: str) -> None:
        self._secret = secret
        self._seen: set[str] = set()

    def process(
        self, *, payload: bytes, signature: str, timestamp: str, event_id: str, event_type: str
    ) -> tuple[bool, str]:
        ok, reason = verify_signature(self._secret, payload, signature, timestamp)
        if not ok:
            logger.warning("webhook rejected: %s", reason)
            return False, reason
        if not event_id:
            return False, "missing event id"
        if event_id in self._seen:
            return False, "duplicate event (replay rejected)"
        self._seen.add(event_id)
        logger.info("webhook accepted event=%s type=%s", event_id, event_type)
        return True, "accepted"
