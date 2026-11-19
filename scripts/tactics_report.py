"""Gera docs/architecture/ia-tatica-lotes.md: decisões por situação, lotes de comportamento e clubes reais.

Uso: .venv/Scripts/python scripts/tactics_report.py
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared" / "python"), str(ROOT / "tests")]

import services  # noqa: E402,F401
from services.bot_ai.tactics import (  # noqa: E402
    CompetitionSituation, OpponentHistory, PreMatchContext, TacticalBot, choose_lineup)
from services.match_engine.params import DEFAULT_PARAMS  # noqa: E402
from services.bot_ai.tactics_params import DEFAULT_TACTICS  # noqa: E402
from services.bot_ai.tactics_report import run_behaviour  # noqa: E402
from services.match_engine.calibration import FORMATION_433, FORMATION_442, FORMATION_532  # noqa: E402
from services.match_engine.lineup import to_match_player  # noqa: E402
from services.match_engine.params import POSTURES  # noqa: E402
from services.match_engine.types import OwnPlayerState, TacticalObservation  # noqa: E402
from support.match_fixtures import team  # noqa: E402

t0 = time.time()


def obs(remaining, gf, ga, players_for=11, players_against=11, condition=90.0, level=60, knockout=False):
    sq = team(1, level=level)
    own = tuple(OwnPlayerState(p.unique_id, s, condition, 0, p) for p, s in zip(sq.starters, sq.formation))[:players_for]
    el = 1 - remaining
    return TacticalObservation(0, el * 5700, 2, remaining, gf, ga, players_for, players_against, "equilibrada",
                               "equilibrada", own, sq.bench, 5, {"xg": 1.15 * el}, {"xg": 1.15 * el}, (), knockout)


def best(situation, o, personality="balanced"):
    u = TacticalBot(PreMatchContext(situation, personality)).utilities(o)
    return max(POSTURES, key=lambda p: (u[p], -POSTURES.index(p)))


L, MW, AD, CUP = (CompetitionSituation.league(), CompetitionSituation.must_win(),
                  CompetitionSituation.avoid_defeat(), CompetitionSituation.cup())
scenarios = [
    ("Perdendo por 1 aos 80'", L, obs(0.12, 0, 1)),
    ("Vencendo por 1 aos 80'", L, obs(0.12, 1, 0)),
    ("Empate aos 70' (Liga)", L, obs(0.25, 0, 0)),
    ("Empate aos 70', precisa vencer (título)", MW, obs(0.25, 0, 0)),
    ("Empate aos 70', evitar derrota", AD, obs(0.25, 0, 0)),
    ("Vencendo por 1 com 10 jogadores aos 55'", L, obs(0.4, 1, 0, players_for=10)),
    ("Empate aos 55' contra 10 jogadores", L, obs(0.4, 0, 0, players_against=10)),
    ("Perdendo por 1 aos 70' com elenco exausto (40%)", L, obs(0.25, 0, 1, condition=40)),
    ("Copa: perdendo por 1 aos 80'", CUP, obs(0.12, 0, 1, knockout=True)),
    ("Copa: empate aos 75', equipe muito superior", CUP, obs(0.2, 0, 0, level=75, knockout=True)),
    ("Copa: empate aos 75', equipe muito inferior", CUP, obs(0.2, 0, 0, level=45, knockout=True)),
]
lines = ["# IA tática dos bots — decisões e lotes de comportamento", "",
         f"> Parâmetros da IA `{DEFAULT_TACTICS.version}` ({DEFAULT_TACTICS.status}). Motor `{DEFAULT_PARAMS.version}`",
         "> (calibrado contra faixas de referência pública na Entrega 9). Gerado por `scripts/tactics_report.py`.", "",
         "## Decisões em situações típicas (personalidade equilibrada)", "",
         "| Situação | Postura escolhida |", "|---|---|"]
for name, sit, o in scenarios:
    lines.append(f"| {name} | {best(sit, o)} |")

states = [("0×0 30'", obs(0.67, 0, 0)), ("0×0 55'", obs(0.4, 0, 0)), ("0×0 70'", obs(0.25, 0, 0)),
          ("0×0 85'", obs(0.07, 0, 0)), ("0×1 45'", obs(0.5, 0, 1)), ("0×1 80'", obs(0.12, 0, 1)),
          ("1×0 45'", obs(0.5, 1, 0)), ("1×0 80'", obs(0.12, 1, 0)), ("0×0 55' contra 10", obs(0.4, 0, 0, players_against=10))]
lines += ["", "## Personalidades (Liga): moderação", "",
          "Em situações claras (perdendo/vencendo) todas concordam; a personalidade desloca a decisão nos empates.", "",
          "| Estado | " + " | ".join(("aggressive", "balanced", "opportunist", "conservative")) + " |",
          "|---|---|---|---|---|"]
for label, o in states:
    lines.append(f"| {label} | " + " | ".join(best(L, o, p) for p in ("aggressive", "balanced", "opportunist", "conservative")) + " |")

both = run_behaviour(team(1), team(2), 300, seed=11, personalities=("aggressive", "conservative"))
vs_static = run_behaviour(team(1), team(2), 400, seed=12, ai_both=False)
lines += ["", "## Lotes de comportamento (times de mesma força)", "",
          "| Métrica | IA × IA (300 jogos) | IA × estático (400 jogos) |", "|---|---|---|",
          f"| Partidas inválidas | {both.invalid} | {vs_static.invalid} |",
          f"| Mudanças de postura por equipe/jogo | {both.changes_per_team:.2f} | {vs_static.changes_per_team:.2f} |",
          f"| Máximo de mudanças de uma equipe num jogo | {both.max_changes} | {vs_static.max_changes} |",
          f"| Mudanças que aumentam o ataque quando perdendo | {both.toward_attack_when_trailing:.0%} | {vs_static.toward_attack_when_trailing:.0%} |",
          f"| Mudanças que protegem quando vencendo | {both.toward_defense_when_leading:.0%} | {vs_static.toward_defense_when_leading:.0%} |",
          f"| Tempo ofensivo após 75', perdendo | {both.late_trailing_attacking_share:.0%} | {vs_static.late_trailing_attacking_share:.0%} |",
          f"| Tempo defensivo após 75', vencendo | {both.late_leading_defending_share:.0%} | {vs_static.late_leading_defending_share:.0%} |",
          f"| Pontos por jogo (lado 0 / lado 1) | {both.ai_points_per_game:.2f} / {both.static_points_per_game:.2f} | IA {vs_static.ai_points_per_game:.2f} / estático {vs_static.static_points_per_game:.2f} |",
          "", f"Posturas adotadas (IA × IA): {both.postures_used}", ""]

real = ROOT / "Dados" / "jogadores.xlsx"
if real.exists():
    from services.data.importer import parse_clubs, parse_players, read_workbook
    from squadforce_shared.domain.players import PlayerProfile

    sheets = read_workbook(real.read_bytes(), "jogadores.xlsx")
    _, clubs = parse_clubs(sheets, "j")
    _, players = parse_players(sheets, "j", {c.club_uid for c in clubs})
    short = {c.club_uid: c.short_name for c in clubs}
    pool = {}
    for p in players:
        pool.setdefault(p.club_uid, []).append(to_match_player(PlayerProfile(
            p.unique_id, p.name, p.age, p.club_uid, short[p.club_uid], tuple(p.natural_positions),
            tuple(p.accomplished_positions), dict(p.familiarity), dict(p.attributes))))
    names = {FORMATION_433: "4-3-3", FORMATION_442: "4-4-2", FORMATION_532: "5-3-2"}
    lines += ["## Clubes reais: formação e postura inicial escolhidas", "",
              "Formações candidatas de TESTE (lista oficial pendente — PM-01). Adversário com histórico público",
              "fictício: forte (marcou 12, sofreu 3 em 5 jogos) ou fraco (marcou 3, sofreu 12).", "",
              "| Clube | Contra adversário forte | Contra adversário fraco |", "|---|---|---|"]
    strong = OpponentHistory(5, 12.0, 3.0)
    weak = OpponentHistory(5, 3.0, 12.0)
    for club in (322, 329, 316, 102496, 900205, 2106413):
        row = []
        for opp in (strong, weak):
            ch = choose_lineup(club, pool[club], [FORMATION_433, FORMATION_442, FORMATION_532],
                               PreMatchContext(L, "balanced", opp))
            row.append(f"{names[ch.sheet.formation]}, {ch.sheet.posture}")
        lines.append(f"| {short[club]} | {row[0]} | {row[1]} |")
    lines.append("")

lines += ["## Leitura", "",
          "- As decisões seguem a situação: perdendo → mais ofensivo; vencendo → protege; 'precisa vencer' ataca",
          "  no empate; 'evitar derrota' protege o empate; time inferior na Copa segura o empate para os pênaltis.",
          "- Como as posturas do motor alteram gols marcados e sofridos em proporções próximas (medido), a IA as usa",
          "  principalmente para gerir risco (variância), não para ganhar força: o desempenho contra um time estático",
          "  de mesma força fica no mesmo patamar (sem vantagem artificial).",
          "- Estabilidade: poucas mudanças por partida; ganho mínimo, histerese e intervalo de 10 min, com exceções",
          "  só após gols, expulsões e perdas de jogador.", "",
          f"_Tempo de geração: {time.time() - t0:.0f} s._", ""]
out = ROOT / "docs" / "architecture" / "ia-tatica-lotes.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Relatório: {out}")
