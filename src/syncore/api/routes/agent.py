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

router = APIRouter(prefix="/api/v1", tags=["agent"])


class DecideRequest(BaseModel):
    user_request: str = Field(..., examples=["500 ke andar 1kg aloo, 100g mirch aur 2 maggi"])
    available_offers: Union[list[dict[str, Any]], str] = "NONE"


@router.post("/agent/decide")
def agent_decide(body: DecideRequest) -> dict[str, Any]:
    return decide(body.user_request, body.available_offers)
