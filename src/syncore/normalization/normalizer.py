"""Product normalization layer.

Turns messy marketplace titles into canonical products with normalized units
and quantities, and validates data quality. Different sites may say:
    "Potato 1 kg" / "Fresh Potato - 1000g" / "Fresh Aloo 1 Kilogram"
all of which normalize to canonical_name="potato", quantity=1kg.
"""

from __future__ import annotations

import re

from ..domain.enums import Unit
from ..domain.errors import NormalizationError
from ..domain.models import Product, Quantity
from . import lexicon

NORMALIZATION_VERSION = "1.0.0"

# Regex for quantity+unit tokens like "1kg", "1 kg", "500g", "1000 g", "1l", "250ml".
_QTY_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kilograms?|kilogram|kgs?|kg|grams?|gms?|gm|g|"
    r"litres?|liters?|litre|liter|lt|l|millilitres?|milliliters?|ml)\b",
    re.IGNORECASE,
)

# Count/pack tokens like "2 pack", "pack of 4", "x2", "2 packs".
_PACK_RE = re.compile(
    r"(?:pack\s*of\s*(?P<n1>\d+))|(?:(?P<n2>\d+)\s*(?:packs?|pcs?|pieces?|units?|nos?))|"
    r"(?:x\s*(?P<n3>\d+))",
    re.IGNORECASE,
)

_UNIT_ALIASES: dict[str, Unit] = {
    "kilogram": Unit.KG, "kilograms": Unit.KG, "kgs": Unit.KG, "kg": Unit.KG,
    "gram": Unit.G, "grams": Unit.G, "gms": Unit.G, "gm": Unit.G, "g": Unit.G,
    "litre": Unit.L, "litres": Unit.L, "liter": Unit.L, "liters": Unit.L, "lt": Unit.L, "l": Unit.L,
    "millilitre": Unit.ML, "milliliters": Unit.ML, "milliliter": Unit.ML,
    "millilitres": Unit.ML, "ml": Unit.ML,
}


def parse_unit(token: str) -> Unit:
    unit = _UNIT_ALIASES.get(token.strip().lower())
    if unit is None:
        raise NormalizationError(f"unknown unit token: {token!r}")
    return unit


def parse_quantity(text: str, *, count_based: bool = False) -> Quantity | None:
    """Extract a Quantity from free text.

    Prefers explicit weight/volume; falls back to pack/count for count-based
    products. Returns None if nothing usable is found.
    """
    text = text.strip()

    m = _QTY_RE.search(text)
    if m and not count_based:
        value = float(m.group("value"))
        unit = parse_unit(m.group("unit"))
        return Quantity(value=value, unit=unit)

    if count_based:
        # weight token still wins if present (e.g. "70g" on a Maggi pack), but
        # the *requested* quantity for count items is number of packs.
        p = _PACK_RE.search(text)
        if p:
            n = p.group("n1") or p.group("n2") or p.group("n3")
            if n:
                return Quantity(value=float(n), unit=Unit.PIECE)
        # bare leading integer, e.g. "2 Maggi"
        lead = re.match(r"\s*(\d+)\b", text)
        if lead:
            return Quantity(value=float(lead.group(1)), unit=Unit.PIECE)
        return Quantity(value=1, unit=Unit.PIECE)

    # count fallback for anything else
    p = _PACK_RE.search(text)
    if p:
        n = p.group("n1") or p.group("n2") or p.group("n3")
        if n:
            return Quantity(value=float(n), unit=Unit.PIECE)
    return None


def canonicalize_name(title: str) -> str | None:
    """Best-effort canonical name from a product title using the lexicon."""
    lowered = title.lower()
    # Longer aliases first to prefer "green chilli" over "chilli".
    for alias in sorted(lexicon.alias_index(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return lexicon.alias_index()[alias]
    return None


def detect_brand(title: str) -> str | None:
    lowered = title.lower()
    for token, brand in lexicon.KNOWN_BRANDS.items():
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return brand
    return None


def normalize_title(
    title: str,
    *,
    fallback_canonical: str | None = None,
    rating: float | None = None,
    review_count: int = 0,
    brand: str | None = None,
    attributes: dict | None = None,
) -> Product:
    """Normalize a raw marketplace title into a canonical Product."""
    canonical = canonicalize_name(title) or fallback_canonical
    if canonical is None:
        raise NormalizationError(f"could not canonicalize title: {title!r}")

    count_based = canonical in lexicon.COUNT_BASED
    quantity = parse_quantity(title, count_based=count_based)

    return Product(
        canonical_name=canonical,
        title=title.strip(),
        brand=brand or detect_brand(title),
        category=lexicon.CATEGORY.get(canonical, "grocery"),
        quantity=quantity,
        rating=rating,
        review_count=review_count,
        attributes=attributes or {},
    )
