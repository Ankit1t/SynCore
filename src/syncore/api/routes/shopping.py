"""Shopping request endpoints: create, fetch, execute, and live SSE stream."""

from __future__ import annotations

import asyncio
import json
import threading

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from ...db import repositories as repo
from ...db.base import session_scope
from ...domain.errors import SyncoreError
from ..schemas import (
    AgentRunOut,
    BasketOut,
    CreateShoppingRequest,
    OptimizeRequest,
    ShoppingRequestOut,
)
from ..service import get_service

router = APIRouter(prefix="/api/v1", tags=["shopping"])


@router.post("/shopping-requests", response_model=ShoppingRequestOut)
def create_shopping_request(body: CreateShoppingRequest) -> ShoppingRequestOut:
    service = get_service()
    try:
        request = service.parse(body.text)
    except SyncoreError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.to_dict()) from exc
    with session_scope() as s:
        repo.save_request(s, request)
    return service.to_request_out(request)


@router.get("/shopping-requests/{request_id}", response_model=ShoppingRequestOut)
def get_shopping_request(request_id: str) -> ShoppingRequestOut:
    service = get_service()
    with session_scope() as s:
        request = repo.get_request_model(s, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="shopping request not found")
    return service.to_request_out(request)


@router.post("/shopping-requests/{request_id}/execute", response_model=AgentRunOut)
def execute_shopping_request(request_id: str, auto_execute: bool = True) -> AgentRunOut:
    service = get_service()
    with session_scope() as s:
        request = repo.get_request_model(s, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="shopping request not found")
    orch = service.new_orchestrator()
    run = orch.run(request, auto_execute=auto_execute)
    service.persist(request, run, orch)
    return service.to_run_out(run)


@router.post("/baskets/optimize", response_model=BasketOut)
def optimize_basket(body: OptimizeRequest) -> BasketOut:
    """Parse + optimize only (Phase-1 brain), no execution."""
    service = get_service()
    try:
        request = service.parse(body.text)
    except SyncoreError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.to_dict()) from exc
    orch = service.new_orchestrator()
    run = orch.run(request, auto_execute=False)
    if run.basket is None:
        raise HTTPException(status_code=422, detail=run.error or "no basket produced")
    return service.to_basket_out(run)


@router.get("/shopping-requests/stream/live")
async def stream_agent_run(
    text: str = Query(..., description="Natural-language shopping request"),
    auto_execute: bool = True,
) -> EventSourceResponse:
    """Run the agent and stream every state transition as Server-Sent Events.

    Parse/validation problems are delivered as an SSE `error` event (with HTTP
    200) rather than an HTTP error, because a non-200 response makes the
    browser's EventSource reconnect in a loop and the UI would hang forever.
    """
    service = get_service()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_step(step) -> None:
        payload = {"index": step.index, "state": step.state, "message": step.message,
                   "data": step.data}
        loop.call_soon_threadsafe(queue.put_nowait, ("step", payload))

    def worker() -> None:
        try:
            # Parsing happens inside the stream so failures become SSE `error`
            # events the client can render, not connection errors.
            request = service.parse(text)
            loop.call_soon_threadsafe(
                queue.put_nowait,
                ("request", service.to_request_out(request).model_dump(mode="json")),
            )
            orch = service.new_orchestrator()
            run = orch.run(request, auto_execute=auto_execute, on_step=on_step)
            service.persist(request, run, orch)
            loop.call_soon_threadsafe(
                queue.put_nowait, ("final", service.to_run_out(run).model_dump(mode="json"))
            )
        except SyncoreError as exc:
            loop.call_soon_threadsafe(
                queue.put_nowait, ("failure", {"code": exc.code, "message": exc.message})
            )
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait, ("failure", {"code": "internal_error", "message": str(exc)})
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_gen():
        while True:
            item = await queue.get()
            if item is None:
                break
            event, data = item
            yield {"event": event, "data": json.dumps(data)}

    return EventSourceResponse(event_gen())
