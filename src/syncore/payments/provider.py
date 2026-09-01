"""Payment provider abstraction + mock provider.

Real providers (Stripe, Razorpay, ...) implement this interface. The mock
provider simulates authorization/capture deterministically for tests and never
touches real money. Idempotency is enforced by the caller (PaymentService).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain.enums import PaymentStatus
from ..domain.models import new_id


@dataclass
class ProviderResult:
    status: PaymentStatus
    provider_reference: str | None
    message: str


class PaymentProvider(Protocol):
    name: str

    def authorize(self, *, amount: float, currency: str, vendor: str,
                  idempotency_key: str) -> ProviderResult:
        ...

    def capture(self, *, provider_reference: str, idempotency_key: str) -> ProviderResult:
        ...

    def get_status(self, provider_reference: str) -> PaymentStatus:
        ...


class MockPaymentProvider:
    """Deterministic sandbox provider. No real network / money involved."""

    name = "mock"

    def __init__(self) -> None:
        self._refs: dict[str, PaymentStatus] = {}
        self._by_key: dict[str, str] = {}

    def authorize(self, *, amount: float, currency: str, vendor: str,
                  idempotency_key: str) -> ProviderResult:
        # Idempotent at the provider level too: same key -> same reference.
        if idempotency_key in self._by_key:
            ref = self._by_key[idempotency_key]
            return ProviderResult(self._refs[ref], ref, "reused existing authorization")
        ref = f"auth_{new_id()[:12]}"
        self._by_key[idempotency_key] = ref
        self._refs[ref] = PaymentStatus.AUTHORIZED
        return ProviderResult(PaymentStatus.AUTHORIZED, ref, "authorized (sandbox)")

    def capture(self, *, provider_reference: str, idempotency_key: str) -> ProviderResult:
        status = self._refs.get(provider_reference)
        if status is None:
            return ProviderResult(PaymentStatus.FAILED, provider_reference, "unknown reference")
        if status == PaymentStatus.SUCCEEDED:
            return ProviderResult(PaymentStatus.SUCCEEDED, provider_reference,
                                  "already captured (idempotent)")
        self._refs[provider_reference] = PaymentStatus.SUCCEEDED
        return ProviderResult(PaymentStatus.SUCCEEDED, provider_reference, "captured (sandbox)")

    def get_status(self, provider_reference: str) -> PaymentStatus:
        return self._refs.get(provider_reference, PaymentStatus.FAILED)


def get_payment_provider() -> PaymentProvider:
    from ..config import get_settings

    settings = get_settings()
    if settings.payment_provider == "mock":
        return MockPaymentProvider()
    # Real providers plug in here (integration boundary).
    return MockPaymentProvider()
