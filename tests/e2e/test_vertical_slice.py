"""End-to-end orchestrator tests (the first working vertical slice)."""

from __future__ import annotations

from syncore.domain.enums import AgentState, OrderStatus
from syncore.intent.parser import parse_request
from syncore.orchestrator.orchestrator import build_default_orchestrator


def test_target_scenario_completes_and_orders(registry):
    request = parse_request("₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar.",
                            user_id="u")
    run = build_default_orchestrator().run(request, auto_execute=True)

    assert run.state == AgentState.COMPLETED.value
    assert run.basket is not None
    assert run.basket.within_budget
    assert run.basket.total <= request.budget.limit
    assert run.order is not None
    assert run.order.status == OrderStatus.CONFIRMED
    assert run.order.total == run.basket.total  # final == what we optimized (no drift in mock)
    # observability: every step recorded
    assert run.steps[0].state == AgentState.REQUEST_RECEIVED.value
    assert run.steps[-1].state == AgentState.COMPLETED.value


def test_phase1_only_stops_at_basket(registry):
    request = parse_request("₹500 ke andar 1kg aloo aur 2 Maggi", user_id="u")
    run = build_default_orchestrator().run(request, auto_execute=False)
    assert run.state == AgentState.COMPLETED.value
    assert run.basket is not None
    assert run.order is None  # no execution in Phase-1-only mode


def test_hard_budget_blocks_order(registry):
    request = parse_request("order 2 maggi and 1kg rice under 100", user_id="u")
    run = build_default_orchestrator().run(request, auto_execute=True)
    assert run.state == AgentState.USER_REVIEW_REQUIRED.value
    assert run.order is None  # never place an over-budget order
    assert run.checkpoint_reason is not None


def test_final_total_never_exceeds_hard_budget_when_ordered(registry):
    """If an order is placed, its total must be within the hard budget."""
    request = parse_request("₹500 ke andar 1kg aloo, 500g onion, 100g mirch aur 2 Maggi",
                            user_id="u")
    run = build_default_orchestrator().run(request, auto_execute=True)
    if run.order is not None:
        assert run.order.total <= request.budget.limit
