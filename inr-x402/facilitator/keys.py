"""Facilitator keypair + agent registry (persisted in the facilitator DB)."""
from __future__ import annotations

from typing import Optional

from shared.crypto import generate_keypair
from shared.models import now_utc, iso
from facilitator import db


def ensure_facilitator_key(facilitator_id: str) -> dict:
    """Return the facilitator keypair, generating + persisting it on first boot."""
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT * FROM facilitator_key WHERE facilitator_id = ?", (facilitator_id,)
        ).fetchone()
        if row:
            return dict(row)
        sk, vk = generate_keypair()
        conn.execute(
            "INSERT INTO facilitator_key(facilitator_id, signing_key_hex, verify_key_hex) VALUES (?, ?, ?)",
            (facilitator_id, sk, vk),
        )
        conn.commit()
        return {"facilitator_id": facilitator_id, "signing_key_hex": sk, "verify_key_hex": vk}
    finally:
        conn.close()


def register_agent(agent_id: str, pubkey_hex: str) -> dict:
    conn = db.connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO agents(agent_id, pubkey_hex, created_at) VALUES (?, ?, ?)",
            (agent_id, pubkey_hex, iso(now_utc())),
        )
        conn.commit()
    finally:
        conn.close()
    return {"agent_id": agent_id, "pubkey_hex": pubkey_hex}


def get_agent_pubkey(agent_id: str) -> Optional[str]:
    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT pubkey_hex FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        return row["pubkey_hex"] if row else None
    finally:
        conn.close()
