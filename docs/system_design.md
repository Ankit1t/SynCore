# System Design

## Purpose

Explain the concrete building blocks, their responsibilities, and how they
compose, so a new engineer can navigate the codebase quickly.

## Module map

| Package | Responsibility |
|---|---|
| `syncore.config` | Env-driven settings (pydantic-settings), ranking weights |
| `syncore.domain` | `models`, `enums`, `errors` — the shared vocabulary |
| `syncore.units` | Deterministic unit conversion + unit price + packs math |
| `syncore.normalization` | `lexicon` (synonyms), `normalizer` (titles→products), `quality` (validation) |
| `syncore.intent` | NL → `ShoppingRequest` (budget + items), Hinglish aware |
| `syncore.llm` | `LLMProvider` interface + `DeterministicProvider` + optional OpenAI |
| `syncore.marketplace` | `BaseMarketplaceAdapter`, `MarketplaceRegistry`, `MockMarketplace` |
| `syncore.search` | Explainable weighted `RankingEngine` |
| `syncore.budget` | `check_budget` verdicts (hard/soft) |
| `syncore.optimizer` | `BasketOptimizer` (basket-level economics, objectives) |
| `syncore.payments` | `policy`, `guard`, `provider`, `service` (idempotency) |
| `syncore.orders` | `OrderManager` (place + verify) |
| `syncore.browser` | `BrowserExecutor` + `MockBrowserExecutor` (+ Playwright stub) |
| `syncore.events` | `EventBus` (+ in-memory), well-known event names |
| `syncore.orchestrator` | `states` (transition map) + `Orchestrator` state machine |
| `syncore.db` | SQLAlchemy engine, tables, repositories |
| `syncore.api` | FastAPI app, schemas, routes, service, static UI |

## Composition (who calls whom)

The `Orchestrator` is the only component that composes services. It receives a
parsed `ShoppingRequest` and drives: plan → search (via registry adapters) →
normalize/validate → rank → optimize → budget gate → (execute: browser cart →
verify → checkout → budget re-guard → payment → order). Services do not call
each other directly, which keeps them independently testable.

## Data ownership

- Canonical product identity lives in `Product`; marketplace-specific price and
  logistics live in `Offer`. They are never merged.
- Advisory pre-execution economics live in `Basket`; authoritative
  post-execution economics live in `Cart`/`CheckoutSession`.

## Extensibility seams

- New marketplace → implement `BaseMarketplaceAdapter`, `registry.register(...)`.
- New LLM/payment/browser vendor → implement the matching provider interface.
- New optimization objective → extend `OptimizationObjective` + a comparator.
- New product category → extend the lexicon and (later) category-specific
  normalizers; domain models already carry `category`.

## Non-goals for the MVP

Distributed queues, multi-region, and full category coverage are explicitly out
of scope until the vertical slice is solid (spec section 79).
