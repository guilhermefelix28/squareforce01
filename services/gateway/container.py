"""Composição dos serviços (injeção de dependências do gateway)."""

from __future__ import annotations

import time
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from fastapi import Request

from services.auction.model import AuctionModel, load_auction_model
from services.auction.service import AuctionService
from services.trading.service import TradingService
from services.competition.planner import plan_competition
from services.competition.service import SeasonService
from services.competition.worker import exit_with_parent
from services.data.service import DataService
from services.session.manager import SessionManager

from .admin import AdminAuth
from .idempotency import IdempotencyStore
from .realtime import SessionHub
from .settings import Settings


@dataclass
class Container:
    settings: Settings
    data: DataService
    sessions: SessionManager
    idempotency: IdempotencyStore
    hub: SessionHub
    auctions: AuctionService
    trading: TradingService
    seasons: SeasonService
    clock: Callable[[], float]
    auction_model: AuctionModel | None  # None = fórmulas pendentes: leilão bloqueado
    admin: AdminAuth


_UNSET = object()


def build_container(
    settings: Settings, clock: Callable[[], float] = time.monotonic, auction_model: object = _UNSET
) -> Container:
    if settings.clock_scale != 1.0:  # somente testes/demonstração (SQUADFORCE_CLOCK_SCALE)
        base, origin, scale = clock, clock(), settings.clock_scale
        clock = lambda: origin + (base() - origin) * scale  # noqa: E731
    faces = settings.graphics_dir / "Faces"

    @lru_cache(maxsize=4096)
    def has_photo(pid: int) -> bool:
        return any((faces / f"{pid}.{ext}").is_file() for ext in ("png", "jpg", "jpeg"))

    # Referência circular resolvida por closure: a trava de importação pertence ao serviço de sessão.
    holder: dict[str, SessionManager] = {}
    data = DataService(
        settings.db_path,
        import_guard=lambda: holder["sessions"].import_guard(),
        max_upload_bytes=settings.max_upload_mb * 1024 * 1024,
    )
    sessions = SessionManager(catalog=data, planner=plan_competition)
    holder["sessions"] = sessions
    return Container(
        settings=settings,
        data=data,
        sessions=sessions,
        idempotency=IdempotencyStore(ttl_seconds=settings.idempotency_ttl_seconds),
        hub=SessionHub(),
        auctions=AuctionService(clock=clock, has_photo=has_photo),
        trading=TradingService(clock=clock),
        seasons=SeasonService(lambda: _match_executor(settings)),
        clock=clock,
        auction_model=load_auction_model() if auction_model is _UNSET else auction_model,  # type: ignore[arg-type]
        admin=AdminAuth(settings.admin_password),
    )


def _match_executor(settings: Settings) -> Executor:
    workers = max(1, settings.match_workers)
    if settings.match_executor == "thread":
        return ThreadPoolExecutor(max_workers=workers, thread_name_prefix="match")
    return ProcessPoolExecutor(max_workers=workers, initializer=exit_with_parent)


def get_container(request: Request) -> Container:
    return request.app.state.container
