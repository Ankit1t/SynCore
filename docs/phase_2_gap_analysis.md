# KIRANA Phase 2 — Gap Analysis

Assessment of the existing codebase against the Phase 2 objective (autonomous
commerce + delegated payments on real data). Verified by inspection + a live
network probe on 2026-09-01.

## Environment reality check (verified, not assumed)

| Data source | Probe result | Verdict |
|---|---|---|
| Outbound HTTPS | works | usable |
| OpenFoodFacts product-by-barcode (`/api/v2/product/<code>.json`) | HTTP 200, real JSON (e.g. "Nutella", brand "Ferrero") | **REAL, no key** — usable for product metadata |
| OpenFoodFacts search (`/api/v2/search`) | HTTP 503 (anti-abuse/availability) | intermittently restricted → circuit-break + barcode-lookup fallback |
| Amazon / Flipkart / Zepto / BigBasket / Blinkit price+cart+order APIs | no public API; site automation violates ToS/anti-bot | **ACCESS_RESTRICTED** — adapter + exact credential required, never faked |
| Live Indian retail prices/availability (free, legitimate) | none exists without partnership | prices come from mock/estimate; clearly labeled non-live |

Honest conclusion: **real product metadata** is available (OFF) and integrated;
**live retail pricing/cart/checkout/order/payment** requires partner credentials
we do not have, so those are production-grade adapters that return
`PROVIDER_ACCESS_RESTRICTED` until credentials exist, with the deterministic mock
marketplace + mock/sandbox payment provider as the runnable path (freeze D6: no
real money until sandbox red-team is green).

## Component-by-component

| Component | Current state (Phase 1) | Production readiness | Missing | Required change | Priority |
|---|---|---|---|---|---|
| Intent / master agent | Deterministic Hinglish parser + master_agent JSON contract | Good | multilingual breadth | keep; reuse | P3 |
| Marketplace | sync `BaseMarketplaceAdapter` + `MockMarketplace` (2 storefronts) | Dev-only | real adapters, capability matrix, resilient async fetcher, provider status | add async provider layer + OFF real adapter + restricted stubs | P1 |
| Normalization | `normalizer` + `quality` (units, canonical, validation) | Good | map real adapter output | reuse; add adapter→canonical mapping | P2 |
| Budget engine | `check_budget` (float) | OK | integer paise, final-total basis | add paise money; enforce on final checkout total | P1 |
| Optimizer | `BasketOptimizer` (basket-level economics) | Good | — | reuse | P3 |
| Payment (Phase 1) | `PaymentPolicy` (vendor/limit), `guard`, `PaymentProvider`+mock, `PaymentService` (idempotent) | Partial | delegation, spending limits, risk, cart binding, UNKNOWN+reconcile, webhooks, broker-as-only-executor | extend into delegated control plane | P1 |
| Delegation / AuthorizationPolicy | none in Python (TS control-plane has W1–W7) | Missing | full domain + service + DB + limits + revoke/pause | build in Python, wired to app | P1 |
| Policy engine `CAN_PAY` | vendor-level `decide()` only | Partial | delegation-aware, integer paise, cart_hash, daily/monthly, ALLOW/DENY/REQUIRES_USER_AUTHORIZATION | build `PolicyEngine.can_pay` | P1 |
| Risk engine | none in Python | Missing | deterministic LOW/MED/HIGH | build `RiskEngine` | P1 |
| Payment broker | none (PaymentService executes) | Missing | single financial execution boundary | build `PaymentBroker` | P1 |
| Provider adapters | mock only | Partial | capability discovery, Razorpay/P3P stubs + sandbox config | add + config/providers | P2 |
| Idempotency | in-memory in PaymentService | Partial | DB unique constraint | add table + unique key | P2 |
| UNKNOWN + reconciliation | none | Missing | first-class state + worker | build | P1 |
| Webhooks | none | Missing | signature+timestamp+dedupe+replay | build verifier + endpoint | P2 |
| Order verification / receipt | `OrderManager` verifies totals | Partial | payment≠order separation, receipt from verified data | extend | P2 |
| DB | SQLAlchemy (SQLite default), tables for intents/attempts/orders/audit | Good | delegations, payment_transactions, payment_events, risk_decisions | add tables + repos | P1 |
| API | health/shopping/products/orders/agent-runs/admin/agent | Good | delegations, payment-intents, payments, kill switch, webhook, marketplace search/status | add routers | P1 |
| Observability / audit | structured logging + AuditEvent + metrics | Good | payment/authorization metrics | extend | P3 |
| Tests | 60 pytest green (Phase 1) | Good | Phase 2 unit + red-team + E2E | add; keep Phase 1 green | P1 |
| TS control-plane | 52 tests green (W1–W7 reference) | Reference | not wired to FastAPI app | keep as Zone-1 reference spec | — |

## Strategy

1. Add integer-paise money and Phase-2 enums without touching Phase-1 float paths.
2. Add an async marketplace provider layer (capability-declaring) beside the
   Phase-1 sync mock; integrate OFF as the one real data source.
3. Extend `payments/` into a delegated control plane (delegation, risk, policy
   `CAN_PAY`, binding, broker, reconciliation, webhooks) — additive, Phase-1
   `PaymentService` untouched.
4. Wire endpoints + persistence + tests + E2E; keep the 60 Phase-1 tests green.
5. Mark every credentialed integration as `ACCESS_RESTRICTED` with the exact
   requirement; never fabricate provider behavior.
