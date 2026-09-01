# Scraping / Marketplace Adapters

## Purpose

Keep every marketplace's quirks (selectors, endpoints, fee rules) inside a
single adapter so business logic stays marketplace-agnostic.

## Interface

`syncore.marketplace.base.BaseMarketplaceAdapter`:

```python
search_products(query, limit) -> list[Offer]
get_product(source_product_id) -> Offer | None
estimate_fees(items_subtotal) -> Fees        # basket-level economics
create_cart(session_id) -> RemoteCart
add_to_cart(cart_id, source_product_id, qty) -> RemoteCart
get_cart(cart_id) -> RemoteCart
get_checkout(cart_id) -> RemoteCheckout       # authoritative total
place_order(checkout_id, payment_reference) -> RemoteOrder
healthy() -> bool
```

## Registry

`MarketplaceRegistry.register/get/list/healthy_adapters` resolves adapters by
name. The optimizer and orchestrator only ever touch the registry + interface,
never a concrete class. This is what makes Syncore multi-marketplace ready
(spec sections 59, 62).

```
MarketplaceRegistry
 ├── MockMarketplace("mock-bazaar")   delivery ₹20 (free ≥₹199), SAVE10 coupon
 ├── MockMarketplace("mock-fresh")    free delivery, ₹5 platform fee
 └── <FutureLiveAdapter>              official API / permitted scrape
```

## Reference implementation

`MockMarketplace` seeds a deterministic catalog with multiple offers per item
(cheap vs premium, different pack sizes) and two storefronts with different
economics, so ranking + optimization make real trade-offs. It is **only** for
dev/tests; `MARKETPLACE_MODE=live` selects real adapters.

## Writing a real adapter (Phase 2)

1. Subclass `BaseMarketplaceAdapter`; keep all selectors/endpoints local.
2. Map site data into canonical `Product` + marketplace `Offer` (with lineage).
3. Implement `estimate_fees` to mirror the site's real delivery/coupon rules.
4. Respect robots/ToS/rate limits; prefer official APIs; no anti-bot evasion.
5. Register it and add contract tests.

## Failure modes

Search failure is caught per-adapter in the orchestrator (circuit-breaker
style) and other sources continue. `healthy()` feeds `/admin/scraping-health`.
