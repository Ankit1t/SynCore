"""Product search endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..service import get_service
from ..schemas import OfferOut

router = APIRouter(prefix="/api/v1", tags=["products"])


@router.get("/products/search", response_model=list[OfferOut])
def search_products(q: str = Query(..., min_length=1), limit: int = 20) -> list[OfferOut]:
    service = get_service()
    offers = service.search(q, limit=limit)
    return [service.offer_to_out(o) for o in offers]
