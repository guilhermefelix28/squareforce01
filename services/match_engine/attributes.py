"""Atributos efetivos (GDD §3, §10, §13).

efetivo(atributo) = base × (1 − penalidade posicional) × fator de cansaço (só atributos sensíveis) × forma do dia

- Penalidade posicional: 0 na familiaridade 100 e até 35% (máximo APROVADO) na familiaridade 1. A forma da
  curva entre os extremos não está no GDD: linear, provisória (PE-03).
- Cansaço: condição 100 → fator 1; condição 0 → 1 − fatigue_effect (provisório).
- Forma do dia: variação pequena por partida, menor para atletas consistentes (atributo real `consistency`).
O overall NÃO participa: o motor só usa atributos da base, por ação.
"""

from __future__ import annotations

from typing import Iterable

from squadforce_shared.domain.positions import Position

from .params import FATIGUE_SENSITIVE, SKILLS, MatchParams
from .types import MatchPlayer


def positional_factor(player: MatchPlayer, slot: Position, params: MatchParams) -> float:
    fam = max(1, min(100, int(player.familiarity.get(slot, 1))))
    penalty = params.max_positional_penalty * (100 - fam) / 99
    return 1.0 - penalty


def fatigue_factor(condition: float, params: MatchParams) -> float:
    return 1.0 - params.fatigue_effect * (1.0 - max(0.0, min(100.0, condition)) / 100.0)


def effective(player: MatchPlayer, attribute: str, slot: Position, condition: float, form: float,
              params: MatchParams) -> float:
    base = float(player.attributes.get(attribute, 1))
    value = base * positional_factor(player, slot, params) * form
    if attribute in FATIGUE_SENSITIVE:
        value *= fatigue_factor(condition, params)
    return value


def skill(player: MatchPlayer, name: str, slot: Position, condition: float, form: float, params: MatchParams) -> float:
    """Composição (média) de atributos reais para uma ação."""
    attrs = SKILLS[name]
    return sum(effective(player, a, slot, condition, form, params) for a in attrs) / len(attrs)


def mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else default
