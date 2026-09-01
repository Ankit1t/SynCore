# Budget Engine

## Purpose

Provide deterministic, testable budget verdicts. A hard budget is a
non-negotiable constraint; the system never intentionally exceeds it.

## Interface

`syncore.budget.engine.check_budget(total, BudgetPolicy) -> BudgetVerdict`
where `BudgetPolicy{limit, currency, constraint_type∈{HARD,SOFT}}` and
`BudgetVerdict{ok, limit, total, remaining, is_hard, reason}`.

Diagram: [`mermaid/09_budget_validation.mmd`](mermaid/09_budget_validation.mmd).

## Rules

- No limit → always ok.
- `total ≤ limit` (with 1e-9 tolerance) → ok, `remaining = limit − total`.
- Over a **hard** limit → `ok = False`.
- Over a **soft** limit → `ok = True` with a warning reason.

## Where it runs (two gates)

1. **After optimization** against the advisory search estimate.
2. **After checkout** against the authoritative re-extracted total, immediately
   before the payment guard (price-change protection).

If gate 2 fails, the run stops at `USER_REVIEW_REQUIRED` before any payment.

## Recovery when over budget

The optimizer re-optimizes for cheapest, then drops optional items, then (if
still over) reports the cheapest achievable total for human review. The engine
itself is pure; recovery orchestration lives in the optimizer/orchestrator.

## Money math is LLM-free

All arithmetic is Python with rounding to 2 dp. The LLM is never consulted for
budget decisions (spec section 14, 78).

## Testing

`tests/unit/test_budget.py` covers within/over/exact/soft/no-limit; the property
test `test_hard_budget_verdict_is_consistent` asserts `ok ⇔ total ≤ limit` for
random inputs.
