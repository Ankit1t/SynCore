"""State machine transition tests."""

from __future__ import annotations

from syncore.domain.enums import AgentState
from syncore.orchestrator import states


def test_happy_path_transitions_allowed():
    path = [
        AgentState.REQUEST_RECEIVED, AgentState.INTENT_PARSED, AgentState.PLAN_CREATED,
        AgentState.SEARCHING, AgentState.DISCOVERING_PRODUCTS, AgentState.NORMALIZING,
        AgentState.RANKING, AgentState.OPTIMIZING, AgentState.BASKET_READY,
        AgentState.BROWSER_SESSION_STARTED, AgentState.CART_BUILDING, AgentState.CART_VERIFIED,
        AgentState.CHECKOUT_READY, AgentState.PAYMENT_PENDING, AgentState.PAYMENT_PROCESSING,
        AgentState.ORDER_PLACED, AgentState.ORDER_VERIFICATION, AgentState.COMPLETED,
    ]
    for src, dst in zip(path, path[1:], strict=False):
        assert states.can_transition(src, dst), f"{src} -> {dst} should be allowed"


def test_illegal_transition_blocked():
    assert not states.can_transition(AgentState.REQUEST_RECEIVED, AgentState.PAYMENT_PROCESSING)


def test_any_state_can_fail_or_cancel():
    assert states.can_transition(AgentState.CART_BUILDING, AgentState.FAILED)
    assert states.can_transition(AgentState.OPTIMIZING, AgentState.CANCELLED)


def test_payment_pending_can_require_auth():
    assert states.can_transition(AgentState.PAYMENT_PENDING, AgentState.PAYMENT_AUTH_REQUIRED)
