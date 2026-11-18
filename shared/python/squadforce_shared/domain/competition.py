"""Formatos de competição permitidos (Game Design v5.2, seções 2, 17 e 18).

Validação de configuração e tipos compartilhados. Seleção, calendário e chaveamento ficam em
services/competition/planner.py (Entrega 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class CompetitionFormat(str, Enum):
    LEAGUE = "league"  # Liga
    CUP = "cup"  # Copa


class LeagueRounds(str, Enum):
    SINGLE = "single"  # Turno único
    DOUBLE = "double"  # Turno e returno


LEAGUE_MIN_CLUBS = 2
LEAGUE_MAX_CLUBS = 20
CUP_SIZES: tuple[int, ...] = (2, 4, 8, 16, 32)

# Ciclo principal (GDD seção 1). Na Entrega 1 apenas SETUP é alcançável.
# As demais fases são declaradas para orientar contratos futuros; nenhuma lógica existe ainda.
SESSION_PHASES: tuple[str, ...] = (
    "setup",  # Configurar a competição e escolher um clube
    "auction",  # Leilão (Entrega futura)
    "squad_completion",  # Complementação automática (Entrega futura)
    "trading",  # Mercado de negociações (Entrega futura)
    "competition",  # Liga/Copa (Entrega futura)
    "finished",  # Campeão e premiações (Entrega futura)
)


@dataclass(frozen=True)
class EligibleClub:
    """Clube elegível para competições: importado e com divisão conhecida (GDD §2)."""

    club_uid: int
    division: Literal["A", "B"]


class CompetitionConfigError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


def validate_competition_config(
    fmt: CompetitionFormat,
    num_clubs: int,
    league_rounds: LeagueRounds | None,
    available_clubs: int,
) -> None:
    """Valida a configuração; lança CompetitionConfigError na primeira violação."""
    if isinstance(num_clubs, bool) or not isinstance(num_clubs, int):
        raise CompetitionConfigError("num_clubs", "A quantidade de clubes deve ser um número inteiro.")

    if fmt is CompetitionFormat.LEAGUE:
        if not LEAGUE_MIN_CLUBS <= num_clubs <= LEAGUE_MAX_CLUBS:
            raise CompetitionConfigError(
                "num_clubs",
                f"A Liga aceita de {LEAGUE_MIN_CLUBS} a {LEAGUE_MAX_CLUBS} clubes (recebido: {num_clubs}).",
            )
        if league_rounds is None:
            raise CompetitionConfigError(
                "league_rounds", "Escolha turno único ou turno e returno para a Liga."
            )
    elif fmt is CompetitionFormat.CUP:
        if num_clubs not in CUP_SIZES:
            allowed = ", ".join(str(s) for s in CUP_SIZES)
            raise CompetitionConfigError(
                "num_clubs", f"A Copa aceita {allowed} participantes (recebido: {num_clubs})."
            )
        if league_rounds is not None:
            raise CompetitionConfigError("league_rounds", "Turnos só se aplicam à Liga.")
    else:  # pragma: no cover - Enum garante
        raise CompetitionConfigError("format", f"Formato desconhecido: {fmt}")

    if num_clubs > available_clubs:
        raise CompetitionConfigError(
            "num_clubs",
            f"Há apenas {available_clubs} clubes elegíveis; não é possível montar {num_clubs} participantes.",
        )
