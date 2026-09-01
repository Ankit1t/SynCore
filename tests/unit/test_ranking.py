"""Ranking engine tests."""

from __future__ import annotations

from syncore.domain.enums import Unit
from syncore.domain.models import Quantity, SearchQuery
from syncore.marketplace.mock import MockMarketplace
from syncore.search.ranking import RankingEngine


def _query(canonical, qty):
    return SearchQuery(item_id="i1", text=canonical, canonical_name=canonical, target_quantity=qty)


def test_ranks_matching_quantity_first():
    mp = MockMarketplace("mock-bazaar")
    offers = mp.search_products("potato")
    q = _query("potato", Quantity(value=1, unit=Unit.KG))
    ranked = RankingEngine().rank(q, offers)
    assert ranked
    # top offer should be a potato with a competitive score and a unit price
    top = ranked[0]
    assert top.offer.product.canonical_name == "potato"
    assert top.unit_price > 0
    assert "unit price" in top.reasons[0]


def test_maggi_noodles_ranks_above_seasoning():
    mp = MockMarketplace("mock-bazaar")
    offers = mp.search_products("maggi")
    q = _query("maggi", Quantity(value=2, unit=Unit.PIECE))
    ranked = RankingEngine().rank(q, offers)
    titles = [r.offer.product.title for r in ranked]
    noodles_idx = next(i for i, t in enumerate(titles) if "Noodles" in t and "Seasoning" not in t)
    seasoning_idx = next(i for i, t in enumerate(titles) if "Seasoning" in t)
    assert noodles_idx < seasoning_idx


def test_score_breakdown_present():
    mp = MockMarketplace("mock-bazaar")
    offers = mp.search_products("onion")
    ranked = RankingEngine().rank(_query("onion", Quantity(value=1, unit=Unit.KG)), offers)
    assert set(ranked[0].score_breakdown) == {
        "semantic", "lexical", "quantity", "category", "brand", "quality"
    }
