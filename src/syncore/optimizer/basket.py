"""Basket optimizer.

Chooses the best combination of offers for a shopping request, reasoning at the
BASKET level (delivery fees, coupons, platform fees), not per product in
isolation. Supports multiple objectives and enforces hard budgets by
re-optimizing / dropping optional items before giving up.

This is deterministic code by design (see spec sections 6 & 15).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.enums import Availability, OptimizationObjective
from ..domain.models import (
    Basket,
    BasketItem,
    RankedOffer,
    ShoppingItem,
    ShoppingRequest,
)
from ..marketplace.registry import MarketplaceRegistry
from ..budget.engine import check_budget
from ..units import conversion


@dataclass
class _Selection:
    item: ShoppingItem
    ranked: RankedOffer
    packs: int
    line_total: float


@dataclass
class _MarketBasket:
    marketplace: str
    selections: list[_Selection] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    items_subtotal: float = 0.0
    delivery_fee: float = 0.0
    platform_fee: float = 0.0
    discount: float = 0.0
    total: float = 0.0

    @property
    def filled(self) -> int:
        return len(self.selections)

    @property
    def avg_rating(self) -> float:
        ratings = [s.ranked.offer.product.rating or 0.0 for s in self.selections]
        return round(sum(ratings) / len(ratings), 3) if ratings else 0.0

    @property
    def max_eta(self) -> int:
        etas = [s.ranked.offer.delivery_eta_minutes or 0 for s in self.selections]
        return max(etas) if etas else 0


class BasketOptimizer:
    def __init__(self, registry: MarketplaceRegistry):
        self._registry = registry

    # ------------------------------------------------------------------ #
    def optimize(
        self,
        request: ShoppingRequest,
        ranked_by_item: dict[str, list[RankedOffer]],
    ) -> Basket:
        objective = request.policy.objective
        min_rating = request.policy.minimum_rating
        marketplaces = self._marketplaces_present(ranked_by_item)

        # 1) Build a candidate basket per marketplace under the chosen objective.
        candidates = [
            self._build(m, request.items, ranked_by_item, objective, min_rating)
            for m in marketplaces
        ]
        best = self._choose(candidates, objective, request.items)
        explanation = self._compare_explanation(candidates, best, objective)

        # 2) Enforce hard budget with recovery.
        within_budget, best, budget_notes = self._enforce_budget(
            request, best, candidates, ranked_by_item, min_rating
        )
        explanation.extend(budget_notes)

        return self._to_basket(request, best, objective, within_budget, explanation)

    # ------------------------------------------------------------------ #
    def _marketplaces_present(self, ranked_by_item: dict[str, list[RankedOffer]]) -> list[str]:
        seen: list[str] = []
        for ranked in ranked_by_item.values():
            for r in ranked:
                if r.offer.marketplace not in seen:
                    seen.append(r.offer.marketplace)
        return seen

    def _candidates_for(
        self, item: ShoppingItem, marketplace: str, ranked_by_item: dict[str, list[RankedOffer]],
        min_rating: float,
    ) -> list[RankedOffer]:
        out: list[RankedOffer] = []
        for r in ranked_by_item.get(item.id, []):
            o = r.offer
            if o.marketplace != marketplace:
                continue
            if o.availability != Availability.IN_STOCK:
                continue
            if (o.product.rating or 0.0) < max(min_rating, item.minimum_rating or 0.0):
                continue
            if not conversion.compatible(item.requested_quantity.unit, o.quantity.unit):
                continue
            out.append(r)
        return out

    def _select_offer(
        self, item: ShoppingItem, candidates: list[RankedOffer],
        objective: OptimizationObjective,
    ) -> _Selection | None:
        best: _Selection | None = None
        for r in candidates:
            packs = conversion.packs_required(item.requested_quantity, r.offer.quantity)
            line_total = round(packs * r.offer.effective_price, 2)
            sel = _Selection(item=item, ranked=r, packs=packs, line_total=line_total)
            if best is None or self._better_selection(sel, best, objective):
                best = sel
        return best

    def _better_selection(
        self, a: _Selection, b: _Selection, objective: OptimizationObjective
    ) -> bool:
        if objective == OptimizationObjective.CHEAPEST:
            return a.line_total < b.line_total
        if objective == OptimizationObjective.BEST_QUALITY:
            ra, rb = a.ranked.offer.product.rating or 0, b.ranked.offer.product.rating or 0
            if ra != rb:
                return ra > rb
            return a.line_total < b.line_total
        if objective == OptimizationObjective.FASTEST:
            ea = a.ranked.offer.delivery_eta_minutes or 10**9
            eb = b.ranked.offer.delivery_eta_minutes or 10**9
            if ea != eb:
                return ea < eb
            return a.line_total < b.line_total
        # BEST_VALUE / BALANCED -> ranking score, tie-break cheaper
        if a.ranked.score != b.ranked.score:
            return a.ranked.score > b.ranked.score
        return a.line_total < b.line_total

    def _build(
        self, marketplace: str, items: list[ShoppingItem],
        ranked_by_item: dict[str, list[RankedOffer]], objective: OptimizationObjective,
        min_rating: float,
    ) -> _MarketBasket:
        mb = _MarketBasket(marketplace=marketplace)
        for item in items:
            candidates = self._candidates_for(item, marketplace, ranked_by_item, min_rating)
            sel = self._select_offer(item, candidates, objective)
            if sel is None:
                if not item.optional:
                    mb.missing.append(item.canonical_name)
                continue
            mb.selections.append(sel)
        self._price(mb)
        return mb

    def _price(self, mb: _MarketBasket) -> None:
        mb.items_subtotal = round(sum(s.line_total for s in mb.selections), 2)
        try:
            fees = self._registry.get(mb.marketplace).estimate_fees(mb.items_subtotal)
        except Exception:
            from ..marketplace.base import Fees

            fees = Fees()
        mb.delivery_fee = fees.delivery_fee
        mb.platform_fee = fees.platform_fee
        mb.discount = fees.discount
        mb.total = round(mb.items_subtotal + mb.delivery_fee + mb.platform_fee - mb.discount, 2)

    def _choose(
        self, candidates: list[_MarketBasket], objective: OptimizationObjective,
        items: list[ShoppingItem],
    ) -> _MarketBasket:
        required = {i.canonical_name for i in items if not i.optional}
        complete = [c for c in candidates if not (required & set(c.missing)) and c.selections]
        pool = complete or [c for c in candidates if c.selections] or candidates

        def key(mb: _MarketBasket):
            if objective == OptimizationObjective.FASTEST:
                return (mb.max_eta, mb.total)
            if objective == OptimizationObjective.BEST_QUALITY:
                return (-mb.avg_rating, mb.total)
            return (mb.total, -mb.filled)

        # Prefer more-filled baskets first, then objective.
        pool.sort(key=lambda mb: (-mb.filled, *(_as_tuple(key(mb)))))
        return pool[0]

    def _enforce_budget(
        self, request: ShoppingRequest, best: _MarketBasket,
        candidates: list[_MarketBasket], ranked_by_item: dict[str, list[RankedOffer]],
        min_rating: float,
    ) -> tuple[bool, _MarketBasket, list[str]]:
        notes: list[str] = []
        verdict = check_budget(best.total, request.budget)
        if verdict.ok:
            return True, best, notes

        notes.append(
            f"Best-value basket ₹{best.total:g} exceeds budget ₹{request.budget.limit:g}; re-optimizing for cost."
        )
        # Recovery 1: re-optimize every marketplace for CHEAPEST, pick min total.
        cheapest_candidates = [
            self._build(m.marketplace, request.items, ranked_by_item,
                        OptimizationObjective.CHEAPEST, min_rating)
            for m in candidates
        ]
        required = {i.canonical_name for i in request.items if not i.optional}
        complete = [c for c in cheapest_candidates if not (required & set(c.missing)) and c.selections]
        pool = complete or cheapest_candidates
        pool.sort(key=lambda mb: mb.total)
        cheapest = pool[0]
        if check_budget(cheapest.total, request.budget).ok:
            notes.append(f"Switched to cheapest offers: new total ₹{cheapest.total:g} fits the budget.")
            return True, cheapest, notes

        # Recovery 2: drop optional items from the cheapest basket.
        optional_names = {i.canonical_name for i in request.items if i.optional}
        if optional_names:
            trimmed = _MarketBasket(marketplace=cheapest.marketplace)
            trimmed.selections = [
                s for s in cheapest.selections if s.item.canonical_name not in optional_names
            ]
            trimmed.missing = cheapest.missing
            self._price(trimmed)
            if check_budget(trimmed.total, request.budget).ok:
                notes.append("Dropped optional items to fit the budget.")
                return True, trimmed, notes

        notes.append(
            f"No basket fits ₹{request.budget.limit:g}; cheapest achievable is ₹{cheapest.total:g}. "
            "Human review required."
        )
        return False, cheapest, notes

    def _compare_explanation(
        self, candidates: list[_MarketBasket], best: _MarketBasket,
        objective: OptimizationObjective,
    ) -> list[str]:
        lines = [f"Objective: {objective.value}."]
        for c in sorted(candidates, key=lambda mb: mb.total):
            tag = " (selected)" if c.marketplace == best.marketplace else ""
            lines.append(
                f"{c.marketplace}: items ₹{c.items_subtotal:g} + delivery ₹{c.delivery_fee:g}"
                f" + platform ₹{c.platform_fee:g} - discount ₹{c.discount:g} = ₹{c.total:g}{tag}"
            )
        return lines

    def _to_basket(
        self, request: ShoppingRequest, mb: _MarketBasket, objective: OptimizationObjective,
        within_budget: bool, explanation: list[str],
    ) -> Basket:
        items: list[BasketItem] = []
        for s in mb.selections:
            items.append(
                BasketItem(
                    item_id=s.item.id,
                    canonical_name=s.item.canonical_name,
                    offer=s.ranked.offer,
                    packs=s.packs,
                    line_total=s.line_total,
                    unit_price=s.ranked.unit_price,
                    reasons=s.ranked.reasons,
                )
            )
        return Basket(
            request_id=request.id,
            marketplace=mb.marketplace,
            items=items,
            items_subtotal=mb.items_subtotal,
            delivery_fee=mb.delivery_fee,
            platform_fee=mb.platform_fee,
            discount=mb.discount,
            total=mb.total,
            currency=request.budget.currency,
            objective=objective,
            within_budget=within_budget,
            missing_items=mb.missing,
            explanation=explanation,
        )


def _as_tuple(value) -> tuple:
    return value if isinstance(value, tuple) else (value,)
