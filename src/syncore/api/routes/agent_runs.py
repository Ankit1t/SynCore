"""Agent run observability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...db import repositories as repo
from ...db.base import session_scope

router = APIRouter(prefix="/api/v1", tags=["agent-runs"])


def _run_row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "request_id": row.request_id,
        "user_id": row.user_id,
        "state": row.state,
        "checkpoint_reason": row.checkpoint_reason,
        "error": row.error,
        "basket": row.basket,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "steps": [
            {"index": st.idx, "state": st.state, "message": st.message, "data": st.data}
            for st in row.steps
        ],
        "decisions": [
            {"kind": d.kind, "summary": d.summary, "evidence": d.evidence} for d in row.decisions
        ],
    }


@router.get("/agent-runs")
def list_agent_runs(limit: int = 50) -> list[dict]:
    with session_scope() as s:
        return [
            {"id": r.id, "request_id": r.request_id, "state": r.state,
             "started_at": r.started_at.isoformat() if r.started_at else None,
             "finished_at": r.finished_at.isoformat() if r.finished_at else None}
            for r in repo.list_runs(s, limit=limit)
        ]


@router.get("/agent-runs/{run_id}")
def get_agent_run(run_id: str) -> dict:
    with session_scope() as s:
        row = repo.get_run_row(s, run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="agent run not found")
        return _run_row_to_dict(row)
