"""Composição dos serviços (injeção de dependências do gateway)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from services.competition.planner import plan_competition
from services.data.service import DataService
from services.session.manager import SessionManager

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


def build_container(settings: Settings) -> Container:
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
    )


def get_container(request: Request) -> Container:
    return request.app.state.container
