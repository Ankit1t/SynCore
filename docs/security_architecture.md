# Security Architecture

## Purpose

Describe the controls that make an autonomous, money-spending, browser-driving
agent safe to operate.

## Controls (spec sections 29–30, 48)

- **AuthN/AuthZ**: user auth + RBAC; every user-scoped entity carries `user_id`
  for tenant isolation. Admin endpoints require the ADMIN role in production.
- **Least privilege for the LLM**: no arbitrary shell/network/DB access; only
  explicit, typed, authorized tools. No secrets (card/CVV/OTP/keys/cookies) are
  ever passed to the model.
- **Untrusted content**: scraped pages and product descriptions are data, never
  instructions. System policy always outranks page content — see prompt
  injection defense in [`mermaid/25_prompt_injection_defense.mmd`](mermaid/25_prompt_injection_defense.mmd).
- **Deterministic money**: budget, guard, policy, idempotency are code, not LLM.
- **Final transaction guard**: mandatory checks before any charge (vendor, cart
  verified, amount, currency, item counts, budget, idempotency).
- **Idempotency**: payments/orders can't double-execute on retry.
- **Browser isolation**: each user gets an isolated session/context; cookies are
  never shared or logged; sessions never exposed to the LLM.
- **Input/output validation**: Pydantic schemas at the edges; typed domain
  errors; no stack traces/secrets leaked to users.
- **Rate limiting**: API, search, scraping, browser, agent, payments (config).
- **Feature flags**: risky capabilities default off (`FEATURE_AUTO_SUBSTITUTION`).
- **SSRF/secret hygiene**: outbound calls limited to configured providers; no
  exfiltration of project code/data.

## Boundaries we never cross

No bypass of authentication, MFA, CAPTCHA, or anti-bot controls; no session
theft; no unauthorized transactions. When legitimate verification is required,
the agent pauses for the human (spec sections 19, 22).

## Auditability

Immutable `AuditEvent` records for payment execution, budget decisions,
selections, approvals, and security events (spec section 49).

## See also

[threat_model](threat_model.md), [authentication](authentication.md),
[authorization](authorization.md), [payment_architecture](payment_architecture.md).
