"""SQLite storage for the facilitator (own DB file)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def db_path() -> str:
    default = Path(__file__).resolve().parent.parent / "data" / "facilitator.db"
    return os.environ.get("FACILITATOR_DB", str(default))


def connect() -> sqlite3.Connection:
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(
            """
            -- Facilitator's own signing keypair (one row). Generated on first boot.
            CREATE TABLE IF NOT EXISTS facilitator_key (
                facilitator_id  TEXT PRIMARY KEY,
                signing_key_hex TEXT NOT NULL,
                verify_key_hex  TEXT NOT NULL
            );

            -- Registered agents + their Ed25519 public keys (set at onboarding).
            CREATE TABLE IF NOT EXISTS agents (
                agent_id   TEXT PRIMARY KEY,
                pubkey_hex TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            -- Replay guard. A nonce is INSERTed BEFORE the bank debit (crash-safe).
            CREATE TABLE IF NOT EXISTS nonces (
                nonce      TEXT PRIMARY KEY,
                agent_id   TEXT NOT NULL,
                mandate_ref TEXT,
                created_at TEXT NOT NULL
            );

            -- Issued receipts, retrievable by nonce for lost-response recovery.
            CREATE TABLE IF NOT EXISTS receipts (
                nonce         TEXT PRIMARY KEY,
                status        TEXT NOT NULL,        -- settled | reversed | rejected
                amount_paise  INTEGER NOT NULL,
                utrn          TEXT,
                settled_at    TEXT,
                agent_id      TEXT,
                mandate_ref   TEXT,
                resource      TEXT,
                receipt_json  TEXT NOT NULL,
                signature     TEXT NOT NULL,
                created_at    TEXT NOT NULL
            );

            -- Every decision (pass or reject) at each pipeline step, with reason + ts.
            CREATE TABLE IF NOT EXISTS decision_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                nonce     TEXT,
                agent_id  TEXT,
                step      TEXT NOT NULL,
                decision  TEXT NOT NULL,           -- pass | reject | info
                reason    TEXT,
                ts        TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
