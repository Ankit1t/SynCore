"""Explainable hybrid ranking engine.

score = semantic*w_s + lexical*w_l + quantity*w_q + category*w_c
        + brand*w_b + quality*w_qual

Weights are configurable (RankingWeights). Every ranked offer carries a
breakdown and human-readable reasons so recommendations are explainable
without exposing hidden chain-of-thought.
"""

from __future__ import annotations

import re

from ..config import RankingWeights, get_settings
from ..domain.models import Offer, Quantity, RankedOffer, SearchQuery
from ..llm.provider import LLMProvider, get_provider
from ..units import conversion


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    return max(0.0, min(1.0, dot))  # inputs are already unit-normalized


def _lexical(query_tokens: set[str], title_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & title_tokens)
    return overlap / len(query_tokens)


def _quantity_match(target: Quantity, offer_qty: Quantity) -> tuple[float, str]:
    if not conversion.compatible(target.unit, offer_qty.unit):
        return 0.2, "different measure type than requested"
    req_base = conversion.to_base(target)
    off_base = conversion.to_base(offer_qty)
    packs = conversion.packs_required(target, offer_qty)
    supplied = packs * off_base
    overshoot = (supplied - req_base) / req_base if req_base else 0.0
    score = 1.0 / (1.0 + max(0.0, overshoot))
    if overshoot <= 0.001:
        note = "quantity matches request exactly"
    else:
        note = f"needs {packs} pack(s); {overshoot*100:.0f}% over requested amount"
    return round(score, 4), note


def _category_match(expected_canonical: str, offer: Offer) -> float:
    if offer.product.canonical_name == expected_canonical:
        return 1.0
    if offer.product.category == "grocery":
        return 0.5
    return 0.2


def _brand_match(preference: str | None, offer: Offer) -> tuple[float, str | None]:
    if not preference:
        return 0.7, None
    brand = (offer.product.brand or "").lower()
    if preference.lower() in brand or brand in preference.lower():
        return 1.0, f"matches preferred brand {offer.product.brand}"
    return 0.2, f"brand {offer.product.brand or 'unknown'} != preferred {preference}"


def _quality_score(offer: Offer) -> float:
    rating = offer.product.rating or 0.0
    reviews = offer.product.review_count or 0
    review_conf = min(reviews / 5000.0, 1.0)
    seller = offer.seller.reliability
    return round((rating / 5.0) * 0.6 + review_conf * 0.2 + seller * 0.2, 4)


class RankingEngine:
    def __init__(self, provider: LLMProvider | None = None, weights: RankingWeights | None = None):
        self._provider = provider or get_provider()
        self._weights = (weights or get_settings().ranking_weights).normalized()

    def rank(self, query: SearchQuery, offers: list[Offer]) -> list[RankedOffer]:
        ranked: list[RankedOffer] = []
        q_emb = self._provider.embed(f"{query.text} {query.canonical_name}")
        q_tokens = set(_tokenize(f"{query.text} {query.canonical_name}"))
        w = self._weights

        for offer in offers:
            title = offer.product.title
            t_emb = self._provider.embed(title)
            semantic = _cosine(q_emb, t_emb)
            lexical = _lexical(q_tokens, set(_tokenize(title)))
            quantity, qty_note = _quantity_match(query.target_quantity, offer.quantity)
            category = _category_match(query.canonical_name, offer)
            brand, brand_note = _brand_match(query.brand_preference, offer)
            quality = _quality_score(offer)

            breakdown = {
                "semantic": round(semantic * w.semantic, 4),
                "lexical": round(lexical * w.lexical, 4),
                "quantity": round(quantity * w.quantity, 4),
                "category": round(category * w.category, 4),
                "brand": round(brand * w.brand, 4),
                "quality": round(quality * w.quality, 4),
            }
            score = round(sum(breakdown.values()), 4)

            try:
                up = conversion.unit_price(offer.effective_price, offer.quantity)
            except Exception:
                up = offer.effective_price

            reasons = [
                f"unit price ~₹{up:g}/{conversion.base_unit_of(offer.quantity.unit).value}",
                qty_note,
            ]
            if offer.product.rating:
                reasons.append(f"rating {offer.product.rating} ({offer.product.review_count} reviews)")
            if brand_note:
                reasons.append(brand_note)

            ranked.append(
                RankedOffer(
                    offer=offer,
                    score=score,
                    unit_price=up,
                    reasons=reasons,
                    score_breakdown=breakdown,
                )
            )

        ranked.sort(key=lambda r: (r.score, -r.unit_price), reverse=True)
        return ranked
