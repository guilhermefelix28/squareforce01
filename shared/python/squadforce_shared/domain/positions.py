"""Posições e normalização posicional (Game Design v5.2, seção 3).

| Exibição | Código interno |
| GOL | GK | LD | DR | LE | DL | ZAG | DC | VOL | DM | ME | MC | ATA | STC |

O banco e os serviços usam SEMPRE o código interno. A exibição é responsabilidade da interface.
"""

from __future__ import annotations

import re
from enum import Enum


class Position(str, Enum):
    GK = "GK"
    DR = "DR"
    DL = "DL"
    DC = "DC"
    DM = "DM"
    MC = "MC"
    STC = "STC"


# Exibição (interface) -> código interno. Fonte: GDD v5.2 seção 3.
DISPLAY_TO_INTERNAL: dict[str, Position] = {
    "GOL": Position.GK,
    "LD": Position.DR,
    "LE": Position.DL,
    "ZAG": Position.DC,
    "VOL": Position.DM,
    "ME": Position.MC,
    "ATA": Position.STC,
}

INTERNAL_TO_DISPLAY: dict[Position, str] = {v: k for k, v in DISPLAY_TO_INTERNAL.items()}

# Ordem canônica usada em listagens (goleiro -> ataque).
POSITION_ORDER: tuple[Position, ...] = (
    Position.GK,
    Position.DR,
    Position.DL,
    Position.DC,
    Position.DM,
    Position.MC,
    Position.STC,
)

# Coluna de familiaridade na planilha para cada posição (positions_gk, ...).
FAMILIARITY_COLUMN: dict[Position, str] = {p: f"positions_{p.value.lower()}" for p in Position}

_SPLIT = re.compile(r"[,;/|\s]+")


class InvalidPositionError(ValueError):
    def __init__(self, raw: str):
        super().__init__(f"Posição desconhecida: {raw!r}")
        self.raw = raw


def normalize_position(raw: str) -> Position:
    """Converte um código de exibição (GOL, LD...) ou interno (GK, DR...) para o código interno.

    Não há aproximações: qualquer valor fora da tabela oficial gera InvalidPositionError.
    """
    if raw is None:
        raise InvalidPositionError(str(raw))
    token = str(raw).strip().upper()
    if token in DISPLAY_TO_INTERNAL:
        return DISPLAY_TO_INTERNAL[token]
    try:
        return Position(token)
    except ValueError as exc:
        raise InvalidPositionError(str(raw)) from exc


def parse_position_list(raw: object) -> list[Position]:
    """Lê uma célula com uma ou mais posições (separadas por vírgula, espaço, '/', ';' ou '|').

    Célula vazia -> lista vazia. Remove duplicatas preservando a ordem.
    """
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    result: list[Position] = []
    for token in _SPLIT.split(text):
        if not token:
            continue
        pos = normalize_position(token)
        if pos not in result:
            result.append(pos)
    return result
