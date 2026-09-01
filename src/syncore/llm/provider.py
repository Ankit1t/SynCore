"""LLM provider interface + a deterministic, offline default.

The LLM is used only for language-shaped tasks (explanations, ambiguity,
semantic hints). It is never trusted for arithmetic, budget verdicts, payment
authorization or security decisions. All structured outputs are schema-checked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from ..config import get_settings
from ..observability.logging import get_logger

logger = get_logger("syncore.llm")


@dataclass
class LLMUsage:
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage


class LLMProvider(Protocol):
    """Minimal provider surface. Implementations validate their own outputs."""

    name: str

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 512) -> LLMResult:
        ...

    def classify(self, text: str, labels: list[str]) -> str:
        ...

    def embed(self, text: str) -> list[float]:
        ...


class CostTracker:
    """Aggregates AI cost/usage per process (see docs/cost_optimization.md)."""

    def __init__(self) -> None:
        self._records: list[LLMUsage] = []

    def record(self, usage: LLMUsage) -> None:
        self._records.append(usage)
        logger.debug(
            "llm_usage provider=%s model=%s tokens=%d+%d cost=$%.5f latency=%.1fms",
            usage.provider, usage.model, usage.prompt_tokens,
            usage.completion_tokens, usage.cost_usd, usage.latency_ms,
        )

    @property
    def total_cost_usd(self) -> float:
        return round(sum(r.cost_usd for r in self._records), 6)

    @property
    def total_tokens(self) -> int:
        return sum(r.prompt_tokens + r.completion_tokens for r in self._records)


COST_TRACKER = CostTracker()


class DeterministicProvider:
    """Rule-based provider used by default (no external calls, zero cost).

    It produces stable, explainable text and a lightweight hashing "embedding"
    so semantic-style matching works without a model. This keeps the whole
    platform runnable offline and cost-free for development and CI.
    """

    name = "deterministic"

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 512) -> LLMResult:
        start = time.perf_counter()
        # Deterministic pass-through summary: echo a compact, safe response.
        text = prompt.strip().split("\n")[-1][:max_tokens]
        usage = LLMUsage(self.name, "rule-based", len(prompt) // 4, len(text) // 4,
                         (time.perf_counter() - start) * 1000, 0.0)
        COST_TRACKER.record(usage)
        return LLMResult(text=text, usage=usage)

    def classify(self, text: str, labels: list[str]) -> str:
        lowered = text.lower()
        best = labels[0]
        best_hits = -1
        for label in labels:
            hits = sum(1 for tok in label.lower().split() if tok in lowered)
            if hits > best_hits:
                best, best_hits = label, hits
        return best

    def embed(self, text: str) -> list[float]:
        # Deterministic token-hash bag-of-words vector (dim=64).
        import hashlib

        dim = 64
        vec = [0.0] * dim
        for tok in _tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


def _tokenize(text: str) -> list[str]:
    import re

    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def get_provider() -> LLMProvider:
    """Factory honoring LLM_PROVIDER. Falls back to deterministic if unset."""
    settings = get_settings()
    if settings.llm_provider == "openai" and settings.llm_api_key:
        try:
            from .openai_provider import OpenAIProvider

            return OpenAIProvider()
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.warning("OpenAI provider unavailable (%s); using deterministic", exc)
    return DeterministicProvider()
