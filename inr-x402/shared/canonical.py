"""Canonical JSON encoding.

Signatures are computed over bytes, so every service MUST serialize the exact
same way or verification will fail. We freeze the rules here:

  - keys sorted lexicographically
  - no insignificant whitespace  (separators=(",", ":"))
  - UTF-8 output
  - ensure_ascii=False so non-ASCII payloads hash identically everywhere

Anything that gets signed goes through canonical_bytes().
"""
from __future__ import annotations

import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Return the canonical string form of a JSON-serializable object."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    """Return canonical UTF-8 bytes to be signed / verified."""
    return canonical_json(obj).encode("utf-8")
