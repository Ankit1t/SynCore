# SYNCCORE — Agent Financial Control Plane (Zone 1)

Implementation of the **Frozen Architecture Blueprint v1.0** (Office of the
Principal Architect, 31 Aug 2026). This is the defensible wedge that survives
the blueprint's commoditization kill‑list: the integrated, provable system that
converts a user's **signed delegation** into a **cryptographically bound,
policy‑checked, auditable** transaction — on rails SYNCCORE never owns.

> SYNCCORE's product is not moving money. It is making delegated money **provable**.

This package delivers **Phase 0** (skeleton + invariants) and **Gate G1a**
(authority + policy + the 19‑attack red team green against a mock provider) from
the 90‑day plan. It needs **no payment partner** and **no infrastructure** to run.

## Run it

Requires **Node ≥ 22.6** (uses native TypeScript type‑stripping — no build, no
`npm install` for the runtime).

```bash
cd control-plane
node src/demo.ts     # end-to-end ALLOW + DENY + duplicate-submit drill
node --test          # 52 tests: Gate G0 + Gate G1a
# optional static type-check (installs typescript):
npm install && npm run typecheck
```

The demo reproduces the blueprint's two worked examples (6.1): INR 427 at a named
grocery merchant → **ALLOW** → executed → 6‑event proof bundle; INR 4270 at an
unknown electronics merchant → **DENY** at `MERCHANT_SCOPE`.

## The three zones (Blueprint 5)

```
Zone 0  Untrusted reasoning (LLM, connectors, unbounded text)
          │  may only emit a typed PaymentIntentProposal
          ▼  ── the one payment door ──
Zone 1  Control plane (THIS package): deterministic authority
          Delegation · Binding · CAN_PAY() · Risk · Ledger/Proof · Broker · Recon
          │  execute only on ALLOW + consumed single-use nonce
          ▼
Zone 2  Execution (PSP / rails / merchants) behind adapters — bought, never built
```

The LLM never decides authorization (**D5**); `CAN_PAY()` is deterministic code
that fails closed. Secrets (UPI PIN, CVV, PAN, OTP/AFA, private keys) never enter
Zone 0 (**B3**).

## The surviving wedge (W1–W7) → where it lives

| # | Component | Module |
|---|-----------|--------|
| W1 | Verifiable delegation chain (signed, versioned artifact) | `src/delegation/service.ts` |
| W2 | Deterministic policy gate — 12 checks, fixed order, fail‑closed | `src/policy/canPay.ts` |
| W3 | Cryptographic transaction binding (cart hash + nonce + Ed25519) | `src/crypto/binding.ts` |
| W4 | Agent identity & key custody (Ed25519, non‑exportable) | `src/crypto/keys.ts` |
| W5 | Agentic risk signals v0 (injection / velocity / amount) | `src/risk/engine.ts` |
| W6 | Reconciliation of UNKNOWN (worker‑owned promotion) | `src/recon/worker.ts` |
| W7 | Hash‑chained proof bundle (dispute evidence per rupee) | `src/ledger/audit.ts` |
| — | The one payment door (wiring) | `src/controlPlane.ts` |
| — | Payment state machine (UNKNOWN never executes) | `src/statemachine/payment.ts` |
| — | Broker orchestrator + mock PSP | `src/broker/*` |

## CAN_PAY() — the 12 checks (Table 6.1)

Evaluated in this fixed order; **first non‑PASS wins** (an attacker learns only
the earliest failing rule); unclassifiable ⇒ **DENY**.

1. `AUTH_IDENTITY` · 2. `DELEGATION_STATE` · 3. `TIME_WINDOW` · 4. `MERCHANT_SCOPE`
· 5. `CATEGORY_SCOPE` · 6. `PER_TX_LIMIT` · 7. `VELOCITY` · 8. `PRICE_DRIFT`
· 9. `CART_BINDING` · 10. `CONFIRMATION` (→ CHALLENGE) · 11. `RISK_GATE`
(HIGH→DENY, MEDIUM→CHALLENGE) · 12. `NONCE_FRESH`.

## Freeze decisions honored (Table 1.1)

| ID | Decision | How this code honors it |
|----|----------|--------------------------|
| D1 | Kill OTP/PIN/AFA automation | No OTP/PIN anywhere; secrets never modeled in Zone 0/1 payloads |
| D2 | No public protocol; internal adapter contract only | Message shapes are internal types in `src/domain/types.ts` |
| D3 | Build the control plane; buy execution as adapters | `ProviderAdapter` interface; `MockProvider` now, real PSPs later |
| D4 | Freeze stack: TS/Node, Postgres, Redis, KMS Ed25519 | TS/Node here; in‑memory stores mirror Postgres/Redis/KMS semantics |
| D5 | LLM never authorizes; `CAN_PAY()` deterministic | Pure function, no model/network calls |
| D6 | No real money until the red‑team suite is green | Mock provider only; `node --test` = 19 attacks, zero spends |
| D7 | Technology service provider; never touch funds flow | No aggregation/settlement/custody; we prove authority only |
| D8 | Agent Financial Control Plane, grocery‑first | Default delegation is the grocery artifact from 6.0 |

## Gates verified

- **G0** — `test/statemachine.test.ts` (machine total, no skip transitions,
  UNKNOWN never executes, terminals terminal, audit event per transition) and
  `test/ledger.test.ts` (chain verifies; tampering detected at its seq).
- **G1a** — `test/canpay.test.ts` (all 12 checks fire correctly, first‑failure
  wins) and `test/redteam.test.ts` (19 attacks → zero successful spends) and
  `test/idempotency.test.ts` (duplicate/timeout drills → exactly one or zero
  charges, never two).

## Integration boundary (not built here — by design)

Per the blueprint's honesty discipline, these are interfaces/stubs, not fakes:

- **Real PSP adapters** (Razorpay AutoPay first — verification V4; then P3P — V1;
  ReservePay — V2) implement `ProviderAdapter`. Only the broker holds their creds.
- **Production stores**: Postgres 16 + Prisma (unique constraints for the
  idempotency triad) and Redis 7 (nonce registry, revocation cache) replace the
  in‑memory stores without changing the control‑plane logic.
- **Cloud KMS** replaces the in‑memory `KeyService` so agent private keys are
  non‑exportable.
- **WebAuthn** replaces the simulated `UserPasskey` for the real signing ceremony.

## Relationship to the Python app (`../src/syncore`)

The existing Python FastAPI project is a **Zone 0** artifact: the shopping
"brain" that understands a request, searches, ranks, and optimizes a basket —
i.e. it *proposes*. This control plane is **Zone 1**: it takes a typed proposal
and decides whether money may move, then proves it. In the target system the
shopping agent would emit a `PaymentIntentProposal` into this control plane's one
door; nothing the agent says can move a rupee without passing `CAN_PAY()`.
