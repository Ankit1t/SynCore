"""Persistence layer (SQLAlchemy 2.0).

Defaults to SQLite for zero-setup local runs; set DATABASE_URL to a
postgresql+psycopg:// URL for Postgres. Canonical product data stays
relational; the ORM tables here mirror a subset of the domain models needed
for the vertical slice and observability.
"""
