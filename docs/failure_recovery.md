# Failure Recovery

## Purpose

Degrade gracefully and never blindly retry financial operations.

Diagram: [`mermaid/16_failure_recovery.mmd`](mermaid/16_failure_recovery.mmd).

## Strategies (spec section 24)

| Failure | Response |
|---|---|
| Product unavailable | mark missing; optimizer seeks alternative offer / substitution |
| Price changed at checkout | re-extract authoritative total; re-run budget gate; stop if over |
| Cart expired | rebuild cart from the basket (idempotent add) |
| Browser crashed | restore session if safe; else fail cleanly |
| Payment timeout | check transaction status **before** any retry (idempotency key) |
| Duplicate payment risk | reconcile via idempotency store before acting |
| Source/scraper failure | circuit-break; use other sources; return partial + inform user |
| LLM timeout / malformed | deterministic fallback path |

## Never-blind-retry rule

Financial operations (authorize/capture, place order) are guarded by idempotency
keys. On timeout or ambiguity, Syncore checks status/reconciles rather than
re-issuing a charge (spec section 24, 45).

## Uncertain order confirmation

If payment succeeded but order confirmation is uncertain, the order is marked
`PAYMENT_SUCCESS_ORDER_UNCONFIRMED` and the run enters `RECOVERY` →
reconciliation, instead of assuming success (spec section 23).

## Crash safety

The orchestrator wraps the whole run in try/except: any unexpected error
transitions to `FAILED` with a structured `error` payload and an `AgentFailed`
event; the API still returns a clean response. Persistence failures are logged
and never crash the request.

## Testing

`tests/e2e` covers the budget-block path; unit tests cover guard rejections and
idempotency. Chaos scenarios (DB down, source timeout, malformed LLM) are listed
in [testing_strategy](testing_strategy.md).
