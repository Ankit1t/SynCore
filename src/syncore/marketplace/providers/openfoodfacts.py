"""OpenFoodFacts provider — a REAL, open, no-credential public data source.

Verified live: the product-by-barcode endpoint returns real structured product
metadata; the free-text search endpoint is intermittently rate-limited (HTTP
503), which we surface honestly as DEGRADED (never faked). This gives Syncore a
genuine external catalog source for names/brands/quantities/categories.

OFF exposes NO retail price/availability, so those fields stay None — the
system never invents a price.
"""

from __future__ import annotations

from ...domain.enums import ProviderStatusCode
from ...observability.logging import get_logger
from .base import MarketplaceProvider, ProviderProduct, ProviderResult
from .capabilities import ProviderCapabilities
from .http import CircuitOpen, FetchError, ResilientFetcher

logger = get_logger("syncore.marketplace.off")

_BASE = "https://world.openfoodfacts.org/api/v2"
_FIELDS = "code,product_name,brands,quantity,categories_tags"


class OpenFoodFactsProvider(MarketplaceProvider):
    name = "openfoodfacts"

    def __init__(self, fetcher: ResilientFetcher | None = None) -> None:
        self._fetch = fetcher or ResilientFetcher(rate_per_min=30)

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            search=True, product=True, price=False, availability=False,
            requires_credentials=False,
            notes="Real open catalog metadata (name/brand/quantity/category). No price/cart/checkout.",
        )

    async def search_products(self, query: str, *, limit: int = 10) -> ProviderResult:
        q = query.strip()
        if q.isdigit():  # barcode lookup — the reliably-available path
            return await self.fetch_product(q)
        url = f"{_BASE}/search?search_terms={q}&fields={_FIELDS}&page_size={max(1, min(limit, 20))}"
        try:
            data = await self._fetch.get_json(url)
        except CircuitOpen:
            return ProviderResult(self.name, ProviderStatusCode.ACCESS_RESTRICTED,
                                  detail="OFF search circuit open (repeated 503)")
        except FetchError as exc:
            code = (ProviderStatusCode.ACCESS_RESTRICTED if exc.status in (403, 451, 429, 503)
                    else ProviderStatusCode.DEGRADED)
            return ProviderResult(self.name, code, detail=f"OFF search unavailable: {exc}")
        products = [self._to_product(p) for p in (data.get("products") or []) if p.get("product_name")]
        return ProviderResult(self.name, ProviderStatusCode.OK, products=products[:limit],
                              detail=f"{len(products)} real OFF result(s)")

    async def fetch_product(self, source_id: str) -> ProviderResult:
        url = f"{_BASE}/product/{source_id}.json?fields={_FIELDS}"
        try:
            data = await self._fetch.get_json(url)
        except FetchError as exc:
            return ProviderResult(self.name, ProviderStatusCode.DEGRADED, detail=f"OFF product unavailable: {exc}")
        if data.get("status") != 1 or not data.get("product"):
            return ProviderResult(self.name, ProviderStatusCode.OK, products=[],
                                  detail="product not found in OFF")
        return ProviderResult(self.name, ProviderStatusCode.OK,
                              products=[self._to_product(data["product"])], detail="real OFF product")

    async def health(self) -> ProviderStatusCode:
        res = await self.fetch_product("3017620422003")  # Nutella — known to exist
        return ProviderStatusCode.OK if res.ok else ProviderStatusCode.DEGRADED

    @staticmethod
    def _to_product(p: dict) -> ProviderProduct:
        cats = p.get("categories_tags") or []
        category = cats[-1].split(":")[-1].replace("-", " ") if cats else None
        return ProviderProduct(
            source="openfoodfacts",
            source_id=str(p.get("code") or ""),
            name=str(p.get("product_name") or "").strip(),
            brand=(str(p.get("brands")).split(",")[0].strip() if p.get("brands") else None),
            quantity_text=(str(p.get("quantity")).strip() or None) if p.get("quantity") else None,
            category=category,
            price_paise=None,  # OFF has no retail price — never invent one
            currency="INR",
            available=None,
            url=f"https://world.openfoodfacts.org/product/{p.get('code')}",
        )
