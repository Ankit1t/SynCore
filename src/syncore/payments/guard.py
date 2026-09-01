"""Final deterministic transaction guard.

Before ANY charge, every one of these must pass. This is the last line of
defense against paying the wrong amount, an unverified cart, a stale price, or
a budget violation (spec sections 55-56).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..budget.engine import check_budget
from ..domain.errors import TransactionGuardError
from ..domain.models import BudgetPolicy


@dataclass
class TransactionContext:
    user_id: str
    vendor: str
    amount: float
    currency: str
    budget: BudgetPolicy
    cart_verified: bool
    expected_item_count: int
    actual_item_count: int
    idempotency_key: str


def run_transaction_guard(ctx: TransactionContext) -> list[str]:
    """Run all pre-payment checks. Raises TransactionGuardError on any failure.

    Returns the list of checks that passed (for audit).
    """
    failures: list[str] = []
    passed: list[str] = []

    def check(name: str, ok: bool) -> None:
        (passed if ok else failures).append(name)

    check("vendor_present", bool(ctx.vendor))
    check("cart_verified", ctx.cart_verified)
    check("positive_amount", ctx.amount > 0)
    check("currency_valid", ctx.currency in {"INR", "USD", "EUR", "GBP"})
    check("item_count_matches", ctx.expected_item_count == ctx.actual_item_count
          and ctx.actual_item_count > 0)
    check("idempotency_key_present", bool(ctx.idempotency_key))

    verdict = check_budget(ctx.amount, ctx.budget)
    check("within_budget", verdict.ok)

    if failures:
        raise TransactionGuardError(
            "final transaction guard rejected the payment",
            details={"failed_checks": failures, "passed_checks": passed,
                     "budget": verdict.to_dict()},
        )
    return passed
