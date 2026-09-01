# Observability

## Purpose

Make every run explainable and every subsystem measurable.

## Logging

`syncore.observability.logging` emits human-readable lines locally or single-line
JSON in production (`LOG_JSON=true`). A `correlation_id` (the `AgentRun.id`) is
bound per run so all log lines for a request are linkable. Output is UTF-8 safe.

## Agent traces

Each state transition creates a persisted `AgentStep` (index, state, message,
data) and publishes an event. `AgentDecision` records why choices were made
(e.g. basket selection evidence). The SSE stream and `/agent-runs/{id}` expose
these.

## Metrics (`/api/v1/admin/metrics`)

- `agent_runs_total`, `agent_runs_completed`, `agent_success_rate`
- `orders_total`, `average_order_value`
- `llm_cost_usd_this_process`, `llm_tokens_this_process`

Planned additions (spec section 33): scraper_success_rate,
cart_build_success_rate, payment_success_rate, budget_violation_attempts,
average_agent_latency, LLM_cost_per_order, scraping_error_rate.

## AI cost tracking

`llm.provider.COST_TRACKER` records provider, model, tokens, latency and cost
per call; the deterministic provider reports \$0. See
[cost_optimization](cost_optimization.md).

## Health

`/health` (db + marketplaces), `/health/live`, `/health/ready` back container
probes and the compose/K8s health checks.

## Tracing (future)

The logging correlation-id is the seam for distributed tracing
(OpenTelemetry): spans per state, per tool call, per external request.
