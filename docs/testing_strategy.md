# Testing Strategy

## Purpose

Prove correctness where it matters most — money, units, state — and keep the
whole flow verifiable offline.

## Layers

| Layer | Location | Covers |
|---|---|---|
| Unit | `tests/unit` | units/conversion, intent (incl. Hinglish + budget), normalization + quality, ranking, budget engine, optimizer, payments (policy/guard/idempotency), state machine |
| Property | `tests/property` | financial invariants via Hypothesis |
| E2E | `tests/e2e` | orchestrator vertical slice (happy path + budget block + Phase-1-only) |
| Integration | `tests/integration` | FastAPI `TestClient` (health, create/execute, optimize, search, listing, over-budget review) |

Run: `pytest -p no:warnings` (60 tests, all green). Tests use a throwaway SQLite
DB set in `tests/conftest.py`.

## Property-based invariants (spec section 43)

- `1000g == 1kg`, and grams↔kg round-trips.
- For any hard budget B: `verdict.ok ⇔ total ≤ B`; and if a basket is
  `within_budget`, `total ≤ B`.
- For any idempotency key: repeated payment processing yields the same intent
  and **no** second charge.

## Chaos / failure testing (spec section 44)

Planned/були-mockable scenarios: DB unavailable, Redis unavailable, LLM
timeout/malformed output, scraper timeout, browser crash, missing selector,
price change, product disappears, cart expiry, payment timeout, duplicate
webhook/event, network interruption. The design degrades gracefully in each
(see [failure_recovery](failure_recovery.md)); harnessing them is the next test
milestone.

## Payments in CI

Only the sandbox/mock provider is used; **no** real financial transactions are
executed in automated tests (spec section 42).

## What we deliberately don't test yet

Real marketplace/browser/payment integrations (integration boundary) — those get
their own suites when implemented.
