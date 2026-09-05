"""Facilitator configuration.

Loaded from a JSON file (env FACILITATOR_CONFIG, default
./data/facilitator_config.json) with env-var overrides. Written by
scripts/seed.py, but sensible defaults let the service boot standalone.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULTS = {
    "facilitator_id": "facil_001",
    "bank_url": "http://localhost:8003",
    # resource path -> category, so the policy engine can enforce mandate
    # categories. The frozen Invoice/Intent formats carry no category field, so
    # the facilitator owns this mapping (see DECISIONS.md). Keyed by URL *path*
    # so it is host-agnostic (localhost vs 127.0.0.1 vs a real domain).
    "resource_categories": {
        "/api/summarize": "content",
        "/api/search": "search",
    },
    # Velocity: max settled txns per mandate within a rolling window.
    "velocity_max_txn": 20,
    "velocity_window_seconds": 60,
    # Bank HTTP timeout (seconds). A blown timeout maps to bank_timeout.
    "bank_timeout_seconds": 5.0,
}


def config_path() -> str:
    default = Path(__file__).resolve().parent.parent / "data" / "facilitator_config.json"
    return os.environ.get("FACILITATOR_CONFIG", str(default))


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = config_path()
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    # env overrides
    cfg["facilitator_id"] = os.environ.get("FACILITATOR_ID", cfg["facilitator_id"])
    cfg["bank_url"] = os.environ.get("BANK_URL", cfg["bank_url"])
    return cfg


def category_for(cfg: dict, resource: str) -> str:
    """Map a resource URL to a category by its path (host-agnostic)."""
    from urllib.parse import urlparse
    mapping = cfg.get("resource_categories", {})
    path = urlparse(resource).path or resource
    # Support both path keys ("/api/x") and full-URL keys for back-compat.
    return mapping.get(path) or mapping.get(resource, "uncategorized")
