"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import get_settings
from ..domain.errors import SyncoreError
from ..observability.logging import configure_logging, get_logger
from .routes import (
    admin,
    agent,
    agent_runs,
    health,
    marketplace,
    orders,
    payments_cp,
    payments_rzp,
    products,
    shopping,
    wallet,
)
from .service import get_service

logger = get_logger("syncore.api.app")
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    get_service()  # initializes DB + registry + demo user
    logger.info("Syncore API ready (env=%s, marketplace=%s, browser=%s)",
                settings.environment, settings.marketplace_mode, settings.browser_mode)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Syncore API",
        version="0.1.0",
        description="AI Shopping & Procurement Agent — Phase 1 vertical slice.",
        lifespan=lifespan,
    )

    cors = settings.cors_origins.strip()
    origins = ["*"] if cors == "*" else [o.strip() for o in cors.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(SyncoreError)
    async def syncore_error_handler(_: Request, exc: SyncoreError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content={"error": exc.to_dict()})

    for router in (health.router, shopping.router, products.router, orders.router,
                   agent_runs.router, agent.router, payments_cp.router, payments_rzp.router,
                   wallet.router, marketplace.router, admin.router):
        app.include_router(router)

    if STATIC_DIR.exists():
        app.mount("/ui", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")

    @app.get("/", include_in_schema=False, response_model=None)
    async def index() -> FileResponse | JSONResponse:
        index_html = STATIC_DIR / "index.html"
        if index_html.exists():
            return FileResponse(str(index_html))
        return JSONResponse({"name": "Syncore API", "docs": "/docs"})

    return app


app = create_app()
