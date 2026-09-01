"""Phase-2 marketplace endpoints: real multi-provider search + capability matrix."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from ...marketplace.providers.registry import get_provider_registry

router = APIRouter(prefix="/api/v1/marketplace", tags=["marketplace"])


@router.get("/providers")
def providers() -> dict[str, Any]:
    return get_provider_registry().capabilities_matrix()


@router.get("/search")
async def search(q: str, limit: int = 5) -> dict[str, Any]:
    results = await get_provider_registry().search_all(q, limit=limit)
    return {
        "query": q,
        "results": [
            {
                "provider": r.provider,
                "status": r.status.value,
                "detail": r.detail,
                "products": [asdict(p) for p in r.products],
            }
            for r in results
        ],
    }
