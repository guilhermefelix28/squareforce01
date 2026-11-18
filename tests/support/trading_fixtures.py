"""Fábricas para testes do mercado: elencos de 18 montados diretamente (rápido) e perfis controlados."""

from __future__ import annotations

import random
from dataclasses import dataclass

from services.auction.engine import Contract
from services.auction.model import PERSONALITIES, TradeProfile
from services.trading.engine import TradingEngine
from squadforce_shared.domain.positions import POSITION_ORDER

from .auction_fixtures import ManualClock, make_pool
from .fake_auction_model import FAKE_TRADE_PROFILES, FakeAuctionModel

NEVER = 10_000.0  # bots não propõem dentro dos 180 s
ALWAYS_ACCEPT = TradeProfile(1e9, 0, 1e9, 1e9, 0.0, (NEVER, NEVER), (1.0, 1.0))
ALWAYS_REJECT = TradeProfile(0.0, 10**12, -10.0, 1e9, 0.0, (NEVER, NEVER), (1.0, 1.0))
SILENT = TradeProfile(0.0, 10**12, -10.0, 1e9, 0.0, (NEVER, NEVER), (9.5, 9.9))  # responde só perto do prazo


def model_with(profile: TradeProfile | None = None, profiles=None) -> FakeAuctionModel:
    return FakeAuctionModel(trade_profiles=profiles or {p: profile for p in PERSONALITIES})


@dataclass
class Market:
    engine: TradingEngine
    clock: ManualClock
    clubs: list[int]

    @property
    def user(self) -> int:
        return self.clubs[0]

    def roster(self, club: int) -> list[int]:
        return [k.player_id for k in self.engine.clubs[club].contracts]

    def total_money(self) -> int:
        return sum(c.budget for c in self.engine.clubs.values())


def make_market(num_clubs: int = 4, model=None, budget: int = 50_000_000, seed: int = 1, start: bool = True) -> Market:
    pool = make_pool(per_position=max(10, num_clubs * 3), seed=seed)
    by_pos = {p: [x for x in pool if x.main_position is p] for p in POSITION_ORDER}
    shape = [p for p in POSITION_ORDER for _ in range(3)][:18] + [POSITION_ORDER[0]] * 0
    shape = (shape + list(POSITION_ORDER) * 3)[:18]
    clubs = list(range(201, 201 + num_clubs))
    taken: dict[int, list[Contract]] = {c: [] for c in clubs}
    cursor = {p: 0 for p in POSITION_ORDER}
    for c in clubs:
        for pos in shape:
            pl = by_pos[pos][cursor[pos]]
            cursor[pos] += 1
            taken[c].append(Contract(pl.unique_id, 1_000_000, "auction", 1))
    rng = random.Random(seed)
    personalities = {c: rng.choice(PERSONALITIES) for c in clubs}
    clock = ManualClock()
    engine = TradingEngine(
        clubs={c: (budget, taken[c], personalities[c]) for c in clubs},
        user_club_uid=clubs[0],
        players={p.unique_id: p for p in pool},
        model=model or model_with(ALWAYS_REJECT),
        rng=random.Random(seed),
        clock=clock,
    )
    if start:
        engine.start()
    return Market(engine, clock, clubs)


__all__ = ["ALWAYS_ACCEPT", "ALWAYS_REJECT", "FAKE_TRADE_PROFILES", "Market", "SILENT", "make_market", "model_with"]
