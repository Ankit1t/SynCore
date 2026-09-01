# Scraping Architecture

## Purpose

Discover live product data resiliently and independently of the agent pipeline,
so a flaky source never destabilizes the platform.

## Pipeline

```
Scraping Orchestrator → Source Registry → Source Adapter → Fetcher (HTTP/Browser)
  → Parser → Normalizer → Validation → Product Event → Product Store / Search Index
```

Diagram: [`mermaid/05_scraping_pipeline.mmd`](mermaid/05_scraping_pipeline.mmd),
failure handling in [`mermaid/23_scraper_failure.mmd`](mermaid/23_scraper_failure.mmd).

## Decoupling

Scraping is a separate subsystem from the agent. In the MVP the
`MockMarketplace` returns already-normalized offers, but the real path is the
same interface (`BaseMarketplaceAdapter.search_products/get_product`), so the
agent never knows or cares whether data came from a mock, an official API, or a
permitted scrape.

## Robustness (spec section 11)

- retries with exponential backoff + jitter, per-request timeouts
- request throttling / rate limiting (`SCRAPER_RATE_LIMIT_PER_MIN`)
- circuit breakers per source; a tripped source is skipped, others continue
- selector fallback and **parser versioning** (`parser_version` on every offer)
- schema validation, stale-data + duplicate detection
- structured logs; screenshots / HTML snapshots on failure **where permitted**
- browser session recovery

A failing source yields partial results; the agent proceeds and the user is
informed rather than the whole request failing.

## Data quality (spec section 12)

Every record carries `source`, `source_id`, `extracted_at`, `parser_version`,
`confidence`, and raw/normalized status. `normalization.quality.validate_offer`
rejects/【flags impossible prices, missing quantity, invalid units, malformed
ratings, price > MRP, impossible discounts, unexpected currency. Scraped values
are never trusted blindly.

## Compliance

Respect each site's robots, terms, APIs, authentication boundaries, and rate
limits; prefer official APIs. Syncore does **not** implement CAPTCHA bypass or
anti-bot evasion. See [scraping_adapters](scraping_adapters.md).

## Testing

Adapter contract tests run against the mock; real adapters get their own
integration tests behind the `live` mode flag.
