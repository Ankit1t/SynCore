"""Event bus abstraction.

The MVP uses an in-process bus. The interface (publish/subscribe) is
deliberately small so it can be backed by Redis Streams or Kafka later without
touching producers/consumers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

Handler = Callable[["Event"], None]


@dataclass
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    def publish(self, event: Event) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def subscribe(self, name: str, handler: Handler) -> None:  # pragma: no cover
        raise NotImplementedError


class InMemoryEventBus(EventBus):
    def __init__(self) -> None:
        self._subs: dict[str, list[Handler]] = {}
        self._wildcard: list[Handler] = []
        self.log: list[Event] = []

    def publish(self, event: Event) -> None:
        self.log.append(event)
        for handler in self._subs.get(event.name, []):
            handler(event)
        for handler in self._wildcard:
            handler(event)

    def subscribe(self, name: str, handler: Handler) -> None:
        if name == "*":
            self._wildcard.append(handler)
        else:
            self._subs.setdefault(name, []).append(handler)


# Well-known event names (spec section 25).
class Events:
    SHOPPING_REQUEST_CREATED = "ShoppingRequestCreated"
    INTENT_PARSED = "IntentParsed"
    PLAN_CREATED = "PlanCreated"
    SEARCH_STARTED = "SearchStarted"
    PRODUCTS_DISCOVERED = "ProductsDiscovered"
    PRODUCTS_NORMALIZED = "ProductsNormalized"
    PRODUCTS_RANKED = "ProductsRanked"
    BASKET_OPTIMIZED = "BasketOptimized"
    BUDGET_VERIFIED = "BudgetVerified"
    CART_BUILD_STARTED = "CartBuildStarted"
    CART_VERIFIED = "CartVerified"
    CHECKOUT_STARTED = "CheckoutStarted"
    PAYMENT_AUTH_REQUIRED = "PaymentAuthorizationRequired"
    PAYMENT_SUCCEEDED = "PaymentSucceeded"
    PAYMENT_FAILED = "PaymentFailed"
    ORDER_PLACED = "OrderPlaced"
    ORDER_VERIFIED = "OrderVerificationCompleted"
    AGENT_STATE_CHANGED = "AgentStateChanged"
    AGENT_FAILED = "AgentFailed"
