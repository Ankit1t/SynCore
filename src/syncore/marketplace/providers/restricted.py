"""Credential-gated marketplace adapters (Blueprint STEP 46/57).

Amazon, Flipkart, Zepto, BigBasket and Blinkit expose no public API for search/
price/cart/checkout/order to an unaffiliated developer, and automating their
sites would violate their terms and anti-bot controls. So these adapters are
implemented as real interfaces that DECLARE the capabilities they would provide
with credentials, and return PROVIDER_ACCESS_RESTRICTED until the named
credential/partnership exists. They never fabricate data and never bypass
anti-bot systems.
"""

from __future__ import annotations

from ...domain.enums import ProviderStatusCode
from .base import MarketplaceProvider, ProviderResult
from .capabilities import ProviderCapabilities


class RestrictedProvider(MarketplaceProvider):
    def __init__(self, name: str, credential: str, caps: ProviderCapabilities) -> None:
        self.name = name
        self._credential = credential
        self._caps = caps

    def capabilities(self) -> ProviderCapabilities:
        return self._caps

    async def search_products(self, query: str, *, limit: int = 10) -> ProviderResult:
        return ProviderResult(
            self.name,
            ProviderStatusCode.ACCESS_RESTRICTED,
            detail=f"requires {self._credential}; no unauthenticated public API and site "
                   f"automation is disallowed by terms/anti-bot",
        )

    async def health(self) -> ProviderStatusCode:
        return ProviderStatusCode.ACCESS_RESTRICTED


def build_restricted_providers() -> list[RestrictedProvider]:
    full = ProviderCapabilities(
        search=True, product=True, price=True, availability=True, offers=True,
        delivery=True, cart=True, checkout=True, order=True, payment=False,
        requires_credentials=True,
        notes="Available only via official/partner API or authorized integration.",
    )
    return [
        RestrictedProvider("amazon", "Amazon SP-API / PA-API partner credentials", full),
        RestrictedProvider("flipkart", "Flipkart Marketplace/Affiliate API credentials", full),
        RestrictedProvider("zepto", "Zepto partner API agreement", full),
        RestrictedProvider("bigbasket", "BigBasket partner API agreement", full),
        RestrictedProvider("blinkit", "Blinkit/Zomato partner API agreement", full),
    ]
