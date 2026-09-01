# Agent Architecture

## Purpose

Explain why Syncore uses a controlled, composed agent instead of one large
autonomous LLM loop, and what each specialized component does.

## Principle: controlled agency

We do **not** build a single free-running LLM agent that can call arbitrary
tools in a loop. Instead, an explicit orchestrator (state machine) sequences
specialized components. LLM usage is confined to language-shaped tasks and is
always schema-validated. Deterministic code owns anything involving money,
security, or integrity.

## Specialized components

| # | Component | Kind | Module |
|---|---|---|---|
| 1 | Intent Agent | deterministic (LLM-optional) | `intent.parser` |
| 2 | Shopping Planner | deterministic | `orchestrator` (plan step) |
| 3 | Search Agent | adapter-driven | `marketplace.*` |
| 4 | Product Extraction | adapter-driven | `marketplace.*` (+ scraping) |
| 5 | Normalization Engine | deterministic | `normalization.*` |
| 6 | Comparison/Ranking | hybrid | `search.ranking` |
| 7 | Budget Agent | deterministic | `budget.engine` |
| 8 | Basket Optimizer | deterministic | `optimizer.basket` |
| 9 | Browser Executor | adapter-driven | `browser.executor` |
| 10 | Cart Verification | deterministic | `browser.executor` |
| 11 | Checkout | adapter-driven | `orchestrator` + adapter |
| 12 | Payment Orchestrator | deterministic | `payments.service` |
| 13 | Order Verification | deterministic | `orders.manager` |
| 14 | Failure Recovery | deterministic | `orchestrator` + `budget` |
| 15 | User Preference | deterministic | `domain.UserPreference` |

## What the LLM may / may not do

**May**: interpret ambiguous language, propose semantic matches, suggest
substitutions, phrase explanations. **May not**: arithmetic, payment
authorization, final total validation, security decisions, authentication,
budget checks, idempotency, DB integrity (spec section 6).

## Loop / cost protection

`MAX_AGENT_STEPS`, `MAX_AGENT_RUNTIME_SECONDS`, and a linear bounded pipeline
prevent runaway loops. The orchestrator wraps the whole run in a try/except that
degrades to a `FAILED` state rather than crashing.

## Tool system

Each capability the agent uses is an explicit, typed function with validation,
authorization, timeout, retry policy, and an audit trail (see
[api_design](api_design.md) and [security_architecture](security_architecture.md)).
The LLM has no arbitrary shell/network/DB access.

## Failure modes

Missing item → optimizer flags it and (optionally) substitution; source failure
→ partial results; over-budget → human review; payment needs auth → checkpoint.
See [failure_recovery](failure_recovery.md).

## Testing

`tests/e2e/test_vertical_slice.py` exercises the full happy path plus the
budget-block path; `tests/unit/test_state_machine.py` validates transitions.
