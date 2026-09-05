"""Product-detail endpoint (view-only).

Returns the rich detail for a basket product so the UI can show a product page:
image showcase, highlights, specifications and rating/reviews. Detail exists for
catalog products (incl. real ones extracted from Amazon); live/estimate lines
return found=false and the UI falls back to the summary it already has.
"""

from __future__ import annotations

from fastapi import APIRouter

from ...master_agent.product_catalog import get_detail

router = APIRouter(prefix="/api/v1/pdp", tags=["product-detail"])


@router.get("/{offer_id}")
def product_detail(offer_id: str) -> dict:
    p = get_detail(offer_id)
    if not p:
        return {"found": False, "offer_id": offer_id}
    return {
        "found": True,
        "offer_id": offer_id,
        "product_name": p.get("product_name"),
        "brand": p.get("brand"),
        "category": p.get("category"),
        "unit_price": p.get("unit_price"),
        "mrp": p.get("mrp"),
        "rating": p.get("rating") or 0,
        "review_count": p.get("review_count") or 0,
        "in_stock": p.get("in_stock", True),
        "image": p.get("image"),
        "images": p.get("images") or ([p["image"]] if p.get("image") else []),
        "highlights": p.get("highlights") or [],
        "specifications": p.get("specifications") or {},
    }
