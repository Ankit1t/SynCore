# Deployment

## Purpose

Run Syncore locally, in staging, and in production with health/readiness probes.

## Local (no containers)

```
pip install -e ".[dev]"
uvicorn syncore.api.app:app --reload   # API + demo UI on :8000
cd web && npm install && npm run dev   # UI on :3000 (proxies to API)
```

## Docker Compose

```
docker compose up --build            # api :8000 + web :3000 (SQLite)
docker compose --profile full up     # + Postgres :5432 + Redis :6379
```

- `Dockerfile` builds the API on `python:3.12-slim`, runs as a non-root user,
  and defines a `HEALTHCHECK` hitting `/health/live`.
- `web/Dockerfile` is a multi-stage Next.js build → `npm run start`.
- Compose services declare healthchecks; `postgres`/`redis` are gated behind the
  `full` profile so the base stack needs no infra.

## Configuration

All via environment (see `.env.example`). Production must set `DATABASE_URL`
(Postgres), real provider keys if used, and `ENVIRONMENT=production` (which
tightens CORS). Never commit secrets; use a secret manager.

## Health / readiness / liveness

`/health` (db + marketplaces summary), `/health/ready` (db connectivity),
`/health/live` (process up). Wire these to your orchestrator (K8s
readiness/liveness probes, ALB health checks).

## Migrations

Dev uses `init_db()` (create-all) via `python -m syncore.scripts.manage migrate`.
Production should adopt Alembic migrations (the schema is stable and ready for
it).

## Kubernetes / Helm (future)

The container + probes are K8s-ready. A Helm chart would template the API
Deployment/Service, the web Deployment/Service, and Postgres/Redis (or managed
equivalents). Not built for the 1-week MVP to avoid over-engineering.

## Retention

Define TTL/rotation for logs, scraped snapshots, agent traces, and audit/payment
records per policy; avoid retaining sensitive data unnecessarily.
