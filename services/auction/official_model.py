"""AuctionModel OFICIAL, aprovado pelo responsável em 2026-11-19 (docs/architecture/proposta-auction-model.md).

Ajustes pedidos pelo responsável na aprovação:
- atletas abaixo da mediana bem mais baratos: a curva do valor é mais inclinada abaixo de overall 70 (§3);
- muito mais chance de atletas acima da mediana nas rodadas: peso 6 contra 1 (§5);
- 20 formações oficiais (§6, lista DR-11, `squadforce_shared.domain.formations`).

O modelo "solto" (`OfficialAuctionModel()`) só fornece regras independentes da base: formações, perfis dos bots
e curvas de preço. Tudo que depende da base (overall calibrado, qualidade, preços por atleta, reservas, sorteio
dos atletas) exige `for_pool(base)`, que o motor do leilão chama com a base atual. Assim, a calibração é refeita
sempre que a base é substituída (GDD §4 e §7).
"""

from __future__ import annotations

import dataclasses
import math
import random
import statistics
from collections import Counter
from typing import Mapping, Sequence

from services.match_engine.attributes import skill
from services.match_engine.lineup import to_match_player
from services.match_engine.params import DEFAULT_PARAMS
from squadforce_shared.domain.formations import OFFICIAL_FORMATIONS, Formation
from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import POSITION_ORDER, Position

from .model import BotProfile, Reserves, TradeProfile

P = Position
VERSION = "oficial-1.0"

# ------------------------------------------------------------------ §1 overall calibrado (PE-01)
# Índice bruto = média ponderada das composições de atributos do motor (SKILLS), por posição principal.
POSITION_MIX: Mapping[Position, Mapping[str, float]] = {
    P.GK: {"goalkeeping": 0.85, "buildup": 0.15},
    P.DR: {"box_defense": 0.45, "pressing": 0.20, "progression": 0.20, "attack_movement": 0.15},
    P.DL: {"box_defense": 0.45, "pressing": 0.20, "progression": 0.20, "attack_movement": 0.15},
    P.DC: {"box_defense": 0.70, "heading": 0.20, "buildup": 0.10},
    P.DM: {"midfield_defense": 0.50, "buildup": 0.30, "pressing": 0.20},
    P.MC: {"progression": 0.40, "creation": 0.30, "buildup": 0.20, "pressing": 0.10},
    P.STC: {"finishing": 0.45, "attack_movement": 0.25, "heading": 0.15, "creation": 0.15},
}
TARGET_MEDIAN = 70.0
SCALE = 8.0  # pontos de overall por desvio (robusto) da posição
OVERALL_MIN, OVERALL_MAX = 30.0, 99.0
IQR_TO_SIGMA = 1.349
MAX_POSITIONAL_PENALTY = 0.35  # GDD §3; mesma curva linear do motor (PE-03)

# ------------------------------------------------------------------ §3 valor de mercado e lance mínimo (PE-02)
VALUE_AT_MEDIAN = 3_000_000
K_ABOVE = math.log(35 / 3) / 20  # 70 → R$ 3 mi; 90 → R$ 35 mi
K_BELOW = 0.25  # abaixo da mediana: bem mais barato (ajuste do responsável)
VALUE_MIN, VALUE_MAX = 100_000, 50_000_000
MIN_BID_FRACTION = 0.5
MIN_BID_MAX = 30_000_000
BASIC_PRICE_MAX = 500_000
AGE_FACTORS = ((23, 1.10), (29, 1.00), (31, 0.85), (33, 0.70), (200, 0.55))

# ------------------------------------------------------------------ §4 reservas (PE-04)
BASIC_MARGIN = 0.25
COMPLEMENTARY_FACTOR = 1.5
HIGHLIGHT_PERCENTILE = 85

# ------------------------------------------------------------------ §5 sorteio (PE-05) e atletas da rodada
NEED_BASE = 0.25
AVAILABILITY_FULL = 10
RECENCY = ((2, 0.4), (5, 0.7))  # saiu numa das 2 últimas rodadas: 0,4; da 3ª à 5ª: 0,7
MAX_UNSOLD_APPEARANCES = 2
WEIGHT_ABOVE_MEDIAN, WEIGHT_BELOW_MEDIAN = 6.0, 1.0

# ------------------------------------------------------------------ §7 e §8 personalidades (PB-01, PB-02)
# Revisados e aprovados em 2026-11-19 (bots mais dispostos a pagar; lotes exploratórios em proposta §7).
APPROVED_BOT_PROFILES: Mapping[str, BotProfile] = {
    "aggressive": BotProfile(2.0, 0.85, 0.0, 0.1, 2.0, 0.50, (0.5, 3.0), 2.0),
    "conservative": BotProfile(1.2, 0.50, 0.5, 0.6, 1.1, 0.20, (1.0, 5.0), 1.5),
    "balanced": BotProfile(1.6, 0.70, 0.2, 0.3, 1.5, 0.35, (0.5, 4.0), 2.0),
    "opportunist": BotProfile(1.3, 0.30, 0.1, 0.9, 1.3, 0.40, (2.0, 6.0), 3.0),
}
APPROVED_TRADE_PROFILES: Mapping[str, TradeProfile] = {
    "aggressive": TradeProfile(0.6, 6_000_000, 0.20, 0.3, 0.30, (6.0, 15.0), (1.0, 4.0)),
    "conservative": TradeProfile(0.2, 12_000_000, 0.05, 0.8, 0.10, (15.0, 30.0), (3.0, 8.0)),
    "balanced": TradeProfile(0.4, 8_000_000, 0.10, 0.5, 0.20, (10.0, 20.0), (2.0, 6.0)),
    "opportunist": TradeProfile(0.5, 7_000_000, 0.05, 0.4, 0.25, (5.0, 12.0), (1.0, 5.0)),
}


def _round_100k(v: float) -> int:
    return int(round(v / 100_000)) * 100_000


def age_factor(age: int) -> float:
    return next(f for limit, f in AGE_FACTORS if age <= limit)


def market_value_for(overall: float, age: int) -> int:
    """§3: overall calibrado + idade. Curva mais inclinada abaixo da mediana."""
    k = K_ABOVE if overall >= TARGET_MEDIAN else K_BELOW
    raw = VALUE_AT_MEDIAN * math.exp(k * (overall - TARGET_MEDIAN)) * age_factor(age)
    return max(VALUE_MIN, min(VALUE_MAX, _round_100k(raw)))


def minimum_bid_for(market_value: int) -> int:
    return max(VALUE_MIN, min(MIN_BID_MAX, _round_100k(MIN_BID_FRACTION * market_value)))


def raw_index(player: PlayerProfile, position: Position) -> float:
    """Índice bruto na posição, sem penalidade posicional (familiaridade tratada à parte)."""
    mp = to_match_player(player)
    return sum(w * skill(mp, name, position, 100.0, 1.0, _NO_PENALTY) for name, w in POSITION_MIX[position].items())


_NO_PENALTY = dataclasses.replace(DEFAULT_PARAMS, max_positional_penalty=0.0)
_DEMAND = Counter(pos for f in OFFICIAL_FORMATIONS for pos in f.slots)
DEMAND_SHARE: Mapping[Position, float] = {p: _DEMAND[p] / sum(_DEMAND.values()) for p in POSITION_ORDER}


class OfficialAuctionModel:
    version = VERSION

    def __init__(self, calibration: Mapping[Position, tuple[float, float]] | None = None,
                 overall_by_id: Mapping[int, float] | None = None):
        self._calibration = dict(calibration) if calibration else None
        values = sorted((overall_by_id or {}).values())
        # cache de índices brutos: (id, posição) -> (objeto de atributos, valor). Só vale para o MESMO objeto
        # de atributos, então perfis diferentes com o mesmo ID nunca se confundem.
        self._raw: dict[tuple[int, Position], tuple[object, float]] = {}
        self.base_median = statistics.median(values) if values else TARGET_MEDIAN
        rank = max(1, math.ceil(HIGHLIGHT_PERCENTILE / 100 * len(values)))
        self.highlight_threshold = values[rank - 1] if values else math.inf

    # ---------------------------------------------------------------- calibração pela base
    def for_pool(self, pool: Sequence[PlayerProfile]) -> "OfficialAuctionModel":
        by_pos: dict[Position, list[float]] = {}
        raws: dict[int, float] = {}
        for p in pool:
            r = raw_index(p, p.main_position)
            raws[p.unique_id] = r
            by_pos.setdefault(p.main_position, []).append(r)
        calibration: dict[Position, tuple[float, float]] = {}
        all_raw = [r for v in by_pos.values() for r in v]
        for pos in POSITION_ORDER:
            vals = by_pos.get(pos) or all_raw  # posição sem atletas: usa a base toda
            calibration[pos] = _median_sigma(vals) if vals else (50.0, 10.0)
        overall = {p.unique_id: _scale(raws[p.unique_id], calibration[p.main_position]) for p in pool}
        bound = OfficialAuctionModel(calibration, overall)
        bound._raw = {(p.unique_id, p.main_position): (p.attributes, raws[p.unique_id]) for p in pool}
        return bound

    def _raw_index(self, player: PlayerProfile, position: Position) -> float:
        key = (player.unique_id, position)
        hit = self._raw.get(key)
        if hit is not None and hit[0] is player.attributes:
            return hit[1]
        value = raw_index(player, position)
        self._raw[key] = (player.attributes, value)
        return value

    def _require(self) -> dict[Position, tuple[float, float]]:
        if self._calibration is None:
            raise RuntimeError("Modelo oficial sem calibração: use for_pool(base) antes de avaliar atletas.")
        return self._calibration

    # ---------------------------------------------------------------- PE-01 / PE-03
    def overall(self, player: PlayerProfile) -> float:
        cal = self._require()
        return _scale(self._raw_index(player, player.main_position), cal[player.main_position])

    def player_quality(self, player: PlayerProfile, position: Position) -> float:
        cal = self._require()
        fam = max(1, min(100, int(player.familiarity.get(position, 1))))
        factor = 1.0 - MAX_POSITIONAL_PENALTY * (100 - fam) / 99
        return _scale(self._raw_index(player, position), cal[position]) * factor

    # ---------------------------------------------------------------- PE-02 / PE-04 preços
    def market_value(self, player: PlayerProfile) -> int:
        return market_value_for(self.overall(player), player.age)

    def minimum_bid(self, player: PlayerProfile) -> int:
        return minimum_bid_for(self.market_value(player))

    def basic_price(self, player: PlayerProfile) -> int:
        return min(BASIC_PRICE_MAX, self.minimum_bid(player))

    # ---------------------------------------------------------------- PM-01
    def formations(self) -> Sequence[Formation]:
        return OFFICIAL_FORMATIONS

    # ---------------------------------------------------------------- PE-05
    def position_weights(self, eligible: Sequence[Position], needs: Mapping[Position, float],
                         recent: Sequence[Position], available: Mapping[Position, int]) -> Mapping[Position, float]:
        total = sum(max(0.0, needs.get(p, 0.0)) for p in eligible)
        recent = list(recent)
        out: dict[Position, float] = {}
        for p in eligible:
            share = max(0.0, needs.get(p, 0.0)) / total if total > 0 else 1 / len(POSITION_ORDER)
            avail = min(1.0, available.get(p, 0) / AVAILABILITY_FULL)
            out[p] = (NEED_BASE + share) * avail * _recency(p, recent)
        return out

    # ---------------------------------------------------------------- §5 atletas da rodada
    def pick_round_players(self, candidates: Sequence[PlayerProfile], unsold_counts: Mapping[int, int],
                           rng: random.Random, k: int) -> Sequence[int]:
        cands = sorted(candidates, key=lambda c: c.unique_id)
        fresh = [c for c in cands if unsold_counts.get(c.unique_id, 0) < MAX_UNSOLD_APPEARANCES]
        if len(fresh) < k:  # poucos atletas: completa com os menos repetidos
            rest = sorted((c for c in cands if c not in fresh),
                          key=lambda c: (unsold_counts.get(c.unique_id, 0), c.unique_id))
            fresh = fresh + rest[: k - len(fresh)]
        above = [c for c in fresh if self.overall(c) >= self.base_median]
        below = [c for c in fresh if self.overall(c) < self.base_median]
        picked: list[PlayerProfile] = []
        if above and below and k >= 2:  # variedade de qualidade: ao menos um de cada grupo
            picked += [rng.choice(above), rng.choice(below)]
        pool = [c for c in fresh if c not in picked]
        while len(picked) < k and pool:
            weights = [WEIGHT_ABOVE_MEDIAN if self.overall(c) >= self.base_median else WEIGHT_BELOW_MEDIAN
                       for c in pool]
            choice = rng.choices(pool, weights=weights, k=1)[0]
            picked.append(choice)
            pool.remove(choice)
        return [c.unique_id for c in picked]

    # ---------------------------------------------------------------- PE-04 reservas
    def build_reserves(self, unsold: Sequence[PlayerProfile], slots_to_fill: int, num_clubs: int) -> Reserves:
        by_pos: dict[Position, list[PlayerProfile]] = {p: [] for p in POSITION_ORDER}
        for p in unsold:
            by_pos[p.main_position].append(p)
        for v in by_pos.values():
            v.sort(key=lambda c: (self.overall(c), c.unique_id))  # do mais simples ao melhor

        size = min(len(unsold), math.ceil(slots_to_fill * (1 + BASIC_MARGIN)))
        quotas = {p: math.ceil(size * DEMAND_SHARE[p]) for p in POSITION_ORDER}
        quotas[P.GK] = max(quotas[P.GK], min(num_clubs, slots_to_fill))  # distribuição protegida
        basic: list[PlayerProfile] = []
        for pos in POSITION_ORDER:
            basic += by_pos[pos][: quotas[pos]]
        if len(basic) > size:  # cotas arredondadas para cima: corta os melhores das posições mais folgadas
            basic.sort(key=lambda c: (self.overall(c), c.unique_id))
            keep_gk = [c for c in basic if c.main_position is P.GK][: quotas[P.GK]]
            others = [c for c in basic if c not in keep_gk][: max(0, size - len(keep_gk))]
            basic = keep_gk + others
        if len(basic) < size:  # posições sem atletas suficientes: cota passa às demais
            chosen = {c.unique_id for c in basic}
            spare = sorted((c for c in unsold if c.unique_id not in chosen),
                           key=lambda c: (self.overall(c), c.unique_id))
            basic += spare[: size - len(basic)]
        basic_ids = {c.unique_id for c in basic}

        comp: list[PlayerProfile] = []
        highlights_left = math.ceil(num_clubs / 4)
        for pos in POSITION_ORDER:
            quota = math.ceil(COMPLEMENTARY_FACTOR * num_clubs * DEMAND_SHARE[pos])
            for c in reversed(by_pos[pos]):  # do melhor para o pior
                if quota == 0:
                    break
                if c.unique_id in basic_ids:
                    continue
                if self.overall(c) >= self.highlight_threshold:
                    if highlights_left == 0:
                        continue
                    highlights_left -= 1
                comp.append(c)
                quota -= 1
        return Reserves(tuple(c.unique_id for c in basic), tuple(c.unique_id for c in comp))

    # ---------------------------------------------------------------- PB-01 / PB-02
    def bot_profile(self, personality: str) -> BotProfile:
        return APPROVED_BOT_PROFILES[personality]

    def trade_profile(self, personality: str) -> TradeProfile:
        return APPROVED_TRADE_PROFILES[personality]


def _median_sigma(values: Sequence[float]) -> tuple[float, float]:
    med = statistics.median(values)
    if len(values) < 4:
        return med, 1.0
    q = statistics.quantiles(values, n=4)
    return med, max(1e-6, (q[2] - q[0]) / IQR_TO_SIGMA)


def _scale(raw: float, cal: tuple[float, float]) -> float:
    med, sigma = cal
    return max(OVERALL_MIN, min(OVERALL_MAX, TARGET_MEDIAN + SCALE * (raw - med) / sigma))


def _recency(position: Position, recent: Sequence[Position]) -> float:
    for i, p in enumerate(reversed(recent), start=1):
        if p is position:
            return next((f for lim, f in RECENCY if i <= lim), 1.0)
    return 1.0


__all__ = ["APPROVED_BOT_PROFILES", "APPROVED_TRADE_PROFILES", "OfficialAuctionModel", "market_value_for",
           "minimum_bid_for", "raw_index"]
