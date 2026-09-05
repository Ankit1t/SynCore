# SynCore — Autonomous AI Shopping Assistant

SynCore turns **one natural-language instruction** (English or Hinglish, e.g.
_"₹500 ke andar 1kg aloo, 100g mirch aur 2 Maggi order kar"_) into an optimized,
budget-guarded, **real-data** order — understood, built, reviewed, paid from a
prepaid wallet, and receipted. It is engineered like a real product: a
**deterministic core** owns money, budgets and state; the **LLM only
understands language**. It never touches arithmetic, budget verdicts or payment.

## 🔴 Live demo

| | URL |
|---|---|
| **App (frontend)** | **https://syn-core-zrja.vercel.app** |
| **API (backend)** | https://syncore-api.onrender.com · [`/docs`](https://syncore-api.onrender.com/docs) |

> The backend is on a free tier and sleeps when idle — the **first request can
> take ~50s** to wake, then it's fast. Send one query to warm it up.

Try: `weekly grocery for a family under 1000` · `2 mega pack maggi and a coke under 250`
· `a bluetooth speaker and a phone charger under 3000` · `order some food for dinner under 500`

---

## What it does (one instruction → done)

```
Instruction ─▶ Understand ─▶ Match real offers ─▶ Build basket ─▶ Budget guard
           ─▶ Self-review + confidence ─▶ Auto-pay from wallet ─▶ Order ID + PDF receipt
```

## Features built

**🧠 Understanding (any item, any language)**
- English + Hinglish, typos, Hindi numerals; not limited to a grocery lexicon —
  electronics, snacks, personal care, meals ("food for dinner") all work.
- **Variant-lock (anti "silent-downgrade"):** ask for a _mega pack_ and it won't
  quietly order a regular pack; ask generically and it picks the cheapest
  sensible option (a plain Type-C charger, not a pricey branded one).

**🌐 Live, real product data (not hard-coded)**
- **Live mode** fetches real, currently-listed products with **live prices,
  ratings and images** at request time via **SerpApi (Google Shopping)** — real
  availability, no stale data. Falls back to a demo API when no key is set.
- **Curated catalog** of real Indian brands (Amul, Maggi, Tata, boAt, …) plus
  **real Amazon products extracted from captured browsing (HAR)** — with image
  galleries, highlights, specifications and real ratings.
- Toggle **Live data** on/off in the header.

**🛒 Product detail (click any item)**
- Image **showcase gallery**, **highlights**, **specifications** table, and
  **rating + reviews** — view-only (reviewing never affects your order/payment).

**💰 Budget guard + confidence**
- Hard budget ceiling — never checks out over budget; reduces quantities or
  drops non-essentials to fit, or asks with concrete options.
- Every basket gets a **confidence score + self-review** (variant / price /
  rating / budget hard-rules) → decides AUTO / notify / ask.

**👛 Prepaid wallet + payments (real gateway, test mode)**
- **Prepaid wallet** (UPI-Lite style): top up once, then orders **auto-settle
  from the wallet — no payment step per order**. Fully automated checkout.
- Top-up uses **real Razorpay (test mode)** — no real money, signature-verified.

**🧾 Order receipts**
- Every order gets a unique **Order ID** (`SYN-YYYYMMDD-XXXXXX`) and a
  **downloadable PDF receipt** (itemized, total, payment method, wallet balance).
- An **Orders** page lists past orders.

**🎨 UI**
- Premium animated dashboard (sidebar history, chat composer, basket panel with
  budget progress bar), **dark/light mode**, built with Next.js + Tailwind +
  Framer Motion.

**🧪 Also in the app (experimental modules)**
- **AgentGuard / agentic checkout** — an AP2-style deterministic `CAN_PAY` gate
  for autonomous payment authorization.
- **Merchant demo**, plus **audit** and **control** views for observing agent
  activity and mandates.

---

## Architecture

```
NL request ─▶ Intent (LLM or deterministic) ─▶ Match offers (live / catalog / estimate)
   ─▶ Variant-aware selection ─▶ Basket build ─▶ Budget guard ─▶ Confidence + self-review
   ─▶ Wallet settlement ─▶ Order + receipt
```

- **Deterministic (LLM-free, tested):** budget engine, basket math, variant
  selection, confidence hard-rules, wallet ledger, order/receipt, orchestrator
  state machine. Money is integer-precise; the LLM never does arithmetic.
- **Probabilistic edge:** intent extraction. Providers are pluggable via
  `LLM_PROVIDER` — **Groq** (`openai/gpt-oss-120b`, default in prod), Gemini,
  OpenAI-compatible, Ollama, or a deterministic fallback that needs no key.
- **Offer sources are pluggable:** live (SerpApi) · curated catalog · market
  estimate. Designed to swap in **ONDC / retailer / PA-API** without touching
  the agent.

## Tech stack

- **Backend:** Python, FastAPI, Pydantic (deployed on Render)
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Framer
  Motion, lucide-react, jsPDF (deployed on Vercel)
- **LLM:** Groq / Gemini / OpenAI-compatible (pluggable)
- **Live data:** SerpApi (Google Shopping)
- **Payments:** Razorpay (test mode) + prepaid wallet

---

## Run locally (Windows / PowerShell)

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn syncore.api.app:app --reload --port 8000
.\.venv\Scripts\python.exe -m pytest -p no:warnings      # tests

# Frontend (separate terminal)
cd web
npm install
npm run dev            # http://127.0.0.1:3000  (proxies /api/* to :8000)
```

No keys needed to run: the deterministic provider works offline, LIVE mode
falls back to a demo API, and the wallet works in-memory. Add keys for the full
experience (below).

## Environment / keys (optional, for full features)

Set on the backend (Render dashboard or local env):

| Key | Purpose |
|---|---|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | Real understanding (e.g. `groq` / `openai/gpt-oss-120b`) |
| `SERPAPI_KEY` | Real live product data (Google Shopping) |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Wallet top-up via Razorpay **test** keys |

## Deployment

- **Backend → Render** (Blueprint from `render.yaml`): `autoDeploy` on push to `main`.
- **Frontend → Vercel** (root = `web/`): auto-deploys on push to `main`; the
  production backend URL is baked into `next.config.mjs` (no env var needed).

---

## Honest notes

- **Live data** reflects real current listings at fetch time; the agent picks
  the cheapest live listing. SerpApi free tier is ~100 searches/month.
- **Payments** run in Razorpay **test mode** (no real money). Order fulfilment
  by a real retailer would use that retailer's order API / ONDC — that's the
  production plug, implemented as a clean boundary.
- Prices marked _"est."_ are market estimates for items not in the catalog.
- Data extracted from HAR is the user's own captured browsing, used to build a
  representative catalog — not live scraping of third-party sites.

## Project structure

```
src/syncore/        # backend: master_agent (intent, catalog, live_offers,
                    #          confidence), api routes, wallet, orders, payments
web/                # Next.js frontend (dashboard, wallet, product modal, orders)
scripts/            # HAR extractor, Kaggle catalog importer
tests/              # unit / property / e2e / integration
docs/               # architecture docs + mermaid diagrams
```

## License

MIT. Reference implementation / portfolio project.
