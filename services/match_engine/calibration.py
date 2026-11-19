"""Lotes EXPLORATÓRIOS de simulação: estatísticas observadas do motor.

Não é calibração oficial: as referências estatísticas do futebol real ainda não foram fornecidas/aprovadas
(PM-02). As faixas usadas aqui são REFERÊNCIAS PRELIMINARES de ligas profissionais (ordem de grandeza
amplamente conhecida), servem só para detectar comportamentos absurdos e estão marcadas como tal.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import Position as P

from .engine import simulate
from .lineup import build_team_sheet
from .params import DEFAULT_PARAMS, POSTURES, MatchParams
from .types import MatchInput
from .validation import validate_result

FORMATION_433 = (P.GK, P.DR, P.DC, P.DC, P.DL, P.DM, P.MC, P.MC, P.STC, P.STC, P.STC)
FORMATION_442 = (P.GK, P.DR, P.DC, P.DC, P.DL, P.DM, P.MC, P.MC, P.MC, P.STC, P.STC)
FORMATION_532 = (P.GK, P.DR, P.DC, P.DC, P.DC, P.DL, P.DM, P.MC, P.MC, P.STC, P.STC)
SAMPLE_FORMATIONS = (FORMATION_433, FORMATION_442, FORMATION_532)  # amostra para testes do motor (oficiais: squadforce_shared.domain.formations)

# Referências PRELIMINARES (não aprovadas) — por partida, salvo indicação.
PRELIMINARY_REFERENCES = {
    "goals_per_match": (2.3, 3.0),
    "draw_rate": (0.20, 0.32),
    "nil_nil_rate": (0.05, 0.11),
    "shots_per_team": (10.0, 15.0),
    "on_target_per_team": (3.2, 5.5),
    "xg_per_team": (1.1, 1.6),
    "conversion_per_shot": (0.08, 0.13),
    "fouls_per_match": (20.0, 28.0),
    "yellows_per_match": (3.0, 5.5),
    "reds_per_match": (0.08, 0.30),
    "corners_per_match": (8.0, 12.0),
}


@dataclass
class BatchReport:
    matches: int
    metrics: dict[str, float]
    score_distribution: dict[str, int]
    invalid: int
    abandoned: int
    within_reference: dict[str, bool]


def run_batch(pool_by_club: dict[int, Sequence[PlayerProfile]], n: int, seed: int = 1,
              params: MatchParams = DEFAULT_PARAMS, postures: Sequence[str] = ("equilibrada",)) -> BatchReport:
    rng = random.Random(seed)
    clubs = sorted(pool_by_club)
    goals, draws, nil, invalid, abandoned = [], 0, 0, 0, 0
    agg = Counter()
    scores = Counter()
    for i in range(n):
        a, b = rng.sample(clubs, 2)
        fa, fb = rng.choice(SAMPLE_FORMATIONS), rng.choice(SAMPLE_FORMATIONS)
        home = build_team_sheet(a, pool_by_club[a], fa, posture=rng.choice(postures), params=params)
        away = build_team_sheet(b, pool_by_club[b], fb, posture=rng.choice(postures), params=params)
        m = MatchInput(f"X-{i}", "exploratorio", home, away, seed=rng.getrandbits(63))
        res = simulate(m, params)
        if validate_result(res, m, params):
            invalid += 1
        abandoned += res.status == "abandoned"
        g = sum(res.score)
        goals.append(g)
        draws += res.score[0] == res.score[1]
        nil += g == 0
        hi, lo = max(res.score), min(res.score)
        scores[f"{hi}-{lo}" if hi < 5 else "5+"] += 1
        for side in ("home", "away"):
            s = res.stats[side]
            for k in ("shots", "shots_on_target", "xg", "fouls", "yellow_cards", "red_cards", "corners", "goals",
                      "big_chances", "saves_made", "injuries", "substitutions", "possession_pct", "shots_blocked"):
                agg[k] += s[k]
    teams = 2 * n
    metrics = {
        "goals_per_match": statistics.mean(goals),
        "goals_sd": statistics.pstdev(goals),
        "draw_rate": draws / n,
        "nil_nil_rate": nil / n,
        "five_plus_goals_rate": sum(1 for g in goals if g >= 5) / n,
        "shots_per_team": agg["shots"] / teams,
        "on_target_per_team": agg["shots_on_target"] / teams,
        "xg_per_team": agg["xg"] / teams,
        "conversion_per_shot": agg["goals"] / max(1, agg["shots"]),
        "big_chances_per_team": agg["big_chances"] / teams,
        "fouls_per_match": agg["fouls"] / n,
        "yellows_per_match": agg["yellow_cards"] / n,
        "reds_per_match": agg["red_cards"] / n,
        "corners_per_match": agg["corners"] / n,
        "injuries_per_match": agg["injuries"] / n,
        "subs_per_team": agg["substitutions"] / teams,
        "blocked_per_team": agg["shots_blocked"] / teams,
    }
    within = {k: lo <= metrics[k] <= hi for k, (lo, hi) in PRELIMINARY_REFERENCES.items()}
    return BatchReport(n, metrics, dict(scores), invalid, abandoned, within)


__all__ = ["BatchReport", "FORMATION_433", "FORMATION_442", "FORMATION_532", "POSTURES", "PRELIMINARY_REFERENCES",
           "SAMPLE_FORMATIONS", "run_batch"]
