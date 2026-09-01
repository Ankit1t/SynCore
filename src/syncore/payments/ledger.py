"""Spend ledger for velocity/limit checks (integer paise, rolling windows)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class _Rec:
    delegation_id: str
    amount_paise: int
    at: datetime


@dataclass
class LedgerView:
    spent_daily_paise: int
    spent_monthly_paise: int


class SpendLedger:
    def __init__(self) -> None:
        self._records: list[_Rec] = []

    def record(self, delegation_id: str, amount_paise: int, at: datetime | None = None) -> None:
        self._records.append(_Rec(delegation_id, amount_paise, at or datetime.now(timezone.utc)))

    def view(self, delegation_id: str, now: datetime | None = None) -> LedgerView:
        now = now or datetime.now(timezone.utc)
        day = now - timedelta(days=1)
        month = now - timedelta(days=30)
        daily = sum(r.amount_paise for r in self._records
                    if r.delegation_id == delegation_id and r.at >= day)
        monthly = sum(r.amount_paise for r in self._records
                      if r.delegation_id == delegation_id and r.at >= month)
        return LedgerView(spent_daily_paise=daily, spent_monthly_paise=monthly)

    def recent_count(self, delegation_id: str, now: datetime | None = None, seconds: int = 60) -> int:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=seconds)
        return sum(1 for r in self._records if r.delegation_id == delegation_id and r.at >= cutoff)
