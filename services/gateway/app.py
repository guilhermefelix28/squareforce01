"""Gateway/API do SquadForce: ponto de entrada HTTP/WebSocket que compõe os serviços."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import services  # noqa: F401  (torna squadforce_shared importável)
from squadforce_shared import __version__

from .container import build_container
from .errors import install_error_handlers
from .routes import auction_clock, router, ws_router
from .settings import Settings


_UNSET = object()


def create_app(
    settings: Settings | None = None, *, clock: Callable[[], float] = time.monotonic, auction_model: object = _UNSET
) -> FastAPI:
    settings = settings or Settings()
    kwargs = {} if auction_model is _UNSET else {"auction_model": auction_model}
    container = build_container(settings, clock=clock, **kwargs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        version = container.data.initialize()
        logging.getLogger("squadforce").info("SQLite pronto em %s (schema v%s)", settings.db_path, version)
        task = asyncio.create_task(auction_clock(container, settings.auction_tick_seconds)) if settings.auction_ticker else None
        yield
        container.seasons.shutdown()
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="SquadForce API",
        version=__version__,
        description="Gateway do SquadForce (Game Design v5.2) — dados, sessão, leilão, mercado e competições.",
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
