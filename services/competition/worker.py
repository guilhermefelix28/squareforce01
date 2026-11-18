"""Execução isolada de UMA partida (GDD §19) — função de nível de módulo, serializável para outro processo.

A tarefa contém apenas o estado inicial imutável da própria partida (escalações, semente, contexto público
do início da rodada e decisões do usuário). Em um processo separado, a partida não tem como acessar
eventos ou resultados de outros confrontos simultâneos.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field

from services.bot_ai.tactics import PreMatchContext, TacticalBot
from services.match_engine.engine import simulate
from services.match_engine.types import MatchInput, MatchResult, PostureChange, TeamSheet
from services.match_engine.validation import validate_result


@dataclass(frozen=True)
class FixtureTask:
    snapshot_id: str
    match_id: str
    round_no: int
    competition: str
    home_club: int
    away_club: int
    home: TeamSheet
    away: TeamSheet
    seed: int
    knockout: bool
    neutral_venue: bool
    home_context: PreMatchContext | None  # None = lado do usuário (sem controlador automático)
    away_context: PreMatchContext | None
    user_decisions: tuple[PostureChange, ...] = ()
    eligible_home: frozenset[int] = field(default_factory=frozenset)
    eligible_away: frozenset[int] = field(default_factory=frozenset)


@dataclass(frozen=True)
class FixtureOutcome:
    snapshot_id: str
    match_id: str
    result: MatchResult | None
    error: str | None = None
    problems: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.result is not None and self.error is None and not self.problems


def match_input(task: FixtureTask) -> MatchInput:
    return MatchInput(task.match_id, task.competition, task.home, task.away, task.seed,
                      neutral_venue=task.neutral_venue, knockout=task.knockout)


def play_fixture(task: FixtureTask) -> FixtureOutcome:
    """Simula e valida uma partida. Mesma tarefa => mesmo resultado (semente e decisões preservadas)."""
    try:
        controllers = {}
        if task.home_context is not None:
            controllers[0] = TacticalBot(task.home_context)
        if task.away_context is not None:
            controllers[1] = TacticalBot(task.away_context)
        m = match_input(task)
        result = simulate(m, decisions=task.user_decisions, controllers=controllers)
        problems = validate_result(result, m, eligible=(set(task.eligible_home), set(task.eligible_away)))
        return FixtureOutcome(task.snapshot_id, task.match_id, result, None, tuple(problems))
    except Exception as exc:  # falha da partida: registrada, nunca consolidada
        return FixtureOutcome(task.snapshot_id, task.match_id, None,
                              f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}")
