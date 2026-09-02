"""Real LLM provider over the OpenAI-compatible Chat Completions API.

One adapter works with every mainstream FREE option — you only change env:

  Provider    LLM_PROVIDER   Free?              Get a key
  ---------   ------------   -----------------  --------------------------------
  Gemini      gemini         yes (free tier)    https://aistudio.google.com/apikey
  Groq        groq           yes (free tier)    https://console.groq.com/keys
  Ollama      ollama         100% local/free    install Ollama, `ollama pull llama3.2`
  OpenRouter  openrouter     free models exist  https://openrouter.ai/keys
  OpenAI      openai         paid               https://platform.openai.com

Uses httpx directly (already a dependency) so no extra package is needed. The
LLM is used only for language understanding; money math stays deterministic.
"""

from __future__ import annotations

import time

import httpx

from ..config import get_settings
from ..observability.logging import get_logger
from .provider import COST_TRACKER, DeterministicProvider, LLMResult, LLMUsage

logger = get_logger("syncore.llm.http")

# provider -> (base_url, default_model, needs_api_key)
# All expose an OpenAI-compatible /chat/completions endpoint. "Free?" below is a
# guide, verify current terms with the provider.
PRESETS: dict[str, tuple[str, str, bool]] = {
    # (gemini has its own native provider; kept here only for completeness)
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.0-flash", True),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b", True),            # FREE tier, fast, strong JSON
    "zai": ("https://api.z.ai/api/paas/v4", "glm-4.5-flash", True),                     # FREE model (GLM flash)
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", True),             # FREE model (China)
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", True),                 # cheap, NOT free
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.1-8b-instruct", True),  # some :free models
    "ollama": ("http://localhost:11434/v1", "llama3.2", False),                         # FREE, local, no key
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", True),                       # paid
}


class HttpLLMProvider:
    """OpenAI-compatible chat provider (Gemini/Groq/Ollama/OpenRouter/OpenAI)."""

    def __init__(self, *, provider: str, base_url: str, model: str, api_key: str | None):
        self.name = provider
        self._base = base_url.rstrip("/")
        self._model = model
        self._key = api_key
        self._fallback = DeterministicProvider()

    # Transient conditions worth retrying: rate limits and server hiccups.
    _RETRY_STATUS = {429, 500, 502, 503, 504}
    _MAX_ATTEMPTS = 3

    def generate(self, prompt: str, *, system: str | None = None, max_tokens: int = 800) -> LLMResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        body = {"model": self._model, "messages": messages, "temperature": 0.1, "max_tokens": max_tokens}

        start = time.perf_counter()
        data: dict = {}
        last_err: Exception | None = None

        # Retry transient failures (429 rate limit, 5xx, timeouts) with backoff.
        # On total failure the caller falls back to the deterministic parser.
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            try:
                resp = httpx.post(f"{self._base}/chat/completions", headers=headers, json=body, timeout=30)
                if resp.status_code in self._RETRY_STATUS:
                    retry_after = resp.headers.get("Retry-After")
                    wait = float(retry_after) if (retry_after or "").replace(".", "", 1).isdigit() else 2.0 * attempt
                    logger.warning("%s %s (attempt %d/%d), retrying in %.1fs",
                                   self.name, resp.status_code, attempt, self._MAX_ATTEMPTS, wait)
                    if attempt < self._MAX_ATTEMPTS:
                        time.sleep(min(wait, 15.0))
                        continue
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_err = exc
                logger.warning("%s network error %s (attempt %d/%d)",
                               self.name, type(exc).__name__, attempt, self._MAX_ATTEMPTS)
                if attempt < self._MAX_ATTEMPTS:
                    time.sleep(1.5 * attempt)

        if not data:
            if last_err is not None:
                raise last_err
            raise RuntimeError(f"{self.name} request failed after {self._MAX_ATTEMPTS} attempts")

        text = (data["choices"][0]["message"]["content"] or "").strip()
        usage = data.get("usage", {}) or {}
        rec = LLMUsage(
            self.name, self._model,
            int(usage.get("prompt_tokens", len(prompt) // 4)),
            int(usage.get("completion_tokens", len(text) // 4)),
            (time.perf_counter() - start) * 1000, 0.0,
        )
        COST_TRACKER.record(rec)
        return LLMResult(text=text, usage=rec)

    def classify(self, text: str, labels: list[str]) -> str:
        prompt = f"Choose exactly one label from {labels} for this text:\n{text}\nAnswer with only the label."
        try:
            out = self.generate(prompt, max_tokens=16).text.strip()
            for label in labels:
                if label.lower() in out.lower():
                    return label
        except Exception:  # noqa: BLE001
            pass
        return self._fallback.classify(text, labels)

    def embed(self, text: str) -> list[float]:
        # Chat providers don't share one embeddings contract; use the offline,
        # deterministic embedding (ranking only needs a stable vector).
        return self._fallback.embed(text)


def build_http_provider() -> HttpLLMProvider | None:
    """Construct a real provider from settings, or None if not configured.

    Known providers use a preset. Any OTHER value works too — just set
    LLM_BASE_URL (+ LLM_MODEL, + LLM_API_KEY) and it's treated as a generic
    OpenAI-compatible provider. So a new free provider needs zero code changes.
    """
    s = get_settings()
    name = (s.llm_provider or "").lower()

    if name in PRESETS:
        default_base, default_model, needs_key = PRESETS[name]
    else:
        # Custom / unknown provider: caller must supply the base URL.
        if not s.llm_base_url:
            logger.warning(
                "LLM_PROVIDER=%s is not a known preset and no LLM_BASE_URL set; "
                "falling back to deterministic", name)
            return None
        default_base, default_model, needs_key = (s.llm_base_url, s.llm_model, True)

    if needs_key and not s.llm_api_key:
        logger.warning("LLM_PROVIDER=%s needs LLM_API_KEY; falling back to deterministic", name)
        return None

    base = s.llm_base_url or default_base
    model = s.llm_model or default_model
    if not model:
        logger.warning("LLM_PROVIDER=%s needs LLM_MODEL; falling back to deterministic", name)
        return None
    return HttpLLMProvider(provider=name, base_url=base, model=model, api_key=s.llm_api_key)
