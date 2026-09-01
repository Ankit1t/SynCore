# KIRANA Phase 2 — Completion Report

Autonomous commerce + delegated-payment control plane, built on the existing
Phase‑1 codebase. Phase‑1 preserved (60 tests still green); Phase‑2 adds 28
tests → **88 passing**.

## Data flow (implemented)

```
USER NL -> Intent (master_agent) -> Real discovery (OpenFoodFacts, live)
  -> Normalization -> Priced cart (integer paise) -> Budget on FINAL total
  -> Delegation -> PaymentIntent (+cart_hash binding) -> RiskEngine
  -> PolicyEngine.CAN_PAY (12 checks, fail-closed) -> PaymentBroker (only executor)
  -> Provider (mock sandbox / Razorpay-when-credentialed) -> SUCCESS|FAILED|UNKNOWN
  -> Reconciliation (UNKNOWN) -> Order verification -> Receipt
```

## Trust boundaries (STEP 43/44)

`UNTRUSTED marketplace/web + LLM  |  application services  |  PolicyEngine +
PaymentBroker (financial control plane)  |  provider  |  network`. A lower-trust
component never controls a higher-trust one. The LLM proposes/plans; only the
broker executes; `CAN_PAY` is deterministic code.

## What runs today (no credentials, no real money)

- Real product metadata via OpenFoodFacts (verified live).
- Integer-paise money end to end; budget enforced on final checkout total.
- Delegation + spending limits (per‑txn / daily / monthly), category/merchant
  scope, expiry, revoke, pause/resume, **kill switch**.
- `CAN_PAY` 12-check gate (identity, state, purpose, merchant, category, currency,
  cart_hash binding, per‑txn, daily, monthly, risk) → ALLOW / DENY /
  REQUIRES_USER_AUTHORIZATION.
- Risk engine (injection / cart‑change / velocity / amount anomaly).
- Broker with idempotency, PAYMENT_UNKNOWN + reconciliation (never blind retry),
  refund path.
- Webhook signature + timestamp + replay protection.
- Order verification separate from payment; receipt from verified records.

## Integration boundaries (credentials required — never faked)

| Capability | Requirement |
|---|---|
| Live retail price/cart/checkout/order (Amazon/Flipkart/Zepto/BigBasket/Blinkit) | partner/official API credentials |
| Real payment execution (Razorpay) | `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (sandbox first) |
| WebAuthn user signing ceremony | passkey infra (TS control-plane has the reference) |

See `provider_capabilities.md` and `config/providers/`.

## Run

```powershell
# tests (Phase 1 + Phase 2)
.\.venv\Scripts\python.exe -m pytest -p no:warnings

# end-to-end demo (the ₹500 order, 19 steps)
.\.venv\Scripts\python.exe -m syncore.scripts.phase2_e2e

# API (adds /api/v1/delegations, /payment-intents, /payments, /agent/pause-payments,
#      /webhooks/payments, /marketplace/search, /marketplace/providers)
.\.venv\Scripts\python.exe -m uvicorn syncore.api.app:app --port 8000
```

## Known limitations

- No live Indian retail pricing (no legitimate free source without partnership);
  priced path uses the deterministic mock marketplace, clearly labeled.
- OFF free-text search is 503-rate-limited; barcode lookup is the reliable path.
- Phase‑2 in-process services are the runtime source of truth; delegations and
  transactions are also persisted to the DB (best-effort mirror).
- Razorpay adapter is structurally complete but not executed without credentials.
