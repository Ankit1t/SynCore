"""Async marketplace provider registry + parallel search orchestration."""

from __future__ import annotations

import asyncio

from ...observability.logging import get_logger
from .base import MarketplaceProvider, ProviderResult

logger = get_logger("syncore.marketplace.registry")


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MarketplaceProvider] = {}

    def register(self, provider: MarketplaceProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> MarketplaceProvider | None:
        return self._providers.get(name)

    def list(self) -> list[str]:
        return sorted(self._providers)

    def capabilities_matrix(self) -> dict[str, dict]:
        return {name: p.capabilities().to_dict() for name, p in self._providers.items()}

    async def search_all(self, query: str, *, limit: int = 10) -> list[ProviderResult]:
        """Query every provider in parallel; a failing provider never breaks the
        others (STEP 33) — it returns its own status."""
        async def _one(p: MarketplaceProvider) -> ProviderResult:
            try:
                return await p.search_products(query, limit=limit)
            except Exception as exc:  # noqa: BLE001 - isolate provider failure
                from ...domain.enums import ProviderStatusCode

                logger.warning("provider %s failed: %s", p.name, exc)
                return ProviderResult(p.name, ProviderStatusCode.UNAVAILABLE, detail=str(exc)[:120])

        return list(await asyncio.gather(*[_one(p) for p in self._providers.values()]))


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
        _register_defaults(_registry)
    return _registry


def _register_defaults(reg: ProviderRegistry) -> None:
    from .openfoodfacts import OpenFoodFactsProvider
    from .restricted import build_restricted_providers

    reg.register(OpenFoodFactsProvider())
    for p in build_restricted_providers():
        reg.register(p)
