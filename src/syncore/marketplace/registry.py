"""Marketplace registry.

The shopping engine resolves adapters by name so new marketplaces can be added
without touching business logic (see spec sections 59 & 62).
"""

from __future__ import annotations

from ..domain.errors import MarketplaceUnavailableError
from .base import BaseMarketplaceAdapter


class MarketplaceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BaseMarketplaceAdapter] = {}

    def register(self, adapter: BaseMarketplaceAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> BaseMarketplaceAdapter:
        try:
            return self._adapters[name]
        except KeyError as exc:
            raise MarketplaceUnavailableError(
                f"marketplace not registered: {name}",
                details={"available": self.list()},
            ) from exc

    def list(self) -> list[str]:
        return sorted(self._adapters)

    def healthy_adapters(self) -> list[BaseMarketplaceAdapter]:
        return [a for a in self._adapters.values() if a.healthy()]


_registry = MarketplaceRegistry()


def get_registry() -> MarketplaceRegistry:
    return _registry
