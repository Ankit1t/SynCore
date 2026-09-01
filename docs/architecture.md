# Architecture

## Purpose

Describe how Syncore is structured so a request in natural language becomes a
verified, budget-safe order, while keeping money logic deterministic and the
system modular, observable and extensible.

## High-level components

```
Web client ─▶ API Gateway ─▶ Agent Orchestrator ─┬─▶ Intent Engine
                                                  ├─▶ Search / Ranking
                                                  ├─▶ Policy / Budget Engine
                                                  ├─▶ Marketplace Adapters (Registry)
                                                  ├─▶ Product Normalization
                                                  ├─▶ Basket Optimizer
                                                  ├─▶ Browser Executor
                                                  ├─▶ Payment Orchestrator
                                                  └─▶ Order Manager
                                     (Event Bus + Audit Log throughout)
```

See [`mermaid/01_system_architecture.mmd`](mermaid/01_system_architecture.mmd).

## Layering (dependency direction points inward)

1. **Domain** (`syncore.domain`): pure models, enums, typed errors. No framework
   imports.
2. **Deterministic services**: `units`, `normalization`, `search` (ranking),
   `budget`, `optimizer`, `payments`, `orders`. Pure Python, fully unit-tested.
3. **Ports/adapters**: `marketplace` (adapter + registry), `browser`, `llm`,
   `payments.provider`, `events`. Interfaces first; concrete + mock behind them.
4. **Orchestration**: `orchestrator` wires services and ports into the state
   machine.
5. **Delivery**: `api` (FastAPI) and `web` (Next.js). Thin; contain no business
   rules.

## Deterministic core vs probabilistic edge

| Deterministic (code, tested) | Probabilistic (LLM-assisted) |
|---|---|
| unit conversion, unit price | intent interpretation of ambiguous text |
| budget verdicts, final guard | semantic product matching hints |
| payment policy + idempotency | substitution suggestions |
| basket optimization math | natural-language explanations |
| state transitions | — |

The LLM is optional (`LLM_PROVIDER=deterministic` by default) and never
authorizes payments, computes totals, or overrides policy.

## Key design principles

- **API-first / DI**: domain logic independent of FastAPI, Next.js, Playwright,
  a specific LLM, payment provider, or marketplace.
- **Provider abstractions** for LLM, embeddings, payments, marketplace, browser,
  notifications, storage → vendor replaceability.
- **Fault isolation**: a failing scraper/source degrades to partial results; it
  never crashes the platform.
- **Everything observable**: each state transition emits an event + persisted
  `AgentStep`; decisions and audits are recorded.

## Technology

Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (SQLite default,
Postgres-ready), SSE for live updates, Next.js 14 + Tailwind for the UI,
pytest + Hypothesis for tests. Redis/Kafka are optional future backends behind
the cache/event abstractions.

## Failure modes (system-level)

- Source down → circuit-break, continue with other sources, inform user.
- LLM unavailable/malformed → deterministic fallback path.
- DB down → API returns `degraded`/`not_ready`; orchestrator still computes but
  persistence is skipped with a logged error (never crashes the response).

## Security posture

RBAC + tenant scoping, untrusted-webpage handling, prompt-injection defense
(system policy always wins), no secrets to the LLM, idempotent payments, final
transaction guard. See [security_architecture](security_architecture.md).

## Testing

Unit tests per deterministic service, property tests for financial invariants,
e2e for the orchestrator slice, integration for the API. See
[testing_strategy](testing_strategy.md).
