"""Application service: bridges HTTP layer, orchestrator and persistence.

Holds the marketplace registry (singleton) and maps domain objects to API
schemas. Orchestrator instances are created per execution so their event bus
and audit log are scoped to a single run.
"""

from __future__ import annotations

from ..config import get_settings
from ..db.base import init_db, session_scope
from ..db import repositories as repo
from ..domain.models import AgentRun, Offer, ShoppingRequest
from ..intent.parser import parse_request
from ..marketplace.mock import build_default_registry
from ..marketplace.registry import get_registry
from ..observability.logging import get_logger
from ..orchestrator.orchestrator import Orchestrator, build_default_orchestrator
from .schemas import (
    AgentRunOut,
    BasketItemOut,
    BasketOut,
    OfferOut,
    OrderOut,
    ParsedItemOut,
    ShoppingRequestOut,
    StepOut,
)

logger = get_logger("syncore.api")


class SyncoreService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._ensure_registry()
        init_db()
        with session_scope() as s:
            self.demo_user = repo.get_or_create_demo_user(s)

    def _ensure_registry(self) -> None:
        registry = get_registry()
        if self.settings.marketplace_mode == "mock" and not registry.list():
            for adapter in build_default_registry():
                registry.register(adapter)

    # --- parsing / execution ------------------------------------------------
    def parse(self, text: str, user_id: str | None = None) -> ShoppingRequest:
        return parse_request(text, user_id=user_id or self.demo_user.id)

    def new_orchestrator(self) -> Orchestrator:
        return build_default_orchestrator()

    def persist(self, request: ShoppingRequest, run: AgentRun, orchestrator: Orchestrator) -> None:
        try:
            with session_scope() as s:
                repo.save_request(s, request)
                repo.save_run(s, run)
                repo.save_audit_events(s, [e for e in orchestrator.audit if e.run_id == run.id])
        except Exception as exc:  # persistence must never break the response
            logger.error("failed to persist run %s: %s", run.id, exc)

    # --- discovery ----------------------------------------------------------
    def search(self, query: str, limit: int = 20) -> list[Offer]:
        offers: list[Offer] = []
        for adapter in get_registry().healthy_adapters():
            try:
                offers.extend(adapter.search_products(query, limit=limit))
            except Exception as exc:
                logger.warning("search on %s failed: %s", adapter.name, exc)
        return offers

    # --- mapping ------------------------------------------------------------
    def to_request_out(self, request: ShoppingRequest) -> ShoppingRequestOut:
        return ShoppingRequestOut(
            id=request.id, user_id=request.user_id, raw_text=request.raw_text,
            budget_limit=request.budget.limit, currency=request.budget.currency,
            items=[
                ParsedItemOut(canonical_name=i.canonical_name,
                              requested_quantity=str(i.requested_quantity), raw_text=i.raw_text)
                for i in request.items
            ],
        )

    def to_run_out(self, run: AgentRun) -> AgentRunOut:
        return AgentRunOut(
            id=run.id, request_id=run.request_id, user_id=run.user_id, state=run.state,
            checkpoint_reason=run.checkpoint_reason.value if run.checkpoint_reason else None,
            error=run.error,
            steps=[StepOut(index=s.index, state=s.state, message=s.message, data=s.data)
                   for s in run.steps],
            basket=self.to_basket_out(run) if run.basket else None,
            order=self.to_order_out(run) if run.order else None,
        )

    def to_basket_out(self, run: AgentRun) -> BasketOut:
        b = run.basket
        assert b is not None
        return BasketOut(
            marketplace=b.marketplace, objective=b.objective.value,
            items=[
                BasketItemOut(canonical_name=bi.canonical_name, title=bi.offer.product.title,
                              packs=bi.packs, unit_price=bi.unit_price, line_total=bi.line_total,
                              reasons=bi.reasons)
                for bi in b.items
            ],
            items_subtotal=b.items_subtotal, delivery_fee=b.delivery_fee,
            platform_fee=b.platform_fee, discount=b.discount, total=b.total,
            currency=b.currency, within_budget=b.within_budget,
            missing_items=b.missing_items, explanation=b.explanation,
        )

    def to_order_out(self, run: AgentRun) -> OrderOut:
        o = run.order
        assert o is not None
        return OrderOut(
            id=o.id, external_order_id=o.external_order_id, status=o.status.value,
            marketplace=o.marketplace, vendor=o.vendor, total=o.total, currency=o.currency,
            delivery_eta_minutes=o.delivery_eta_minutes,
            items=[i.model_dump(mode="json") for i in o.items],
        )

    @staticmethod
    def offer_to_out(offer: Offer) -> OfferOut:
        return OfferOut(
            marketplace=offer.marketplace, title=offer.product.title, brand=offer.product.brand,
            price=offer.price, mrp=offer.mrp, quantity=str(offer.quantity),
            rating=offer.product.rating, review_count=offer.product.review_count,
            availability=offer.availability.value, delivery_eta_minutes=offer.delivery_eta_minutes,
        )


_service: SyncoreService | None = None


def get_service() -> SyncoreService:
    global _service
    if _service is None:
        _service = SyncoreService()
    return _service
