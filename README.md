# Syncore — AI Shopping & Procurement Agent

Syncore turns a natural-language shopping request (including Hinglish, e.g.
_"₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar"_) into an
optimized, budget-guarded, executed order. It is engineered as a real SaaS
platform, not a chatbot: a **deterministic core** owns money, budgets,
idempotency and state; a **probabilistic edge** handles language and semantic
matching. The LLM never touches arithmetic, budget verdicts, payment
authorization or database integrity.

This repository is a **Phase-1 vertical slice** that runs end-to-end today
against a deterministic mock marketplace, plus the full architecture (adapters,
provider abstractions, state machine) ready for real integrations.

---

## What works right now

Run this and watch the whole pipeline execute:

```
USER: ₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar.

[00] REQUEST_RECEIVED       Request received.
[01] INTENT_PARSED          Understood 3 item(s): 1kg potato, 100g green chilli, 2 pieces maggi. Budget ₹500.
[02] PLAN_CREATED           Built plan with 3 search queries.
[03] SEARCHING              Searching marketplaces...
[04] DISCOVERING_PRODUCTS   Discovered 16 offers across 2 source(s).
[05] NORMALIZING            Normalized offers; rejected 0 low-quality record(s).
[06] RANKING                Ranked candidate offers by explainable score.
[07] OPTIMIZING             Optimized basket at basket-level economics.
[08] BASKET_READY           Basket ready. Total ₹89.24. within budget (₹410.76 remaining).
[09] BROWSER_SESSION_STARTED Started isolated browser session on mock-fresh.
[10] CART_BUILDING          Building cart...
[11] CART_VERIFIED          Cart verified: 3 line(s), subtotal ₹84.24.
[12] CHECKOUT_READY         Final checkout total ₹89.24 ... within budget.
[13] PAYMENT_PENDING        Preparing payment...
[14] PAYMENT_PROCESSING     Payment authorized and captured: ₹89.24 to mock-fresh.
[15] ORDER_PLACED           Order placed: ORD-XXXXXXXX.
[16] ORDER_VERIFICATION     Order status: CONFIRMED.
[17] COMPLETED              Done. Order confirmed, total ₹89.24, ETA ~120 min.
```

A tight budget (e.g. `order 2 maggi and 1kg rice under 100`) correctly stops at
`USER_REVIEW_REQUIRED` with **no order placed** — a hard budget is never
silently exceeded.

---

## Prerequisites

- Python 3.11+ (tested on 3.13)
- Node.js 18.17+ (only for the Next.js UI; the API also ships a zero-Node demo UI)
- Optional: Docker + Docker Compose

No API keys are required: the default `LLM_PROVIDER=deterministic` runs fully
offline and the default `DATABASE_URL` is SQLite.

---

## Quickstart (Windows / PowerShell)

```powershell
# 1. Create a virtualenv and install the backend (editable + dev extras)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 2. Run the whole pipeline from the CLI (no server needed)
.\.venv\Scripts\python.exe -m syncore.scripts.vertical_slice
# ...or pass your own request:
.\.venv\Scripts\python.exe -m syncore.scripts.vertical_slice "1kg aloo, 500g onion, 2 maggi under 250"

# 3. Create tables + seed a demo order (optional)
.\.venv\Scripts\python.exe -m syncore.scripts.manage seed

# 4. Run the API (serves REST + SSE + a demo UI at http://127.0.0.1:8000/)
.\.venv\Scripts\python.exe -m uvicorn syncore.api.app:app --reload --host 127.0.0.1 --port 8000

# 5. Run the tests
.\.venv\Scripts\python.exe -m pytest -p no:warnings
```

## Quickstart (macOS / Linux)

```bash
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip && pip install -e ".[dev]"

python -m syncore.scripts.vertical_slice
uvicorn syncore.api.app:app --reload --host 127.0.0.1 --port 8000
pytest -p no:warnings
```

### Frontend (Next.js)

```bash
cd web
npm install
# optional: cp .env.local.example .env.local   (defaults to http://127.0.0.1:8000)
npm run dev          # http://127.0.0.1:3000  (proxies /api/* to the API)
```

The API must be running for the UI to work. If you don't want to run Node,
just open **http://127.0.0.1:8000/** — the API serves an equivalent live demo UI.

### Docker

```bash
docker compose up --build              # API :8000 + Web :3000 (SQLite, no infra)
docker compose --profile full up       # + Postgres :5432 + Redis :6379
```

---

## API

Interactive docs (OpenAPI) at `http://127.0.0.1:8000/docs`. Key endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET  | `/health`, `/health/live`, `/health/ready` | Probes |
| POST | `/api/v1/shopping-requests` | Parse a request into structured items + budget |
| GET  | `/api/v1/shopping-requests/{id}` | Fetch a parsed request |
| POST | `/api/v1/shopping-requests/{id}/execute` | Run the agent for a saved request |
| GET  | `/api/v1/shopping-requests/stream/live?text=...` | **SSE** live agent run |
| POST | `/api/v1/baskets/optimize` | Parse + optimize only (Phase-1 brain, no execution) |
| GET  | `/api/v1/products/search?q=aloo` | Search offers |
| GET  | `/api/v1/orders`, `/api/v1/orders/{id}` | Orders |
| GET  | `/api/v1/agent-runs`, `/api/v1/agent-runs/{id}` | Agent observability |
| GET  | `/api/v1/admin/metrics`, `/api/v1/admin/scraping-health`, `/api/v1/admin/feature-flags` | Admin |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/baskets/optimize \
  -H "content-type: application/json" \
  -d '{"text":"₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi"}'
```

---

## How it fits together

```
NL request -> Intent -> Plan -> Discover (marketplace adapters) -> Normalize
   -> Rank -> Optimize basket -> Budget guard -> Browser cart build
   -> Cart verify -> Final total re-extract -> Budget re-guard -> Checkout
   -> Payment (policy + idempotency + human-in-loop) -> Order verify -> Persist
```

- **Deterministic** (tested, LLM-free): units/conversion, normalization, budget
  engine, basket optimizer, payment policy, final transaction guard,
  idempotency, orchestrator state machine.
- **Probabilistic edge**: intent (deterministic regex + lexicon by default; LLM
  optional), semantic ranking hints, explanations. Swap providers via
  `LLM_PROVIDER`.
- **Marketplace** is abstracted behind `BaseMarketplaceAdapter` + a registry.
  `MockMarketplace` ships two storefronts with different delivery economics so
  the optimizer makes real basket-level trade-offs. Real adapters are the
  **integration boundary** (`MARKETPLACE_MODE=live`).
- **Browser** execution is abstracted behind `BrowserExecutor`; the mock
  executor verifies cart state after every action. `PlaywrightExecutor` is the
  Phase-2 boundary.

See [`docs/`](docs/) for architecture, security, payments, scraping, and
Mermaid diagrams in [`docs/mermaid/`](docs/mermaid/).

---

## Safety & scope

- Hard budgets are never intentionally exceeded; the final checkout price is
  re-validated before any payment.
- Payments over the auto-pay limit, or to untrusted vendors, stop at a secure
  human-in-the-loop checkpoint. Idempotency keys prevent double charges.
- The system does **not** bypass authentication, MFA, CAPTCHA, anti-bot
  controls, or perform unauthorized transactions. Where legitimate verification
  is required, it pauses for the user.
- Live marketplace/payment integrations are implemented as interfaces and are
  clearly marked as the integration boundary; they are not faked.

## Project structure

```
src/syncore/        # backend package (domain, services, api)
web/               # Next.js frontend
tests/             # unit, property, e2e, integration
docs/              # architecture docs + docs/mermaid diagrams
docker-compose.yml Dockerfile Makefile .env.example
```

## License

MIT (see pyproject). This is a reference implementation / MVP.
