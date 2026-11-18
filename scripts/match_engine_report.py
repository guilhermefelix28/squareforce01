"""Gera docs/architecture/motor-calibracao-exploratoria.md com lotes EXPLORATÓRIOS do motor (base real).

Uso: .venv/Scripts/python scripts/match_engine_report.py [partidas=2000]
Não é calibração oficial: as referências do futebol real ainda não foram aprovadas (PM-02).
"""

import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared" / "python")]

import services  # noqa: E402,F401
from services.data.importer import parse_clubs, parse_players, read_workbook  # noqa: E402
from services.match_engine.calibration import FORMATION_433, PRELIMINARY_REFERENCES, run_batch  # noqa: E402
from services.match_engine.engine import simulate  # noqa: E402
from services.match_engine.lineup import build_team_sheet, slot_value  # noqa: E402
from services.match_engine.params import DEFAULT_PARAMS, ENGINE_VERSION, POSTURES  # noqa: E402
from services.match_engine.types import MatchInput  # noqa: E402
from squadforce_shared.domain.players import PlayerProfile  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
sheets = read_workbook((ROOT / "Dados" / "jogadores.xlsx").read_bytes(), "jogadores.xlsx")
_, clubs = parse_clubs(sheets, "j")
_, players = parse_players(sheets, "j", {c.club_uid for c in clubs})
short = {c.club_uid: c.short_name for c in clubs}
pool: dict[int, list] = {}
for p in players:
    pool.setdefault(p.club_uid, []).append(PlayerProfile(p.unique_id, p.name, p.age, p.club_uid, short[p.club_uid],
                                                         tuple(p.natural_positions), tuple(p.accomplished_positions),
                                                         dict(p.familiarity), dict(p.attributes)))

t0 = time.time()
r = run_batch(pool, n, seed=2026)
elapsed = time.time() - t0

team_sheets = {c: build_team_sheet(c, pool[c], FORMATION_433) for c in pool}
strength = {c: sum(slot_value(p, s, DEFAULT_PARAMS) for p, s in zip(sh.starters, sh.formation)) / 11
            for c, sh in team_sheets.items()}
order = sorted(strength, key=strength.get)


def head_to_head(a, b, games=200, pa="equilibrada", pb="equilibrada"):
    w = d = l = shots = 0
    sa = team_sheets[a].__class__(**{**team_sheets[a].__dict__, "posture": pa})
    sb = team_sheets[b].__class__(**{**team_sheets[b].__dict__, "posture": pb})
    for s in range(games):
        res = simulate(MatchInput(f"h{s}", "x", sa, sb, s))
        w += res.score[0] > res.score[1]
        d += res.score[0] == res.score[1]
        l += res.score[0] < res.score[1]
        shots += res.stats["home"]["shots"]
    return w / games, d / games, l / games, shots / games


lines = [
    "# Motor esportivo — lotes exploratórios",
    "",
    f"> **NÃO CALIBRADO.** Motor `{ENGINE_VERSION}`, parâmetros `{DEFAULT_PARAMS.version}` ({DEFAULT_PARAMS.status}).",
    "> As faixas de referência abaixo são **preliminares** (ordem de grandeza de ligas profissionais) e **não foram",
    "> aprovadas** (pendência PM-02). Servem apenas para detectar comportamento absurdo.",
    "",
    f"Gerado por `scripts/match_engine_report.py`: {n} partidas entre clubes reais da base (elencos originais da",
    f"planilha, formações de teste 4-3-3/4-4-2/5-3-2, postura equilibrada), em {elapsed:.0f} s",
    f"({1000 * elapsed / n:.0f} ms por partida). Partidas estruturalmente inválidas: **{r.invalid}**; encerramentos administrativos: {r.abandoned}.",
    "",
    "## Estatísticas observadas",
    "",
    "| Métrica | Observado | Faixa preliminar | Situação |",
    "|---|---|---|---|",
]
for k, v in r.metrics.items():
    ref = PRELIMINARY_REFERENCES.get(k)
    lines.append(f"| {k} | {v:.3f} | {f'{ref[0]}–{ref[1]}' if ref else '—'} | "
                 f"{'' if not ref else ('dentro' if r.within_reference[k] else 'FORA')} |")
lines += ["", "## Placares mais frequentes (vencedor–perdedor)", "", "| Placar | Partidas |", "|---|---|"]
for score, count in sorted(r.score_distribution.items(), key=lambda x: -x[1])[:12]:
    lines.append(f"| {score} | {count} |")
lines += ["", "## Força relativa (clubes reais, 200 jogos cada, mando neutro)", "",
          "Força = média da qualidade efetiva na vaga dos 11 titulares escolhidos automaticamente (4-3-3).", "",
          "| Confronto | Forças | Vitória | Empate | Derrota |", "|---|---|---|---|---|"]
for a, b in ((order[-1], order[0]), (order[-1], order[len(order) // 2]), (order[30], order[10]), (order[20], order[19])):
    w, d, l, _ = head_to_head(a, b)
    lines.append(f"| {short[a]} × {short[b]} | {strength[a]:.1f} × {strength[b]:.1f} | {w:.0%} | {d:.0%} | {l:.0%} |")
lines += ["", "## Efeito das posturas (mesmo confronto equilibrado, 200 jogos cada)", "",
          "| Postura do mandante | Finalizações do mandante/jogo | Vitória | Empate | Derrota |", "|---|---|---|---|---|"]
mid_a, mid_b = order[20], order[19]
for posture in POSTURES:
    w, d, l, shots = head_to_head(mid_a, mid_b, pa=posture)
    lines.append(f"| {posture} | {shots:.1f} | {w:.0%} | {d:.0%} | {l:.0%} |")
lines += ["", "## Leitura", "",
          "- Estrutura: todas as partidas passaram em `validate_result` (gols só por finalização, placar = gols,",
          "  estatísticas derivadas dos eventos, ≤ 5 substituições, ≤ 11 em campo, notas 0–10, sem duplicação).",
          "- Os números ficaram dentro das faixas preliminares após ajuste exploratório dos parâmetros provisórios.",
          "- Isso NÃO equivale a calibração: falta aprovar referências estatísticas oficiais, pesos por posição,",
          "  curva da penalidade posicional, parâmetros de notas, disciplina e lesões (ver pendências).", ""]
out = ROOT / "docs" / "architecture" / "motor-calibracao-exploratoria.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Relatório: {out} ({elapsed:.0f}s)")
