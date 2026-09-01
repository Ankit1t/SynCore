"""Intent parser tests, including the Hinglish target scenario."""

from __future__ import annotations

import pytest

from syncore.domain.enums import Unit
from syncore.domain.errors import IntentParseError
from syncore.intent.parser import parse_request


def test_target_scenario():
    r = parse_request("₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar.", user_id="u")
    assert r.budget.limit == 500.0
    names = {i.canonical_name for i in r.items}
    assert names == {"potato", "green chilli", "maggi"}

    by_name = {i.canonical_name: i for i in r.items}
    assert by_name["potato"].requested_quantity.unit == Unit.KG
    assert by_name["potato"].requested_quantity.value == 1
    assert by_name["green chilli"].requested_quantity.value == 100
    assert by_name["green chilli"].requested_quantity.unit == Unit.G
    assert by_name["maggi"].requested_quantity.unit == Unit.PIECE
    assert by_name["maggi"].requested_quantity.value == 2


@pytest.mark.parametrize(
    "text,expected",
    [
        ("order 2 maggi and 1kg rice under 100", 100.0),   # bare amount after hint
        ("buy 1kg aloo below 250", 250.0),
        ("1kg aloo under rs 300", 300.0),
        ("500 ke andar 2 maggi", 500.0),                    # amount before postposition
        ("₹750 budget me 1kg onion", 750.0),
        ("1kg aloo aur 2 maggi", None),                     # no budget stated
    ],
)
def test_budget_parsing(text, expected):
    r = parse_request(text, user_id="u")
    assert r.budget.limit == expected


def test_dinner_multi_item():
    r = parse_request(
        "₹500 ke andar dinner ke liye 1kg aloo, 500g onion, 100g green chilli aur 2 Maggi order kar.",
        user_id="u",
    )
    names = {i.canonical_name for i in r.items}
    assert names == {"potato", "onion", "green chilli", "maggi"}


def test_empty_request_raises():
    with pytest.raises(IntentParseError):
        parse_request("   ", user_id="u")


def test_no_items_raises():
    with pytest.raises(IntentParseError):
        parse_request("hello there under 500", user_id="u")
