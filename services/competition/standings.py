"""Classificação da Liga (GDD §17) — atualizada somente na consolidação de rodadas completas.

- Pontuação: `PointsSystem` (vitória/empate/derrota). O GDD não define a escala: 3/1/0 é uma decisão
  PROVISÓRIA (PC-09), configurável.
- Desempate: o GDD não define os critérios (PC-01, o responsável enviará). Por isso a lista padrão é VAZIA:
  clubes com os mesmos pontos ficam empatados e são sinalizados (`tied_with`). Nenhuma ordem é inventada.
  Critérios suportados quando forem definidos (na ordem informada): "wins", "goal_difference",
  "goals_for", "goals_against_fewer", "head_to_head_points".
- Ordem de exibição entre empatados sem critério: alfabética por clube (apenas apresentação, sinalizada).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

SUPPORTED_TIEBREAKERS = ("wins", "goal_difference", "goals_for", "goals_against_fewer", "head_to_head_points")


@dataclass(frozen=True)
class PointsSystem:
    win: int = 3
    draw: int = 1
    loss: int = 0
    status: str = "PROVISÓRIO — escala não definida no GDD (PC-09)"


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


def apply_result(records: dict[int, ClubRecord], m: MatchScore, points: PointsSystem) -> None:
    """Aplica um resultado OFICIAL (pênaltis não contam na Liga). Usado só na consolidação."""
    h, a = records[m.home], records[m.away]
    for rec, gf, ga in ((h, m.home_goals, m.away_goals), (a, m.away_goals, m.home_goals)):
        rec.played += 1
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


def _key(rec: ClubRecord, criteria: Sequence[str], h2h: Mapping[int, int]) -> tuple:
    values: list = [-rec.points]
    for c in criteria:
        if c == "wins":
            values.append(-rec.wins)
        elif c == "goal_difference":
            values.append(-rec.goal_difference)
        elif c == "goals_for":
            values.append(-rec.goals_for)
        elif c == "goals_against_fewer":
            values.append(rec.goals_against)
        elif c == "head_to_head_points":
            values.append(-h2h.get(rec.club_uid, 0))
        else:
            raise ValueError(f"Critério de desempate não suportado: {c}")
    return tuple(values)


def standings(records: Mapping[int, ClubRecord], names: Mapping[int, str], tiebreakers: Sequence[str] = (),
              results: Iterable[MatchScore] = (), points: PointsSystem = PointsSystem()) -> list[StandingRow]:
    for c in tiebreakers:
        if c not in SUPPORTED_TIEBREAKERS:
            raise ValueError(f"Critério de desempate não suportado: {c}")
    results = list(results)

    def h2h_points(group: set[int]) -> dict[int, int]:
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

    by_points: dict[int, set[int]] = {}
    for rec in records.values():
        by_points.setdefault(rec.points, set()).add(rec.club_uid)
    h2h: dict[int, int] = {}
    if "head_to_head_points" in tiebreakers:
        for group in by_points.values():
            h2h.update(h2h_points(group))

    keyed = {uid: _key(rec, tiebreakers, h2h) for uid, rec in records.items()}
    order = sorted(records, key=lambda uid: (keyed[uid], names.get(uid, str(uid)), uid))
    rows: list[StandingRow] = []
    for i, uid in enumerate(order):
        rec = records[uid]
        tied = tuple(sorted(u for u in records if u != uid and keyed[u] == keyed[uid]))
        first_of_group = next(j for j, u in enumerate(order) if keyed[u] == keyed[uid])
        rows.append(StandingRow(
            position=first_of_group + 1, club_uid=uid, played=rec.played, wins=rec.wins, draws=rec.draws,
            losses=rec.losses, goals_for=rec.goals_for, goals_against=rec.goals_against,
            goal_difference=rec.goal_difference, points=rec.points, form=tuple(rec.form[-5:]), tied_with=tied,
        ))
    return rows
