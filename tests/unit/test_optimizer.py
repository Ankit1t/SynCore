"""Basket optimizer tests: basket-level economics + budget enforcement."""

from __future__ import annotations

from syncore.domain.enums import OptimizationObjective, Unit
from syncore.domain.models import (
    BudgetPolicy,
    Quantity,
    SearchQuery,
    ShoppingItem,
    ShoppingPolicy,
    ShoppingRequest,
)
from syncore.marketplace.mock import build_default_registry
from syncore.marketplace.registry import MarketplaceRegistry
from syncore.optimizer.basket import BasketOptimizer
from syncore.search.ranking import RankingEngine


def _registry() -> MarketplaceRegistry:
    reg = MarketplaceRegistry()
    for a in build_default_registry():
        reg.register(a)
    return reg


def _request(items, budget=500.0, objective=OptimizationObjective.BEST_VALUE):
    return ShoppingRequest(
        user_id="u", raw_text="t", items=items, budget=BudgetPolicy(limit=budget),
        policy=ShoppingPolicy(objective=objective),
    )


def _rank(reg, request):
    ranking = RankingEngine()
    ranked = {}
    for item in request.items:
        offers = []
        for adapter in reg.healthy_adapters():
            offers.extend(adapter.search_products(item.canonical_name))
        q = SearchQuery(item_id=item.id, text=item.canonical_name,
                        canonical_name=item.canonical_name,
                        target_quantity=item.requested_quantity)
        ranked[item.id] = ranking.rank(q, offers)
    return ranked


def _items():
    return [
        ShoppingItem(raw_text="1kg aloo", canonical_name="potato",
                     requested_quantity=Quantity(value=1, unit=Unit.KG)),
        ShoppingItem(raw_text="100g mirch", canonical_name="green chilli",
                     requested_quantity=Quantity(value=100, unit=Unit.G)),
        ShoppingItem(raw_text="2 maggi", canonical_name="maggi",
                     requested_quantity=Quantity(value=2, unit=Unit.PIECE)),
    ]


def test_basket_fits_budget_and_has_all_items():
    reg = _registry()
    request = _request(_items(), budget=500.0)
    basket = BasketOptimizer(reg).optimize(request, _rank(reg, request))
    assert basket.within_budget
    assert basket.total <= 500.0
    assert {i.canonical_name for i in basket.items} == {"potato", "green chilli", "maggi"}


def test_basket_level_delivery_economics():
    """The optimizer must account for delivery/platform fees, not just item prices."""
    reg = _registry()
    request = _request(_items(), budget=500.0)
    basket = BasketOptimizer(reg).optimize(request, _rank(reg, request))
    # total must equal items + delivery + platform - discount
    expected = round(basket.items_subtotal + basket.delivery_fee + basket.platform_fee
                     - basket.discount, 2)
    assert basket.total == expected
    # explanation should compare both marketplaces
    joined = " ".join(basket.explanation)
    assert "mock-bazaar" in joined and "mock-fresh" in joined


def test_hard_budget_not_exceeded_marks_review():
    reg = _registry()
    # rice + 2 maggi can't fit in ₹100
    items = [
        ShoppingItem(raw_text="1kg rice", canonical_name="rice",
                     requested_quantity=Quantity(value=1, unit=Unit.KG)),
        ShoppingItem(raw_text="2 maggi", canonical_name="maggi",
                     requested_quantity=Quantity(value=2, unit=Unit.PIECE)),
    ]
    request = _request(items, budget=100.0)
    basket = BasketOptimizer(reg).optimize(request, _rank(reg, request))
    assert not basket.within_budget  # never silently exceed a hard budget
