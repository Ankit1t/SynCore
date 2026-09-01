"""Property-based tests for critical financial and conversion logic."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from syncore.budget.engine import check_budget
from syncore.domain.enums import ConstraintType, Unit
from syncore.domain.models import BudgetPolicy, CheckoutSession, Quantity
from syncore.payments.guard import TransactionContext
from syncore.payments.policy import PaymentPolicy
from syncore.payments.provider import MockPaymentProvider
from syncore.payments.service import IdempotencyStore, PaymentService
from syncore.units import conversion


@given(grams=st.integers(min_value=1, max_value=1_000_000))
def test_grams_kg_roundtrip(grams):
    q = Quantity(value=grams, unit=Unit.G)
    as_kg = conversion.convert(q, Unit.KG)
    back = conversion.convert(as_kg, Unit.G)
    assert abs(back.value - grams) < 1e-6


def test_1000g_equals_1kg():
    assert conversion.to_base(Quantity(value=1000, unit=Unit.G)) == conversion.to_base(
        Quantity(value=1, unit=Unit.KG)
    )


@given(
    total=st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False),
    limit=st.floats(min_value=0.01, max_value=100000, allow_nan=False, allow_infinity=False),
)
def test_hard_budget_verdict_is_consistent(total, limit):
    """For a hard budget B: verdict.ok is True iff total <= B."""
    v = check_budget(total, BudgetPolicy(limit=limit, constraint_type=ConstraintType.HARD))
    assert v.ok == (round(total, 2) <= limit + 1e-9)


@given(key=st.text(min_size=1, max_size=40), amount=st.floats(min_value=1, max_value=400))
def test_idempotent_payment_single_charge(key, amount):
    """Repeated processing with the same idempotency key never charges twice."""
    svc = PaymentService(MockPaymentProvider(), PaymentPolicy(
        auto_limit=500, daily_limit=100000, trusted_vendors={"mock-fresh"}), IdempotencyStore())
    checkout = CheckoutSession(cart_id="c", marketplace="mock-fresh", vendor="mock-fresh",
                               final_total=round(amount, 2))
    ctx = TransactionContext(user_id="u", vendor="mock-fresh", amount=round(amount, 2),
                             currency="INR", budget=BudgetPolicy(limit=100000),
                             cart_verified=True, expected_item_count=1, actual_item_count=1,
                             idempotency_key=key)
    i1, a1 = svc.process(checkout=checkout, user_id="u", guard_ctx=ctx)
    i2, a2 = svc.process(checkout=checkout, user_id="u", guard_ctx=ctx)
    assert i1.id == i2.id
    assert a2 == []  # no second set of attempts -> no double charge
