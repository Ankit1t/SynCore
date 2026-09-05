"""SQLite storage for the mock bank.

Own DB file (env MOCK_BANK_DB, default ./data/mock_bank.db). A fresh connection
per operation keeps things simple for the prototype's low concurrency.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def db_path() -> str:
    default = Path(__file__).resolve().parent.parent / "data" / "mock_bank.db"
    return os.environ.get("MOCK_BANK_DB", str(default))


def connect() -> sqlite3.Connection:
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id       TEXT PRIMARY KEY,
                balance_paise INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mandates (
                mandate_token     TEXT PRIMARY KEY,
                user_id           TEXT NOT NULL,
                per_txn_max_paise INTEGER NOT NULL,
                daily_max_paise   INTEGER NOT NULL,
                categories        TEXT NOT NULL,   -- JSON array
                expires_at        TEXT NOT NULL,   -- ISO8601
                created_at        TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            -- Double-entry ledger. Each debit/reversal writes two rows
            -- (a credit and a debit) that net to zero across the system.
            CREATE TABLE IF NOT EXISTS ledger (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                from_acct    TEXT NOT NULL,
                to_acct      TEXT NOT NULL,
                amount_paise INTEGER NOT NULL,
                nonce        TEXT,
                utrn         TEXT,
                ts           TEXT NOT NULL,
                type         TEXT NOT NULL         -- debit | credit | reversal
            );

            -- Idempotency store: same idempotency_key -> same stored response,
            -- so a debit is NEVER applied twice.
            CREATE TABLE IF NOT EXISTS debit_idempotency (
                idempotency_key TEXT PRIMARY KEY,
                response_json   TEXT NOT NULL,
                created_at      TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
