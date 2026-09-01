"""Normalization + data-quality tests."""

from __future__ import annotations

from syncore.domain.enums import Availability, Unit
from syncore.domain.models import Offer, Product, Quantity, Seller
from syncore.normalization.normalizer import (
    canonicalize_name,
    normalize_title,
    parse_quantity,
)
from syncore.normalization.quality import validate_offer


def test_canonicalize_variants():
    assert canonicalize_name("Fresh Potato - 1000g") == "potato"
    assert canonicalize_name("Fresh Aloo 1 Kilogram") == "potato"
    assert canonicalize_name("Hari Mirch 100g") == "green chilli"
    # longest alias wins: "green chilli" over "chilli"
    assert canonicalize_name("Green Chilli 250g") == "green chilli"


def test_parse_quantity_weight():
    q = parse_quantity("Fresh Potato 1000g")
    assert q.unit == Unit.G and q.value == 1000


def test_parse_quantity_count():
    q = parse_quantity("Maggi Pack of 4", count_based=True)
    assert q.unit == Unit.PIECE and q.value == 4


def test_normalize_title_builds_product():
    p = normalize_title("Fresh Aloo 1 Kilogram", rating=4.2, review_count=100)
    assert p.canonical_name == "potato"
    assert p.quantity.unit == Unit.KG and p.quantity.value == 1


def _offer(price=10.0, mrp=12.0, rating=4.0, qty=Quantity(value=1, unit=Unit.KG)):
    product = Product(canonical_name="potato", title="Potato 1kg", rating=rating, quantity=qty)
    return Offer(product=product, seller=Seller(name="s"), marketplace="m",
                 source_product_id="m:potato:0", price=price, mrp=mrp, quantity=qty,
                 availability=Availability.IN_STOCK)


def test_valid_offer_passes():
    result = validate_offer(_offer())
    assert result.ok and not result.issues


def test_price_above_mrp_flagged():
    result = validate_offer(_offer(price=20.0, mrp=12.0))
    assert "price exceeds MRP" in result.issues
    assert result.confidence < 1.0


def test_negative_price_rejected():
    result = validate_offer(_offer(price=-1))
    assert not result.ok
