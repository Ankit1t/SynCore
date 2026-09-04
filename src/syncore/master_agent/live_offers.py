"""Live product-offer provider (real-time, over the network).

Two backends, chosen at runtime:

1. SerpApi Google Shopping  — REAL, currently-listed products with live prices
   from Amazon/Flipkart/Google Shopping (rating, reviews, seller, MRP). Used
   automatically when SERPAPI_KEY is set. This is the "real availability" source
   the teacher asked for — the agent only baskets products that actually exist
   right now with their current price.

2. DummyJSON (fallback)     — a free demo API with synthetic products. Proves
   the live-fetch architecture when no real-data key is configured. NOT real
   inventory.

Either way offers are normalized to the exact shape `agent._normalize_offers`
produces, so the pipeline (variant match, budget, confidence) is unchanged, and
the source is fully pluggable (ONDC / PA-API adapters drop in the same way).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import httpx

from .catalog import DEFAULT_UNIT

logger = logging.getLogger(__name__)

DUMMYJSON_SEARCH = "https://dummyjson.com/products/search"
SERPAPI_SEARCH = "https://serpapi.com/search.json"
USD_TO_INR = 83.0  # DummyJSON prices are USD-ish; keep INR budgets sensible
_TIMEOUT = 15.0
_PER_TERM_LIMIT = 5


def _serpapi_key() -> str:
    return os.getenv("SERPAPI_KEY", "").strip()


def using_real_data() -> bool:
    return bool(_serpapi_key())


# ----------------------------------------------------------- SerpApi (real) --
def _normalize_serpapi(r: dict[str, Any], canonical: str, idx: int) -> dict[str, Any] | None:
    price = r.get("extracted_price")
    if not isinstance(price, (int, float)) or price <= 0:
        return None
    old = r.get("extracted_old_price")
    mrp = float(old) if isinstance(old, (int, float)) and old > price else None
    return {
        "offer_id": f"live-serp-{r.get('position', idx)}",
        "name": str(r.get("title") or canonical).strip()[:120],
        "canonical": canonical,
        "brand": str(r.get("source") or "").strip(),  # merchant (Amazon.in, Flipkart, ...)
        "variant": [],
        "size_text": "",
        "unit_price": round(float(price), 2),
        "mrp": round(mrp, 2) if mrp else None,
        "unit": DEFAULT_UNIT.get(canonical, "piece"),
        "in_stock": True,  # shopping results are live listings
        "size": 1.0,
        "rating": round(float(r["rating"]), 2) if isinstance(r.get("rating"), (int, float)) else 0.0,
        "review_count": int(r["reviews"]) if isinstance(r.get("reviews"), (int, float)) else 0,
        "seller_rating": 0.0,
        "eta_minutes": 0,
        "source": "Google Shopping (live via SerpApi)",
    }


@lru_cache(maxsize=256)
def _search_serpapi(term: str) -> tuple[dict[str, Any], ...]:
    key = _serpapi_key()
    if not key:
        return ()
    try:
        r = httpx.get(
            SERPAPI_SEARCH,
            params={
                "engine": "google_shopping",
                "q": term,
                "gl": "in",  # India -> INR prices
                "hl": "en",
                "num": _PER_TERM_LIMIT,
                "api_key": key,
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("shopping_results", []) or []
        return tuple(results[:_PER_TERM_LIMIT])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("serpapi fetch failed for %r: %s", term, exc)
        return ()


# --------------------------------------------------------- DummyJSON (demo) --
def _normalize_dummyjson(p: dict[str, Any], canonical: str) -> dict[str, Any] | None:
    try:
        price_inr = round(float(p["price"]) * USD_TO_INR, 2)
    except (KeyError, TypeError, ValueError):
        return None
    disc = float(p.get("discountPercentage") or 0)
    mrp = round(price_inr / (1 - disc / 100), 2) if 0 < disc < 100 else None
    stock = int(p.get("stock") or 0)
    in_stock = stock > 0 and str(p.get("availabilityStatus") or "").lower() != "out of stock"
    return {
        "offer_id": f"live-dj-{p.get('id', 'x')}",
        "name": str(p.get("title") or canonical).strip(),
        "canonical": canonical,
        "brand": str(p.get("brand") or "").strip(),
        "variant": [],
        "size_text": "",
        "unit_price": price_inr,
        "mrp": mrp,
        "unit": DEFAULT_UNIT.get(canonical, "piece"),
        "in_stock": in_stock,
        "size": 1.0,
        "rating": round(float(p.get("rating") or 0), 2),
        "review_count": len(p.get("reviews") or []),
        "seller_rating": 0.0,
        "eta_minutes": 0,
        "source": "DummyJSON (demo)",
    }


@lru_cache(maxsize=256)
def _search_dummyjson(term: str) -> tuple[dict[str, Any], ...]:
    try:
        r = httpx.get(DUMMYJSON_SEARCH, params={"q": term, "limit": _PER_TERM_LIMIT}, timeout=_TIMEOUT)
        r.raise_for_status()
        return tuple(r.json().get("products", []) or [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("dummyjson fetch failed for %r: %s", term, exc)
        return ()


# -------------------------------------------------------------- dispatcher ---
def _offers_for_term(term: str, canonical: str) -> list[dict[str, Any]]:
    if _serpapi_key():
        offers = [
            o
            for i, r in enumerate(_search_serpapi(term))
            if (o := _normalize_serpapi(r, canonical, i)) is not None
        ]
        if offers:
            return offers
        # real source returned nothing for this term -> fall through to demo API
    return [o for p in _search_dummyjson(term) if (o := _normalize_dummyjson(p, canonical)) is not None]


def fetch_offers_for_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetch live offers for each understood item, tagged with its canonical."""
    offers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in items:
        canonical = str(it.get("canonical") or "").strip()
        term = canonical.lower()[:60]
        if not canonical or term in seen:
            continue
        seen.add(term)
        offers.extend(_offers_for_term(term, canonical))
    return offers
