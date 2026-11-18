"""Perfil interno de atleta (dados do SQLite) usado pelos serviços de leilão e IA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .positions import Position


@dataclass(frozen=True)
class PlayerProfile:
    """Dados de um atleta usados no leilão (vindos do SQLite). Atributos nunca saem para o cliente."""

    unique_id: int
    name: str
    age: int
    club_uid: int
    club_short_name: str
    natural_positions: tuple[Position, ...]
    accomplished_positions: tuple[Position, ...]
    familiarity: Mapping[Position, int]
    attributes: Mapping[str, int] = field(repr=False)

    @property
    def main_position(self) -> Position:
        return self.natural_positions[0]
