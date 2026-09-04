"""Live product-offer provider.

Fetches REAL product offers at request time from a public live API
(DummyJSON — https://dummyjson.com) instead of a bundled catalog. This proves
the agent works on data pulled dynamically over the network, not a hard-coded
list. The provider is fault-tolerant: any network/parse error yields no offers
for that term, and the agent falls back to its catalog / market estimate.

Offers are normalized to the exact shape `agent._normalize_offers` produces, so
the rest of the pipeline (variant match, budget, confidence) is unchanged.

The source is pluggable — swap DummyJSON for an ONDC / retailer / PA-API feed
without touching the agent.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx

from .catalog import DEFAULT_UNIT

logger = logging.getLogger(__name__)

DUMMYJSON_SEARCH = "https://dummyjson.com/products/search"
USD_TO_INR = 83.0  # approximate; keeps INR budgets sensible for the demo
_TIMEOUT = 12.0
_PER_TERM_LIMIT = 5


def _to_inr(usd: float) -> float:
    return round(float(usd) * USD_TO_INR, 2)


def _normalize_product(p: dict[str, Any], canonical: str) -> dict[str, Any] | None:
    """Map one DummyJSON product to the agent's offer schema."""
    try:
        price_inr = _to_inr(p["price"])
    except (KeyError, TypeError, ValueError):
        return None
    disc = float(p.get("discountPercentage") or 0)
    mrp = round(price_inr / (1 - disc / 100), 2) if 0 < disc < 100 else None
    stock = int(p.get("stock") or 0)
    status = str(p.get("availabilityStatus") or "").lower()
    in_stock = stock > 0 and status != "out of stock"
    reviews = p.get("reviews") or []
    brand = str(p.get("brand") or "").strip()
    title = str(p.get("title") or canonical).strip()
    return {
        "offer_id": f"live-dj-{p.get('id', 'x')}",
        "name": title,
        "canonical": canonical,
        "brand": brand,
        "variant": [],
        "size_text": "",
        "unit_price": price_inr,
        "mrp": mrp,
        "unit": DEFAULT_UNIT.get(canonical, "piece"),
        "in_stock": in_stock,
        "size": 1.0,
        "rating": round(float(p.get("rating") or 0), 2),
        "review_count": len(reviews),
        "seller_rating": 0.0,
        "eta_minutes": 0,
        "source": "DummyJSON (live)",
    }


@lru_cache(maxsize=256)
def _search_term(term: str) -> tuple[dict[str, Any], ...]:
    """Raw DummyJSON search for a term (cached per process)."""
    try:
        r = httpx.get(
            DUMMYJSON_SEARCH,
            params={"q": term, "limit": _PER_TERM_LIMIT},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        products = r.json().get("products", []) or []
        return tuple(products)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("live offers fetch failed for %r: %s", term, exc)
        return ()


def fetch_offers_for_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch live offers for each understood item, tagged with its canonical."""
    offers: list[dict[str, Any]] = []
    seen_terms: set[str] = set()
    for it in items:
        canonical = str(it.get("canonical") or "").strip()
        # Search by the clean canonical (avoids filler like "buy"/"get" in raw).
        term = canonical.lower()[:40]
        if not canonical or term in seen_terms:
            continue
        seen_terms.add(term)
        for p in _search_term(term):
            offer = _normalize_product(p, canonical)
            if offer is not None:
                offers.append(offer)
    return offers
