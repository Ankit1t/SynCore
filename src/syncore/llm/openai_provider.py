"""Optional OpenAI-backed provider (requires `pip install syncore[llm]`).

This is the "real adapter" for the LLMProvider interface. It is only imported
when LLM_PROVIDER=openai and an API key is configured, so the base install
stays dependency-free and offline-capable.
"""

from __future__ import annotations

import time

from ..config import get_settings
from .provider import COST_TRACKER, LLMResult, LLMUsage

# Rough public price references (USD per 1K tokens) for cost tracking only.
_PRICES = {
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4o": (0.005, 0.015),
}


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        from openai import OpenAI  # imported lazily

        settings = get_settings()
        self._client = OpenAI(api_key=settings.llm_api_key)
        self._model = settings.llm_model

    def _cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        pin, pout = _PRICES.get(self._model, (0.0, 0.0))
        return round(prompt_tokens / 1000 * pin + completion_tokens / 1000 * pout, 6)

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 512) -> LLMResult:
        start = time.perf_counter()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self._model, messages=messages, max_tokens=max_tokens, temperature=0.2
        )
        text = resp.choices[0].message.content or ""
        pt = getattr(resp.usage, "prompt_tokens", 0)
        ct = getattr(resp.usage, "completion_tokens", 0)
        usage = LLMUsage(self.name, self._model, pt, ct,
                         (time.perf_counter() - start) * 1000, self._cost(pt, ct))
        COST_TRACKER.record(usage)
        return LLMResult(text=text, usage=usage)

    def classify(self, text: str, labels: list[str]) -> str:
        prompt = f"Classify the text into exactly one label from {labels}.\nText: {text}\nLabel:"
        return self.generate(prompt, max_tokens=8).text.strip()

    def embed(self, text: str) -> list[float]:
        resp = self._client.embeddings.create(model="text-embedding-3-small", input=text)
        return list(resp.data[0].embedding)
