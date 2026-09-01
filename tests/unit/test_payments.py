"""Payment policy, guard, provider and idempotency tests."""

from __future__ import annotations

import pytest

from syncore.domain.enums import ConstraintType, PaymentStatus
from syncore.domain.errors import TransactionGuardError
from syncore.domain.models import BudgetPolicy, CheckoutSession
from syncore.payments.guard import TransactionContext, run_transaction_guard
from syncore.payments.policy import PaymentAction, PaymentPolicy
from syncore.payments.provider import MockPaymentProvider
from syncore.payments.service import IdempotencyStore, PaymentService


def _policy():
    return PaymentPolicy(auto_limit=500, daily_limit=5000, trusted_vendors={"mock-fresh"})


def _checkout(amount=100.0, vendor="mock-fresh"):
    return CheckoutSession(cart_id="c", marketplace=vendor, vendor=vendor, final_total=amount)


def _guard_ctx(amount=100.0, vendor="mock-fresh", key="k1", limit=500.0):
    return TransactionContext(
        user_id="u", vendor=vendor, amount=amount, currency="INR",
        budget=BudgetPolicy(limit=limit, constraint_type=ConstraintType.HARD),
        cart_verified=True, expected_item_count=2, actual_item_count=2, idempotency_key=key,
    )


def test_auto_pay_within_limit():
    d = _policy().decide(amount=100, vendor="mock-fresh", currency="INR")
    assert d.action == PaymentAction.AUTO


def test_over_limit_requires_user():
    d = _policy().decide(amount=600, vendor="mock-fresh", currency="INR")
    assert d.action == PaymentAction.REQUIRE_USER


def test_untrusted_vendor_requires_user():
    d = _policy().decide(amount=50, vendor="sketchy-shop", currency="INR")
    assert d.action == PaymentAction.REQUIRE_USER


def test_guard_rejects_unverified_cart():
    ctx = _guard_ctx()
    ctx.cart_verified = False
    with pytest.raises(TransactionGuardError):
        run_transaction_guard(ctx)


def test_guard_rejects_over_budget():
    with pytest.raises(TransactionGuardError):
        run_transaction_guard(_guard_ctx(amount=600.0, limit=500.0))


def test_successful_auto_payment():
    svc = PaymentService(MockPaymentProvider(), _policy(), IdempotencyStore())
    intent, attempts = svc.process(checkout=_checkout(100.0), user_id="u", guard_ctx=_guard_ctx())
    assert intent.status == PaymentStatus.SUCCEEDED
    assert any(a.provider_reference for a in attempts)


def test_idempotency_no_double_charge():
    store = IdempotencyStore()
    svc = PaymentService(MockPaymentProvider(), _policy(), store)
    intent1, _ = svc.process(checkout=_checkout(100.0), user_id="u",
                             guard_ctx=_guard_ctx(key="same-key"))
    intent2, attempts2 = svc.process(checkout=_checkout(100.0), user_id="u",
                                     guard_ctx=_guard_ctx(key="same-key"))
    # Same idempotency key -> same intent, no new charge attempts.
    assert intent1.id == intent2.id
    assert attempts2 == []


def test_high_value_amount_stops_for_user():
    svc = PaymentService(MockPaymentProvider(), _policy(), IdempotencyStore())
    intent, _ = svc.process(checkout=_checkout(900.0), user_id="u",
                            guard_ctx=_guard_ctx(amount=900.0, limit=1000.0, key="big"))
    assert intent.status == PaymentStatus.REQUIRES_USER_ACTION
    assert intent.requires_user_action
