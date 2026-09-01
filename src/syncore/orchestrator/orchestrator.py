"""AI Shopping Orchestrator.

Drives a shopping request through the explicit state machine, wiring together
intent, discovery, normalization, ranking, optimization, budget guarding, the
(mock) browser cart build, checkout re-validation, policy-gated payment, and
order verification. Every transition is recorded as an AgentStep and published
as an event, so runs are observable and (in principle) resumable.

Deterministic financial logic (budget, guard, payment policy) is never handed
to an LLM.
"""

from __future__ import annotations

from collections.abc import Callable

from ..budget.engine import check_budget
from ..config import get_settings
from ..domain.enums import (
    AgentState,
    HumanCheckpointReason,
    OrderStatus,
    PaymentStatus,
)
from ..domain.errors import SyncoreError
from ..domain.models import (
    AgentDecision,
    AgentRun,
    AgentStep,
    AuditEvent,
    Offer,
    SearchQuery,
    ShoppingPlan,
    ShoppingRequest,
)
from ..events.bus import Event, EventBus, Events, InMemoryEventBus
from ..llm.provider import COST_TRACKER
from ..marketplace.registry import MarketplaceRegistry, get_registry
from ..normalization.quality import validate_offer
from ..observability.logging import get_logger, set_correlation_id
from ..optimizer.basket import BasketOptimizer
from ..orders.manager import OrderManager
from ..payments.guard import TransactionContext
from ..payments.policy import PaymentPolicy
from ..payments.provider import get_payment_provider
from ..payments.service import IdempotencyStore, PaymentService
from ..search.ranking import RankingEngine
from . import states

logger = get_logger("syncore.orchestrator")

StepCallback = Callable[[AgentStep], None]


class Orchestrator:
    def __init__(
        self,
        *,
        registry: MarketplaceRegistry | None = None,
        ranking: RankingEngine | None = None,
        optimizer: BasketOptimizer | None = None,
        payment_service: PaymentService | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings = get_settings()
        self.registry = registry or get_registry()
        self.ranking = ranking or RankingEngine()
        self.optimizer = optimizer or BasketOptimizer(self.registry)
        self.payment_service = payment_service or PaymentService(
            provider=get_payment_provider(),
            policy=PaymentPolicy.from_settings(),
            idempotency_store=IdempotencyStore(),
        )
        self.event_bus = event_bus or InMemoryEventBus()
        self.audit: list[AuditEvent] = []

    # ------------------------------------------------------------------ #
    def run(
        self,
        request: ShoppingRequest,
        *,
        auto_execute: bool = True,
        on_step: StepCallback | None = None,
    ) -> AgentRun:
        run = AgentRun(request_id=request.id, user_id=request.user_id,
                       state=AgentState.REQUEST_RECEIVED.value)
        set_correlation_id(run.id)
        self._step(run, AgentState.REQUEST_RECEIVED, "Request received.", on_step,
                   emit=Events.SHOPPING_REQUEST_CREATED,
                   data={"raw_text": request.raw_text})
        try:
            self._run_pipeline(run, request, auto_execute, on_step)
        except SyncoreError as exc:
            self._fail(run, exc.code, exc.message, exc.details, on_step)
        except Exception as exc:  # noqa: BLE001 - safety net, never crash the SaaS
            logger.exception("orchestrator crashed")
            self._fail(run, "internal_error", str(exc), {}, on_step)
        finally:
            from ..domain.models import utcnow

            run.finished_at = utcnow()
            set_correlation_id(None)
        return run

    # ------------------------------------------------------------------ #
    def _run_pipeline(
        self, run: AgentRun, request: ShoppingRequest, auto_execute: bool,
        on_step: StepCallback | None,
    ) -> None:
        # 1. Intent (already parsed by caller) ---------------------------
        items_desc = ", ".join(f"{i.requested_quantity} {i.canonical_name}" for i in request.items)
        budget_desc = (f"₹{request.budget.limit:g}" if request.budget.limit else "no limit")
        self._step(run, AgentState.INTENT_PARSED,
                   f"Understood {len(request.items)} item(s): {items_desc}. Budget {budget_desc}.",
                   on_step, emit=Events.INTENT_PARSED,
                   data={"items": items_desc, "budget": request.budget.limit})

        # 2. Plan --------------------------------------------------------
        plan = ShoppingPlan(
            request_id=request.id,
            queries=[
                SearchQuery(item_id=i.id, text=i.raw_text, canonical_name=i.canonical_name,
                            target_quantity=i.requested_quantity, brand_preference=i.brand_preference)
                for i in request.items
            ],
        )
        self._step(run, AgentState.PLAN_CREATED, f"Built plan with {len(plan.queries)} search queries.",
                   on_step, emit=Events.PLAN_CREATED)

        # 3. Search / discover ------------------------------------------
        self._step(run, AgentState.SEARCHING, "Searching marketplaces...", on_step,
                   emit=Events.SEARCH_STARTED)
        adapters = self._active_adapters()
        offers_by_item: dict[str, list[Offer]] = {}
        total_offers = 0
        for query in plan.queries:
            found: list[Offer] = []
            for adapter in adapters:
                try:
                    found.extend(adapter.search_products(query.text or query.canonical_name))
                except Exception as exc:  # circuit-breaker style: skip failing source
                    logger.warning("source %s failed: %s", adapter.name, exc)
            offers_by_item[query.item_id] = found
            total_offers += len(found)
        self._step(run, AgentState.DISCOVERING_PRODUCTS,
                   f"Discovered {total_offers} offers across {len(adapters)} source(s).",
                   on_step, emit=Events.PRODUCTS_DISCOVERED, data={"offers": total_offers})

        # 4. Normalize + validate data quality --------------------------
        clean_by_item: dict[str, list[Offer]] = {}
        rejected = 0
        for item_id, offers in offers_by_item.items():
            keep: list[Offer] = []
            for offer in offers:
                result = validate_offer(offer)
                if result.ok:
                    offer.confidence = result.confidence
                    keep.append(offer)
                else:
                    rejected += 1
            clean_by_item[item_id] = keep
        self._step(run, AgentState.NORMALIZING,
                   f"Normalized offers; rejected {rejected} low-quality record(s).",
                   on_step, emit=Events.PRODUCTS_NORMALIZED)

        # 5. Rank --------------------------------------------------------
        ranked_by_item = {}
        for query in plan.queries:
            ranked_by_item[query.item_id] = self.ranking.rank(query, clean_by_item.get(query.item_id, []))
        self._step(run, AgentState.RANKING, "Ranked candidate offers by explainable score.",
                   on_step, emit=Events.PRODUCTS_RANKED)

        # 6. Optimize ----------------------------------------------------
        basket = self.optimizer.optimize(request, ranked_by_item)
        run.basket = basket
        self._decision(run, "basket_selected",
                       f"Selected {basket.marketplace} basket totalling ₹{basket.total:g}.",
                       {"explanation": basket.explanation, "within_budget": basket.within_budget})
        self._step(run, AgentState.OPTIMIZING, "Optimized basket at basket-level economics.",
                   on_step, emit=Events.BASKET_OPTIMIZED,
                   data=self._basket_summary(basket))

        # 7. Basket ready + budget gate ---------------------------------
        verdict = check_budget(basket.total, request.budget)
        required_missing = [m for m in basket.missing_items]
        self._step(run, AgentState.BASKET_READY,
                   f"Basket ready. Total ₹{basket.total:g}. {verdict.reason}.",
                   on_step, emit=Events.BUDGET_VERIFIED, data=verdict.to_dict())

        if required_missing or not basket.within_budget or not verdict.ok:
            reason = (HumanCheckpointReason.AMBIGUOUS_PRODUCT if required_missing
                      else HumanCheckpointReason.BUDGET_EXCEEDED)
            run.checkpoint_reason = reason
            self._step(run, AgentState.USER_REVIEW_REQUIRED,
                       self._review_message(basket, required_missing, verdict),
                       on_step)
            return

        if not auto_execute or not self.settings.feature_browser_execution:
            self._step(run, AgentState.COMPLETED,
                       "Phase-1 complete: optimized basket ready for review.", on_step)
            return

        # 8. Execute: browser cart build --------------------------------
        self._execute(run, request, on_step)

    # ------------------------------------------------------------------ #
    def _execute(self, run: AgentRun, request: ShoppingRequest, on_step: StepCallback | None) -> None:
        from ..browser.executor import get_browser_executor

        assert run.basket is not None
        basket = run.basket
        adapter = self.registry.get(basket.marketplace)
        executor = get_browser_executor(adapter)

        session = executor.start_session(request.user_id)
        self._step(run, AgentState.BROWSER_SESSION_STARTED,
                   f"Started isolated browser session on {basket.marketplace}.", on_step,
                   data={"session_id": session.id})

        self._step(run, AgentState.CART_BUILDING, "Building cart...", on_step,
                   emit=Events.CART_BUILD_STARTED)
        expected: dict[str, int] = {}
        for bi in basket.items:
            spid = bi.offer.source_product_id
            executor.add_to_cart(spid, bi.packs)
            expected[spid] = expected.get(spid, 0) + bi.packs

        cart = executor.open_cart()
        ok, issues = executor.verify_cart(expected)
        if not ok:
            from ..domain.errors import CartVerificationError

            raise CartVerificationError("cart verification failed", details={"issues": issues})
        cart.verified = True
        self._step(run, AgentState.CART_VERIFIED,
                   f"Cart verified: {len(cart.items)} line(s), subtotal ₹{cart.items_subtotal:g}.",
                   on_step, emit=Events.CART_VERIFIED)

        # 9. Checkout + price-change protection -------------------------
        checkout = executor.open_checkout()
        final_verdict = check_budget(checkout.final_total, request.budget)
        drift = round(checkout.final_total - basket.total, 2)
        self._step(run, AgentState.CHECKOUT_READY,
                   f"Final checkout total ₹{checkout.final_total:g} "
                   f"(search estimate ₹{basket.total:g}, drift ₹{drift:g}). {final_verdict.reason}.",
                   on_step, emit=Events.CHECKOUT_STARTED, data=final_verdict.to_dict())

        if not final_verdict.ok:
            run.checkpoint_reason = HumanCheckpointReason.BUDGET_EXCEEDED
            self._step(run, AgentState.USER_REVIEW_REQUIRED,
                       f"Checkout total ₹{checkout.final_total:g} exceeds hard budget. Stopping before payment.",
                       on_step)
            executor.close()
            return

        # 10. Payment (policy + guard + idempotency) --------------------
        self._step(run, AgentState.PAYMENT_PENDING, "Preparing payment...", on_step)
        guard_ctx = TransactionContext(
            user_id=request.user_id, vendor=checkout.vendor, amount=checkout.final_total,
            currency=checkout.currency, budget=request.budget, cart_verified=cart.verified,
            expected_item_count=len(expected), actual_item_count=len(cart.items),
            idempotency_key=f"{request.id}:{checkout.id}",
        )
        intent, attempts = self.payment_service.process(
            checkout=checkout, user_id=request.user_id, guard_ctx=guard_ctx,
            category="grocery", daily_spent=0.0,
            auto_pay_enabled=self.settings.feature_automatic_payment,
        )

        if intent.status == PaymentStatus.REQUIRES_USER_ACTION:
            run.checkpoint_reason = intent.checkpoint_reason
            self._step(run, AgentState.PAYMENT_AUTH_REQUIRED,
                       self._auth_message(intent), on_step, emit=Events.PAYMENT_AUTH_REQUIRED,
                       data={"amount": intent.amount, "vendor": intent.vendor,
                             "reason": intent.checkpoint_reason.value if intent.checkpoint_reason else None})
            executor.close()
            return

        if intent.status != PaymentStatus.SUCCEEDED:
            executor.close()
            from ..domain.errors import PaymentFailedError

            raise PaymentFailedError("payment did not succeed",
                                     details={"status": intent.status.value})

        self._step(run, AgentState.PAYMENT_PROCESSING,
                   f"Payment authorized and captured: ₹{intent.amount:g} to {intent.vendor}.",
                   on_step, emit=Events.PAYMENT_SUCCEEDED)
        self._audit("PAYMENT_EXECUTED", run, {"amount": intent.amount, "currency": intent.currency,
                                              "vendor": intent.vendor, "intent_id": intent.id})

        # 11. Place + verify order --------------------------------------
        payment_reference = next(
            (a.provider_reference for a in reversed(attempts) if a.provider_reference), None
        )
        order = OrderManager(adapter).place_and_verify(
            user_id=request.user_id, request_id=request.id, cart=cart, checkout=checkout,
            payment_intent_id=intent.id, payment_reference=payment_reference or "",
        )
        run.order = order
        self._step(run, AgentState.ORDER_PLACED,
                   f"Order placed: {order.external_order_id}.", on_step, emit=Events.ORDER_PLACED)

        self._step(run, AgentState.ORDER_VERIFICATION,
                   f"Order status: {order.status.value}.", on_step, emit=Events.ORDER_VERIFIED)
        executor.close()

        if order.status == OrderStatus.CONFIRMED:
            self._step(run, AgentState.COMPLETED,
                       f"Done. Order {order.external_order_id} confirmed, total ₹{order.total:g}, "
                       f"ETA ~{order.delivery_eta_minutes} min. LLM cost this run: "
                       f"${COST_TRACKER.total_cost_usd:.4f}.", on_step)
        else:
            self._step(run, AgentState.RECOVERY,
                       "Payment succeeded but order confirmation is uncertain; scheduled for reconciliation.",
                       on_step)
            self._step(run, AgentState.COMPLETED,
                       f"Completed with reconciliation pending for order {order.external_order_id}.",
                       on_step)

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    def _active_adapters(self):
        if self.settings.feature_multi_marketplace:
            healthy = self.registry.healthy_adapters()
            if healthy:
                return healthy
        return [self.registry.get(self.settings.default_marketplace)]

    def _step(self, run: AgentRun, state: AgentState, message: str,
              on_step: StepCallback | None, *, emit: str | None = None,
              data: dict | None = None) -> None:
        current = AgentState(run.state)
        if not states.can_transition(current, state):
            logger.debug("non-standard transition %s -> %s", current.value, state.value)
        run.state = state.value
        step = AgentStep(run_id=run.id, index=len(run.steps), state=state.value,
                         message=message, data=data or {})
        run.steps.append(step)
        logger.info("[%s] %s", state.value, message)
        if emit:
            self.event_bus.publish(Event(name=emit, payload=data or {}, correlation_id=run.id))
        self.event_bus.publish(Event(name=Events.AGENT_STATE_CHANGED,
                                     payload={"state": state.value, "message": message},
                                     correlation_id=run.id))
        if on_step:
            on_step(step)

    def _decision(self, run: AgentRun, kind: str, summary: str, evidence: dict) -> None:
        run.decisions.append(AgentDecision(run_id=run.id, kind=kind, summary=summary,
                                           evidence=evidence))

    def _fail(self, run: AgentRun, code: str, message: str, details: dict,
              on_step: StepCallback | None) -> None:
        run.error = {"code": code, "message": message, "details": details}
        self.event_bus.publish(Event(name=Events.AGENT_FAILED,
                                     payload=run.error, correlation_id=run.id))
        self._step(run, AgentState.FAILED, f"Failed: {message}", on_step)

    def _audit(self, event: str, run: AgentRun, payload: dict) -> None:
        self.audit.append(AuditEvent(event=event, user_id=run.user_id, run_id=run.id, payload=payload))

    def _basket_summary(self, basket) -> dict:
        return {
            "marketplace": basket.marketplace,
            "items": [
                {"name": bi.canonical_name, "title": bi.offer.product.title,
                 "packs": bi.packs, "line_total": bi.line_total, "unit_price": bi.unit_price}
                for bi in basket.items
            ],
            "items_subtotal": basket.items_subtotal,
            "delivery_fee": basket.delivery_fee,
            "platform_fee": basket.platform_fee,
            "discount": basket.discount,
            "total": basket.total,
            "currency": basket.currency,
            "within_budget": basket.within_budget,
            "missing_items": basket.missing_items,
        }

    def _review_message(self, basket, missing, verdict) -> str:
        if missing:
            return f"Human review needed: could not source {', '.join(missing)}."
        return (f"Human review needed: cheapest achievable basket is ₹{basket.total:g}, "
                f"over the hard budget of ₹{verdict.limit:g}.")

    def _auth_message(self, intent) -> str:
        reason = intent.checkpoint_reason.value if intent.checkpoint_reason else "authorization required"
        return (f"Payment of ₹{intent.amount:g} to {intent.vendor} is ready. "
                f"Authentication required ({reason}).")


def build_default_orchestrator() -> Orchestrator:
    """Wire an orchestrator from config, registering mock marketplaces if needed."""
    settings = get_settings()
    registry = get_registry()
    if settings.marketplace_mode == "mock" and not registry.list():
        from ..marketplace.mock import build_default_registry

        for adapter in build_default_registry():
            registry.register(adapter)
    return Orchestrator(registry=registry)
