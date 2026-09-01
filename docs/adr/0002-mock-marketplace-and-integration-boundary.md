# ADR 0002: Mock marketplace + explicit integration boundary

- Status: Accepted
- Date: 2026-08-29

## Context

Live marketplaces change, require authentication, and must not be automated in
unsafe ways. We still need the full agent workflow — search, cart, checkout,
order — to be runnable and testable deterministically, without faking the
architecture.

## Decision

Define `BaseMarketplaceAdapter` and a registry as the only surface the agent
touches. Ship two `MockMarketplace` storefronts (different delivery economics)
for deterministic dev/tests. Real adapters (official APIs / permitted scrapes)
and the `PlaywrightExecutor` are implemented as **interfaces/stubs** and clearly
marked as the integration boundary, selected via `MARKETPLACE_MODE=live` /
`BROWSER_MODE=playwright`.

## Consequences

- The vertical slice runs end-to-end today with no external dependencies.
- Adding a real marketplace is additive and localized (no business-logic churn).
- We never fake "live" behavior; the boundary is explicit and honest
  (spec sections 53–54, 83).
