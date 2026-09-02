"""LLM-based intent extraction.

Turns ANY natural-language request into structured items — not limited to the
built-in grocery lexicon. So "2 tubs of vanilla ice cream and a bluetooth
speaker under 3000" works just like "1kg aloo". The LLM only *understands*;
prices/budget math stay deterministic in agent.py.

Returns None on any failure so the caller falls back to the deterministic parser
(the system never crashes if the LLM is down or misconfigured).
"""

from __future__ import annotations

import json
import re
from typing import Any

SYSTEM = (
    "You are an intent parser for an autonomous shopping agent. "
    "Extract exactly what the user wants to buy. Reply with ONLY a JSON object — "
    "no explanation, no markdown, no code fences."
)


def _prompt(text: str) -> str:
    return (
        f'User request: "{text}"\n\n'
        "Return a JSON object with this shape:\n"
        "{\n"
        '  "budget_inr": <number or null>,   // total spending cap in INR if the user gave one\n'
        '  "items": [\n'
        "    {\n"
        '      "name": "<product name>",\n'
        '      "quantity": <number or null>,\n'
        '      "unit": "kg" | "g" | "l" | "ml" | "piece" | "pack" | "dozen" | null,\n'
        '      "category": "<short category, e.g. grocery, dairy, snacks, electronics, frozen>",\n'
        '      "unit_price_inr": <realistic current Indian retail price for ONE unit/kg/pack, a number>\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Include EVERY item the user mentions, including non-grocery items "
        "(electronics, ice cream, household, etc.). If a quantity/unit is not "
        "stated, use null.\n\n"
        "If the user describes a MEAL, OCCASION, or a vague CATEGORY instead of "
        "naming exact products (e.g. \"food for dinner\", \"party snacks\", "
        "\"something to cook\", \"breakfast items\", \"stuff for a road trip\"), "
        "infer 3-6 concrete, realistic products that together satisfy it. Pick "
        "sensible staples for that meal/occasion in the Indian context (e.g. "
        "dinner -> rice, dal, a vegetable, roti/atta). If a budget is given, "
        "keep the inferred selection reasonable for it.\n\n"
        "Only return an empty items list when the request names nothing that "
        "could be turned into products at all (e.g. \"buy me something\", "
        "\"order anything\"). Otherwise always return at least one item. Never "
        "invent items that contradict what the user asked for."
    )


def _extract_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    # Strip code fences if the model added them despite instructions.
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _num(v: Any) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None  # reject NaN
    except (TypeError, ValueError):
        return None


def _pos(v: Any) -> float | None:
    f = _num(v)
    return f if (f is not None and f > 0) else None


def extract_intent(text: str, provider: Any) -> dict[str, Any] | None:
    """Return {'budget_inr': float|None, 'items': [...]} or None on failure."""
    try:
        out = provider.generate(_prompt(text), system=SYSTEM, max_tokens=2048).text
    except Exception:  # noqa: BLE001 - network/provider errors -> fall back
        return None

    data = _extract_json(out)
    if not data:
        return None
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return None

    items: list[dict[str, Any]] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        if not name:
            continue
        items.append({
            "name": name[:80],
            "quantity": _num(it.get("quantity")),
            "unit": (str(it.get("unit")).strip().lower() if it.get("unit") else None),
            "category": (str(it.get("category")).strip() if it.get("category") else None),
            "unit_price_inr": _pos(it.get("unit_price_inr")),
        })
    if not items:
        return None
    return {"budget_inr": _num(data.get("budget_inr")), "items": items}
