"""Tipos do motor esportivo: entrada imutável, eventos e resultado."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from squadforce_shared.domain.positions import Position


@dataclass(frozen=True)
class MatchPlayer:
    """Atleta na partida. `attributes` são os atributos REAIS da base (1–100)."""

    unique_id: int
    name: str
    attributes: Mapping[str, int]
    familiarity: Mapping[Position, int]
    natural_position: Position
    is_emergency: bool = False


@dataclass(frozen=True)
class TeamSheet:
    """Escalação: formação fixa (11 posições), titulares na ordem das vagas, até 7 reservas e postura inicial."""

    club_uid: int
    formation: tuple[Position, ...]
    starters: tuple[MatchPlayer, ...]
    bench: tuple[MatchPlayer, ...] = ()
    posture: str = "equilibrada"

    def __post_init__(self) -> None:
        if len(self.formation) != 11 or len(self.starters) != 11:
            raise ValueError("A escalação exige 11 vagas e 11 titulares.")
        if self.formation.count(Position.GK) != 1:
            raise ValueError("A formação exige exatamente um goleiro.")
        if len(self.bench) > 7:
            raise ValueError("No máximo 7 reservas.")
        ids = [p.unique_id for p in (*self.starters, *self.bench)]
        if len(ids) != len(set(ids)):
            raise ValueError("Jogador repetido na escalação.")


@dataclass(frozen=True)
class PostureChange:
    """Decisão tática: vale a partir da primeira posse que começa em `second` ou depois."""

    second: float
    side: int  # 0 = mandante/clube A, 1 = visitante/clube B
    posture: str


@dataclass(frozen=True)
class MatchInput:
    match_id: str
    competition: str  # chave da competição (cartões são controlados por competição)
    home: TeamSheet
    away: TeamSheet
    seed: int
    neutral_venue: bool = False
    knockout: bool = False  # Copa: empate nos 90 min => disputa de pênaltis (GDD §18)


@dataclass(frozen=True)
class Event:
    seq: int
    second: float  # tempo de jogo em segundos (inclui acréscimos)
    period: int  # 1 ou 2
    type: str
    side: int | None = None
    player: int | None = None
    other: int | None = None  # segundo jogador (assistente, defensor, substituto...)
    data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def minute(self) -> int:
        return int(self.second // 60) + 1


@dataclass(frozen=True)
class Injury:
    player: int
    side: int
    matches: int  # 0 a 3 (GDD §13)
    second: float


@dataclass(frozen=True)
class Card:
    player: int
    side: int
    color: str  # "yellow" | "red"
    second: float
    second_yellow: bool = False


@dataclass(frozen=True)
class PlayerRating:
    player: int
    side: int
    rating: float  # precisão interna
    display: float  # uma casa decimal
    minutes: float
    decisive_impact: float


@dataclass(frozen=True)
class MatchResult:
    match_id: str
    competition: str
    engine_version: str
    params_version: str
    seed: int
    events: tuple[Event, ...]
    score: tuple[int, int]  # gols esportivos (eventos de gol)
    official_score: tuple[int, int]  # pode diferir em encerramento administrativo
    status: str  # "completed" | "abandoned"
    abandoned_side: int | None
    stats: Mapping[str, Any]
    ratings: tuple[PlayerRating, ...]
    man_of_the_match: int | None
    injuries: tuple[Injury, ...]
    cards: tuple[Card, ...]
    final_postures: tuple[str, str]
    shootout: tuple[int, int] | None = None  # pênaltis registrados à parte (não são gols da partida)
    winner_side: int | None = None  # vencedor oficial (inclui pênaltis); None = empate
