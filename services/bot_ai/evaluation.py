"""Avaliação esportiva de elencos (GDD §6): mesma capacidade para todos os bots.

Ganho marginal = 80% da mudança na qualidade dos 11 titulares + 20% da mudança na qualidade dos
sete reservas. Titulares = melhor atribuição jogador→vaga entre as formações do modelo (algoritmo
húngaro); reservas = os 7 melhores restantes. Qualidade = média das vagas (vaga vazia vale 0).
A qualidade por posição vem do AuctionModel (pendente de calibração).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from services.auction.model import AuctionModel, Formation, PlayerProfile
from services.auction.rules import RESERVES, RESERVES_WEIGHT, STARTERS, STARTERS_WEIGHT
from squadforce_shared.domain.assignment import hungarian_max as _hungarian_max


@dataclass(frozen=True)
class SquadQuality:
    formation: str
    starters: float  # média das 11 vagas
    reserves: float  # média das 7 vagas de reserva
    lineup: tuple[int | None, ...]  # unique_id por vaga da formação (None = vaga vazia)


def squad_quality(squad: Sequence[PlayerProfile], model: AuctionModel) -> SquadQuality:
    best: SquadQuality | None = None
    formations: Sequence[Formation] = model.formations()
    if not formations:
        raise ValueError("O modelo não forneceu formações.")
    for f in formations:
        if len(f.slots) != STARTERS:
            raise ValueError(f"Formação {f.name} não tem 11 vagas.")
        players = list(squad)
        # completa com "vagas vazias" (peso 0) para garantir colunas >= linhas
        pad = max(0, STARTERS - len(players))
        weights = [
            [model.player_quality(p, slot) for p in players] + [0.0] * pad for slot in f.slots
        ]
        total, assign = _hungarian_max(weights)
        lineup = tuple(players[a].unique_id if a < len(players) else None for a in assign)
        used = {uid for uid in lineup if uid is not None}
        bench = sorted(
            (max(model.player_quality(p, pos) for pos in p.natural_positions) for p in players if p.unique_id not in used),
            reverse=True,
        )[:RESERVES]
        q = SquadQuality(f.name, total / STARTERS, sum(bench) / RESERVES, lineup)
        if best is None or (q.starters, q.reserves) > (best.starters, best.reserves):
            best = q
    assert best is not None
    return best


def marginal_gain(
    squad: Sequence[PlayerProfile], candidate: PlayerProfile, model: AuctionModel, before: SquadQuality | None = None
) -> float:
    """§6: 0,8 × Δtitulares + 0,2 × Δreservas ao acrescentar `candidate`."""
    before = before or squad_quality(squad, model)
    after = squad_quality([*squad, candidate], model)
    return STARTERS_WEIGHT * (after.starters - before.starters) + RESERVES_WEIGHT * (after.reserves - before.reserves)
