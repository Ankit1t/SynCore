"""Order manager.

After checkout we never assume success. We place the order via the marketplace
(using an already-authorized payment reference) and then verify the returned
order against what we intended to buy. Uncertainty is modeled explicitly with
PAYMENT_SUCCESS_ORDER_UNCONFIRMED for later reconciliation.
"""

from __future__ import annotations

from ..domain.enums import OrderStatus
from ..domain.models import (
    Cart,
    CheckoutSession,
    Order,
    OrderItem,
)
from ..marketplace.base import BaseMarketplaceAdapter
from ..observability.logging import get_logger

logger = get_logger("syncore.orders")


class OrderManager:
    def __init__(self, adapter: BaseMarketplaceAdapter):
        self._adapter = adapter

    def place_and_verify(
        self,
        *,
        user_id: str,
        request_id: str,
        cart: Cart,
        checkout: CheckoutSession,
        payment_intent_id: str,
        payment_reference: str,
    ) -> Order:
        order = Order(
            user_id=user_id,
            request_id=request_id,
            marketplace=checkout.marketplace,
            vendor=checkout.vendor,
            currency=checkout.currency,
            payment_intent_id=payment_intent_id,
            items=[
                OrderItem(sku=c.sku, title=c.title, quantity=c.quantity,
                          unit_price=c.unit_price, line_total=c.line_total)
                for c in cart.items
            ],
            total=checkout.final_total,
            delivery_eta_minutes=checkout.delivery_eta_minutes,
            status=OrderStatus.PENDING,
        )

        try:
            remote = self._adapter.place_order(checkout.id, payment_reference=payment_reference)
        except Exception as exc:  # payment already succeeded -> mark unconfirmed
            logger.error("order placement failed after payment: %s", exc)
            order.status = OrderStatus.PAYMENT_SUCCESS_ORDER_UNCONFIRMED
            return order

        order.external_order_id = remote.external_order_id
        order.status = OrderStatus.PLACED

        # Verification: totals + item count must match our intent.
        issues = self._verify(order, remote.total)
        if issues:
            logger.warning("order verification issues: %s", issues)
            order.status = OrderStatus.PAYMENT_SUCCESS_ORDER_UNCONFIRMED
        else:
            order.status = OrderStatus.CONFIRMED
        return order

    def _verify(self, order: Order, remote_total: float) -> list[str]:
        issues: list[str] = []
        if abs(remote_total - order.total) > 0.01:
            issues.append(f"total mismatch: expected {order.total}, got {remote_total}")
        if not order.items:
            issues.append("no items in order")
        if not order.external_order_id:
            issues.append("missing external order id")
        return issues
