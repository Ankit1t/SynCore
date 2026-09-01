# API Design

## Purpose

Expose the platform over REST + SSE with typed schemas and OpenAPI docs.

## Conventions

- Versioned under `/api/v1`.
- JSON in/out; request/response schemas in `syncore.api.schemas` (kept separate
  from domain models).
- Typed domain errors → structured error bodies `{ "error": { code, message,
  details } }` via a FastAPI exception handler; no stack traces to clients.
- OpenAPI at `/docs` and `/openapi.json`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/health/live`, `/health/ready` | probes |
| POST | `/api/v1/shopping-requests` | parse → `ShoppingRequestOut` |
| GET | `/api/v1/shopping-requests/{id}` | fetch parsed request |
| POST | `/api/v1/shopping-requests/{id}/execute` | run agent → `AgentRunOut` |
| GET | `/api/v1/shopping-requests/stream/live?text=` | **SSE** live run |
| POST | `/api/v1/baskets/optimize` | parse + optimize only |
| GET | `/api/v1/products/search?q=` | offers |
| GET | `/api/v1/orders`, `/api/v1/orders/{id}` | orders |
| GET | `/api/v1/agent-runs`, `/api/v1/agent-runs/{id}` | observability |
| GET | `/api/v1/admin/{metrics,scraping-health,feature-flags}` | admin |

## SSE contract

`stream/live` emits named events: `request` (parsed request), repeated `step`
(each `AgentStep`), then `final` (`AgentRunOut`) or `error`. The orchestrator
runs in a worker thread pushing steps to an async queue; the generator relays
them. This powers the live agent UI (spec sections 35, 37).

## Tool schema (agent tools)

Every agent tool has: input schema, validation, authorization, timeout, retry
policy, structured result, and an audit event (spec section 31).

## Idempotency

Payment/order operations use idempotency keys; repeated calls are safe.

## Testing

`tests/integration/test_api.py` uses FastAPI `TestClient` to cover health,
create/execute, optimize, search, listing, and the over-budget review path.
