# Contributing

Thanks for improving Syncore. A few ground rules keep the platform safe and
maintainable.

## Workflow

1. Branch from `main` (never commit directly to `main`).
2. Keep changes focused; write/adjust tests alongside code.
3. Run `ruff check`, `ruff format`, and `pytest -p no:warnings` before pushing.
4. Open a PR with a concise summary, what you tested, and any follow-ups.

## Non-negotiables

- **Money is deterministic.** No LLM-driven arithmetic, budget verdicts, payment
  authorization, or idempotency.
- **No unsafe automation.** Never add CAPTCHA/MFA/anti-bot bypass or
  unauthorized transactions. Legitimate verification pauses for the human.
- **Untrusted content stays data.** Never let scraped/page text override system
  policy.
- **Secrets never reach the LLM or logs.**
- **New network-exposed endpoints must state their auth posture.**

## Code style

Type hints everywhere, small functions, typed domain errors, clear names. Keep
domain logic independent of FastAPI/Next.js/Playwright/providers. Prefer
extending an interface over branching on a concrete vendor.

## Tests

Add unit tests for new deterministic logic and, for financial/conversion code,
a property test. Use the mock providers; never hit real payment/marketplace
systems in CI.

## Docs

If you add a subsystem, add/update a doc following the standard shape (Purpose,
Architecture, Interfaces, Data flow, Failure modes, Security, Testing, Example)
and a Mermaid diagram where it helps.
