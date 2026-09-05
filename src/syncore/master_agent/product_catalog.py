"""Loader for the curated seed product catalog.

This is a static, curated dataset (no live scraping) that gives the agent a
pool of REAL products — with brand, variant, size, MRP, rating and delivery
ETA — to match requests against. When an item has no catalog match, the agent
falls back to a flagged market estimate.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_SEED_PATH = Path(__file__).with_name("catalog_seed.json")


@lru_cache(maxsize=1)
def load_catalog() -> list[dict[str, Any]]:
    """Return the seed products as a list of offer dicts (cached)."""
    try:
        data = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    products = data.get("products") if isinstance(data, dict) else None
    return products if isinstance(products, list) else []


def catalog_offers() -> list[dict[str, Any]]:
    """A fresh shallow copy of the catalog offers (safe for callers to mutate)."""
    return [dict(p) for p in load_catalog()]


@lru_cache(maxsize=1)
def _by_offer_id() -> dict[str, dict[str, Any]]:
    return {str(p.get("offer_id")): p for p in load_catalog()}


def get_detail(offer_id: str) -> dict[str, Any] | None:
    """Full product record (images, highlights, specifications, ...) by id."""
    return _by_offer_id().get(offer_id)
