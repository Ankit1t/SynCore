"""LLM-powered master agent: ANY item (not just grocery) lands in the basket."""

from __future__ import annotations

import json

from syncore.llm.provider import DeterministicProvider, LLMResult, LLMUsage
from syncore.master_agent.agent import decide


class FakeLLM:
    """Stand-in for a real provider (Gemini/Groq/Ollama) returning canned JSON."""

    name = "fake-llm"

    def __init__(self, payload: str) -> None:
        self._payload = payload

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 800) -> LLMResult:
        return LLMResult(text=self._payload, usage=LLMUsage("fake", "fake", 0, 0, 0.0, 0.0))

    def classify(self, text, labels):  # pragma: no cover
        return labels[0]

    def embed(self, text):  # pragma: no cover
        return []


def test_non_grocery_items_go_into_basket_via_llm():
    payload = json.dumps({
        "budget_inr": 3000,
        "items": [
            {"name": "vanilla ice cream", "quantity": 2, "unit": "pack",
             "category": "frozen", "unit_price_inr": 120},
            {"name": "bluetooth speaker", "quantity": 1, "unit": "piece",
             "category": "electronics", "unit_price_inr": 1499},
        ],
    })
    r = decide("order 2 tubs of vanilla ice cream and a bluetooth speaker under 3000",
               "NONE", provider=FakeLLM(payload))

    names = [ln["satisfies"] for ln in r["basket"]["lines"]]
    assert any("ice cream" in n for n in names), names
    assert any("speaker" in n for n in names), names
    # exact integer-ish math: 2*120 + 1*1499
    assert r["basket"]["total"] == 1739
    assert r["understanding"]["budget_inr"] == 3000
    assert r["budget_check"]["within_budget"] is True
    assert r["next_action"] == "PROCEED_TO_CHECKOUT"
    # created (estimated) products are flagged, never presented as real offers
    assert all(ln["estimated"] for ln in r["basket"]["lines"])


def test_llm_budget_guard_still_enforced_for_any_item():
    payload = json.dumps({
        "budget_inr": 1000,
        "items": [{"name": "gaming mouse", "quantity": 1, "unit": "piece",
                   "category": "electronics", "unit_price_inr": 2500}],
    })
    r = decide("buy a gaming mouse under 1000", "NONE", provider=FakeLLM(payload))
    # single item over budget -> cannot fit -> asks the user (never silently over)
    assert r["budget_check"]["within_budget"] is False
    assert r["next_action"] == "ASK_USER"


def test_deterministic_fallback_still_works_without_llm():
    r = decide("1kg aloo, 2 maggi under 500", "NONE", provider=DeterministicProvider())
    names = {ln["satisfies"] for ln in r["basket"]["lines"]}
    assert "potato" in names and "maggi" in names
    assert r["next_action"] == "PROCEED_TO_CHECKOUT"
