"""Marketplace subsystem: abstract adapter, registry and mock implementation.

The shopping engine operates against the abstract BaseMarketplaceAdapter only.
Marketplace-specific selectors/logic live inside adapters and never leak into
business logic. Real adapters (live sites, official APIs) are the integration
boundary; MockMarketplace provides deterministic data for dev and tests.
"""
