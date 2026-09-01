# ADR 0003: SQLite by default, Postgres-ready

- Status: Accepted
- Date: 2026-08-29

## Context

The spec calls for PostgreSQL, but a one-command local run and fast CI are also
required. Forcing Postgres for the vertical slice adds friction that conflicts
with "make the project runnable" and "don't over-engineer before the slice
works".

## Decision

Use SQLAlchemy 2.0 with a `DATABASE_URL` default of SQLite. Provide Postgres via
`docker compose --profile full`. Schema uses portable types (JSON columns, UUID
string keys) so switching engines is a config change. Dev uses `create_all`;
production adopts Alembic migrations.

## Consequences

- `pip install -e . && uvicorn ...` runs with zero infra.
- CI is fast and hermetic (temp SQLite).
- Postgres-specific features (e.g. `pgvector`) are opt-in at the integration
  stage without reworking the models.
