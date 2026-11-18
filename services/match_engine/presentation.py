"""Apresentação da partida (GDD §16): 15 s, 30 s, 60 s ou instantânea — o motor é o mesmo.

O relógio da interface é separado do motor: a apresentação só converte tempo de tela em tempo de jogo.
Decisões do usuário são registradas no tempo de JOGO correspondente (`to_match_second`), portanto a
mesma sequência de decisões produz os mesmos eventos em qualquer velocidade.
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import MatchSimulation
from .types import Event

SPEEDS = {"15s": 15.0, "30s": 30.0, "60s": 60.0, "instant": 0.0}
NOMINAL_MATCH_SECONDS = 90 * 60 + 6 * 60  # 90 min + acréscimo médio para converter tempo de tela


@dataclass
class LivePresentation:
    sim: MatchSimulation
    speed: str = "30s"

    def __post_init__(self) -> None:
        if self.speed not in SPEEDS:
            raise ValueError(f"Velocidade inválida: {self.speed}")

    def to_match_second(self, screen_seconds: float) -> float:
        duration = SPEEDS[self.speed]
        if duration == 0:
            return float("inf")
        return screen_seconds / duration * NOMINAL_MATCH_SECONDS

    def reveal(self, screen_seconds: float) -> list[Event]:
        """Avança a simulação até o tempo de jogo equivalente e devolve os eventos já revelados."""
        target = self.to_match_second(screen_seconds)
        self.sim.advance_to(target)
        return [e for e in self.sim.events if e.second <= target or self.sim.finished and target == float("inf")]

    def change_posture(self, screen_seconds: float, side: int, posture: str) -> float:
        """Aplica uma mudança de postura no tempo de jogo equivalente; retorna esse tempo."""
        second = self.to_match_second(screen_seconds)
        self.sim.advance_to(second)
        self.sim.set_posture(side, posture)
        return self.sim.t
