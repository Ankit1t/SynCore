# Browser Automation

## Purpose

Execute high-level, verifiable shopping actions against a storefront without
leaking selectors into business logic, and without unsafe automation.

## Abstraction

`syncore.browser.executor.BrowserExecutor` exposes intent-level actions:
`start_session`, `search`, `add_to_cart`, `open_cart`, `verify_cart`,
`open_checkout`, `close`. Two implementations:

- `MockBrowserExecutor` — drives a marketplace adapter; used by the vertical
  slice and tests.
- `PlaywrightExecutor` — Phase-2 integration boundary (raises `NotImplementedError`
  with guidance); real per-site page objects live in that site's adapter.

Diagrams: [`mermaid/10_browser_automation.mmd`](mermaid/10_browser_automation.mmd),
[`mermaid/11_cart_building.mmd`](mermaid/11_cart_building.mmd).

## Golden rule: verify, never blind-click

After every mutating action the executor re-reads state:

```
add_to_cart(sku, qty)
  → re-read cart
  → assert sku present AND qty increased by exactly `qty`
  → else raise CartVerificationError
```

Before checkout, `verify_cart(expected{sku:qty})` confirms the live cart matches
the optimized basket (correct SKUs and quantities, no extras).

## Isolation & safety (spec sections 18–19, 48)

- Each user gets an isolated session/context; cookies are never shared.
- Session cookies/secrets are never logged or exposed to the LLM.
- No bypass of auth/MFA/CAPTCHA/anti-bot; legitimate verification pauses for the
  human at a checkpoint.
- Recovery: on selector changes a real executor tries alternates and re-verifies
  resulting state before continuing.

## Testing

The mock executor is covered indirectly by the e2e slice (cart build + verify +
checkout). Real executors get their own integration tests behind `live` mode.
