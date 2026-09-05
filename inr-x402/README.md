# INR-x402 — Agentic Micropayment Protocol (INR / mocked Indian rails)

An HTTP-native micropayment protocol for autonomous AI agents, inspired by
Coinbase's x402 and adapted to INR with a UPI-Autopay-style mandate model. The
bank is fully mocked, but the code is structured so the single `bank.debit()`
boundary can later be swapped for a real UPI Autopay charge API.

> Hackathon prototype. Quality bar: working demo, clean protocol, correct
> security primitives — not a production bank integration.

---

## Architecture

```
                 ┌─────────────────────────────────────────────────────────────┐
                 │                        INR-x402                               │
                 └─────────────────────────────────────────────────────────────┘

   ┌─────────┐   1. GET /api/summarize (no X-PAYMENT)      ┌──────────────────┐
   │         │ ──────────────────────────────────────────► │                  │
   │         │   2. 402 + Invoice JSON                      │     MERCHANT     │
   │         │ ◄────────────────────────────────────────── │   :8001          │
   │  AGENT  │                                              │  price config +  │
   │  (CLI)  │   3. GET again + X-PAYMENT: base64(intent,   │  middleware      │
   │         │      signature, agentId)                     │                  │
   │ Ed25519 │ ──────────────────────────────────────────► │                  │
   │  signs  │                                              └───────┬──────────┘
   │ intent  │                                                      │ 4. POST /settle
   │         │                                                      ▼
   │         │                                              ┌──────────────────┐
   │         │                                              │   FACILITATOR    │
   │         │                                              │   :8002 (PRODUCT)│
   │         │                                              │                  │
   │         │                                              │ pipeline:        │
   │         │                                              │  signature →     │
   │         │                                              │  agent →         │
   │         │                                              │  mandate →       │
   │         │                                              │  per-txn →       │
   │         │                                              │  daily cap →     │
   │         │                                              │  category →      │
   │         │                                              │  velocity →      │
   │         │                                              │  replay →        │
   │         │                                              │  intent expiry → │
   │         │                                              │  [persist nonce] │
   │         │                                              │  bank debit      │
   │         │                                              └───────┬──────────┘
   │         │                                                      │ 5. POST /debit
   │         │                                                      │  (idempotency_key = nonce)
   │         │   6. 200 + data + X-PAYMENT-RESPONSE (receipt)       ▼
   │         │ ◄──────────────────────────────────────────  ┌──────────────────┐
   └─────────┘   (settle FIRST, deliver SECOND)             │    MOCK BANK     │
        │                                                   │    :8003         │
        │  persists every receipt to a local JSONL          │  mandates +      │
        └── agent_receipts.jsonl                            │  double-entry    │
                                                            │  ledger +        │
                                                            │  idempotent      │
                                                            │  debit +         │
                                                            │  FAIL_RATE       │
                                                            └──────────────────┘

   shared/  = canonical JSON + Ed25519 sign/verify + protocol models (the only
              thing services share in-process; they otherwise talk ONLY over HTTP)
```

Key ordering rule: **settle first, deliver content second** (bank debits are
fallible — the opposite of crypto x402 where settlement is atomic).

---

## Quick start

```bash
# from the inr-x402/ folder
make install     # create venv + install deps  (Windows: python -m venv venv; ...)
make demo        # boot all services, seed, run the happy path end-to-end
make test        # run the pytest suite (unit + the 6 scenarios)
```

On Windows without `make`:

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m scripts.run_demo      # or: scripts\demo.ps1
venv\Scripts\python.exe -m pytest -q
```

`make demo` prints the happy path, a second purchase, receipt recovery, a
reversal, and the resulting double-entry bank ledger.

---

## Running the services manually

Each service is its own uvicorn app. Pin `127.0.0.1` to avoid Windows
`localhost`→IPv6 delays.

```bash
venv/Scripts/python.exe -m uvicorn mock_bank.app:app    --host 127.0.0.1 --port 8003
venv/Scripts/python.exe -m uvicorn facilitator.app:app  --host 127.0.0.1 --port 8002
venv/Scripts/python.exe -m uvicorn merchant.app:app     --host 127.0.0.1 --port 8001
venv/Scripts/python.exe -m scripts.seed                 # after all 3 are up
```

Then drive the autonomous agent:

```bash
venv/Scripts/python.exe -m agent.cli pay --resource /api/summarize
venv/Scripts/python.exe -m agent.cli pay --resource /api/search --times 3
venv/Scripts/python.exe -m agent.cli pay --resource /api/summarize --simulate-timeout
venv/Scripts/python.exe -m agent.cli balance
```

---

## curl walkthrough

### 1. Ask for a paid resource with no payment → 402 + Invoice

```bash
curl -i http://127.0.0.1:8001/api/summarize
```

```
HTTP/1.1 402 Payment Required
{"scheme":"inr-x402","resource":"http://127.0.0.1:8001/api/summarize",
 "pricePaise":50,"payTo":"merchant_demo",
 "facilitatorUrl":"http://127.0.0.1:8002","expiresAt":"<ISO8601>"}
```

### 2. Onboarding (done by scripts/seed.py, shown here as curl)

```bash
# a user with ₹10,000
curl -s -XPOST http://127.0.0.1:8003/onboard \
  -H 'content-type: application/json' -d '{"user_id":"user_agent_001"}'

# a UPI-Autopay-style e-mandate (₹1/txn, ₹50/day, content+search)
curl -s -XPOST http://127.0.0.1:8003/mandates \
  -H 'content-type: application/json' \
  -d '{"user_id":"user_agent_001","per_txn_max_paise":100,
       "daily_max_paise":5000,"categories":["content","search"],
       "expires_at":"2099-01-01T00:00:00+00:00"}'

# register the agent public key with the facilitator
curl -s -XPOST http://127.0.0.1:8002/admin/agents \
  -H 'content-type: application/json' \
  -d '{"agent_id":"agent_001","pubkey_hex":"<agent ed25519 pubkey>"}'
```

### 3. Pay (the signed step)

The `X-PAYMENT` header is `base64(json({intent, signature, agentId}))` where
`intent` is a canonical-JSON `PaymentIntent` signed with the agent's Ed25519
key. Building this by hand is impractical, so the agent CLI does it:

```bash
venv/Scripts/python.exe -m agent.cli pay --resource /api/summarize
```

A successful call returns `200`, the resource data, and an `X-PAYMENT-RESPONSE`
header carrying the facilitator-signed `Receipt`.

### 4. Recover a lost receipt / reverse within 10 minutes

```bash
curl -s http://127.0.0.1:8002/receipt/<nonce>
curl -s -XPOST http://127.0.0.1:8002/reverse \
  -H 'content-type: application/json' -d '{"nonce":"<nonce>"}'
```

### 5. Inspect the double-entry ledger

```bash
curl -s "http://127.0.0.1:8003/ledger?nonce=<nonce>"
```

---

## Frozen formats

**Invoice (402 body)**

```json
{"scheme":"inr-x402","resource":"http://localhost:8001/api/summarize",
 "pricePaise":50,"payTo":"merchant_demo",
 "facilitatorUrl":"http://localhost:8002","expiresAt":"<ISO8601>"}
```

**PaymentIntent (signed with canonical JSON: sorted keys, no whitespace)**

```json
{"nonce":"<uuid4>","resource":"...","amountPaise":50,"payTo":"merchant_demo",
 "mandateRef":"mdt_...","agentId":"agent_001",
 "issuedAt":"<ISO8601>","expiresAt":"<ISO8601>"}
```

**Receipt (facilitator-signed)**

```json
{"nonce":"...","status":"settled|reversed|rejected","amountPaise":50,
 "utrn":"BK012345678901","settledAt":"<ISO8601>","facilitatorId":"facil_001"}
```

**Reject codes** (always machine-readable): `bad_signature`, `unknown_agent`,
`mandate_not_found`, `mandate_expired`, `over_per_txn_limit`, `over_daily_cap`,
`category_blocked`, `velocity_exceeded`, `replay_detected`, `intent_expired`,
`bank_declined`, `bank_timeout`.

---

## Reliability rules (and where they live)

| Rule | Where |
|------|-------|
| Nonce persisted BEFORE the bank debit (crash-safe) | `facilitator/engine.py` — `_persist_nonce` before `bank.debit` |
| Bank `idempotency_key` == intent nonce | `facilitator/engine.py` — `self.bank.debit(..., nonce)` |
| Receipt recovery for lost responses | `GET /receipt/{nonce}` + agent `_poll_receipt` |
| 10-minute reversal window, idempotent | `facilitator/engine.py` — `reverse()` |
| Every rejection returns a machine-readable code | `shared/reject_codes.py`, `_reject()` |
| Intent expiry (5 min) invalidates stale intents | `PaymentIntent.is_expired`, pipeline step 9 |

---

## The six demo scenarios (`make test`)

1. **Happy path** — 402 → signed intent → 200 + data + valid signed receipt.
2. **Policy reject** — amount over the mandate per-txn limit → `over_per_txn_limit`.
3. **Replay** — the same signed intent twice → second is `replay_detected`.
4. **Bank decline** — `FAIL_RATE=1.0` → agent retries once, degrades gracefully.
5. **Reversal** — settle then reverse in window; ledger shows a reversal row;
   the second reverse is a no-op.
6. **Recovery** — drop the 200 response; recover the receipt via
   `GET /receipt/{nonce}` with no double charge.

---

## Swapping the mock bank for real UPI Autopay

The entire mock lives behind **one function**:

```python
# mock_bank/bank.py
def debit(mandate_token: str, amount_paise: int, idempotency_key: str) -> dict:
    """Returns {status, utrn, balance_after, reason?}."""
```

To go live, replace the body of `debit()` with a real UPI Autopay recurring
charge call, keeping the same signature and return contract:

- Map your `mandate_token` to the PSP's mandate/UMN reference.
- Call the PSP's *recurring debit / execute mandate* API for `amount_paise`.
- Return `status="settled"` with the PSP's transaction reference as `utrn` on
  success, or `status="declined"` with a `reason` on failure.
- Keep passing `idempotency_key` (the intent nonce) to the PSP's idempotency
  mechanism so retries never double-charge. If the PSP lacks native
  idempotency, retain the existing `debit_idempotency` table as the guard.

Nothing else changes: the facilitator already talks to the bank purely over
HTTP (`facilitator/bank_client.py`), so only the bank's internal `debit()`
implementation is swapped. Mandate creation (`POST /mandates`) similarly maps to
the PSP's e-mandate registration flow.

---

## Layout

```
inr-x402/
├── agent/          # autonomous CLI client (sign intents, retry, recover, log)
├── merchant/       # paywalled demo API + x402 payment middleware  (:8001)
├── facilitator/    # verify + policy engine + nonce + settle + reverse (:8002)
├── mock_bank/      # mandates + double-entry ledger + idempotent debit  (:8003)
├── shared/         # canonical JSON + Ed25519 + protocol models
├── scripts/        # seed.py, run_demo.py, demo.sh, demo.ps1
├── tests/          # pytest: unit + the 6 scenarios (real HTTP stack)
├── Makefile
├── DECISIONS.md
└── README.md
```
