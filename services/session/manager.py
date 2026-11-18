"""SessionManager: estado temporário da competição, protegido por trava (thread-safe)."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Iterator, Protocol

from squadforce_shared.contracts import CompetitionConfig, SessionOut
from squadforce_shared.domain.competition import CompetitionConfigError, validate_competition_config
from squadforce_shared.errors import AppError, ErrorCode

MAX_CLOSED_TOMBSTONES = 50


class ClubCatalog(Protocol):
    """Porta de leitura do catálogo (implementada pelo DataService)."""

    def club_count(self) -> int: ...
    def club_exists(self, club_uid: int) -> bool: ...
    def catalog_ready(self) -> bool: ...


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SessionState:
    id: str
    version: int
    status: str
    phase: str
    config: CompetitionConfig
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    participants: tuple[int, ...] | None = None

    def to_out(self) -> SessionOut:
        return SessionOut(
            id=self.id,
            version=self.version,
            status=self.status,  # type: ignore[arg-type]
            phase=self.phase,  # type: ignore[arg-type]
            config=self.config,
            created_at=self.created_at,
            updated_at=self.updated_at,
            closed_at=self.closed_at,
            participants=list(self.participants) if self.participants is not None else None,
        )


@dataclass
class _Internal:
    active: SessionState | None = None
    closed: "OrderedDict[str, SessionState]" = field(default_factory=OrderedDict)
    imports_running: int = 0


class SessionManager:
    def __init__(self, catalog: ClubCatalog):
        self._catalog = catalog
        self._lock = threading.RLock()
        self._s = _Internal()

    # -------------------------------------------------------------- consultas
    @property
    def has_active(self) -> bool:
        with self._lock:
            return self._s.active is not None

    def active(self) -> SessionState | None:
        with self._lock:
            return self._s.active

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            if self._s.active is not None and self._s.active.id == session_id:
                return self._s.active
            if session_id in self._s.closed:
                return self._s.closed[session_id]
        raise AppError(
            404,
            ErrorCode.SESSION_NOT_FOUND,
            "Sessão não encontrada. Se o servidor foi reiniciado, a competição não pode ser restaurada.",
            details={"session_id": session_id},
        )

    # -------------------------------------------------------------- comandos
    def create(self, config: CompetitionConfig, confirm_replace: bool = False) -> SessionState:
        with self._lock:
            if self._s.imports_running:
                raise AppError(
                    409, ErrorCode.IMPORT_IN_PROGRESS,
                    "Há uma importação em andamento. Aguarde a conclusão para iniciar a competição.",
                    retryable=True,
                )
            if not self._catalog.catalog_ready():
                raise AppError(
                    409, ErrorCode.CATALOG_EMPTY,
                    "Importe as bases de clubes e jogadores antes de iniciar uma competição.",
                )
            try:
                validate_competition_config(
                    config.format, config.num_clubs, config.league_rounds, self._catalog.club_count()
                )
            except CompetitionConfigError as exc:
                raise AppError(
                    422, ErrorCode.INVALID_COMPETITION_CONFIG, str(exc), details={"field": exc.field}
                ) from exc
            if not self._catalog.club_exists(config.user_club_uid):
                raise AppError(
                    422, ErrorCode.CLUB_NOT_FOUND,
                    f"O clube {config.user_club_uid} não existe no catálogo importado.",
                    details={"field": "user_club_uid"},
                )
            if self._s.active is not None:
                if not confirm_replace:
                    raise AppError(
                        409, ErrorCode.SESSION_ALREADY_ACTIVE,
                        "Já existe uma competição ativa. Confirme para encerrá-la e iniciar outra (o progresso será perdido).",
                        details={"active_session_id": self._s.active.id},
                    )
                self._close_locked(self._s.active)

            now = _now()
            state = SessionState(
                id=str(uuid.uuid4()),
                version=1,
                status="active",
                phase="setup",
                config=config,
                created_at=now,
                updated_at=now,
            )
            self._s.active = state
            return state

    def close(self, session_id: str, expected_version: int | None = None) -> SessionState:
        with self._lock:
            current = self.get(session_id)
            if current.status == "closed":
                return current  # encerramento é idempotente por natureza
            if expected_version is not None and expected_version != current.version:
                raise AppError(
                    409, ErrorCode.VERSION_CONFLICT,
                    "A sessão foi alterada por outra operação. Atualize o estado e tente novamente.",
                    retryable=True,
                    details={"expected_version": expected_version, "current_version": current.version},
                )
            return self._close_locked(current)

    def _close_locked(self, state: SessionState) -> SessionState:
        now = _now()
        closed = replace(state, status="closed", version=state.version + 1, updated_at=now, closed_at=now)
        self._s.active = None
        self._s.closed[closed.id] = closed
        while len(self._s.closed) > MAX_CLOSED_TOMBSTONES:
            self._s.closed.popitem(last=False)
        return closed

    # -------------------------------------------------------------- trava de importação
    @contextmanager
    def import_guard(self) -> Iterator[None]:
        """Bloqueia importações com competição ativa e impede importações simultâneas."""
        with self._lock:
            if self._s.active is not None:
                raise AppError(
                    409, ErrorCode.IMPORT_BLOCKED_ACTIVE_COMPETITION,
                    "Importações estão bloqueadas enquanto existir uma competição ativa. Encerre a sessão primeiro.",
                    details={"active_session_id": self._s.active.id},
                )
            if self._s.imports_running:
                raise AppError(
                    409, ErrorCode.IMPORT_IN_PROGRESS,
                    "Outra importação está em andamento. Tente novamente em instantes.",
                    retryable=True,
                )
            self._s.imports_running += 1
        try:
            yield
        finally:
            with self._lock:
                self._s.imports_running -= 1
