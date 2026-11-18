"""Lotes de comportamento da IA tática (Entrega 6) — usados pelos testes e pelo relatório.

Mede, a partir dos EVENTOS das partidas (sem acesso privilegiado):
- mudanças de postura por equipe e por partida;
- direção das mudanças conforme o placar e o tempo (perdendo → mais ofensivo; vencendo → mais defensivo);
- desempenho da IA contra um adversário estático de mesma força (pontos por jogo), sem bônus de atributos;
- validade estrutural de todas as partidas.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from services.match_engine.engine import MatchSimulation
from services.match_engine.params import POSTURES
from services.match_engine.types import MatchInput, TeamSheet
from services.match_engine.validation import validate_result

from .tactics import CompetitionSituation, PreMatchContext, TacticalBot

ORD = {p: i for i, p in enumerate(POSTURES)}


@dataclass
class BehaviourReport:
    matches: int
    invalid: int
    changes_per_team: float
    max_changes: int
    toward_attack_when_trailing: float  # fração das mudanças, com o time perdendo, que aumentam o ataque
    toward_defense_when_leading: float  # fração das mudanças, com o time vencendo, que reduzem o ataque
    late_trailing_attacking_share: float  # no fim (≥ 75'), perdendo: fração do tempo em postura ofensiva
    late_leading_defending_share: float
    ai_points_per_game: float
    static_points_per_game: float
    postures_used: dict[str, int]


def _points(a: int, b: int) -> int:
    return 3 if a > b else 1 if a == b else 0


def run_behaviour(home: TeamSheet, away: TeamSheet, n: int, seed: int = 1,
                  personalities: tuple[str, str] = ("balanced", "balanced"), ai_both: bool = True) -> BehaviourReport:
    invalid = changes = max_changes = 0
    toward_att = trailing_changes = toward_def = leading_changes = 0
    late_trailing = late_trailing_att = late_leading = late_leading_def = 0
    ai_pts = static_pts = 0
    used = Counter()
    for i in range(n):
        m = MatchInput(f"B{i}", "liga", home, away, seed=seed * 100_000 + i)
        ctrls = {0: TacticalBot(PreMatchContext(CompetitionSituation.league(), personalities[0]))}
        if ai_both:
            ctrls[1] = TacticalBot(PreMatchContext(CompetitionSituation.league(), personalities[1]))
        sim = MatchSimulation(m, controllers=ctrls)
        res = sim.run()
        invalid += bool(validate_result(res, m))
        ai_pts += _points(res.score[0], res.score[1])
        static_pts += _points(res.score[1], res.score[0])
        score = [0, 0]
        posture = [home.posture, away.posture]
        last_t = 0.0
        team_changes = Counter()
        for e in res.events:
            dt = e.second - last_t
            last_t = e.second
            if e.second >= 75 * 60 and e.period == 2:
                for side in ctrls:
                    diff = score[side] - score[1 - side]
                    if diff < 0:
                        late_trailing += dt
                        late_trailing_att += dt if ORD[posture[side]] > ORD["equilibrada"] else 0
                    elif diff > 0:
                        late_leading += dt
                        late_leading_def += dt if ORD[posture[side]] < ORD["equilibrada"] else 0
            if e.type == "goal":
                score[e.side] += 1
            elif e.type == "posture_change":
                side, new = e.side, e.data["posture"]
                used[new] += 1
                team_changes[side] += 1
                diff = score[side] - score[1 - side]
                if diff < 0:
                    trailing_changes += 1
                    toward_att += ORD[new] > ORD[posture[side]]
                elif diff > 0:
                    leading_changes += 1
                    toward_def += ORD[new] < ORD[posture[side]]
                posture[side] = new
        changes += sum(team_changes.values())
        max_changes = max([max_changes, *team_changes.values()])
    teams = n * len(ctrls)
    return BehaviourReport(
        matches=n, invalid=invalid, changes_per_team=changes / teams, max_changes=max_changes,
        toward_attack_when_trailing=toward_att / trailing_changes if trailing_changes else 0.0,
        toward_defense_when_leading=toward_def / leading_changes if leading_changes else 0.0,
        late_trailing_attacking_share=late_trailing_att / late_trailing if late_trailing else 0.0,
        late_leading_defending_share=late_leading_def / late_leading if late_leading else 0.0,
        ai_points_per_game=ai_pts / n, static_points_per_game=static_pts / n, postures_used=dict(used),
    )
