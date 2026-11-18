"""Fábricas para testes do motor: atletas sintéticos com força controlada e escalações prontas."""

from __future__ import annotations

import dataclasses
from typing import Sequence

from services.match_engine.calibration import FORMATION_433
from services.match_engine.params import DEFAULT_PARAMS, GOALKEEPING, MENTAL, PHYSICAL, TECHNICAL, MatchParams
from services.match_engine.types import MatchInput, MatchPlayer, TeamSheet
from squadforce_shared.domain.positions import Position

ALL = (*TECHNICAL, *MENTAL, *PHYSICAL, *GOALKEEPING)


def player(uid: int, pos: Position, level: int = 60, **overrides: int) -> MatchPlayer:
    attrs = {a: level for a in ALL}
    if pos is not Position.GK:
        for a in GOALKEEPING:
            attrs[a] = 10
    attrs["attributes_injury_proneness"] = 30
    attrs["attributes_dirtiness"] = 40
    attrs.update({f"attributes_{k}": v for k, v in overrides.items()})
    fam = {p: (100 if p is pos else 1) for p in Position}
    return MatchPlayer(uid, f"J{uid}", attrs, fam, pos)


def team(club: int, level: int = 60, formation: Sequence[Position] = FORMATION_433, posture: str = "equilibrada",
         bench_size: int = 7, **overrides: int) -> TeamSheet:
    base = club * 100
    starters = tuple(player(base + i, pos, level, **overrides) for i, pos in enumerate(formation, start=1))
    bench_pos = [Position.GK, Position.DC, Position.DR, Position.DM, Position.MC, Position.STC, Position.STC][:bench_size]
    bench = tuple(player(base + 50 + i, pos, level, **overrides) for i, pos in enumerate(bench_pos))
    return TeamSheet(club, tuple(formation), starters, bench, posture)


def match(seed: int = 1, home: TeamSheet | None = None, away: TeamSheet | None = None, competition: str = "liga") -> MatchInput:
    return MatchInput(f"M-{seed}", competition, home or team(1), away or team(2), seed)


def params(**kw) -> MatchParams:
    return dataclasses.replace(DEFAULT_PARAMS, **kw)
