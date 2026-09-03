"""KIRANA Master Agent endpoint.

POST /api/v1/agent/decide
  body: { "user_request": "<text>", "available_offers": [ ... ] | "NONE" }
  returns: the v1 Master Agent JSON contract (one object).
"""

from __future__ import annotations

from typing import Any, Union

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...master_agent import decide
from ...master_agent.product_catalog import catalog_offers

router = APIRouter(prefix="/api/v1", tags=["agent"])


class DecideRequest(BaseModel):
    user_request: str = Field(..., examples=["500 ke andar 1kg aloo, 100g mirch aur 2 maggi"])
    # "NONE"     -> match against the curated seed catalog (real offers), then
    #               fall back to flagged estimates for anything not stocked.
    # "ESTIMATE" -> skip the catalog and use market estimates only.
    # a list     -> use these caller-supplied offers.
    available_offers: Union[list[dict[str, Any]], str] = "NONE"


@router.post("/agent/decide")
def agent_decide(body: DecideRequest) -> dict[str, Any]:
    offers = body.available_offers
    if isinstance(offers, str):
        offers = catalog_offers() if offers.upper() == "NONE" else "NONE"
    return decide(body.user_request, offers)
