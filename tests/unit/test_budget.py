"""Budget engine tests."""

from __future__ import annotations

from syncore.budget.engine import check_budget
from syncore.domain.enums import ConstraintType
from syncore.domain.models import BudgetPolicy


def test_within_hard_budget():
    v = check_budget(94.0, BudgetPolicy(limit=500.0))
    assert v.ok and v.remaining == 406.0


def test_over_hard_budget_not_ok():
    v = check_budget(520.0, BudgetPolicy(limit=500.0, constraint_type=ConstraintType.HARD))
    assert not v.ok and v.is_hard


def test_over_soft_budget_ok_with_warning():
    v = check_budget(520.0, BudgetPolicy(limit=500.0, constraint_type=ConstraintType.SOFT))
    assert v.ok and "over budget" in v.reason


def test_no_limit_always_ok():
    v = check_budget(9999.0, BudgetPolicy(limit=None))
    assert v.ok and v.remaining is None


def test_exact_limit_is_within():
    v = check_budget(500.0, BudgetPolicy(limit=500.0))
    assert v.ok and v.remaining == 0.0
