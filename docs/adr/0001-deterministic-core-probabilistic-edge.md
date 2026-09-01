# ADR 0001: Deterministic core, probabilistic edge

- Status: Accepted
- Date: 2026-08-29

## Context

An autonomous shopping agent spends real money and drives browsers. LLMs are
excellent at language but unreliable for arithmetic, security decisions, and
consistency. Letting an LLM decide totals or authorize payments is unacceptable.

## Decision

Split the system into a **deterministic core** (units, budget, optimizer,
payment policy, transaction guard, idempotency, state machine) and a
**probabilistic edge** (intent interpretation, semantic matching, explanations).
The LLM advises; it never decides money, security, or integrity. The default LLM
provider is deterministic and offline so the platform runs with zero keys/cost.

## Consequences

- All financial logic is unit- and property-testable and reproducible.
- The platform runs and is fully testable without any API key.
- Slightly less "magical" language handling by default; real LLMs can be enabled
  per environment for richer interpretation without changing money logic.
