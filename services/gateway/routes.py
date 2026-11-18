"""Rotas HTTP/WebSocket do gateway. Os serviços de domínio não conhecem HTTP."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from services.auction.engine import AuctionError
from services.trading.engine import TradingError
from services.competition.options import competition_options
from squadforce_shared import __version__
from squadforce_shared.contracts import (
    AuctionBidAck,
    AuctionBidRequest,
    AuctionStateOut,
    AuctionSummaryOut,
    ProposalCreate,
    ProposalOut,
    TradingSquadOut,
    TradingStateOut,
    ClubPage,
    CompetitionConfig,
    CompetitionOptions,
    CompetitionOut,
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
            "auction": "ready" if c.auction_model is not None else "planned",
            "trading": "ready" if c.auction_model is not None else "planned",
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
        if previous is not None and previous.id != state.id:
            c.auctions.discard(previous.id)
            c.trading.discard(previous.id)
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


@router.get("/sessions/{session_id}/competition", response_model=CompetitionOut, responses=ERR, tags=["sessions"])
def get_competition(c: C, session_id: str) -> CompetitionOut:
    """Estrutura da competição da sessão: calendário da Liga ou chaveamento da Copa."""
    return c.sessions.get(session_id).to_competition_out()


@router.post("/sessions/{session_id}/close", response_model=SessionOut, responses=ERR, tags=["sessions"])
async def close_session(
    c: C, request: Request, session_id: str, body: SessionCloseRequest | None = None, idempotency_key: IdemKey = None
):
    key = validate_key(idempotency_key)
    raw = await request.body()
    expected = body.expected_version if body else None

    def run() -> tuple[int, dict[str, Any]]:
        out = c.sessions.close(session_id, expected).to_out().model_dump(mode="json")
        c.auctions.discard(session_id)  # estado do leilão e do mercado some com a sessão (sem persistência)
        c.trading.discard(session_id)
        return 200, out

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
    return competition_options(
        c.data.club_count(), c.data.eligible_clubs(), c.data.catalog_ready(), c.sessions.has_active
    )


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


# ------------------------------------------------------------------ leilão (Entrega 3)
def _auction_error(exc: AuctionError) -> AppError:
    return AppError(exc.status, exc.code, exc.message, retryable=exc.retryable, details=exc.details)


def _engine(c: Container, session_id: str):
    c.sessions.get(session_id)  # 404 se a sessão não existe
    engine = c.auctions.get(session_id)
    if engine is None:
        raise AppError(404, ErrorCode.AUCTION_NOT_FOUND, "O leilão desta sessão ainda não foi iniciado.")
    return engine


def _sync_phase(c: Container, session_id: str, engine) -> None:
    """Leilão concluído (com complementação) => sessão avança para 'squad_completion'."""
    if engine.phase == "completed":
        state = c.sessions.active()
        if state is not None and state.id == session_id and state.phase == "auction":
            c.sessions.transition(session_id, "auction", "squad_completion")


@router.post("/sessions/{session_id}/auction/start", response_model=AuctionStateOut, status_code=201, responses=ERR, tags=["auction"])
async def start_auction(c: C, request: Request, session_id: str, idempotency_key: IdemKey = None):
    key = validate_key(idempotency_key)
    raw = await request.body()

    def run() -> tuple[int, dict[str, Any]]:
        state = c.sessions.get(session_id)
        if c.auction_model is None:
            raise AppError(
                409, ErrorCode.AUCTION_MODEL_NOT_CONFIGURED,
                "O leilão depende das fórmulas de overall, valor de mercado, lance mínimo, reservas, pesos de "
                "posição, formações e perfis dos bots, ainda não aprovadas (pendências PE-01…PE-05, PM-01).",
            )
        if state.phase != "setup" or state.status != "active":
            raise AppError(409, ErrorCode.INVALID_PHASE, f"O leilão só pode começar na fase de configuração (atual: {state.phase}).")
        pool = c.data.load_player_profiles()
        c.sessions.transition(session_id, "setup", "auction")
        try:
            engine = c.auctions.create(
                session_id, state.config, list(state.participants or ()), pool, c.auction_model,
                seed=(state.seed or 0) + 1,
            )
        except (ValueError, AuctionError) as exc:
            c.sessions.transition(session_id, "auction", "setup")
            c.auctions.discard(session_id)
            raise AppError(500, ErrorCode.AUCTION_REJECTED, f"Não foi possível iniciar o leilão: {exc}") from exc
        return 201, c.auctions.state(session_id, engine).model_dump(mode="json")

    status, out, replayed = c.idempotency.execute(f"auction:start:{session_id}", key, fingerprint(raw), run)
    if not replayed:
        await c.hub.broadcast(session_id, WsEnvelope(type="auction.started", session_id=session_id))
    return _respond(status, out, replayed)


@router.get("/sessions/{session_id}/auction", response_model=AuctionStateOut, responses=ERR, tags=["auction"])
def get_auction(c: C, session_id: str) -> AuctionStateOut:
    engine = _engine(c, session_id)
    out = c.auctions.state(session_id, engine)
    _sync_phase(c, session_id, engine)
    return out


@router.post("/sessions/{session_id}/auction/bids", response_model=AuctionBidAck, responses=ERR, tags=["auction"])
async def place_bid(c: C, request: Request, session_id: str, body: AuctionBidRequest, idempotency_key: IdemKey = None):
    """Lance do usuário. A Idempotency-Key é também o identificador da operação no motor."""
    key = validate_key(idempotency_key)
    raw = await request.body()
    engine = _engine(c, session_id)

    def run() -> tuple[int, dict[str, Any]]:
        try:
            ack = engine.place_bid(engine.user_club_uid, body.player_id, body.amount, key, body.round_number)
        except AuctionError as exc:
            raise _auction_error(exc) from exc
        return 200, AuctionBidAck(
            round=ack.round, player_id=ack.player_id, amount=ack.amount, seq=ack.seq,
            replaced_player_id=ack.replaced_player_id, replayed=ack.replayed,
        ).model_dump(mode="json")

    status, out, replayed = c.idempotency.execute(f"auction:bid:{session_id}", key, fingerprint(raw), run)
    return _respond(status, out, replayed)


@router.get("/sessions/{session_id}/auction/summary", response_model=AuctionSummaryOut, responses=ERR, tags=["auction"])
def auction_summary(c: C, session_id: str) -> AuctionSummaryOut:
    engine = _engine(c, session_id)
    c.auctions.state(session_id, engine)  # avança o relógio
    _sync_phase(c, session_id, engine)
    if engine.phase != "completed":
        raise AppError(409, ErrorCode.AUCTION_NOT_FINISHED, "O resumo fica disponível após o leilão e a complementação.")
    return c.auctions.summary(session_id, engine)


async def auction_clock(container: Container, interval: float) -> None:
    """Relógio autoritativo: avança leilões e mercados em andamento e publica eventos (sem dados sigilosos)."""
    while True:
        await asyncio.sleep(interval)
        for sid, market in container.trading.running():
            try:
                events = market.tick()
                _sync_trading_phase(container, sid, market)
            except Exception:
                logging.getLogger("squadforce.trading").exception("falha no relógio do mercado %s", sid)
                continue
            for ev in events:
                await container.hub.broadcast(sid, WsEnvelope(type=ev["type"], session_id=sid, data=ev))
        for sid, engine in container.auctions.running():
            try:
                events = engine.tick()
                _sync_phase(container, sid, engine)
            except Exception:  # um leilão com erro não derruba o relógio dos demais
                logging.getLogger("squadforce.auction").exception("falha no relógio do leilão %s", sid)
                continue
            for ev in events:
                await container.hub.broadcast(sid, WsEnvelope(type=ev["type"], session_id=sid, data=ev))


# ------------------------------------------------------------------ mercado de negociações (Entrega 4)
def _trading_error(exc: TradingError) -> AppError:
    return AppError(exc.status, exc.code, exc.message, retryable=exc.retryable, details=exc.details)


def _market(c: Container, session_id: str):
    c.sessions.get(session_id)
    market = c.trading.get(session_id)
    if market is None:
        raise AppError(404, ErrorCode.MARKET_NOT_FOUND, "O mercado de negociações desta sessão ainda não foi iniciado.")
    return market


def _sync_trading_phase(c: Container, session_id: str, market) -> None:
    """Mercado encerrado => sessão avança para 'competition' (preparação das partidas, entrega futura)."""
    if market.phase == "finished":
        state = c.sessions.active()
        if state is not None and state.id == session_id and state.phase == "trading":
            c.sessions.transition(session_id, "trading", "competition")


@router.post("/sessions/{session_id}/trading/start", response_model=TradingStateOut, status_code=201, responses=ERR, tags=["trading"])
async def start_trading(c: C, request: Request, session_id: str, idempotency_key: IdemKey = None):
    """Inicia o mercado (somente por ação do usuário). Exige leilão e complementação concluídos."""
    key = validate_key(idempotency_key)
    raw = await request.body()

    def run() -> tuple[int, dict[str, Any]]:
        state = c.sessions.get(session_id)
        auction = c.auctions.get(session_id)
        if auction is not None:
            c.auctions.state(session_id, auction)  # avança o relógio do leilão
            _sync_phase(c, session_id, auction)
            state = c.sessions.get(session_id)
        if state.status != "active" or state.phase != "squad_completion" or auction is None:
            raise AppError(409, ErrorCode.INVALID_PHASE,
                           f"O mercado só abre após o leilão e a complementação (fase atual: {state.phase}).")
        c.sessions.transition(session_id, "squad_completion", "trading")
        try:
            market = c.trading.create(session_id, auction, seed=(state.seed or 0) + 2)
        except (ValueError, TradingError) as exc:
            c.sessions.transition(session_id, "trading", "squad_completion")
            c.trading.discard(session_id)
            raise AppError(500, ErrorCode.AUCTION_REJECTED, f"Não foi possível abrir o mercado: {exc}") from exc
        return 201, c.trading.state(session_id, market).model_dump(mode="json")

    status, out, replayed = c.idempotency.execute(f"trading:start:{session_id}", key, fingerprint(raw), run)
    if not replayed:
        await c.hub.broadcast(session_id, WsEnvelope(type="trading.started", session_id=session_id))
    return _respond(status, out, replayed)


@router.get("/sessions/{session_id}/trading", response_model=TradingStateOut, responses=ERR, tags=["trading"])
def get_trading(c: C, session_id: str) -> TradingStateOut:
    market = _market(c, session_id)
    out = c.trading.state(session_id, market)
    _sync_trading_phase(c, session_id, market)
    return out


@router.get("/sessions/{session_id}/trading/squads", response_model=list[TradingSquadOut], responses=ERR, tags=["trading"])
def trading_squads(
    c: C,
    session_id: str,
    search: Annotated[str | None, Query(max_length=80)] = None,
    club_uid: int | None = None,
    position: Annotated[str | None, Query(description="GK... ou GOL...")] = None,
) -> list[TradingSquadOut]:
    market = _market(c, session_id)
    try:
        return c.trading.squads(market, search, club_uid, position)
    except ValueError as exc:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, str(exc), details={"field": "position"}) from exc


def _trading_command(c: Container, session_id: str, key: str, raw: bytes, scope: str, action) -> JSONResponse:
    market = _market(c, session_id)

    def run() -> tuple[int, dict[str, Any]]:
        try:
            proposal = action(market)
        except TradingError as exc:
            raise _trading_error(exc) from exc
        with market.lock:
            out = c.trading.proposal_out(market, proposal, c.trading.clock())
        _sync_trading_phase(c, session_id, market)
        return 200, out.model_dump(mode="json")

    status, out, replayed = c.idempotency.execute(f"trading:{scope}:{session_id}", key, fingerprint(scope, raw), run)
    return _respond(status, out, replayed)


@router.post("/sessions/{session_id}/trading/proposals", response_model=ProposalOut, responses=ERR, tags=["trading"])
async def create_proposal(c: C, request: Request, session_id: str, body: ProposalCreate, idempotency_key: IdemKey = None):
    key = validate_key(idempotency_key)
    raw = await request.body()
    return _trading_command(
        c, session_id, key, raw, "propose",
        lambda m: m.propose(m.user_club_uid, body.recipient_club_uid, body.offered_player_id,
                            body.requested_player_id, body.money, key),
    )


@router.post("/sessions/{session_id}/trading/proposals/{proposal_id}/{action}", response_model=ProposalOut, responses=ERR, tags=["trading"])
async def act_on_proposal(
    c: C, request: Request, session_id: str, proposal_id: str, action: Literal["accept", "reject", "cancel"],
    idempotency_key: IdemKey = None,
):
    """accept/reject: destinatário (usuário). cancel: proponente (usuário). Uma única decisão vale."""
    key = validate_key(idempotency_key)
    raw = await request.body()

    def act(m):
        if action == "cancel":
            return m.cancel(m.user_club_uid, proposal_id, key)
        return m.respond(m.user_club_uid, proposal_id, action == "accept", key)

    return _trading_command(c, session_id, key, raw + proposal_id.encode() + action.encode(), "act", act)
