"""Delegation service (Blueprint STEP 13/54).

Owns delegated authority lifecycle: create, get, list, revoke, pause, resume.
Status is server-authoritative and evaluated at decision time. A global kill
switch pauses all of a user's delegations at once.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..observability.logging import get_logger
from ..domain.enums import DelegationStatus
from .models import Delegation, SpendingLimits

logger = get_logger("syncore.payments.delegation")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DelegationService:
    """In-memory store (mirrors DB rows in syncore.db.tables for persistence)."""

    def __init__(self) -> None:
        self._by_id: dict[str, Delegation] = {}

    def create(
        self,
        *,
        user_id: str,
        agent_id: str,
        limits: SpendingLimits,
        purpose: str = "GROCERY",
        allowed_categories: list[str] | None = None,
        allowed_merchants: list[str] | None = None,
        currency: str = "INR",
        substitution: str = "ASK",
        expires_at: datetime | None = None,
    ) -> Delegation:
        d = Delegation(
            user_id=user_id, agent_id=agent_id, purpose=purpose,
            allowed_categories=allowed_categories or ["GROCERY"],
            allowed_merchants=allowed_merchants or [],
            currency=currency, limits=limits, substitution=substitution,
        )
        if expires_at:
            d.expires_at = expires_at
        self._by_id[d.id] = d
        logger.info("delegation created id=%s user=%s per_txn=%d", d.id, user_id, limits.per_txn_paise)
        return d

    def get(self, delegation_id: str) -> Delegation | None:
        return self._by_id.get(delegation_id)

    def list_for_user(self, user_id: str) -> list[Delegation]:
        return [d for d in self._by_id.values() if d.user_id == user_id]

    def effective_status(self, d: Delegation, now: datetime | None = None) -> DelegationStatus:
        now = now or _now()
        if d.status in (DelegationStatus.REVOKED, DelegationStatus.PAUSED):
            return d.status
        exp = d.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now >= exp:
            return DelegationStatus.EXPIRED
        return d.status

    def revoke(self, delegation_id: str) -> Delegation:
        d = self._require(delegation_id)
        d.status = DelegationStatus.REVOKED
        logger.info("delegation revoked id=%s", delegation_id)
        return d

    def pause(self, delegation_id: str) -> Delegation:
        d = self._require(delegation_id)
        if d.status == DelegationStatus.ACTIVE:
            d.status = DelegationStatus.PAUSED
        return d

    def resume(self, delegation_id: str) -> Delegation:
        d = self._require(delegation_id)
        if d.status == DelegationStatus.PAUSED:
            d.status = DelegationStatus.ACTIVE
            d.version += 1
        return d

    def pause_all_for_user(self, user_id: str) -> int:
        """Kill switch: pause every ACTIVE delegation for a user."""
        n = 0
        for d in self._by_id.values():
            if d.user_id == user_id and d.status == DelegationStatus.ACTIVE:
                d.status = DelegationStatus.PAUSED
                n += 1
        logger.info("kill-switch paused %d delegation(s) for user=%s", n, user_id)
        return n

    def resume_all_for_user(self, user_id: str) -> int:
        n = 0
        for d in self._by_id.values():
            if d.user_id == user_id and d.status == DelegationStatus.PAUSED:
                d.status = DelegationStatus.ACTIVE
                d.version += 1
                n += 1
        return n

    def _require(self, delegation_id: str) -> Delegation:
        d = self._by_id.get(delegation_id)
        if not d:
            raise KeyError(f"unknown delegation {delegation_id}")
        return d
