"""Rotas HTTP/WebSocket do gateway. Os serviços de domínio não conhecem HTTP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from services.competition.options import competition_options
from squadforce_shared import __version__
from squadforce_shared.contracts import (
    ClubPage,
    CompetitionConfig,
    CompetitionOptions,
    DatabaseHealth,
    ErrorResponse,
    HealthResponse,
    ImportReport,
    PlayerPage,
    SessionCloseRequest,
    SessionCreateRequest,
    SessionOut,
    WsEnvelope,
)
from squadforce_shared.errors import AppError, ErrorCode

from .container import Container, get_container
from .idempotency import fingerprint, validate_key

router = APIRouter(prefix="/api")
ws_router = APIRouter()

C = Annotated[Container, Depends(get_container)]
IdemKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", description="Obrigatório: identificador único do comando (8–128 caracteres)."),
]

ERR = {code: {"model": ErrorResponse} for code in (400, 404, 409, 413, 415, 422, 500)}


def _respond(status: int, body: dict[str, Any], replayed: bool) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, headers={"Idempotent-Replayed": str(replayed).lower()})


# ------------------------------------------------------------------ health
@router.get("/health", response_model=HealthResponse, tags=["gateway"])
def health(c: C) -> HealthResponse:
    db = c.data.health()
    return HealthResponse(
        status="ok" if db["status"] == "ok" else "degraded",
        service="squadforce-gateway",
        version=__version__,
        time=datetime.now(timezone.utc),
        database=DatabaseHealth(**db),
        active_session=c.sessions.has_active,
        services={
            "gateway": "ready",
            "session": "ready",
            "data": "ready",
            "competition": "ready",
            "auction": "planned",
            "trading": "planned",
            "bot_ai": "planned",
            "match_engine": "planned",
        },
    )


# ------------------------------------------------------------------ catálogo
@router.get("/catalog/clubs", response_model=ClubPage, responses=ERR, tags=["catalog"])
def list_clubs(
    c: C,
    search: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ClubPage:
    return c.data.list_clubs(search, limit, offset)


@router.get("/catalog/players", response_model=PlayerPage, responses=ERR, tags=["catalog"])
def list_players(
    c: C,
    club_uid: int | None = None,
    position: Annotated[str | None, Query(description="Código interno (GK…) ou de exibição (GOL…).")] = None,
    search: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PlayerPage:
    return c.data.list_players(club_uid, position, search, limit, offset)


# ------------------------------------------------------------------ importações
def _run_import(c: Container, base: str, file: UploadFile, key: str | None) -> JSONResponse:
    key = validate_key(key)
    limit = c.data.max_upload_bytes
    content = file.file.read(limit + 1)  # somente memória: nenhuma cópia em disco
    if len(content) > limit:
        raise AppError(413, ErrorCode.FILE_TOO_LARGE, f"Arquivo excede o limite de {limit // (1024 * 1024)} MB.")
    name = file.filename or "arquivo.xlsx"
    importer = c.data.import_clubs if base == "clubs" else c.data.import_players

    def run() -> tuple[int, dict[str, Any]]:
        return 200, importer(content, name).model_dump(mode="json")

    status, body, replayed = c.idempotency.execute(f"import:{base}", key, fingerprint(base, name, content), run)
    return _respond(status, body, replayed)


@router.post("/imports/clubs", response_model=ImportReport, responses=ERR, tags=["imports"])
def import_clubs(c: C, file: Annotated[UploadFile, File(description="Planilha .xlsx com colunas club_*")], idempotency_key: IdemKey = None):
    return _run_import(c, "clubs", file, idempotency_key)


@router.post("/imports/players", response_model=ImportReport, responses=ERR, tags=["imports"])
def import_players(c: C, file: Annotated[UploadFile, File(description="Planilha jogadores.xlsx")], idempotency_key: IdemKey = None):
    return _run_import(c, "players", file, idempotency_key)


# ------------------------------------------------------------------ sessões
@router.post("/sessions", response_model=SessionOut, status_code=201, responses=ERR, tags=["sessions"])
async def create_session(c: C, request: Request, body: SessionCreateRequest, idempotency_key: IdemKey = None):
    key = validate_key(idempotency_key)
    raw = await request.body()
    previous = c.sessions.active()

    def run() -> tuple[int, dict[str, Any]]:
        cfg = body.model_dump(exclude={"confirm_replace"})
        state = c.sessions.create(CompetitionConfig(**cfg), confirm_replace=body.confirm_replace)
        return 201, state.to_out().model_dump(mode="json")

    status, out, replayed = c.idempotency.execute("sessions:create", key, fingerprint(raw), run)
    if not replayed and previous is not None and previous.id != out["id"]:
        closed = c.sessions.get(previous.id)
        await c.hub.broadcast(
            previous.id,
            WsEnvelope(type="session.closed", session_id=previous.id, version=closed.version,
                       data=closed.to_out().model_dump(mode="json")),
            close_after=True,
        )
    return _respond(status, out, replayed)


@router.get("/sessions/{session_id}", response_model=SessionOut, responses=ERR, tags=["sessions"])
def get_session(c: C, session_id: str) -> SessionOut:
    return c.sessions.get(session_id).to_out()


@router.post("/sessions/{session_id}/close", response_model=SessionOut, responses=ERR, tags=["sessions"])
async def close_session(
    c: C, request: Request, session_id: str, body: SessionCloseRequest | None = None, idempotency_key: IdemKey = None
):
    key = validate_key(idempotency_key)
    raw = await request.body()
    expected = body.expected_version if body else None

    def run() -> tuple[int, dict[str, Any]]:
        return 200, c.sessions.close(session_id, expected).to_out().model_dump(mode="json")

    status, out, replayed = c.idempotency.execute(f"sessions:close:{session_id}", key, fingerprint(raw), run)
    if not replayed:
        await c.hub.broadcast(
            session_id,
            WsEnvelope(type="session.closed", session_id=session_id, version=out["version"], data=out),
            close_after=True,
        )
    return _respond(status, out, replayed)


# ------------------------------------------------------------------ competições
@router.get("/competitions/options", response_model=CompetitionOptions, tags=["competitions"])
def options(c: C) -> CompetitionOptions:
    return competition_options(c.data.club_count(), c.data.catalog_ready(), c.sessions.has_active)


# ------------------------------------------------------------------ imagens (escudos e fotos por identificador)
def _asset(path_candidates: list, kind: str) -> FileResponse:
    for p in path_candidates:
        if p.is_file():
            return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})
    raise AppError(404, ErrorCode.NOT_FOUND, f"Imagem de {kind} não encontrada.")


@router.get("/assets/clubs/{club_uid}", tags=["assets"], responses={404: {"model": ErrorResponse}})
def club_logo(c: C, club_uid: int):
    return _asset([c.settings.graphics_dir / "Clubes" / f"club_{club_uid}.png"], "clube")


@router.get("/assets/players/{unique_id}", tags=["assets"], responses={404: {"model": ErrorResponse}})
def player_face(c: C, unique_id: int):
    base = c.settings.graphics_dir / "Faces"
    return _asset([base / f"{unique_id}.{ext}" for ext in ("png", "jpg", "jpeg")], "jogador")


# ------------------------------------------------------------------ websocket
@ws_router.websocket("/ws/sessions/{session_id}")
async def session_socket(ws: WebSocket, session_id: str) -> None:
    c: Container = ws.app.state.container
    try:
        state = c.sessions.get(session_id)
    except AppError:
        await ws.close(code=4404)
        return
    await ws.accept()
    await c.hub.join(session_id, ws)
    try:
        await ws.send_json(
            WsEnvelope(type="session.snapshot", session_id=session_id, version=state.version,
                       data=state.to_out().model_dump(mode="json")).model_dump(mode="json")
        )
        if state.status == "closed":
            await ws.close(code=1000)
            return
        while True:
            msg = await ws.receive_json()
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await ws.send_json(WsEnvelope(type="pong", session_id=session_id).model_dump(mode="json"))
            else:
                await ws.send_json(
                    WsEnvelope(type="error", session_id=session_id,
                               data={"code": "UNSUPPORTED_MESSAGE", "message": "Mensagem não suportada nesta entrega."}
                               ).model_dump(mode="json")
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await c.hub.leave(session_id, ws)
