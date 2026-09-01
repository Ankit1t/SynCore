"""Order verification + receipt generation (Blueprint STEP 23/24/55).

Payment success does NOT imply order success. The order is verified separately;
a receipt is assembled only from verified structured records (never from LLM
assumptions). Payment-success-with-order-failure routes to refund.
"""

from __future__ import annotations

from ..domain.enums import OrderStatus, PaymentTxnState
from .models import Cart, PaymentTransaction, Receipt


def verify_order(*, cart: Cart, txn: PaymentTransaction, merchant_confirmed: bool) -> OrderStatus:
    """Separate payment truth from order truth."""
    if txn.state not in (PaymentTxnState.SETTLED,):
        return OrderStatus.FAILED
    if not merchant_confirmed:
        # money moved but order not confirmed -> needs reconciliation / refund
        return OrderStatus.PAYMENT_SUCCESS_ORDER_UNCONFIRMED
    return OrderStatus.CONFIRMED


def build_receipt(*, cart: Cart, txn: PaymentTransaction, order_status: OrderStatus,
                  order_id: str | None) -> Receipt:
    payment_status = txn.state.value if txn else "NONE"
    fees = cart.platform_fee_paise + cart.handling_fee_paise
    return Receipt(
        order_id=order_id,
        merchant_id=cart.merchant_id,
        lines=cart.lines,
        subtotal_paise=cart.subtotal_paise,
        delivery_paise=cart.delivery_paise,
        fees_paise=fees,
        tax_paise=cart.tax_paise,
        discount_paise=cart.discount_paise,
        final_total_paise=cart.final_total_paise,
        currency=cart.currency,
        payment_status=payment_status,
        payment_reference=txn.provider_ref if txn else None,
        order_status=order_status.value,
        cart_hash=cart.cart_hash,
    )
