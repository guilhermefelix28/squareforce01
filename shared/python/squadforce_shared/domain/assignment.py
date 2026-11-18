"""Atribuição de peso máximo (algoritmo húngaro) — usada pela IA dos bots e pela escalação do motor."""

from __future__ import annotations


def hungarian_max(weights: list[list[float]]) -> tuple[float, list[int]]:
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
