"""Apresentação AO VIVO da partida do usuário (GDD §11, §16): relógio do servidor, revelação progressiva.

- A partida é a mesma `FixtureTask` do snapshot da rodada (mesma semente, escalações e contexto dos bots).
- O servidor só revela os eventos até o tempo de jogo atual. O cliente nunca recebe eventos futuros, então
  não há como "espiar" o resultado antes de decidir a postura.
- Tempo de jogo = âncora + (tempo real decorrido) × (duração nominal / velocidade). A velocidade (15 s, 30 s,
  60 s ou instantâneo) só muda essa conversão. A partida não pausa: o relógio segue mesmo desconectado.
- Mudança de postura: registrada no tempo de jogo já simulado (`MatchSimulation.set_posture`) e vale para as
  posses seguintes (GDD §11). As decisões do usuário são `PostureChange` comuns. Ao jogar a rodada, a mesma
  tarefa com as mesmas decisões reproduz exatamente esta partida (verificado na consolidação).
"""

from __future__ import annotations

import dataclasses
import math
import threading
from dataclasses import dataclass, field
from typing import Callable

from services.bot_ai.tactics import TacticalBot
from services.match_engine.engine import MatchSimulation
from services.match_engine.presentation import NOMINAL_MATCH_SECONDS, SPEEDS
from services.match_engine.stats import compute_stats
from services.match_engine.types import Event, MatchResult, PostureChange

from .worker import FixtureTask, match_input


class LiveError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass
class LiveMatch:
    task: FixtureTask
    user_side: int
    clock: Callable[[], float]
    speed: str = "30s"
    anchor_real: float = 0.0
    anchor_game: float = 0.0
    sim: MatchSimulation | None = None
    decisions: list[PostureChange] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    @classmethod
    def start(cls, task: FixtureTask, user_club: int, speed: str, clock: Callable[[], float]) -> "LiveMatch":
        if speed not in SPEEDS:
            raise LiveError("INVALID_SPEED", f"Velocidade inválida: {speed}. Use 15s, 30s, 60s ou instant.")
        side = 0 if task.home_club == user_club else 1
        controllers = {}
        if task.home_context is not None:
            controllers[0] = TacticalBot(task.home_context)
        if task.away_context is not None:
            controllers[1] = TacticalBot(task.away_context)
        sim = MatchSimulation(match_input(task), decisions=task.user_decisions, controllers=controllers)
        live = cls(task=task, user_side=side, clock=clock, speed=speed, anchor_real=clock(), sim=sim,
                   decisions=list(task.user_decisions))
        live._advance()
        return live

    # -------------------------------------------------------------- relógio
    def game_second(self) -> float:
        duration = SPEEDS[self.speed]
        if duration == 0:
            return math.inf
        return self.anchor_game + (self.clock() - self.anchor_real) * NOMINAL_MATCH_SECONDS / duration

    def _advance(self) -> float:
        target = self.game_second()
        self.sim.advance_to(target)
        return target

    @property
    def finished(self) -> bool:
        if not self.sim.finished:
            return False
        last = self.sim.events[-1].second if self.sim.events else 0.0
        return self.game_second() >= last

    def set_speed(self, speed: str) -> None:
        if speed not in SPEEDS:
            raise LiveError("INVALID_SPEED", f"Velocidade inválida: {speed}.")
        with self.lock:
            now_game = min(self.game_second(), self._end_second())
            self.anchor_real, self.anchor_game, self.speed = self.clock(), now_game, speed
            self._advance()

    def _end_second(self) -> float:
        if not self.sim.finished:
            return math.inf
        return self.sim.events[-1].second if self.sim.events else 0.0

    def change_posture(self, posture: str) -> float:
        with self.lock:
            self._advance()
            if self.finished or self.sim.finished:
                raise LiveError("MATCH_FINISHED", "A partida já terminou.")
            pending = [d for d in self.sim.decisions if d.side == self.user_side]
            effective = pending[-1].posture if pending else self.sim.teams[self.user_side].posture
            if effective == posture:
                raise LiveError("SAME_POSTURE", "Esta já é a postura atual.")
            self.sim.set_posture(self.user_side, posture)
            decision = PostureChange(self.sim.t, self.user_side, posture)
            self.decisions.append(decision)
            return decision.second

    # -------------------------------------------------------------- visão (somente o já revelado)
    def view(self) -> dict:
        with self.lock:
            target = self._advance()
            revealed: list[Event] = [e for e in self.sim.events if e.second <= target]
            finished = self.sim.finished and len(revealed) == len(self.sim.events)
            score = [0, 0]
            postures = [self.task.home.posture, self.task.away.posture]
            for e in revealed:
                if e.type == "goal":
                    score[e.side] += 1
                elif e.type == "posture_change":
                    postures[e.side] = e.data.get("posture", postures[e.side])
            shootout = None
            if finished and self.sim.shootout:
                shootout = self.sim.shootout
            team = self.sim.teams[self.user_side]
            # condição física: SOMENTE do próprio time (a do adversário não é informação pública)
            own = [{"player": p.player.unique_id, "name": p.player.name, "slot": p.slot.value,
                    "condition": round(p.condition, 1), "on_field": p.active, "yellow_cards": p.yellow}
                   for p in team.players]
            now = min(target, revealed[-1].second if finished and revealed else target)
            return {
                "game_second": 0.0 if not revealed else (revealed[-1].second if finished else now),
                "finished": finished,
                "score": tuple(score),
                "shootout": shootout,
                "events": revealed,
                "stats": compute_stats(revealed),
                "postures": tuple(postures),
                "own_players": own,
                "own_bench": [{"player": p.unique_id, "name": p.name} for p in team.bench],
                "substitutions_used": team.subs_used,
                "speed": self.speed,
            }

    def result(self) -> MatchResult:
        """Resultado completo (somente após o fim da apresentação)."""
        with self.lock:
            self._advance()
            if not self.finished:
                raise LiveError("MATCH_IN_PROGRESS", "A partida ainda está em andamento.")
            return self.sim.result()

    def final_task(self) -> FixtureTask:
        return dataclasses.replace(self.task, user_decisions=tuple(self.decisions))
