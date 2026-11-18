"""Montagem da escalação (GDD §9): apenas atletas aptos; emergenciais só se houver menos de 11 aptos.

A escolha automática usa a melhor atribuição jogador→vaga (algoritmo húngaro) pela qualidade efetiva na
vaga (penalidade posicional incluída). É um auxílio técnico para testes e para a futura IA (Entrega 6);
o usuário poderá escalar livremente (interface futura).
"""

from __future__ import annotations

from typing import Sequence

from squadforce_shared.domain.assignment import hungarian_max
from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import Position

from .attributes import skill
from .availability import AvailabilityLedger
from .params import DEFAULT_PARAMS, TECHNICAL, MENTAL, PHYSICAL, GOALKEEPING, MatchParams
from .types import MatchPlayer, TeamSheet

SLOT_SKILL = {Position.GK: "goalkeeping", Position.DR: "box_defense", Position.DL: "box_defense",
              Position.DC: "box_defense", Position.DM: "midfield_defense", Position.MC: "progression",
              Position.STC: "finishing"}


def to_match_player(p: PlayerProfile) -> MatchPlayer:
    return MatchPlayer(p.unique_id, p.name, dict(p.attributes), dict(p.familiarity), p.main_position)


def emergency_player(club_uid: int, index: int, slot: Position, params: MatchParams = DEFAULT_PARAMS) -> MatchPlayer:
    """Atleta emergencial genérico, temporário e de baixa qualidade (não pertence ao elenco)."""
    v = params.emergency_attribute
    attrs = {a: v for a in (*TECHNICAL, *MENTAL, *PHYSICAL, *GOALKEEPING)}
    if slot is not Position.GK:
        for a in GOALKEEPING:
            attrs[a] = 5
    return MatchPlayer(
        unique_id=-(club_uid * 100 + index), name=f"Emergencial {index}", attributes=attrs,
        familiarity={p: (100 if p is slot else 1) for p in Position}, natural_position=slot, is_emergency=True,
    )


def slot_value(player: MatchPlayer, slot: Position, params: MatchParams) -> float:
    return skill(player, SLOT_SKILL[slot], slot, 100.0, 1.0, params)


def build_team_sheet(
    club_uid: int,
    squad: Sequence[PlayerProfile | MatchPlayer],
    formation: Sequence[Position],
    ledger: AvailabilityLedger | None = None,
    competition: str = "",
    posture: str = "equilibrada",
    params: MatchParams = DEFAULT_PARAMS,
) -> TeamSheet:
    players = [p if isinstance(p, MatchPlayer) else to_match_player(p) for p in squad]
    available = [p for p in players if ledger is None or ledger.is_available(p.unique_id, competition)]
    slots = list(formation)
    if len(available) >= 11:
        weights = [[slot_value(p, s, params) for p in available] for s in slots]
        _, assign = hungarian_max(weights)
        starters = [available[a] for a in assign]
    else:
        # menos de 11 aptos: todos os aptos jogam; vagas restantes recebem emergenciais (GDD §9)
        weights = [[slot_value(p, s, params) for p in available] + [0.0] * (11 - len(available)) for s in slots]
        _, assign = hungarian_max(weights)
        starters, n = [], 0
        for slot, a in zip(slots, assign):
            if a < len(available):
                starters.append(available[a])
            else:
                n += 1
                starters.append(emergency_player(club_uid, n, slot, params))
    chosen = {p.unique_id for p in starters}
    bench = sorted((p for p in available if p.unique_id not in chosen),
                   key=lambda p: (-max(slot_value(p, s, params) for s in set(slots)), p.unique_id))[:7]
    return TeamSheet(club_uid, tuple(slots), tuple(starters), tuple(bench), posture)
