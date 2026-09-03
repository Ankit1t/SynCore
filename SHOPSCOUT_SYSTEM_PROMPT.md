# SYSTEM PROMPT — BUILD "ShopScout"
## Amazon India Catalog Aggregator + ONDC-Ready Storefront (Portfolio Project)

> **How to use:** Paste this ENTIRE file as the first prompt into Cursor / Claude Code / Windsurf. It is fully self-contained. The AI should build everything in one autonomous run.

---

## 1. ROLE & MISSION

You are a senior full-stack engineer and data engineer. Build a complete, runnable, portfolio-quality project named **ShopScout** from this single specification. Work autonomously: scaffold the repo, implement every module, seed the database, and verify the app runs. Do not ask clarifying questions about anything already specified below. For anything not specified, make sensible production-quality choices and document them in the README.

**What ShopScout is:** a product discovery and deals platform for the Indian market with three integrated parts:

1. **Scraper (Python):** politely collects public catalog data from Amazon India (amazon.in) across selected verticals — Grocery & Packaged Foods, Electronics, and Personal Care & Home essentials. NOT the whole site — only these ~18 categories.
2. **Website (Next.js):** a fast storefront over the collected catalog — search, category browse, filters, deals page, rich product pages with offers and price history.
3. **ONDC Layer (TypeScript):** a Beckn-protocol-style adapter exposing the same catalog through ONDC buyer-app flows (search → select → init → confirm → status), sandbox-ready, running against the local catalog without external approvals.

**Intended use:** educational / portfolio demo to demonstrate scraping, data engineering, full-stack development, and open-e-commerce-network (ONDC/Beckn) skills. It is NOT a commercial service.

---

## 2. HARD CONSTRAINTS (non-negotiable)

1. **Polite crawling only:** respect robots.txt; randomized 2–5 s delay between requests; max 1 concurrent request to the domain; realistic browser User-Agent header; on HTTP 429/503 use exponential backoff (3 retries), and if a category stays blocked, skip it and continue — never hammer.
2. **Public catalog pages only.** No login-gated pages, no cart/checkout/wishlist actions, no account creation, no bypassing captchas (if a hard captcha appears, stop that category and log it).
3. **Defensive parsing:** every field extraction must have a chain of fallback CSS selectors; a missing field becomes `null`; one broken/odd product page must NEVER crash the run. Log every parse failure with the ASIN and URL to `scraper.log`.
4. **No secrets in code.** All configuration via `.env` (commit `.env.example` only).
5. **Attribution & disclaimer** in README and site footer: "Demo project for learning purposes. Product data and trademarks belong to their respective owners. Not affiliated with Amazon or ONDC."
6. Code quality: TypeScript strict mode, ESLint clean, typed Pydantic models in Python, no `any` where avoidable.

---

## 3. TECH STACK

| Layer | Choice |
|---|---|
| Scraper | Python 3.11+, httpx (async-capable client), BeautifulSoup4 (lxml parser), Playwright (headless fallback for blocked/JS-heavy pages), tenacity (retries), pydantic v2 (models), PyYAML (category config), SQLAlchemy + SQLite |
| Website | Next.js 14+ (App Router), TypeScript (strict), Tailwind CSS, shadcn/ui components |
| ONDC layer | TypeScript inside the Next.js app; @noble/ed25519 for Beckn-style request signing |
| Storage | SQLite (dev) via SQLAlchemy; scraper exports JSON; JSON feeds the web-app seed script; schema written so swapping to Postgres later is trivial |

Repo layout: a single repo with `scraper/` (Python package) and the Next.js app at root or in `web/` — choose the monorepo layout you consider cleanest and document it.

---

## 4. SCOPE — CATEGORIES (~18, configured, extensible)

Each category is one entry in `scraper/config/categories.yaml`:

```yaml
- name: "Rice & Staples"
  slug: rice-staples
  vertical: grocery            # grocery | electronics | personal-care
  url_template: "https://www.amazon.in/s?k={query}&page={page}"
  query: "rice daal atta staples"
  max_pages: 5
  active: true
```

**Grocery & Packaged Foods (9):** Rice & Staples · Dal & Pulses · Edible Oil & Ghee · Tea & Coffee · Juices & Soft Drinks · Snacks & Namkeen · Instant Foods (noodles/pasta/soups) · Chocolates & Confectionery · Ice Cream & Frozen Foods

**Electronics (7):** Mobiles · Mobile Accessories · Laptops · Headphones & Earbuds · Smartwatches & Wearables · TVs & Displays · Kitchen Appliances (mixer/OTG/kettle)

**Personal Care & Home (4):** Shampoo & Hair Care · Skin Care · Home & Floor Cleaners · Detergents & Dishwash

Target volume: 15–20 categories × ~5 listing pages × ~20–30 products ≈ **1,500–2,500 product records** per full run. One full polite run must finish in **under 30 minutes**.

---

## 5. DATA MODEL — scrape ALL of these fields where present

### ProductModel (Pydantic v2 / mirrored as TS interface)

```ts
{
  // identity
  asin: string            // primary key
  title: string
  brand: string | null
  category_slug: string
  vertical: "grocery" | "electronics" | "personal-care"
  product_url: string
  image_urls: string[]

  // pricing
  current_price: number | null      // normalized float (₹1,299.00 -> 1299.00)
  mrp: number | null                // list/strikethrough price
  currency: "INR"
  discount_percent: number | null   // computed: round((mrp-current)/mrp*100) when both exist

  // social proof
  average_rating: number | null     // 4.2
  review_count: number | null       // 18,430 -> 18430

  // offers & deals  (IMPORTANT - this is a headline feature)
  coupon_text: string[]             // e.g. "Save 10% with coupon"
  bank_offers: string[]             // e.g. "10% off with HDFC Credit Card"
  deal_type: "lightning_deal" | "deal_of_the_day" | "limited_time_deal" | "none"
  badge: "best_seller" | "amazons_choice" | null
  sponsored: boolean

  // availability & fulfillment
  in_stock: boolean
  delivery_info: string | null      // "FREE delivery Tomorrow 8 AM - 12 PM"
  sold_by: string | null            // seller name from merchant info
  return_policy: string | null

  // content
  description: string | null
  bullet_points: string[]           // About this item
  specs: Record<string, string>     // detail-bullets / tech-spec table as key-value
  variant_info: string | null       // e.g. "Pack of 2", "500g", colour/size variants count

  // meta
  price_history: { date: string; price: number | null }[]   // append on every run for same ASIN
  run_id: string          // identifies the scraping run
  scraped_at: string      // ISO timestamp
  updated_at: string
}
```

**Normalization rules:** strip `₹`, `,`, spaces from prices before parsing; `%` off computed not scraped; "out of 5 stars" parsed from rating strings; ratings/review counts may be null on some listing-only items — enrich them in the PDP phase.

---

## 6. SCRAPER ARCHITECTURE (`scraper/` Python package)

```
scraper/
  config/
    categories.yaml          # category definitions (section 4)
  models/
    product.py               # Pydantic v2 ProductModel + CategoryConfig
  core/
    http_client.py           # httpx client wrapper: UA rotation, rate limiter (2-5s), retry/backoff
    browser.py               # Playwright fallback: only used when httpx response looks blocked
                             # (captcha page, <200KB body, missing results markup)
    ratelimit.py             # token bucket, 1 concurrent request, jittered delays
  scrapers/
    listing.py               # Phase 1: category listing pages -> paginated ASIN + quick-field collection
    product.py               # Phase 2: per-ASIN PDP full parse -> ProductModel
    offers.py                # offer/coupon/bank-offer/deal extraction helpers
  pipelines/
    clean.py                 # price/rating normalization, dedupe by ASIN, merge price_history
    db.py                    # SQLAlchemy upsert (SQLite)
    export.py                # export to data/products.json + data/products.csv for the web seed
  run.py                     # CLI entrypoint
  scraper.log                # structured log: per-ASIN success/fail, per-category progress
```

**Two-phase design (mandatory):**
- **Phase 1 — Listing crawl:** for each active category, iterate pages (`&page=2,3...` until no results or `max_pages`), parse result cards for ASIN, title, thumbnail, price, rating, review count, badges, sponsored flag. Emit `candidates.jsonl`.
- **Phase 2 — Product crawl:** for each unique ASIN, fetch the PDP and fill ALL remaining fields (offers, coupons, bank offers, specs, bullets, description, delivery, seller, stock, images). Respect the global rate limiter across both phases.

**Selector hints for amazon.in (verify at runtime, keep fallback chains — Amazon changes markup):**
- Listing result card: `div[data-component-type="s-search-result"]` with attribute `data-asin`
- Title: `h2 a span` / `h2 span > span`; Price now: `span.a-price span.a-offscreen`; MRP: `span.a-price.a-text-price span.a-offscreen`
- Rating: `span.a-icon-alt` (text like "4.2 out of 5 stars"); review count: `.s-underline-text` / `aria-label` ending in "ratings"
- Badge: `.a-badge-text` or text "Best Seller"/"Amazon's Choice"; Deal: `.a-dealBadge`, "Limited time deal"/"Deal of the Day"
- PDP: title `#productTitle`; price `#corePriceDisplay_desktop_feature_div .a-offscreen` / `#priceblock_ourprice`; rating `#acrPopover .a-icon-alt`; reviews `#acrCustomerReviewText`; bullets `#feature-bullets li span`; description `#productDescription`; specs `#detailBullets_feature_div` + `#productDetails_techSpec_section_1` + `#prodDetails`; seller `#sellerProfileTriggerId` / `#merchant-info`; coupons/offers `#promoPriceBlockMessage_feature_div`; delivery `#deliveryBlockMessage` / `#mir-layout-DELIVERY_BLOCK`; availability `#availability`

**CLI:**
```bash
python -m scraper.run --list-categories
python -m scraper.run --vertical grocery --max-pages 5
python -m scraper.run --all --export        # full run + JSON/CSV export
python -m scraper.run --retry-failed        # re-run ASINs that failed last run
```

---

## 7. WEBSITE SPEC (Next.js 14+ App Router, TS strict, Tailwind + shadcn/ui)

**Pages:**
- `/` — hero with big search bar, vertical tabs (Grocery / Electronics / Personal Care), category grid, "Top Deals Today" carousel (discount_percent desc), "Trending" grid
- `/category/[slug]` — product grid + sidebar filters: price range (min/max inputs + presets), rating (3★+, 4★+, 4.5★+), discount (10%+, 25%+, 50%+), brand multi-select, in-stock toggle; sort dropdown: relevance, price ↑↓, discount, rating, review count; URL-search-params driven (shareable filter links); pagination
- `/product/[asin]` — image gallery + thumbnails, title, brand link, rating stars + review count, **price block (current price big, MRP strikethrough, % off pill)**, **offers box (coupons + bank offers + deal badge, green accent)**, delivery info + sold by + return policy, About-this-item bullets, specs table, **price-history sparkline chart** (recharts), similar-products row (same category)
- `/deals` — everything with deal_type != none or discount ≥ 25%, filter by deal type
- `/search?q=` — full-text search over title/brand (SQLite LIKE or FTS5), same filter UI as category
- Empty states, loading skeletons, error boundaries everywhere; fully mobile responsive

**API routes:** `GET /api/products` (filters, sort, pagination) · `GET /api/products/[asin]` · `GET /api/search?q=` · `GET /api/categories` · `GET /api/deals` · `GET /api/price-history/[asin]`

**Seed:** `npm run db:seed` imports `scraper/data/products.json` into the web DB. If the JSON is missing, seed with realistic sample data (≥100 fake products across all categories) so the site is demo-able even before scraping.

---

## 8. ONDC LAYER SPEC (`app/ondc/` + `lib/ondc/`)

Implement a **Beckn/ONDC buyer-app-style adapter** over the local catalog (mock network, real protocol shapes):

- `POST /ondc/search` — accept Beckn search intent (category descriptor, keywords, price range); respond with `on_search` catalog JSON (items mapped from local products: descriptor, price, category_id, location/provider)
- `POST /ondc/select` → `on_select` (quote with item + breakup), `POST /ondc/init` → `on_init` (mock billing/shipping), `POST /ondc/confirm` → `on_confirm` (create order, status=Accepted), `POST /ondc/status` → `on_status` (order state machine)
- Keep an in-memory/SQLite order store keyed by `transaction_id`; follow Beckn callback pattern (`/ondc/x` → `on_x`)
- **Request signing:** generate/load Ed25519 keys from env (`ONDC_SUBSCRIBER_ID`, `ONDC_UNIQUE_KEY_ID`, `ONDC_PRIVATE_KEY`); implement the ONDC authorization header pattern (digest + signature) and a `npm run ondc:keys` helper; verify signatures on incoming callbacks
- A `/ondc/docs` page (or README section) explaining: what ONDC is, buyer app vs seller app vs gateway vs registry, the full flow diagram, and **exact steps to register on the ONDC sandbox** (sandbox.ondc.org → participant onboarding → key exchange) and how this adapter would switch from mock to real gateway by changing base URL + env keys

---

## 9. BUILD ORDER & DEFINITION OF DONE

1. Scaffold repo + configs + models + empty tests
2. Scraper end-to-end for **2 categories** → verify rows in SQLite (`SELECT count(*)` proof in README)
3. All ~18 categories + export JSON/CSV + `retry-failed` working
4. Next.js site: seed + all pages + filters + product page + deals (pixel-clean, responsive)
5. ONDC adapter: full flow happy-path with signed requests + docs page
6. README (below) + final polish: loading states, empty states, footer disclaimer

**Definition of done:** `python -m scraper.run --all --export` completes politely and writes `data/products.json`; `npm i && npm run db:seed && npm run dev` serves a working site at localhost:3000 with real scraped data; every page has no console errors; `curl POST /ondc/search` returns a valid Beckn `on_search` payload.

---

## 10. README REQUIREMENTS

Must include, in this order: 1-line pitch + screenshots placeholder · architecture ASCII diagram (scraper → SQLite → JSON → Next.js → ONDC adapter) · setup steps (scraper + web) · `.env.example` with all vars · how-to-run commands · data dictionary for ProductModel · **Legal & Ethics section** (ToS/robots.txt reality, personal/educational use, production alternatives: Amazon PA-API / SP-API / official ONDC seller onboarding) · **ONDC section** (concept explainer + sandbox registration steps + flow diagram) · Known limitations · **Interview prep appendix:** 10 likely questions with strong answers (anti-bot handling, robots.txt stance, why two-phase crawl, price-history design, Beckn flow, ONDC vs Amazon marketplace model, scaling to 50k products with proxies, incremental vs full refresh, dedup strategy, legal way to commercialize).

---

## 11. TONE & WORKING STYLE FOR THE AI

- Build in the order of section 9; after each milestone, print a 5-line progress summary.
- Prefer complete, copy-pasteable files over fragments. No TODO leftovers.
- If amazon.in markup differs from the selector hints at runtime, adapt selectors automatically and record final working selectors in `scraper/config/selectors.yaml`.
- Optimize for interview storytelling: clean commits-style milestones, observable logs, and a README an interviewer can skim in 3 minutes.

