"""Deterministic unit conversion.

Money and quantity math must never be delegated to an LLM. This module
converts between compatible units and computes canonical unit prices.

Canonical base units:
    mass   -> kg   (1 kg == 1000 g)
    volume -> l    (1 l  == 1000 ml)
    count  -> piece
"""

from __future__ import annotations

from ..domain.enums import Unit
from ..domain.errors import NormalizationError
from ..domain.models import Quantity

# Conversion factor to the canonical base unit of each dimension.
_TO_BASE: dict[Unit, tuple[str, float]] = {
    Unit.KG: ("mass", 1.0),
    Unit.G: ("mass", 0.001),
    Unit.L: ("volume", 1.0),
    Unit.ML: ("volume", 0.001),
    Unit.PIECE: ("count", 1.0),
}

_BASE_UNIT: dict[str, Unit] = {"mass": Unit.KG, "volume": Unit.L, "count": Unit.PIECE}


def dimension_of(unit: Unit) -> str:
    return _TO_BASE[unit][0]


def base_unit_of(unit: Unit) -> Unit:
    return _BASE_UNIT[dimension_of(unit)]


def to_base(quantity: Quantity) -> float:
    """Return the quantity expressed in its canonical base unit."""
    _dim, factor = _TO_BASE[quantity.unit]
    return quantity.value * factor


def compatible(a: Unit, b: Unit) -> bool:
    return dimension_of(a) == dimension_of(b)


def convert(quantity: Quantity, target: Unit) -> Quantity:
    """Convert a quantity to a compatible target unit."""
    if not compatible(quantity.unit, target):
        raise NormalizationError(
            f"incompatible units: {quantity.unit.value} -> {target.value}",
            details={"from": quantity.unit.value, "to": target.value},
        )
    base_value = to_base(quantity)
    _dim, target_factor = _TO_BASE[target]
    return Quantity(value=base_value / target_factor, unit=target)


def unit_price(total_price: float, quantity: Quantity) -> float:
    """Price per canonical base unit (e.g. INR per kg / per l / per piece).

    Example: (60, 1kg) -> 60.0 ; (35, 500g) -> 70.0
    """
    base_quantity = to_base(quantity)
    if base_quantity <= 0:
        raise NormalizationError("cannot compute unit price for non-positive quantity")
    return round(total_price / base_quantity, 4)


def packs_required(requested: Quantity, offer_quantity: Quantity) -> int:
    """How many offer units are needed to meet or exceed the requested quantity."""
    if not compatible(requested.unit, offer_quantity.unit):
        raise NormalizationError("incompatible units when computing packs")
    req_base = to_base(requested)
    off_base = to_base(offer_quantity)
    if off_base <= 0:
        raise NormalizationError("offer quantity must be positive")
    import math

    return max(1, math.ceil(round(req_base / off_base, 6)))
