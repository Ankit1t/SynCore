"""Native Google Gemini provider (generateContent + X-goog-api-key).

We use Gemini's native REST API rather than its OpenAI-compatibility shim,
because the shim resolves models against a different API version and is
unreliable for some keys. Native `:generateContent` with the `X-goog-api-key`
header is the documented, dependable path.

Only used for language understanding; money/budget math stays deterministic. On
any error (rate limit, network, safety block) the caller falls back to the
deterministic parser — the app never crashes.
"""

from __future__ import annotations

import time

import httpx

from ..config import get_settings
from ..observability.logging import get_logger
from .provider import COST_TRACKER, DeterministicProvider, LLMResult, LLMUsage

logger = get_logger("syncore.llm.gemini")

_BASE = "https://generativelanguage.googleapis.com/v1beta"
_DEFAULT_MODEL = "gemini-3.5-flash"


class GeminiNativeProvider:
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None):
        self._key = api_key
        self._model = model
        self._base = (base_url or _BASE).rstrip("/")
        self._fallback = DeterministicProvider()

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 2048) -> LLMResult:
        body: dict = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            # Generous output budget: on 2.5/3.x some tokens go to internal
            # "thinking", so a small cap can yield empty text.
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": max(1024, max_tokens)},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        start = time.perf_counter()
        resp = httpx.post(
            f"{self._base}/models/{self._model}:generateContent",
            headers={"X-goog-api-key": self._key, "Content-Type": "application/json"},
            json=body,
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        text = ""
        for cand in data.get("candidates", []) or []:
            parts = (cand.get("content") or {}).get("parts") or []
            text = "".join(p.get("text", "") for p in parts).strip()
            if text:
                break

        usage_meta = data.get("usageMetadata", {}) or {}
        usage = LLMUsage(
            self.name, self._model,
            int(usage_meta.get("promptTokenCount", len(prompt) // 4)),
            int(usage_meta.get("candidatesTokenCount", len(text) // 4)),
            (time.perf_counter() - start) * 1000, 0.0,
        )
        COST_TRACKER.record(usage)
        return LLMResult(text=text, usage=usage)

    def classify(self, text: str, labels: list[str]) -> str:
        prompt = f"Choose exactly one label from {labels} for this text:\n{text}\nReply with only the label."
        try:
            out = self.generate(prompt, max_tokens=1024).text.strip().lower()
            for label in labels:
                if label.lower() in out:
                    return label
        except Exception:  # noqa: BLE001
            pass
        return self._fallback.classify(text, labels)

    def embed(self, text: str) -> list[float]:
        # Ranking only needs a stable vector; keep the offline embedding.
        return self._fallback.embed(text)


def build_gemini_provider() -> GeminiNativeProvider | None:
    s = get_settings()
    if not s.llm_api_key:
        logger.warning("LLM_PROVIDER=gemini needs LLM_API_KEY; falling back to deterministic")
        return None
    model = s.llm_model or _DEFAULT_MODEL
    return GeminiNativeProvider(api_key=s.llm_api_key, model=model, base_url=s.llm_base_url)
