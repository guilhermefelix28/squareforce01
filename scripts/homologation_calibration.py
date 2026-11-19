"""Calibração estatística da homologação (Entrega 9).

Lotes (sementes fixas, reprodutíveis):
  A. amplo: >= 10.000 partidas entre bots com IA tática, forças, formações, personalidades e situações variadas
     (20% eliminatórias com pênaltis);
  B. posturas: equipes iguais, postura fixa de um lado contra Equilibrada;
  C. diferença de qualidade: 0, 5, 10, 15 e 20 pontos de nível;
  D. formações: todas as combinações das formações provisórias.
Compara com as faixas de docs/homologacao/criterios.md (definidas ANTES deste lote) e grava
docs/homologacao/calibracao.md + scratch JSON.

Uso: python scripts/homologation_calibration.py [--broad 10000] [--workers 10]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "shared" / "python"), str(ROOT / "tests")]

import services  # noqa: E402,F401
from services.bot_ai.tactics import CompetitionSituation, PreMatchContext, TacticalBot  # noqa: E402
from services.match_engine.calibration import SAMPLE_FORMATIONS  # noqa: E402
from services.match_engine.engine import simulate  # noqa: E402
from services.match_engine.params import DEFAULT_PARAMS, POSTURES  # noqa: E402
from services.match_engine.types import MatchInput, TeamSheet  # noqa: E402
from services.match_engine.validation import validate_result  # noqa: E402
from services.bot_ai.tactics import choose_lineup  # noqa: E402
from services.data.importer import parse_clubs, parse_players, read_workbook  # noqa: E402
from services.match_engine.lineup import slot_value, to_match_player  # noqa: E402
from squadforce_shared.domain.players import PlayerProfile  # noqa: E402
from squadforce_shared.domain.positions import Position as P  # noqa: E402
from support.match_fixtures import player  # noqa: E402

BENCH = (P.GK, P.DC, P.DR, P.DM, P.MC, P.STC, P.STC)
PERSONALITIES = ("aggressive", "balanced", "conservative", "opportunist")

# faixas de docs/homologacao/criterios.md (commit d2cda8e, anterior aos lotes)
BANDS = {
    "goals": (2.20, 3.56), "draw_pct": (22.5, 33.0), "shots": (22.1, 30.1), "xg": (2.24, 3.44),
    "fouls": (23.3, 31.4), "yellow_cards": (2.88, 5.26), "red_cards": (0.071, 0.54),
}


REAL: dict[int, list] = {}
STRENGTH: dict[int, float] = {}


def load_real() -> None:
    """Elencos REAIS lidos da planilha oficial em memória (somente leitura, sem cópia)."""
    if REAL:
        return
    sheets = read_workbook((ROOT / "Dados" / "jogadores.xlsx").read_bytes(), "jogadores.xlsx")
    _, clubs = parse_clubs(sheets, "j")
    _, players = parse_players(sheets, "j", {c.club_uid for c in clubs})
    short = {c.club_uid: c.short_name for c in clubs}
    for p in players:
        REAL.setdefault(p.club_uid, []).append(to_match_player(PlayerProfile(
            p.unique_id, p.name, p.age, p.club_uid, short[p.club_uid], tuple(p.natural_positions),
            tuple(p.accomplished_positions), dict(p.familiarity), dict(p.attributes))))
    for c, squad in REAL.items():
        best = sorted((max(slot_value(m, pos, DEFAULT_PARAMS) for pos in P) for m in squad), reverse=True)[:11]
        STRENGTH[c] = sum(best) / len(best)


def make_team(club: int, level: float, formation, rng: random.Random, posture: str = "equilibrada") -> TeamSheet:
    """Elenco com variação individual: nível ~ N(level, 4), propensão a lesão e agressividade variadas."""
    def one(uid, pos):
        lv = int(max(30, min(92, rng.gauss(level, 4))))
        return player(uid, pos, lv, injury_proneness=rng.randint(15, 60), dirtiness=rng.randint(20, 70))
    starters = tuple(one(club * 100 + i, pos) for i, pos in enumerate(formation, start=1))
    bench = tuple(one(club * 100 + 50 + i, pos) for i, pos in enumerate(BENCH))
    return TeamSheet(club, tuple(formation), starters, bench, posture)


def situation(rng: random.Random, knockout: bool) -> CompetitionSituation:
    if knockout:
        return CompetitionSituation.cup()
    return rng.choices([CompetitionSituation.league(), CompetitionSituation.must_win(), CompetitionSituation.avoid_defeat()],
                       weights=[8, 1, 1])[0]


def summarize(res, m: MatchInput, levels: tuple[float, float]) -> dict:
    s = res.stats
    problems = validate_result(res, m)
    played = [r for r in res.ratings if r.minutes > 0]
    motm_ok = True
    if res.man_of_the_match is not None and played:
        best = max(r.display for r in played)
        motm = next(r for r in played if r.player == res.man_of_the_match)
        motm_ok = motm.display == best
    subs = [sum(1 for e in res.events if e.type == "substitution" and e.side == k) for k in (0, 1)]
    reds = [(e.side, e.second) for e in res.events if e.type == "red_card"]
    goals_t = [(e.side, e.second) for e in res.events if e.type == "goal"]
    end = res.events[-1].second if res.events else 5400.0
    return {
        "score": res.score, "official": res.official_score, "status": res.status, "shootout": res.shootout,
        "winner": res.winner_side, "levels": levels, "problems": len(problems),
        "motm_ok": motm_ok, "subs": subs, "inj": [i.matches for i in res.injuries],
        "ratings": [round(r.display, 1) for r in played],
        "stats": {k: [s["home"].get(k, 0), s["away"].get(k, 0)] for k in (
            "shots", "shots_on_target", "xg", "big_chances", "possession_pct", "fouls", "yellow_cards", "red_cards",
            "corners", "saves_made", "injuries", "goals")},
        "reds": reds, "goal_times": goals_t, "end": end, "postures": list(res.final_postures),
    }


def run_broad(seed: int) -> dict:
    """Clubes REAIS sorteados; escalação e formação escolhidas pela IA; controladores táticos dos dois lados."""
    load_real()
    rng = random.Random(seed)
    knockout = rng.random() < 0.2
    a, b = rng.sample(sorted(REAL), 2)
    ctxs = [PreMatchContext(situation(rng, knockout), rng.choice(PERSONALITIES)) for _ in (0, 1)]
    sheets = [choose_lineup(c, REAL[c], SAMPLE_FORMATIONS, ctx).sheet for c, ctx in zip((a, b), ctxs)]
    m = MatchInput(f"B-{seed}", "liga" if not knockout else "copa", sheets[0], sheets[1], seed,
                   neutral_venue=knockout, knockout=knockout)
    ctrl = {k: TacticalBot(ctxs[k]) for k in (0, 1)}
    out = summarize(simulate(m, controllers=ctrl), m, (STRENGTH[a] * 100, STRENGTH[b] * 100))
    out["changes"] = [len(ctrl[k].decisions) for k in (0, 1)]
    return out


def run_posture(args) -> dict:
    seed, posture = args
    rng = random.Random(seed)
    home, away = make_team(1, 62, SAMPLE_FORMATIONS[0], rng, posture), make_team(2, 62, SAMPLE_FORMATIONS[0], rng)
    m = MatchInput(f"P-{seed}", "liga", home, away, seed)
    return {"posture": posture, **summarize(simulate(m), m, (62, 62))}


def run_gap(args) -> dict:
    seed, gap = args
    rng = random.Random(seed)
    home, away = make_team(1, 55 + gap, SAMPLE_FORMATIONS[0], rng), make_team(2, 55, SAMPLE_FORMATIONS[0], rng)
    m = MatchInput(f"G-{seed}", "copa", home, away, seed, neutral_venue=True)
    return {"gap": gap, **summarize(simulate(m), m, (55 + gap, 55))}


def run_formation(args) -> dict:
    seed, i, j = args
    rng = random.Random(seed)
    home, away = make_team(1, 62, SAMPLE_FORMATIONS[i], rng), make_team(2, 62, SAMPLE_FORMATIONS[j], rng)
    m = MatchInput(f"F-{seed}", "copa", home, away, seed, neutral_venue=True)
    return {"pair": (i, j), **summarize(simulate(m), m, (62, 62))}


def mean(xs):
    return statistics.fmean(xs) if xs else float("nan")


def per_match(rows, key):
    return mean([r["stats"][key][0] + r["stats"][key][1] for r in rows])


def analyse(broad, postures, gaps, forms) -> dict:
    n = len(broad)
    regular = [r for r in broad if r["status"] == "completed"]
    goals = mean([sum(r["score"]) for r in broad])
    draws = 100 * mean([1.0 if r["score"][0] == r["score"][1] else 0.0 for r in broad])
    obs = {
        "goals": goals, "draw_pct": draws, "shots": per_match(broad, "shots"), "xg": per_match(broad, "xg"),
        "fouls": per_match(broad, "fouls"), "yellow_cards": per_match(broad, "yellow_cards"),
        "red_cards": per_match(broad, "red_cards"),
    }
    monitored = {
        "shots_on_target": per_match(broad, "shots_on_target"),
        "on_target_pct": 100 * per_match(broad, "shots_on_target") / per_match(broad, "shots"),
        "big_chances": per_match(broad, "big_chances"), "corners": per_match(broad, "corners"),
        "saves": per_match(broad, "saves_made"), "injuries": per_match(broad, "injuries"),
        "possession_team_sd": statistics.pstdev([r["stats"]["possession_pct"][0] for r in broad]),
        "possession_team_min": min(r["stats"]["possession_pct"][0] for r in broad),
        "possession_team_max": max(r["stats"]["possession_pct"][0] for r in broad),
        "goals_sd": statistics.pstdev([sum(r["score"]) for r in broad]),
        "zero_zero_pct": 100 * mean([1.0 if sum(r["score"]) == 0 else 0.0 for r in broad]),
        "five_plus_pct": 100 * mean([1.0 if sum(r["score"]) >= 5 else 0.0 for r in broad]),
        "max_goals": max(sum(r["score"]) for r in broad),
        "administrative": sum(1 for r in broad if r["status"] != "completed"),
        "shootouts": sum(1 for r in broad if r["shootout"]),
        "posture_changes_per_team": mean([c for r in broad for c in r["changes"]]),
        "posture_changes_max": max(c for r in broad for c in r["changes"]),
    }
    ratings = [x for r in broad for x in r["ratings"]]
    monitored["rating_mean"] = mean(ratings)
    monitored["rating_sd"] = statistics.pstdev(ratings)
    monitored["rating_lt5_pct"] = 100 * mean([1.0 if x < 5 else 0.0 for x in ratings])
    monitored["rating_ge8_pct"] = 100 * mean([1.0 if x >= 8 else 0.0 for x in ratings])
    monitored["rating_min"], monitored["rating_max"] = min(ratings), max(ratings)
    integrity = {
        "invalid_matches": sum(1 for r in broad + postures + gaps + forms if r["problems"]),
        "motm_mismatch": sum(1 for r in broad + postures + gaps + forms if not r["motm_ok"]),
        "subs_over_5": sum(1 for r in broad + postures + gaps + forms if max(r["subs"]) > 5),
        "injury_out_of_range": sum(1 for r in broad + postures + gaps + forms for x in r["inj"] if not 0 <= x <= 3),
        "rating_out_of_range": sum(1 for x in ratings if not 0 <= x <= 10),
        "xg_goal_gap_pct": 100 * abs(goals - obs["xg"]) / obs["xg"],
    }
    # qualidade e resultados inesperados (lote C)
    quality = {}
    for g in sorted({r["gap"] for r in gaps}):
        rows = [r for r in gaps if r["gap"] == g]
        fav = mean([1.0 if r["score"][0] > r["score"][1] else 0.0 for r in rows])
        und = mean([1.0 if r["score"][0] < r["score"][1] else 0.0 for r in rows])
        quality[g] = {"n": len(rows), "fav_win_pct": 100 * fav, "draw_pct": 100 * (1 - fav - und), "underdog_win_pct": 100 * und,
                      "goal_diff": mean([r["score"][0] - r["score"][1] for r in rows])}
    # lote amplo: diferença de nível >= 15
    diffs = sorted(abs(r["levels"][0] - r["levels"][1]) for r in broad)
    cut = diffs[int(0.8 * len(diffs))] if diffs else 0  # 20% dos confrontos mais desiguais entre clubes reais
    big = [r for r in broad if abs(r["levels"][0] - r["levels"][1]) >= cut]
    def fav_side(r):
        return 0 if r["levels"][0] > r["levels"][1] else 1
    broad_upset = {
        "n": len(big), "strength_gap_cut": cut,
        "fav_win_pct": 100 * mean([1.0 if r["score"][fav_side(r)] > r["score"][1 - fav_side(r)] else 0.0 for r in big]),
        "underdog_win_pct": 100 * mean([1.0 if r["score"][fav_side(r)] < r["score"][1 - fav_side(r)] else 0.0 for r in big]),
    }
    # posturas (lote B): gols marcados/sofridos relativos à Equilibrada
    post = {}
    base = [r for r in postures if r["posture"] == "equilibrada"]
    gf0, ga0 = mean([r["score"][0] for r in base]), mean([r["score"][1] for r in base])
    for p in POSTURES:
        rows = [r for r in postures if r["posture"] == p]
        gf, ga = mean([r["score"][0] for r in rows]), mean([r["score"][1] for r in rows])
        post[p] = {"n": len(rows), "gf": gf, "ga": ga, "gf_rel": gf / gf0 - 1, "ga_rel": ga / ga0 - 1,
                   "fouls": mean([r["stats"]["fouls"][0] for r in rows])}
    # formações (lote D)
    form = {}
    for r in forms:
        k = f"{r['pair'][0]}x{r['pair'][1]}"
        form.setdefault(k, []).append(r)
    form = {k: {"n": len(v), "goals": mean([sum(x["score"]) for x in v]), "home_win_pct": 100 * mean([1.0 if x["score"][0] > x["score"][1] else 0.0 for x in v])}
            for k, v in sorted(form.items())}
    # inferioridade numérica (lote amplo): taxa de gols por minuto antes/depois da 1ª expulsão
    before = {"for": 0, "against": 0, "min": 0.0}
    after = {"for": 0, "against": 0, "min": 0.0}
    for r in broad:
        if not r["reds"] or r["status"] != "completed":
            continue
        side, t = r["reds"][0]
        if t < 600 or t > r["end"] - 600:
            continue
        for gs, gt in r["goal_times"]:
            bucket = before if gt < t else after
            bucket["for" if gs == side else "against"] += 1
        before["min"] += t / 60
        after["min"] += (r["end"] - t) / 60
    numeric = {
        "matches": sum(1 for r in broad if r["reds"]),
        "scored_per90_before": 90 * before["for"] / max(1, before["min"]),
        "scored_per90_after": 90 * after["for"] / max(1, after["min"]),
        "conceded_per90_before": 90 * before["against"] / max(1, before["min"]),
        "conceded_per90_after": 90 * after["against"] / max(1, after["min"]),
    }
    return {"n": {"broad": n, "postures": len(postures), "gaps": len(gaps), "formations": len(forms),
                  "total": n + len(postures) + len(gaps) + len(forms)},
            "observed": obs, "monitored": monitored, "integrity": integrity, "quality": quality,
            "broad_upsets": broad_upset, "postures": post, "formations": form, "numeric": numeric,
            "regular_matches": len(regular)}


def verdicts(a: dict) -> list[tuple[str, str, bool]]:
    out = []
    for k, (lo, hi) in BANDS.items():
        v = a["observed"][k]
        out.append((k, f"{v:.3f} ∈ [{lo}, {hi}]", lo <= v <= hi))
    i = a["integrity"]
    out.append(("gols ≈ xG (≤10%)", f"{i['xg_goal_gap_pct']:.2f}%", i["xg_goal_gap_pct"] <= 10))
    for k in ("invalid_matches", "motm_mismatch", "subs_over_5", "injury_out_of_range", "rating_out_of_range"):
        out.append((k, str(i[k]), i[k] == 0))
    q = a["quality"]
    gaps = sorted(q)
    mono = all(q[gaps[j]]["fav_win_pct"] <= q[gaps[j + 1]]["fav_win_pct"] for j in range(len(gaps) - 1))
    out.append(("qualidade monótona", " → ".join(f"{q[g]['fav_win_pct']:.1f}%" for g in gaps), mono))
    u = [g for g in gaps if g >= 15]
    ok = all(0 < q[g]["underdog_win_pct"] < q[g]["fav_win_pct"] for g in u) and \
        0 < a["broad_upsets"]["underdog_win_pct"] < a["broad_upsets"]["fav_win_pct"]
    out.append(("resultados inesperados possíveis (≥15)", ", ".join(f"{g}: {q[g]['underdog_win_pct']:.1f}%" for g in u)
                + f"; amplo (20% mais desiguais) {a['broad_upsets']['underdog_win_pct']:.1f}%", ok))
    p = a["postures"]
    moderate = all(abs(p[x]["gf_rel"]) <= 0.35 and abs(p[x]["ga_rel"]) <= 0.35 for x in POSTURES)
    order = [p[x]["gf"] for x in POSTURES]
    conc = [p[x]["ga"] for x in POSTURES]
    mono_p = all(order[j] < order[j + 1] for j in range(4)) and all(conc[j] < conc[j + 1] for j in range(4))
    out.append(("posturas moderadas (±35%)", ", ".join(f"{x}: {p[x]['gf_rel']:+.0%}/{p[x]['ga_rel']:+.0%}" for x in POSTURES), moderate))
    out.append(("posturas monótonas", "marcados " + " < ".join(f"{v:.2f}" for v in order) + "; sofridos " + " < ".join(f"{v:.2f}" for v in conc), mono_p))
    nm = a["numeric"]
    out.append(("inferioridade numérica", f"sofridos/90 {nm['conceded_per90_before']:.2f}→{nm['conceded_per90_after']:.2f}; marcados/90 {nm['scored_per90_before']:.2f}→{nm['scored_per90_after']:.2f}",
                nm["conceded_per90_after"] > nm["conceded_per90_before"] and nm["scored_per90_after"] < nm["scored_per90_before"]))
    m = a["monitored"]
    out.append(("IA: mudanças de postura por time ≤ 4 (máx ≤ 8)", f"{m['posture_changes_per_team']:.2f} (máx {m['posture_changes_max']})",
                m["posture_changes_per_team"] <= 4 and m["posture_changes_max"] <= 8))
    return out


def write_report(a: dict, v: list, elapsed: float, workers: int) -> Path:
    o, m = a["observed"], a["monitored"]
    lines = [
        "# Calibração estatística — homologação (Entrega 9)", "",
        f"Gerado por `scripts/homologation_calibration.py` ({a['n']['total']} partidas simuladas em {elapsed:.0f} s, "
        f"{workers} processos; motor `{DEFAULT_PARAMS.version}`). Faixas de `criterios.md` (commit `d2cda8e`, anterior a este lote).", "",
        f"Lotes: amplo {a['n']['broad']} (40 clubes REAIS da base, escalação/formação/posturas pela IA, personalidades e situações variadas, 20% eliminatórias) · "
        f"posturas {a['n']['postures']} · qualidade {a['n']['gaps']} · formações {a['n']['formations']}.", "",
        "## Veredito por critério", "", "| Critério | Observado | Resultado |", "|---|---|---|",
    ]
    lines += [f"| {k} | {val} | {'✅ dentro' if ok else '❌ FORA'} |" for k, val, ok in v]
    lines += ["", "## Métricas monitoradas (sem referência confiável: NÃO validadas)", "", "| Métrica | Valor |", "|---|---|"]
    for k, val in m.items():
        lines.append(f"| {k} | {val:.3f} |" if isinstance(val, float) else f"| {k} | {val} |")
    lines += ["", "## Qualidade (lote C, campo neutro)", "", "| Diferença de nível | n | Vitória do mais forte | Empate | Vitória do mais fraco | Saldo médio |", "|---|---|---|---|---|---|"]
    for g, q in a["quality"].items():
        lines.append(f"| {g} | {q['n']} | {q['fav_win_pct']:.1f}% | {q['draw_pct']:.1f}% | {q['underdog_win_pct']:.1f}% | {q['goal_diff']:+.2f} |")
    lines += ["", "## Posturas (lote B, um lado com postura fixa contra Equilibrada)", "", "| Postura | n | Gols marcados | Sofridos | Δ marcados | Δ sofridos | Faltas |", "|---|---|---|---|---|---|---|"]
    for p, q in a["postures"].items():
        lines.append(f"| {p} | {q['n']} | {q['gf']:.3f} | {q['ga']:.3f} | {q['gf_rel']:+.1%} | {q['ga_rel']:+.1%} | {q['fouls']:.2f} |")
    lines += ["", "## Formações (lote D; índice: 0 = 4-3-3, 1 = 4-4-2, 2 = 5-3-2)", "", "| Confronto | n | Gols/jogo | Vitória do lado A |", "|---|---|---|---|"]
    for k, q in a["formations"].items():
        lines.append(f"| {k} | {q['n']} | {q['goals']:.2f} | {q['home_win_pct']:.1f}% |")
    nm = a["numeric"]
    lines += ["", "## Inferioridade numérica (lote amplo, 1ª expulsão entre 10' e o fim − 10')", "",
              f"{nm['matches']} partidas com expulsão. Time com 10: marcados/90 {nm['scored_per90_before']:.2f} → {nm['scored_per90_after']:.2f}; "
              f"sofridos/90 {nm['conceded_per90_before']:.2f} → {nm['conceded_per90_after']:.2f}.", ""]
    path = ROOT / "docs" / "homologacao" / "calibracao.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad", type=int, default=10_000)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    t0 = time.perf_counter()
    with Pool(a.workers) as pool:
        broad = pool.map(run_broad, range(1, a.broad + 1), chunksize=50)
        postures = pool.map(run_posture, [(100_000 + i * 7 + k, p) for k, p in enumerate(POSTURES) for i in range(1000)], chunksize=50)
        gaps = pool.map(run_gap, [(200_000 + i * 5 + k, g) for k, g in enumerate((0, 5, 10, 15, 20)) for i in range(600)], chunksize=50)
        forms = pool.map(run_formation, [(300_000 + n, i, j) for n, (i, j) in enumerate(
            [(i, j) for i in range(3) for j in range(3) for _ in range(250)])], chunksize=50)
    elapsed = time.perf_counter() - t0
    analysis = analyse(broad, postures, gaps, forms)
    v = verdicts(analysis)
    path = write_report(analysis, v, elapsed, a.workers)
    if a.json:
        Path(a.json).write_text(json.dumps(analysis, indent=1, default=str), encoding="utf-8")
    print(f"{analysis['n']['total']} partidas em {elapsed:.0f} s -> {path}")
    for k, val, ok in v:
        print(("OK  " if ok else "FORA"), k, val)


if __name__ == "__main__":
    main()
