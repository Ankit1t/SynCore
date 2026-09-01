"""Health, readiness and liveness probes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ...db.base import get_engine
from ...marketplace.registry import get_registry
from ..schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    checks: dict = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"
    registry = get_registry()
    checks["marketplaces"] = registry.list()
    status = "ok" if checks.get("database") == "ok" else "degraded"
    return HealthOut(status=status, checks=checks)


@router.get("/health/live")
def live() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
def ready() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "not_ready", "error": str(exc)}
