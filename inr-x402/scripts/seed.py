"""Seed the demo: keys, agent onboarding, and a UPI-Autopay-style mandate.

Assumes the mock bank (8003) and facilitator (8002) are already running.
Talks to both ONLY over HTTP (like any onboarding tool would). Writes:
  data/agent_config.json         (agent identity + signing key + budget)
  data/facilitator_config.json   (resource->category map + bank url + limits)

Run:  python -m scripts.seed
"""
from __future__ import annotations

import json
import os
from datetime import timedelta
from pathlib import Path

import httpx

from shared.crypto import generate_keypair
from shared.models import now_utc, iso
from facilitator.config import DEFAULTS as FAC_DEFAULTS

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

BANK_URL = os.environ.get("BANK_URL", "http://localhost:8003")
FACILITATOR_URL = os.environ.get("FACILITATOR_URL", "http://localhost:8002")
MERCHANT_BASE = os.environ.get("MERCHANT_PUBLIC_BASE", "http://localhost:8001")
AGENT_ID = os.environ.get("AGENT_ID", "agent_001")


def main() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)

    # 1) Write the facilitator config file (resource->category map, bank url).
    fac_cfg = dict(FAC_DEFAULTS)
    fac_cfg["bank_url"] = BANK_URL
    with open(DATA / "facilitator_config.json", "w", encoding="utf-8") as f:
        json.dump(fac_cfg, f, indent=2)

    # 2) Generate the agent's Ed25519 keypair.
    signing_key_hex, verify_key_hex = generate_keypair()

    with httpx.Client(timeout=10.0) as c:
        # 3) Onboard a bank user with the default ₹10,000 balance.
        user = c.post(f"{BANK_URL}/onboard", json={"user_id": f"user_{AGENT_ID}"}).json()

        # 4) Create a UPI-Autopay-style e-mandate scoped to 'content'/'search'.
        expires_at = iso(now_utc() + timedelta(days=30))
        mandate = c.post(
            f"{BANK_URL}/mandates",
            json={
                "user_id": user["user_id"],
                "per_txn_max_paise": 100,       # ₹1.00 per call
                "daily_max_paise": 5000,        # ₹50.00 per day
                "categories": ["content", "search"],
                "expires_at": expires_at,
            },
        ).json()

        # 5) Register the agent's public key with the facilitator.
        c.post(
            f"{FACILITATOR_URL}/admin/agents",
            json={"agent_id": AGENT_ID, "pubkey_hex": verify_key_hex},
        ).raise_for_status()

    # 6) Persist the agent config (identity, key, mandate, local budget).
    agent_cfg = {
        "agent_id": AGENT_ID,
        "signing_key_hex": signing_key_hex,
        "mandate_ref": mandate["mandate_token"],
        "merchant_base": MERCHANT_BASE,
        "budget_paise": 5000,   # agent's own spend cap for the demo (₹50)
        "receipts_path": str(DATA / "agent_receipts.jsonl"),
    }
    with open(DATA / "agent_config.json", "w", encoding="utf-8") as f:
        json.dump(agent_cfg, f, indent=2)

    summary = {
        "agent_id": AGENT_ID,
        "user_id": user["user_id"],
        "balance_paise": user["balance_paise"],
        "mandate_ref": mandate["mandate_token"],
        "per_txn_max_paise": mandate["per_txn_max_paise"],
        "daily_max_paise": mandate["daily_max_paise"],
        "categories": mandate["categories"],
        "agent_config": str(DATA / "agent_config.json"),
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
