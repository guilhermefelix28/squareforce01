"""Fábricas para testes do leilão: base sintética rápida, relógio manual e motor configurado."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from services.auction.engine import AuctionEngine
from squadforce_shared.domain.competition import CompetitionFormat
from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import POSITION_ORDER, Position

from .fake_auction_model import KEY_ATTRS, FakeAuctionModel

ALL_ATTRS = sorted({a for attrs in KEY_ATTRS.values() for a in attrs})


@dataclass
class ManualClock:
    now: float = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> float:
        self.now += seconds
        return self.now


def make_pool(per_position: int = 60, seed: int = 0, start_id: int = 1) -> list[PlayerProfile]:
    rng = random.Random(seed)
    pool, uid = [], start_id
    for pos in POSITION_ORDER:
        for _ in range(per_position):
            base = rng.randint(30, 90)
            attrs = {a: max(1, min(100, base + rng.randint(-10, 10))) for a in ALL_ATTRS}
            fam = {p: (100 if p is pos else rng.choice([1, 1, 1, 50, 70])) for p in Position}
            pool.append(PlayerProfile(
                unique_id=uid, name=f"Atleta {uid}", age=rng.randint(17, 36), club_uid=1,
                club_short_name="Origem", natural_positions=(pos,), accomplished_positions=(),
                familiarity=fam, attributes=attrs,
            ))
            uid += 1
    return pool


@dataclass
class EngineSetup:
    engine: AuctionEngine
    clock: ManualClock
    clubs: list[int] = field(default_factory=list)


def make_engine(
    num_clubs: int = 4,
    fmt: CompetitionFormat = CompetitionFormat.CUP,
    pool: list[PlayerProfile] | None = None,
    model=None,
    seed: int = 1,
    start: bool = True,
) -> EngineSetup:
    clock = ManualClock()
    clubs = list(range(101, 101 + num_clubs))
    engine = AuctionEngine(
        participants=clubs, user_club_uid=clubs[0], fmt=fmt, num_clubs=num_clubs,
        pool=pool if pool is not None else make_pool(), model=model or FakeAuctionModel(),
        rng=random.Random(seed), clock=clock,
    )
    if start:
        engine.start()
    return EngineSetup(engine, clock, clubs)


def run_to_end(setup: EngineSetup, step: float = 1.0) -> None:
    while setup.engine.phase == "running":
        setup.clock.advance(step)
        setup.engine.tick()
