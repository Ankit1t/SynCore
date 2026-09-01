# Database Schema

## Purpose

Persist requests, agent runs, orders, payments, audit and scraper health, with
UUID keys, timestamps, indexes and tenant scoping.

## Engine

SQLAlchemy 2.0. Default `sqlite:///./syncore.db` for zero-setup; set
`DATABASE_URL=postgresql+psycopg://...` for Postgres (docker-compose `full`
profile). `init_db()` creates tables for dev; production uses migrations.

Diagram: [`mermaid/22_data_lifecycle.mmd`](mermaid/22_data_lifecycle.mmd).

## Tables (`syncore.db.tables`)

| Table | Key columns | Notes |
|---|---|---|
| `users` | id, email(uniq), role | tenant root |
| `user_preferences` | user_id(pk), data(json) | brands, rating, substitution |
| `shopping_requests` | id, user_id, raw_text, budget_limit, data(json) | full request in JSON |
| `agent_runs` | id, request_id, user_id, state, checkpoint_reason, error, basket(json) | observability |
| `agent_steps` | id, run_id(fk), idx, state, message, data(json) | ordered timeline |
| `agent_decisions` | id, run_id(fk), kind, summary, evidence(json) | explainability |
| `orders` | id, user_id, request_id, marketplace, vendor, total, status, external_order_id, items(json) | |
| `payment_intents` | id, user_id, amount, vendor, idempotency_key(uniq), status | dedupe by key |
| `payment_attempts` | id, intent_id(fk), status, provider_reference | |
| `audit_events` | id, event, user_id, run_id, payload(json) | immutable-by-convention |
| `scraping_sources` | name(pk), healthy, supports_live, last_run_at | |
| `scraping_runs` | id, source, status, offers_found, error | |
| `system_errors` | id, code, message, details(json) | |

## Design choices

- **UUID string** primary keys.
- Scalar columns for fields we query/aggregate; rich nested structures (basket,
  order items, evidence) as JSON to avoid premature over-normalization while
  staying Postgres/SQLite portable.
- Indexes on `user_id`, `state`, `status`, `idempotency_key`, event/run ids.
- Unique constraint on `payment_intents.idempotency_key`.
- Canonical relational data stays the source of truth; JSON blobs are
  derived/denormalized views.

## Retention

Logs, scraped snapshots, agent traces, and audit/payment records follow the
retention policy in [deployment](deployment.md) (spec section 69); avoid storing
sensitive data unnecessarily.
