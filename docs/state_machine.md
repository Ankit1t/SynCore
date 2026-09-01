# Orchestrator State Machine

## Purpose

Make agent execution explicit, observable and resumable. Every transition is
validated, recorded as an `AgentStep`, and published as an event.

## States

`REQUEST_RECEIVED → INTENT_PARSED → PLAN_CREATED → SEARCHING →
DISCOVERING_PRODUCTS → (EXTRACTING_PRODUCTS) → NORMALIZING → RANKING →
OPTIMIZING → BASKET_READY → [USER_REVIEW_REQUIRED] → BROWSER_SESSION_STARTED →
CART_BUILDING → CART_VERIFIED → CHECKOUT_READY → PAYMENT_PENDING →
[PAYMENT_AUTH_REQUIRED] → PAYMENT_PROCESSING → ORDER_PLACED → ORDER_VERIFICATION
→ COMPLETED`

Terminal/branch states: `COMPLETED`, `FAILED`, `CANCELLED`, `RECOVERY`,
`USER_REVIEW_REQUIRED`, `PAYMENT_AUTH_REQUIRED`.

Diagram: [`mermaid/17_state_machine.mmd`](mermaid/17_state_machine.mmd).

## Transition rules

Defined in `syncore.orchestrator.states.TRANSITIONS`. Any state may enter
`RECOVERY`, `FAILED`, or `CANCELLED` (failure handling). `can_transition(src,
dst)` guards moves; unexpected transitions are logged but not fatal (the map is
a guide, and safety states are always reachable).

## Pausing (not failing)

- `BASKET_READY → USER_REVIEW_REQUIRED`: over hard budget or missing required
  items, or `auto_execute=False` (Phase-1-only).
- `CHECKOUT_READY → USER_REVIEW_REQUIRED`: authoritative total exceeds budget.
- `PAYMENT_PENDING → PAYMENT_AUTH_REQUIRED`: policy needs human authorization.

These are legitimate stopping points, not errors. The run persists with a
`checkpoint_reason` so it can be resumed after the human acts.

## Persistence & resume

Each step is appended to the `AgentRun` and saved via repositories. Because the
state and all inputs are persisted, a crashed or paused run can be reconstructed
and continued (Phase-2 resume hooks into the same repository).

## Observability

Every transition publishes `AgentStateChanged` plus a domain event
(`BasketOptimized`, `PaymentSucceeded`, ...). The SSE endpoint streams these to
the UI in real time.

## Testing

`tests/unit/test_state_machine.py` asserts the happy path is allowed, illegal
jumps are blocked, and every state can fail/cancel.
