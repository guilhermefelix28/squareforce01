"""MODELO FALSO — EXCLUSIVO PARA TESTES. NÃO representa fórmulas aprovadas do SquadForce.

Serve apenas para exercitar o motor do leilão de ponta a ponta enquanto as fórmulas reais
(PE-01…PE-05, PM-01) não são fornecidas. Os números são arbitrários e simples, escolhidos para
gerar variedade suficiente nos testes. Nunca use em produção.
"""

from __future__ import annotations

import random
from typing import Mapping, Sequence

from services.auction.model import BotProfile, Formation, PlayerProfile, Reserves
from squadforce_shared.domain.positions import Position

P = Position
KEY_ATTRS = {
    P.GK: ("attributes_reflexes", "attributes_handling", "attributes_one_on_ones", "attributes_positioning"),
    P.DR: ("attributes_tackling", "attributes_marking", "attributes_pace", "attributes_crossing"),
    P.DL: ("attributes_tackling", "attributes_marking", "attributes_pace", "attributes_crossing"),
    P.DC: ("attributes_tackling", "attributes_marking", "attributes_heading", "attributes_positioning"),
    P.DM: ("attributes_tackling", "attributes_passing", "attributes_positioning", "attributes_work_rate"),
    P.MC: ("attributes_passing", "attributes_vision", "attributes_technique", "attributes_first_touch"),
    P.STC: ("attributes_finishing", "attributes_off_the_ball", "attributes_composure", "attributes_dribbling"),
}


def _round_100k(v: float) -> int:
    return max(100_000, int(round(v / 100_000)) * 100_000)


class FakeAuctionModel:
    version = "fake-test-only"

    def __init__(self, formations: Sequence[Formation] | None = None, profiles: Mapping[str, BotProfile] | None = None):
        self._formations = list(formations or [
            Formation("4-3-3", (P.GK, P.DR, P.DL, P.DC, P.DC, P.DM, P.MC, P.MC, P.STC, P.STC, P.STC)),
        ])
        self._profiles = dict(profiles or FAKE_PROFILES)
        self._overall: dict[int, float] = {}

    def overall(self, p: PlayerProfile) -> float:
        if p.unique_id not in self._overall:
            attrs = KEY_ATTRS[p.main_position]
            self._overall[p.unique_id] = sum(p.attributes.get(a, 1) for a in attrs) / len(attrs)
        return self._overall[p.unique_id]

    def player_quality(self, p: PlayerProfile, position: Position) -> float:
        fam = p.familiarity.get(position, 1)
        return self.overall(p) * (0.65 + 0.35 * fam / 100)

    def market_value(self, p: PlayerProfile) -> int:
        o = max(0.0, self.overall(p) - 30) / 60
        age = 1.1 if p.age <= 24 else (0.7 if p.age >= 32 else 1.0)
        return min(50_000_000, _round_100k(50_000_000 * o**3 * age))

    def minimum_bid(self, p: PlayerProfile) -> int:
        return min(30_000_000, _round_100k(self.market_value(p) * 0.4))

    def basic_price(self, p: PlayerProfile) -> int:
        return min(500_000, self.minimum_bid(p))

    def formations(self) -> Sequence[Formation]:
        return self._formations

    def position_weights(self, eligible, needs, recent, available) -> Mapping[Position, float]:
        return {p: 1.0 + needs.get(p, 0) for p in eligible}

    def pick_round_players(self, candidates, unsold_counts, rng: random.Random, k: int) -> Sequence[int]:
        fresh = [c for c in candidates if unsold_counts.get(c.unique_id, 0) < 2] or list(candidates)
        if len(fresh) < k:
            fresh = list(candidates)
        ranked = sorted(fresh, key=lambda c: (self.overall(c), c.unique_id))
        size = len(ranked) / k
        return [rng.choice(ranked[int(i * size): max(int(i * size) + 1, int((i + 1) * size))]).unique_id for i in range(k)]

    def build_reserves(self, unsold, slots_to_fill: int, num_clubs: int) -> Reserves:
        ranked = sorted(unsold, key=lambda c: (self.overall(c), c.unique_id))
        n_basic = min(len(ranked), max(slots_to_fill, int(slots_to_fill * 1.5)))
        basic = [p.unique_id for p in ranked[:n_basic]]
        rest = ranked[n_basic:]
        comp = [p.unique_id for p in rest[-3 * num_clubs:]]
        return Reserves(tuple(basic), tuple(comp))

    def bot_profile(self, personality: str) -> BotProfile:
        return self._profiles[personality]


FAKE_PROFILES = {
    "aggressive": BotProfile(1.6, 0.7, 0.0, 0.1, 1.8, 0.5, (0.5, 3.0), 2.0),
    "conservative": BotProfile(0.9, 0.2, 0.5, 0.6, 1.0, 0.2, (1.0, 5.0), 1.5),
    "balanced": BotProfile(1.2, 0.4, 0.2, 0.3, 1.3, 0.35, (0.5, 4.0), 2.0),
    "opportunist": BotProfile(1.0, 0.1, 0.1, 0.9, 1.2, 0.4, (2.0, 6.0), 3.0),
}
