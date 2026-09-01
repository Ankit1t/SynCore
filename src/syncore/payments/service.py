"""PaymentService: orchestrates guard -> policy -> provider with idempotency.

Guarantees:
  * The final transaction guard runs before any authorization.
  * A repeated idempotency key never creates a second charge.
  * Amounts over policy limits / untrusted vendors stop at a human checkpoint
    instead of silently charging.
"""

from __future__ import annotations

from ..domain.enums import PaymentStatus
from ..domain.errors import TransactionGuardError
from ..domain.models import (
    CheckoutSession,
    PaymentAttempt,
    PaymentIntent,
)
from ..observability.logging import get_logger
from .guard import TransactionContext, run_transaction_guard
from .policy import PaymentAction, PaymentPolicy
from .provider import PaymentProvider

logger = get_logger("syncore.payments")


class IdempotencyStore:
    """In-memory idempotency store (swap for Redis/DB in production)."""

    def __init__(self) -> None:
        self._store: dict[str, PaymentIntent] = {}

    def get(self, key: str) -> PaymentIntent | None:
        return self._store.get(key)

    def put(self, key: str, intent: PaymentIntent) -> None:
        self._store[key] = intent


class PaymentService:
    def __init__(
        self,
        provider: PaymentProvider,
        policy: PaymentPolicy,
        idempotency_store: IdempotencyStore | None = None,
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._idempotency = idempotency_store or IdempotencyStore()

    def process(
        self,
        *,
        checkout: CheckoutSession,
        user_id: str,
        guard_ctx: TransactionContext,
        category: str = "grocery",
        daily_spent: float = 0.0,
        auto_pay_enabled: bool = True,
    ) -> tuple[PaymentIntent, list[PaymentAttempt]]:
        key = guard_ctx.idempotency_key

        # Idempotency: return the prior terminal result unchanged.
        cached = self._idempotency.get(key)
        if cached is not None:
            logger.info("payment idempotency hit key=%s status=%s", key, cached.status)
            return cached, []

        intent = PaymentIntent(
            checkout_session_id=checkout.id,
            user_id=user_id,
            amount=checkout.final_total,
            currency=checkout.currency,
            vendor=checkout.vendor,
            idempotency_key=key,
            status=PaymentStatus.CREATED,
        )
        attempts: list[PaymentAttempt] = []

        # 1) Deterministic final guard (raises on failure).
        try:
            run_transaction_guard(guard_ctx)
        except TransactionGuardError as exc:
            intent.status = PaymentStatus.FAILED
            attempts.append(PaymentAttempt(intent_id=intent.id, status=PaymentStatus.FAILED,
                                           message=exc.message))
            self._idempotency.put(key, intent)
            raise

        # 2) Policy decision.
        decision = self._policy.decide(
            amount=intent.amount, vendor=intent.vendor, currency=intent.currency,
            category=category, daily_spent=daily_spent, auto_pay_enabled=auto_pay_enabled,
        )
        if decision.action != PaymentAction.AUTO:
            intent.status = (
                PaymentStatus.REQUIRES_USER_ACTION
                if decision.action == PaymentAction.REQUIRE_USER
                else PaymentStatus.FAILED
            )
            intent.requires_user_action = decision.action == PaymentAction.REQUIRE_USER
            intent.checkpoint_reason = decision.checkpoint_reason
            attempts.append(PaymentAttempt(intent_id=intent.id, status=intent.status,
                                           message=decision.reason))
            self._idempotency.put(key, intent)
            logger.info("payment requires action: %s", decision.reason)
            return intent, attempts

        # 3) Authorize + capture through the provider.
        auth = self._provider.authorize(amount=intent.amount, currency=intent.currency,
                                        vendor=intent.vendor, idempotency_key=key)
        attempts.append(PaymentAttempt(intent_id=intent.id, status=auth.status,
                                       provider_reference=auth.provider_reference,
                                       message=auth.message))
        if auth.status != PaymentStatus.AUTHORIZED:
            intent.status = PaymentStatus.FAILED
            self._idempotency.put(key, intent)
            return intent, attempts

        intent.status = PaymentStatus.PROCESSING
        cap = self._provider.capture(provider_reference=auth.provider_reference or "",
                                     idempotency_key=key)
        attempts.append(PaymentAttempt(intent_id=intent.id, status=cap.status,
                                       provider_reference=cap.provider_reference,
                                       message=cap.message))
        intent.status = cap.status
        self._idempotency.put(key, intent)
        return intent, attempts

    def check_status(self, provider_reference: str) -> PaymentStatus:
        return self._provider.get_status(provider_reference)
