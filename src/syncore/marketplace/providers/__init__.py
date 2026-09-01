"""Phase 2 async marketplace provider layer.

Provider-independent commerce ingestion, decoupled from the AI pipeline:
    provider adapter -> resilient fetcher -> parser -> normalizer -> structured
    data -> storage/agent query.

Every provider declares its capabilities and health; nothing is assumed. Real
adapters (OpenFoodFacts) sit beside credential-gated adapters that honestly
return PROVIDER_ACCESS_RESTRICTED instead of faking access or bypassing anti-bot.
"""
