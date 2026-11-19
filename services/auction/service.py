"""AuctionService: um motor por sessão (somente em memória) e visões públicas tipadas."""

from __future__ import annotations

import random
import secrets
import threading
from typing import Callable

from squadforce_shared.contracts import (
    AuctionBidOut,
    AuctionClubOut,
    AuctionContractOut,
    AuctionPlayerOut,
    AuctionRoundOut,
    AuctionRoundResultOut,
    AuctionSaleOut,
    AuctionSquadOut,
    AuctionStateOut,
    AuctionSummaryOut,
    CompetitionConfig,
)
from squadforce_shared.domain.players import PlayerProfile

from . import rules
from .engine import AuctionEngine, Contract
from .model import AuctionModel

RECENT_RESULTS = 8


def _ms(seconds: float) -> int:
    return max(0, int(round(seconds * 1000)))


class AuctionService:
    def __init__(self, clock: Callable[[], float], has_photo: Callable[[int], bool] = lambda _: False):
        self.clock = clock
        self._has_photo = has_photo
        self._engines: dict[str, AuctionEngine] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------- ciclo de vida
    def create(
        self,
        session_id: str,
        config: CompetitionConfig,
        participants: list[int],
        pool: list[PlayerProfile],
        model: AuctionModel,
        seed: int | None = None,
    ) -> AuctionEngine:
        engine = AuctionEngine(
            participants=participants,
            user_club_uid=config.user_club_uid,
            fmt=config.format,
            num_clubs=config.num_clubs,
            pool=pool,
            model=model,
            rng=random.Random(seed if seed is not None else secrets.randbits(63)),
            clock=self.clock,
        )
        with self._lock:
            self._engines[session_id] = engine
        engine.start()
        return engine

    def get(self, session_id: str) -> AuctionEngine | None:
        with self._lock:
            return self._engines.get(session_id)

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._engines.pop(session_id, None)

    def running(self) -> list[tuple[str, AuctionEngine]]:
        with self._lock:
            return [(sid, e) for sid, e in self._engines.items() if e.phase == "running"]

    # -------------------------------------------------------------- visões
    def _contract(self, e: AuctionEngine, k: Contract) -> AuctionContractOut:
        p = e.players[k.player_id]
        return AuctionContractOut(
            player_id=p.unique_id, name=p.name, position=p.main_position, age=p.age,
            price=k.price, source=k.source, round=k.round,
        )

    def state(self, session_id: str, e: AuctionEngine) -> AuctionStateOut:
        with e.lock:
            now = self.clock()
            e._advance(now)  # o relógio do servidor é a referência; consultas também avançam o estado
            user = e.clubs[e.user_club_uid]
            r = e.round
            round_out = None
            active = None
            if r is not None:
                round_out = AuctionRoundOut(
                    number=r.number,
                    position=r.position,
                    players=[
                        AuctionPlayerOut(
                            unique_id=pid, name=e.players[pid].name, age=e.players[pid].age,
                            club_short_name=e.players[pid].club_short_name,
                            club_uid=e.players[pid].club_uid, position=e.players[pid].main_position,
                            minimum_bid=r.minimum_bids[pid], has_photo=self._has_photo(pid),
                        )
                        for pid in r.player_ids
                    ],
                    remaining_ms=_ms(r.ends_at - now),
                    duration_ms=_ms(r.ends_at - r.starts_at),
                )
                bid = r.bids.get(e.user_club_uid)  # SOMENTE o lance do próprio usuário
                if bid:
                    active = AuctionBidOut(round=r.number, player_id=bid.player_id, amount=bid.amount, seq=bid.seq)
            names = {pid: p.name for pid, p in e.players.items()}
            return AuctionStateOut(
                session_id=session_id,
                phase=e.phase,
                global_remaining_ms=_ms((e.ends_at or now) - now) if e.phase == "running" else 0,
                global_duration_ms=_ms(e.duration),
                round=round_out,
                user_club_uid=e.user_club_uid,
                budget=user.budget,
                max_bid=max(0, rules.max_affordable_bid(user.budget, len(user.contracts))) if user.open_slots else 0,
                open_slots=user.open_slots,
                active_bid=active,
                squad=[self._contract(e, k) for k in user.contracts],
                clubs=[
                    AuctionClubOut(club_uid=u, is_user=u == e.user_club_uid, squad_count=len(c.contracts), budget=c.budget)
                    for u, c in e.clubs.items()
                ],
                recent_results=[
                    AuctionRoundResultOut(
                        number=res.number, position=res.position,
                        sales=[AuctionSaleOut(player_id=p, player_name=names[p], club_uid=c, price=v) for p, c, v in res.sales],
                        unsold_player_ids=list(res.unsold),
                    )
                    for res in reversed(e.results[-RECENT_RESULTS:])
                ],
                rounds_completed=len(e.results),
                finish_reason=e.finish_reason,
                bid_increments=list(rules.BID_INCREMENTS),
            )

    def summary(self, session_id: str, e: AuctionEngine) -> AuctionSummaryOut:
        with e.lock:
            comp = e.completion
            assert comp is not None
            return AuctionSummaryOut(
                session_id=session_id,
                finish_reason=e.finish_reason or "",
                rounds_completed=len(e.results),
                squads=[
                    AuctionSquadOut(
                        club_uid=u, is_user=u == e.user_club_uid, budget=c.budget,
                        spent=rules.INITIAL_BUDGET - c.budget,
                        auction_signings=comp.auction_signings[u], improvement_limit=comp.improvement_limits[u],
                        contracts=[self._contract(e, k) for k in c.contracts],
                    )
                    for u, c in e.clubs.items()
                ],
            )
