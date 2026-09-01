"""Resilient async HTTP fetcher (Blueprint STEP 4/39).

Adds timeout, bounded retries with exponential backoff + jitter, a per-host
rate limiter and circuit breaker, and structured errors with a trace id. Never
implements anti-bot bypass: 403/451 and repeated 5xx trip the breaker and the
caller reports PROVIDER_ACCESS_RESTRICTED / UNAVAILABLE.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from ...observability.logging import get_logger
from ...domain.models import new_id

logger = get_logger("syncore.marketplace.http")


class FetchError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class CircuitOpen(FetchError):
    def __init__(self, host: str):
        super().__init__(f"circuit open for {host}", retryable=False)


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float = 0.0


class ResilientFetcher:
    def __init__(
        self,
        *,
        timeout: float = 12.0,
        retries: int = 3,
        backoff_base: float = 0.4,
        rate_per_min: int = 60,
        cb_threshold: int = 4,
        cb_cooldown: float = 30.0,
        user_agent: str = "SyncoreBot/1.0 (+https://syncore.local; contact dev@syncore.local)",
    ) -> None:
        self._timeout = timeout
        self._retries = retries
        self._backoff_base = backoff_base
        self._min_interval = 60.0 / max(1, rate_per_min)
        self._cb_threshold = cb_threshold
        self._cb_cooldown = cb_cooldown
        self._ua = user_agent
        self._breakers: dict[str, _Breaker] = {}
        self._last_call: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, host: str) -> asyncio.Lock:
        return self._locks.setdefault(host, asyncio.Lock())

    def _breaker_open(self, host: str) -> bool:
        b = self._breakers.get(host)
        if not b or b.failures < self._cb_threshold:
            return False
        if time.monotonic() - b.opened_at >= self._cb_cooldown:
            b.failures = 0  # half-open: allow a probe
            return False
        return True

    def _record(self, host: str, ok: bool) -> None:
        b = self._breakers.setdefault(host, _Breaker())
        if ok:
            b.failures = 0
        else:
            b.failures += 1
            if b.failures >= self._cb_threshold:
                b.opened_at = time.monotonic()

    async def _throttle(self, host: str) -> None:
        async with self._lock(host):
            last = self._last_call.get(host, 0.0)
            wait = self._min_interval - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call[host] = time.monotonic()

    async def get_json(self, url: str, *, headers: dict | None = None) -> dict:
        host = urlparse(url).netloc
        trace_id = new_id()[:8]
        if self._breaker_open(host):
            raise CircuitOpen(host)

        hdrs = {"User-Agent": self._ua, "Accept": "application/json"}
        if headers:
            hdrs.update(headers)

        last_exc: Exception | None = None
        for attempt in range(1, self._retries + 1):
            await self._throttle(host)
            try:
                async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers=hdrs)
                status = resp.status_code
                if status == 200 and "json" in resp.headers.get("content-type", ""):
                    self._record(host, True)
                    return resp.json()
                if status in (403, 451):
                    self._record(host, False)
                    raise FetchError(f"access restricted ({status})", status=status, retryable=False)
                if status in (429, 500, 502, 503, 504):
                    self._record(host, False)
                    last_exc = FetchError(f"server busy ({status})", status=status, retryable=True)
                else:
                    # non-retryable client error or unexpected content-type
                    self._record(host, False)
                    raise FetchError(f"unexpected response ({status})", status=status, retryable=False)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self._record(host, False)
                last_exc = FetchError(f"network error: {type(exc).__name__}", retryable=True)

            if attempt < self._retries:
                delay = self._backoff_base * (2 ** (attempt - 1)) + random.uniform(0, self._backoff_base)
                logger.debug("fetch retry host=%s attempt=%d trace=%s delay=%.2fs", host, attempt, trace_id, delay)
                await asyncio.sleep(delay)

        raise last_exc or FetchError("fetch failed", retryable=True)
