"""Classificação da Liga (GDD §17) — atualizada somente na consolidação de rodadas completas.

- Pontuação: `PointsSystem` 3/1/0 (vitória/empate/derrota), CONFIRMADA pelo responsável em 2026-11-19 (PC-09).
- Desempate: padrão Brasileirão, CONFIRMADO em 2026-11-19 (PC-01) — `BRASILEIRAO_TIEBREAKERS`:
  vitórias → saldo de gols → gols pró → confronto direto (somente entre DOIS clubes) → menos cartões
  vermelhos → menos cartões amarelos → sorteio.
  Os critérios são aplicados em cascata: cada um só separa os clubes que continuam empatados após os
  anteriores. O sorteio é determinístico pela semente da competição (`draw_seed`).
- A função `standings` sem critérios mantém clubes de mesmos pontos empatados (`tied_with`), ordem alfabética
  apenas para apresentação.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import hashlib

SUPPORTED_TIEBREAKERS = ("wins", "goal_difference", "goals_for", "goals_against_fewer", "head_to_head_points",
                         "head_to_head_two_clubs", "fewer_red_cards", "fewer_yellow_cards", "draw")
BRASILEIRAO_TIEBREAKERS = ("wins", "goal_difference", "goals_for", "head_to_head_two_clubs",
                           "fewer_red_cards", "fewer_yellow_cards", "draw")


@dataclass(frozen=True)
class PointsSystem:
    win: int = 3
    draw: int = 1
    loss: int = 0
    status: str = "CONFIRMADO pelo responsável em 2026-11-19 (PC-09)"


@dataclass
class ClubRecord:
    club_uid: int
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    points: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    form: list[str] = field(default_factory=list)  # "V", "E", "D" (últimos resultados)

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against


@dataclass(frozen=True)
class StandingRow:
    position: int  # posição compartilhada entre empatados sem critério de desempate
    club_uid: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: tuple[str, ...]
    tied_with: tuple[int, ...]  # clubes empatados SEM critério para separar (desempate pendente)


@dataclass(frozen=True)
class MatchScore:
    home: int
    away: int
    home_goals: int
    away_goals: int
    home_yellow: int = 0
    home_red: int = 0
    away_yellow: int = 0
    away_red: int = 0


def apply_result(records: dict[int, ClubRecord], m: MatchScore, points: PointsSystem) -> None:
    """Aplica um resultado OFICIAL (pênaltis não contam na Liga). Usado só na consolidação."""
    h, a = records[m.home], records[m.away]
    for rec, gf, ga, yc, rc in ((h, m.home_goals, m.away_goals, m.home_yellow, m.home_red),
                                (a, m.away_goals, m.home_goals, m.away_yellow, m.away_red)):
        rec.played += 1
        rec.yellow_cards += yc
        rec.red_cards += rc
        rec.goals_for += gf
        rec.goals_against += ga
        if gf > ga:
            rec.wins += 1
            rec.points += points.win
            rec.form.append("V")
        elif gf == ga:
            rec.draws += 1
            rec.points += points.draw
            rec.form.append("E")
        else:
            rec.losses += 1
            rec.points += points.loss
            rec.form.append("D")


def _h2h_points(group: set[int], results: Sequence[MatchScore], points: PointsSystem) -> dict[int, int]:
    pts = {c: 0 for c in group}
    for m in results:
        if m.home in group and m.away in group:
            if m.home_goals > m.away_goals:
                pts[m.home] += points.win
            elif m.home_goals < m.away_goals:
                pts[m.away] += points.win
            else:
                pts[m.home] += points.draw
                pts[m.away] += points.draw
    return pts


def _draw_value(seed: int, uid: int) -> str:
    return hashlib.sha256(f"sorteio:{seed}:{uid}".encode()).hexdigest()


def _values(group: list[ClubRecord], c: str, results: Sequence[MatchScore], points: PointsSystem,
            draw_seed: int) -> dict[int, object]:
    """Valor de ordenação (menor = melhor) de cada clube do grupo AINDA empatado, para o critério `c`."""
    if c == "wins":
        return {r.club_uid: -r.wins for r in group}
    if c == "goal_difference":
        return {r.club_uid: -r.goal_difference for r in group}
    if c == "goals_for":
        return {r.club_uid: -r.goals_for for r in group}
    if c == "goals_against_fewer":
        return {r.club_uid: r.goals_against for r in group}
    if c == "fewer_red_cards":
        return {r.club_uid: r.red_cards for r in group}
    if c == "fewer_yellow_cards":
        return {r.club_uid: r.yellow_cards for r in group}
    if c == "head_to_head_points" or (c == "head_to_head_two_clubs" and len(group) == 2):
        pts = _h2h_points({r.club_uid for r in group}, results, points)
        return {u: -v for u, v in pts.items()}
    if c == "head_to_head_two_clubs":  # 3+ clubes empatados: o confronto direto não se aplica
        return {r.club_uid: 0 for r in group}
    if c == "draw":
        return {r.club_uid: _draw_value(draw_seed, r.club_uid) for r in group}
    raise ValueError(f"Critério de desempate não suportado: {c}")


def _cascade(group: list[ClubRecord], criteria: Sequence[str], results: Sequence[MatchScore],
             points: PointsSystem, draw_seed: int) -> list[list[ClubRecord]]:
    """Separa o grupo em blocos ordenados; um bloco com mais de um clube continua empatado."""
    if len(group) <= 1 or not criteria:
        return [group]
    vals = _values(group, criteria[0], results, points, draw_seed)
    buckets: dict[object, list[ClubRecord]] = {}
    for r in group:
        buckets.setdefault(vals[r.club_uid], []).append(r)
    out: list[list[ClubRecord]] = []
    for v in sorted(buckets):
        out.extend(_cascade(buckets[v], criteria[1:], results, points, draw_seed))
    return out


def standings(records: Mapping[int, ClubRecord], names: Mapping[int, str], tiebreakers: Sequence[str] = (),
              results: Iterable[MatchScore] = (), points: PointsSystem = PointsSystem(),
              draw_seed: int = 0) -> list[StandingRow]:
    for c in tiebreakers:
        if c not in SUPPORTED_TIEBREAKERS:
            raise ValueError(f"Critério de desempate não suportado: {c}")
    results = list(results)
    by_points: dict[int, list[ClubRecord]] = {}
    for rec in records.values():
        by_points.setdefault(-rec.points, []).append(rec)
    blocks: list[list[ClubRecord]] = []
    for p in sorted(by_points):
        blocks.extend(_cascade(by_points[p], tuple(tiebreakers), results, points, draw_seed))
    rows: list[StandingRow] = []
    for block in blocks:
        position = len(rows) + 1  # posição compartilhada dentro do bloco empatado
        uids = sorted((r.club_uid for r in block), key=lambda u: (names.get(u, str(u)), u))
        for uid in uids:
            rec = records[uid]
            rows.append(StandingRow(
                position=position, club_uid=uid, played=rec.played, wins=rec.wins, draws=rec.draws,
                losses=rec.losses, goals_for=rec.goals_for, goals_against=rec.goals_against,
                goal_difference=rec.goal_difference, points=rec.points, form=tuple(rec.form[-5:]),
                tied_with=tuple(sorted(u for u in uids if u != uid)),
            ))
    return rows
