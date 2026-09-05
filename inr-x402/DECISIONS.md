# DECISIONS.md

Every ambiguity resolved while building INR-x402, with the reasoning. These are
prototype decisions, not production mandates.

## Protocol / pipeline

1. **Signature vs agent-registration ordering.** The spec lists checks as
   `signature -> agent registered -> ...`. Ed25519 verification requires the
   agent's registered public key, so the key lookup must physically precede the
   cryptographic verify. Resolution:
   - `intent.agentId != claimed agentId` -> `bad_signature`.
   - registered agent + bad signature -> `bad_signature` (at the signature step).
   - unknown agent (no key on file) -> `unknown_agent` (at the agent step).
   The externally observable reject codes still match the spec; only the
   internal evaluation order is adjusted out of cryptographic necessity.

2. **Category source.** The frozen `Invoice` and `PaymentIntent` formats carry
   no category field, yet the mandate is category-scoped. Decision: the
   facilitator owns a `resource -> category` map (in its config). It is keyed by
   URL **path** (e.g. `/api/summarize`), so the check is host-agnostic
   (`localhost` vs `127.0.0.1` vs a real domain all resolve identically).
   Unknown paths map to `uncategorized` and are blocked unless the mandate
   explicitly allows that category.

3. **Daily cap accounting.** The facilitator computes the daily cap as the sum
   of today's (UTC) `settled` receipts for the mandate plus the current amount,
   compared against the mandate's `daily_max_paise`. Reversed receipts are not
   counted as spend.

4. **Velocity definition.** "Velocity" is implemented as: at most
   `velocity_max_txn` settle attempts per mandate within a rolling
   `velocity_window_seconds` window (defaults 20 / 60s). It counts persisted
   nonces (i.e. attempts that reached the debit stage), so a burst of attempts
   is throttled regardless of outcome.

5. **Nonce persist point.** The spec requires the nonce to be persisted BEFORE
   the bank debit. The replay check (SELECT) runs at its ordered position; the
   nonce INSERT happens immediately after the intent-expiry check and right
   before the debit. Trade-off: a tiny race window exists between the SELECT and
   INSERT (acceptable for a single-node prototype; a real deployment would use a
   unique-constraint insert or a transaction). Because nonces are per-intent
   UUIDs, burning a nonce on an expired/failed attempt is harmless — the agent
   always mints a fresh nonce on retry.

6. **Declined debits do not produce a signed receipt.** A `Receipt` is proof of
   settlement, so only `settled`/`reversed` states are stored and retrievable
   via `GET /receipt/{nonce}`. Declines are recorded in the facilitator
   `decision_log` and returned inline as `bank_declined`. Consequently the
   recovery endpoint only ever surfaces genuinely settled payments.

7. **Bank decline vs bank timeout.** A structured decline from the bank maps to
   `bank_declined`. An actual HTTP timeout talking to the bank maps to
   `bank_timeout` (raised as `BankTimeout` in the bank client). The agent
   retries `bank_declined` once with a fresh nonce; on a post-submit network
   timeout it first polls `GET /receipt/{nonce}` to see whether the debit
   actually landed before retrying (no double charge).

## Services / infrastructure

8. **Facilitator owns its own keypair.** Rather than injecting the facilitator
   signing key via seed, the facilitator generates and persists its Ed25519
   keypair on first boot and exposes the public half at
   `GET /facilitator/pubkey`, so agents can verify receipts. Agent public keys
   are registered at onboarding via `POST /admin/agents`.

9. **Mandates live in the bank.** The mandate is a UPI-Autopay-style e-mandate,
   so it is issued and stored by the mock bank. The facilitator fetches mandate
   details over HTTP (`GET /mandates/{token}`) at settle time. This keeps the
   "bank owns money + mandates" boundary clean.

10. **Runtime failure-rate hook.** `POST /admin/failrate` lets the demo/tests
    flip `FAIL_RATE` without restarting the bank. The RNG is seeded
    (`FAIL_SEED`, default 42) for deterministic declines.

11. **Idempotency stores all outcomes.** The bank's idempotency table caches the
    full response (settled *or* declined) per `idempotency_key`, so any replay
    of the same key returns the identical result and never moves money twice.
    Reversals reuse the same table keyed by `rev_<nonce>`.

12. **127.0.0.1 pinning.** Inter-service URLs are pinned to `127.0.0.1` in the
    test harness and demo. On Windows, `localhost` can resolve to `::1` first
    while uvicorn binds IPv4, adding multi-second connect stalls. Code defaults
    still use `localhost` for readability.

13. **Local budget is agent-side only.** The agent tracks a local
    `budget_paise` and refuses to sign an intent that exceeds it (pre-flight,
    before any network spend). This is independent of the mandate limits the
    facilitator enforces. Reversals are not credited back to the local budget in
    this prototype (kept simple; the ledger is the source of truth for money).

14. **Testing strategy.** The 6 scenarios run against the real 3-service stack
    booted as uvicorn subprocesses and driven over HTTP — faithful to
    "services talk ONLY over HTTP". Unit tests cover the shared crypto/canonical
    layer directly.

15. **Timestamps.** All timestamps are timezone-aware UTC ISO-8601. Invoice TTL
    and intent TTL are both 300s; the reversal window is 600s.

16. **`on_event('startup')`.** FastAPI's deprecated `on_event` hook is used for
    brevity to initialize the DB/keypair. A production build would use the
    lifespan context manager.
