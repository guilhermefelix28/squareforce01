"""Gateway/API do SquadForce: ponto de entrada HTTP/WebSocket que compõe os serviços."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import services  # noqa: F401  (torna squadforce_shared importável)
from squadforce_shared import __version__

from .container import build_container
from .errors import install_error_handlers
from .routes import router, ws_router
from .settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    container = build_container(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        version = container.data.initialize()
        logging.getLogger("squadforce").info("SQLite pronto em %s (schema v%s)", settings.db_path, version)
        yield

    app = FastAPI(
        title="SquadForce API",
        version=__version__,
        description="Gateway do SquadForce (Game Design v5.2) — Entrega 1: dados, importações e sessão.",
        lifespan=lifespan,
    )
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
        expose_headers=["Idempotent-Replayed"],
    )
    install_error_handlers(app)
    app.include_router(router)
    app.include_router(ws_router)
    return app


app = create_app()
