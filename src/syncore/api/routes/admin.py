"""Admin endpoints: scraper/marketplace health, metrics, feature flags.

In production these must sit behind admin RBAC (see docs/authorization.md). The
vertical slice exposes them read-only for observability.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from ...config import get_settings
from ...db.base import session_scope
from ...db.tables import AgentRunRow, OrderRow
from ...llm.provider import COST_TRACKER
from ...marketplace.registry import get_registry

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/scraping-health")
def scraping_health() -> list[dict]:
    registry = get_registry()
    out = []
    for name in registry.list():
        adapter = registry.get(name)
        out.append({
            "name": name,
            "healthy": adapter.healthy(),
            "supports_live_execution": adapter.supports_live_execution,
        })
    return out


@router.get("/feature-flags")
def feature_flags() -> dict:
    s = get_settings()
    return {
        "automatic_payment": s.feature_automatic_payment,
        "browser_execution": s.feature_browser_execution,
        "multi_marketplace": s.feature_multi_marketplace,
        "auto_substitution": s.feature_auto_substitution,
        "marketplace_mode": s.marketplace_mode,
        "browser_mode": s.browser_mode,
        "payment_auto_limit": s.payment_auto_limit,
    }


@router.get("/metrics")
def metrics() -> dict:
    with session_scope() as s:
        total_runs = s.scalar(select(func.count()).select_from(AgentRunRow)) or 0
        completed = s.scalar(
            select(func.count()).select_from(AgentRunRow).where(AgentRunRow.state == "COMPLETED")
        ) or 0
        total_orders = s.scalar(select(func.count()).select_from(OrderRow)) or 0
        aov = s.scalar(select(func.avg(OrderRow.total)))
    return {
        "agent_runs_total": total_runs,
        "agent_runs_completed": completed,
        "agent_success_rate": round(completed / total_runs, 3) if total_runs else None,
        "orders_total": total_orders,
        "average_order_value": round(aov, 2) if aov else None,
        "llm_cost_usd_this_process": COST_TRACKER.total_cost_usd,
        "llm_tokens_this_process": COST_TRACKER.total_tokens,
    }
