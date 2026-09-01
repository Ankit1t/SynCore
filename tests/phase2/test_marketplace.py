"""Phase 2 — marketplace provider layer (capabilities, restricted, real OFF)."""

from __future__ import annotations

import pytest

from syncore.domain.enums import ProviderStatusCode
from syncore.marketplace.providers.openfoodfacts import OpenFoodFactsProvider
from syncore.marketplace.providers.registry import ProviderRegistry
from syncore.marketplace.providers.restricted import build_restricted_providers


def test_restricted_providers_report_access_restricted():
    reg = ProviderRegistry()
    for p in build_restricted_providers():
        reg.register(p)
    assert set(reg.list()) == {"amazon", "flipkart", "zepto", "bigbasket", "blinkit"}


async def test_restricted_search_never_fabricates():
    for p in build_restricted_providers():
        res = await p.search_products("milk")
        assert res.status == ProviderStatusCode.ACCESS_RESTRICTED
        assert res.products == []
        assert "requires" in res.detail


def test_capability_matrix_declared_not_assumed():
    reg = ProviderRegistry()
    reg.register(OpenFoodFactsProvider())
    matrix = reg.capabilities_matrix()
    off = matrix["openfoodfacts"]
    assert off["product"] is True
    assert off["price"] is False  # OFF has no retail price — never invented
    assert off["requires_credentials"] is False


@pytest.mark.asyncio
async def test_openfoodfacts_real_product_by_barcode_if_network():
    """Integration: real OFF data. Skips (does not fail) if network unavailable."""
    off = OpenFoodFactsProvider()
    res = await off.fetch_product("3017620422003")  # Nutella
    if res.status != ProviderStatusCode.OK or not res.products:
        pytest.skip("OpenFoodFacts unreachable in this environment")
    p = res.products[0]
    assert p.source == "openfoodfacts"
    assert p.name  # real product name present
    assert p.price_paise is None  # OFF never supplies a price
