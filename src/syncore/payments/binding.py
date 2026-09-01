"""Transaction binding (Blueprint STEP 10/19).

Deterministic cart canonicalization + SHA-256 cart_hash so an authorization is
bound to exactly one transaction. If amount, merchant, category, quantities or
line prices change, the hash changes and authorization must fail.
"""

from __future__ import annotations

import hashlib
import json

from ..domain.money import line_total_paise, sum_paise
from .models import Cart, CartLine


def canonical_cart_payload(cart: Cart) -> dict:
    return {
        "merchant_id": cart.merchant_id,
        "merchant_category": cart.merchant_category,
        "currency": cart.currency,
        "final_total_paise": cart.final_total_paise,
        "lines": sorted(
            [
                {"sku": ln.sku, "quantity": ln.quantity, "unit_price_paise": ln.unit_price_paise}
                for ln in cart.lines
            ],
            key=lambda x: x["sku"],
        ),
    }


def compute_cart_hash(cart: Cart) -> str:
    payload = json.dumps(canonical_cart_payload(cart), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def price_cart(
    *,
    merchant_id: str,
    merchant_category: str,
    lines: list[CartLine],
    delivery_paise: int = 0,
    platform_fee_paise: int = 0,
    handling_fee_paise: int = 0,
    tax_paise: int = 0,
    discount_paise: int = 0,
    currency: str = "INR",
) -> Cart:
    """Build a fully-priced cart with exact integer math + cart_hash.

    Budget decisions must use `final_total_paise` (subtotal + fees + tax -
    discount), never the subtotal (STEP 8).
    """
    for ln in lines:
        expected = line_total_paise(ln.unit_price_paise, ln.quantity)
        if ln.line_total_paise != expected:
            raise ValueError(f"line math mismatch for {ln.sku}: {ln.line_total_paise} != {expected}")

    subtotal = sum_paise([ln.line_total_paise for ln in lines])
    final_total = subtotal + delivery_paise + platform_fee_paise + handling_fee_paise + tax_paise - discount_paise
    cart = Cart(
        merchant_id=merchant_id, merchant_category=merchant_category, currency=currency,
        lines=lines, subtotal_paise=subtotal, delivery_paise=delivery_paise,
        platform_fee_paise=platform_fee_paise, handling_fee_paise=handling_fee_paise,
        tax_paise=tax_paise, discount_paise=discount_paise, final_total_paise=final_total,
    )
    cart.cart_hash = compute_cart_hash(cart)
    return cart
