# Payment Architecture

## Purpose

Execute payments as a separate, security-sensitive subsystem: policy-gated,
idempotent, guarded, and never driven by an LLM.

## Flow

```
Agent → PaymentIntent → Policy Engine → Transaction Guard → PaymentProvider
      → (Authorized Provider → Network) → PaymentAttempt(s) → status
```

Diagrams: [`mermaid/13_payment.mmd`](mermaid/13_payment.mmd),
[`mermaid/14_human_in_loop.mmd`](mermaid/14_human_in_loop.mmd).

## Statuses

`CREATED → AUTHORIZED → PROCESSING → SUCCEEDED` on the happy path; branches to
`REQUIRES_USER_ACTION`, `FAILED`, `CANCELLED`.

## Components

- `payments.policy.PaymentPolicy.decide(...)` → `AUTO | REQUIRE_USER | BLOCK`
  using auto-pay limit, daily limit, trusted/blocked vendors, high-value
  categories (electronics always require approval).
- `payments.guard.run_transaction_guard(ctx)` → the final deterministic checks:
  vendor present, cart verified, positive amount, valid currency, item counts
  match, idempotency key present, and **within budget**. Any failure raises
  `TransactionGuardError` before authorization.
- `payments.provider` → `PaymentProvider` interface + `MockPaymentProvider`
  (sandbox, no real money). Real providers are the integration boundary.
- `payments.service.PaymentService` → orchestrates guard → policy → provider,
  backed by an `IdempotencyStore`.

## Idempotency (no double charge)

The idempotency key (`{request_id}:{checkout_id}`) is checked before processing;
a repeat returns the prior terminal intent with **zero** new attempts. The mock
provider is also idempotent at the authorize/capture level. Verified by a
property test over random keys/amounts.

## Secrets & the LLM

The LLM never receives card numbers, CVV, OTP, bank passwords, or keys
(spec section 20). Payment references are opaque tokens.

## Human-in-the-loop

Over-limit, untrusted vendor, high-value category, or auto-pay disabled →
`REQUIRES_USER_ACTION` with a `HumanCheckpointReason`. The orchestrator stops at
`PAYMENT_AUTH_REQUIRED` and surfaces what/why/amount/vendor to the user.

## Testing

`tests/unit/test_payments.py` (policy, guard, success, idempotency, HITL) and
`tests/property/test_financial_invariants.py` (idempotent single charge).
