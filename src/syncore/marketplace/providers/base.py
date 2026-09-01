"""Async MarketplaceProvider interface + typed results (Blueprint STEP 3/4/32)."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ...domain.enums import ProviderStatusCode
from .capabilities import ProviderCapabilities


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProviderProduct:
    """A raw product observation from a provider (pre-normalization).

    price_paise is None when the provider exposes no price (e.g. a catalog-only
    source like OpenFoodFacts) — the system must never invent one.
    """

    source: str
    source_id: str
    name: str
    brand: str | None = None
    quantity_text: str | None = None
    category: str | None = None
    price_paise: int | None = None
    currency: str = "INR"
    available: bool | None = None
    url: str | None = None
    observed_at: str = field(default_factory=_utcnow)


@dataclass
class ProviderResult:
    provider: str
    status: ProviderStatusCode
    products: list[ProviderProduct] = field(default_factory=list)
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status == ProviderStatusCode.OK


class MarketplaceProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abc.abstractmethod
    async def search_products(self, query: str, *, limit: int = 10) -> ProviderResult: ...

    async def fetch_product(self, source_id: str) -> ProviderResult:  # optional
        return ProviderResult(self.name, ProviderStatusCode.UNAVAILABLE, detail="not supported")

    async def health(self) -> ProviderStatusCode:
        return ProviderStatusCode.OK
