"""Budget engine.

A hard budget is a non-negotiable constraint: the system never intentionally
exceeds it. This module provides deterministic verdicts used both when
optimizing (advisory search prices) and at the final pre-payment guard
(authoritative checkout total).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.enums import ConstraintType
from ..domain.models import BudgetPolicy


@dataclass
class BudgetVerdict:
    ok: bool
    limit: float | None
    total: float
    currency: str
    remaining: float | None
    is_hard: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "limit": self.limit,
            "total": round(self.total, 2),
            "currency": self.currency,
            "remaining": round(self.remaining, 2) if self.remaining is not None else None,
            "is_hard": self.is_hard,
            "reason": self.reason,
        }


def check_budget(total: float, budget: BudgetPolicy) -> BudgetVerdict:
    """Evaluate a candidate total against the budget policy."""
    total = round(total, 2)
    is_hard = budget.constraint_type == ConstraintType.HARD
    if budget.limit is None:
        return BudgetVerdict(
            ok=True, limit=None, total=total, currency=budget.currency,
            remaining=None, is_hard=is_hard, reason="no budget limit set",
        )

    remaining = round(budget.limit - total, 2)
    if total <= budget.limit + 1e-9:
        return BudgetVerdict(
            ok=True, limit=budget.limit, total=total, currency=budget.currency,
            remaining=remaining, is_hard=is_hard,
            reason=f"within budget (₹{remaining:g} remaining)",
        )

    over = round(total - budget.limit, 2)
    # A soft budget may be exceeded (with a warning); a hard budget may not.
    ok = not is_hard
    return BudgetVerdict(
        ok=ok, limit=budget.limit, total=total, currency=budget.currency,
        remaining=remaining, is_hard=is_hard,
        reason=f"over budget by ₹{over:g}" + ("" if ok else " (hard limit)"),
    )
