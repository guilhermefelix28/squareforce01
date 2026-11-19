"""Fábricas para testes de temporada: elencos sintéticos de 18 atletas e Liga/Copa prontas."""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from services.competition.planner import build_cup_bracket, build_league_schedule
from services.competition.standings import BRASILEIRAO_TIEBREAKERS
from services.competition.season import Season
from services.competition.worker import FixtureOutcome, FixtureTask, play_fixture
from services.match_engine.calibration import SAMPLE_FORMATIONS
from squadforce_shared.domain.competition import LeagueRounds
from squadforce_shared.domain.positions import Position as P

from .match_fixtures import player

SQUAD_POSITIONS = (P.GK, P.GK, P.DR, P.DL, P.DC, P.DC, P.DC, P.DM, P.DM, P.MC, P.MC, P.MC, P.MC,
                   P.STC, P.STC, P.STC, P.STC, P.DC)
USER = 1


def squad(club: int, level: int = 60):
    return [player(club * 100 + i, pos, level) for i, pos in enumerate(SQUAD_POSITIONS, start=1)]


def clubs(n: int, levels: dict[int, int] | None = None) -> list[int]:
    return list(range(1, n + 1))


def make_season(kind: str, n: int, *, rounds: LeagueRounds = LeagueRounds.SINGLE, seed: int = 7,
                levels: dict[int, int] | None = None, runner: Callable[[FixtureTask], FixtureOutcome] = play_fixture,
                tiebreakers=BRASILEIRAO_TIEBREAKERS) -> Season:
    ids = clubs(n)
    rng = random.Random(seed)
    structure = build_league_schedule(ids, rounds, rng) if kind == "league" else build_cup_bracket(ids, rng)
    levels = levels or {}
    return Season(
        competition_id=kind, structure=structure,
        squads={c: squad(c, levels.get(c, 60)) for c in ids}, names={c: f"Clube {c:02}" for c in ids},
        user_club=USER, personalities={c: ("aggressive", "balanced", "conservative", "opportunist")[c % 4] for c in ids},
        formations=SAMPLE_FORMATIONS, seed=seed, runner=runner, tiebreakers=tiebreakers,
    )


def run_all(season: Season, workers: int = 4) -> None:
    with ThreadPoolExecutor(max_workers=workers) as ex:
        while season.phase != "finished":
            season.play(ex)
            season.advance()
