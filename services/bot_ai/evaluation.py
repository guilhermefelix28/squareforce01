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


def _hungarian_max(weights: list[list[float]]) -> tuple[float, list[int]]:
    """Atribuição de peso máximo (linhas = vagas, colunas = jogadores; colunas >= linhas).
    Retorna (soma, coluna atribuída a cada linha). Implementação O(n²m) clássica."""
    n, m = len(weights), len(weights[0]) if weights else 0
    if n == 0:
        return 0.0, []
    big = max((w for row in weights for w in row), default=0.0)
    cost = [[big - w for w in row] for row in weights]  # minimizar custo = maximizar peso
    inf = float("inf")
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assign = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            assign[p[j] - 1] = j - 1
    return sum(weights[i][assign[i]] for i in range(n)), assign


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
