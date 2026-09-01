"""Unit conversion and unit-price math."""

from __future__ import annotations

import pytest

from syncore.domain.enums import Unit
from syncore.domain.models import Quantity
from syncore.units import conversion


def test_kg_g_conversion():
    q = Quantity(value=1, unit=Unit.KG)
    assert conversion.to_base(q) == 1.0
    assert conversion.convert(q, Unit.G).value == 1000.0


def test_l_ml_conversion():
    q = Quantity(value=250, unit=Unit.ML)
    assert conversion.convert(q, Unit.L).value == pytest.approx(0.25)


def test_unit_price_examples():
    # ₹60 / 1kg = ₹60/kg ; ₹35 / 500g = ₹70/kg
    assert conversion.unit_price(60, Quantity(value=1, unit=Unit.KG)) == 60.0
    assert conversion.unit_price(35, Quantity(value=500, unit=Unit.G)) == 70.0


def test_cheaper_per_unit_is_detected():
    a = conversion.unit_price(60, Quantity(value=1, unit=Unit.KG))
    b = conversion.unit_price(35, Quantity(value=500, unit=Unit.G))
    assert a < b  # 60/kg cheaper than 70/kg


def test_packs_required():
    # need 1kg, offer is 500g -> 2 packs
    assert conversion.packs_required(
        Quantity(value=1, unit=Unit.KG), Quantity(value=500, unit=Unit.G)
    ) == 2
    # need 100g, offer is 250g -> 1 pack
    assert conversion.packs_required(
        Quantity(value=100, unit=Unit.G), Quantity(value=250, unit=Unit.G)
    ) == 1
    # need 2 pieces, offer 1 piece -> 2 packs
    assert conversion.packs_required(
        Quantity(value=2, unit=Unit.PIECE), Quantity(value=1, unit=Unit.PIECE)
    ) == 2


def test_incompatible_units_raise():
    from syncore.domain.errors import NormalizationError

    with pytest.raises(NormalizationError):
        conversion.convert(Quantity(value=1, unit=Unit.KG), Unit.L)
