"""TradingService: um mercado por sessão (somente em memória) e visões públicas tipadas."""

from __future__ import annotations

import random
import secrets
import threading
from typing import Callable

from services.auction.engine import AuctionEngine
from squadforce_shared.contracts import (
    ProposalOut,
    TradeRecordOut,
    TradingClubOut,
    TradingPlayerOut,
    TradingSquadOut,
    TradingStateOut,
)
from squadforce_shared.domain.positions import normalize_position

from . import rules
from .engine import Proposal, TradingEngine

RECENT = 8
HISTORY = 50


def _ms(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


class TradingService:
    def __init__(self, clock: Callable[[], float]):
        self.clock = clock
        self._markets: dict[str, TradingEngine] = {}
        self._lock = threading.Lock()

    def create(self, session_id: str, auction: AuctionEngine, seed: int | None = None) -> TradingEngine:
        """Abre o mercado a partir dos elencos finais do leilão (após a complementação)."""
        with auction.lock:
            if auction.phase != "completed":
                raise ValueError("O leilão ainda não terminou.")
            clubs = {u: (c.budget, list(c.contracts), c.personality) for u, c in auction.clubs.items()}
            engine = TradingEngine(
                clubs=clubs, user_club_uid=auction.user_club_uid, players=auction.players, model=auction.model,
                rng=random.Random(seed if seed is not None else secrets.randbits(63)), clock=self.clock,
            )
        with self._lock:
            self._markets[session_id] = engine
        engine.start()
        return engine

    def get(self, session_id: str) -> TradingEngine | None:
        with self._lock:
            return self._markets.get(session_id)

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._markets.pop(session_id, None)

    def running(self) -> list[tuple[str, TradingEngine]]:
        with self._lock:
            return [(s, e) for s, e in self._markets.items() if e.phase == "running"]

    # -------------------------------------------------------------- visões
    @staticmethod
    def _player(e: TradingEngine, pid: int, club: int) -> TradingPlayerOut:
        p = e.players[pid]
        return TradingPlayerOut(unique_id=pid, name=p.name, age=p.age, position=p.main_position, club_uid=club)

    def proposal_out(self, e: TradingEngine, p: Proposal, now: float) -> ProposalOut:
        return ProposalOut(
            id=p.id,
            direction="outgoing" if p.proponent == e.user_club_uid else "incoming",
            proponent_club_uid=p.proponent,
            recipient_club_uid=p.recipient,
            offered=self._player(e, p.offered_player_id, p.proponent),
            requested=self._player(e, p.requested_player_id, p.recipient),
            money=p.money,
            status=p.status,
            reason=p.reason,
            remaining_ms=_ms(p.expires_at - now) if p.status == "pending" else 0,
        )

    def state(self, session_id: str, e: TradingEngine) -> TradingStateOut:
        with e.lock:
            now = self.clock()
            e._advance(now)
            user = e.clubs[e.user_club_uid]
            mine = [p for p in e.proposals.values() if e.user_club_uid in (p.proponent, p.recipient)]
            outgoing = next((p for p in mine if p.status == "pending" and p.proponent == e.user_club_uid), None)
            incoming = [p for p in mine if p.status == "pending" and p.recipient == e.user_club_uid]
            decided = sorted((p for p in mine if p.status != "pending"), key=lambda p: (p.decided_at or 0, p.seq), reverse=True)
            return TradingStateOut(
                session_id=session_id,
                phase=e.phase if e.phase in ("running", "finished") else "running",
                remaining_ms=_ms(e.ends_at - now) if e.phase == "running" else 0,
                duration_ms=_ms(rules.MARKET_SECONDS),
                user_club_uid=e.user_club_uid,
                budget=user.budget,
                completed_trades=user.completed,
                max_trades=rules.MAX_COMPLETED_TRADES,
                outgoing=self.proposal_out(e, outgoing, now) if outgoing else None,
                incoming=[self.proposal_out(e, p, now) for p in sorted(incoming, key=lambda p: p.expires_at)],
                recent_decisions=[self.proposal_out(e, p, now) for p in decided[:RECENT]],
                history=[
                    TradeRecordOut(
                        proposal_id=r.proposal_id, proponent_club_uid=r.proponent, recipient_club_uid=r.recipient,
                        offered=self._player(e, r.offered_player_id, r.recipient),
                        requested=self._player(e, r.requested_player_id, r.proponent),
                        money=r.money, elapsed_ms=_ms(r.completed_at - (e.started_at or 0)),
                    )
                    for r in reversed(e.history[-HISTORY:])
                ],
                clubs=[
                    TradingClubOut(club_uid=u, is_user=u == e.user_club_uid, budget=c.budget, completed_trades=c.completed)
                    for u, c in e.clubs.items()
                ],
            )

    def squads(
        self, e: TradingEngine, search: str | None = None, club_uid: int | None = None, position: str | None = None
    ) -> list[TradingSquadOut]:
        """Elencos públicos com filtros por nome, clube e posição (códigos GK… ou GOL…)."""
        pos = normalize_position(position) if position else None
        term = (search or "").strip().casefold()
        with e.lock:
            e._advance(self.clock())
            out = []
            for u, c in e.clubs.items():
                if club_uid is not None and u != club_uid:
                    continue
                players = [
                    self._player(e, k.player_id, u) for k in c.contracts
                    if (pos is None or e.players[k.player_id].main_position == pos)
                    and (not term or term in e.players[k.player_id].name.casefold())
                ]
                out.append(TradingSquadOut(
                    club_uid=u, is_user=u == e.user_club_uid, budget=c.budget, completed_trades=c.completed, players=players,
                ))
            return out
