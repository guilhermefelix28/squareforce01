"""Invariantes estruturais de uma partida simulada. Lista vazia = resultado coerente.

Recusa: gols sem evento válido, placar ≠ gols, estatísticas impossíveis, substituições além do limite,
atletas inelegíveis em campo, notas fora da faixa, eventos duplicados ou fora de ordem, mais de 11 em campo,
expulsos/substituídos que voltam a agir.
"""

from __future__ import annotations

from .params import DEFAULT_PARAMS, MatchParams
from .stats import compute_stats
from .types import MatchInput, MatchResult

ACTING = {"progression", "tackle", "interception", "foul", "shot", "goal", "save", "miss", "block", "corner",
          "yellow_card", "injury"}


def validate_result(res: MatchResult, match: MatchInput, params: MatchParams = DEFAULT_PARAMS,
                    eligible: tuple[set[int], set[int]] | None = None) -> list[str]:
    problems: list[str] = []
    ev = res.events
    seqs = [e.seq for e in ev]
    if seqs != list(range(1, len(ev) + 1)):
        problems.append("Sequência de eventos com buraco ou duplicação.")
    if any(b.second < a.second for a, b in zip(ev, ev[1:])):
        problems.append("Eventos fora de ordem temporal.")
    if ev and ev[0].type != "lineups":
        problems.append("Primeiro evento deve ser a escalação.")
    if ev and ev[-1].type not in ("full_time", "abandoned", "shootout_end"):
        problems.append("Partida não termina com apito final ou encerramento.")

    goals = [0, 0]
    on = [set(), set()]
    gone: set[int] = set()
    subs = [0, 0]
    sheets = (match.home, match.away)
    for side in (0, 1):
        on[side] = {p.unique_id for p in sheets[side].starters}
    bench = [{p.unique_id for p in s.bench} for s in sheets]
    if eligible is not None:
        for side in (0, 1):
            bad = [p.unique_id for p in (*sheets[side].starters, *sheets[side].bench)
                   if not p.is_emergency and p.unique_id not in eligible[side]]
            if bad:
                problems.append(f"Atletas inelegíveis escalados: {bad}")

    for i, e in enumerate(ev):
        if e.type == "goal":
            goals[e.side] += 1
            prev = [x for x in ev[max(0, i - 3):i] if x.type == "shot"]
            if not prev or prev[-1].side != e.side or prev[-1].player != e.player:
                problems.append(f"Gol sem finalização válida (evento {e.seq}).")
            if e.player not in on[e.side]:
                problems.append(f"Gol de jogador fora de campo (evento {e.seq}).")
        if e.type in ACTING and e.player is not None and e.side is not None:
            if e.player in gone or e.player not in on[e.side]:
                problems.append(f"Jogador {e.player} age sem estar em campo (evento {e.seq}, {e.type}).")
        if e.type == "substitution":
            subs[e.side] += 1
            if e.other not in on[e.side] or e.player not in bench[e.side]:
                problems.append(f"Substituição inválida (evento {e.seq}).")
            on[e.side].discard(e.other)
            gone.add(e.other)
            bench[e.side].discard(e.player)
            on[e.side].add(e.player)
        elif e.type in ("red_card", "player_off"):
            on[e.side].discard(e.player)
            gone.add(e.player)
        for side in (0, 1):
            if len(on[side]) > 11:
                problems.append(f"Mais de 11 jogadores em campo (evento {e.seq}).")
    if res.shootout is not None:
        if not match.knockout or res.score[0] != res.score[1] or res.shootout[0] == res.shootout[1]:
            problems.append("Disputa de pênaltis inválida.")
        kicks = [e for e in ev if e.type == "shootout_kick"]
        if (sum(1 for k in kicks if k.side == 0 and k.data["scored"]), sum(1 for k in kicks if k.side == 1 and k.data["scored"])) != res.shootout:
            problems.append("Placar dos pênaltis não corresponde às cobranças.")
    if match.knockout and res.status == "completed" and res.winner_side is None:
        problems.append("Jogo eliminatório sem vencedor.")
    if tuple(goals) != res.score:
        problems.append(f"Placar {res.score} difere dos gols {tuple(goals)}.")
    if any(n > params.max_substitutions for n in subs):
        problems.append("Substituições além do limite.")
    if res.status == "completed" and res.official_score != res.score:
        problems.append("Placar oficial difere do esportivo sem encerramento administrativo.")
    if res.status == "completed" and any(len(on[s]) < params.min_players for s in (0, 1)):
        problems.append("Partida concluída com menos de 7 jogadores.")
    if res.status == "abandoned":
        loser = res.abandoned_side
        if len(on[loser]) >= params.min_players:
            problems.append("Encerramento administrativo sem a equipe ter menos de 7 jogadores.")
        if res.official_score[1 - loser] < 3 or res.official_score[1 - loser] - res.official_score[loser] < 3:
            problems.append("Placar oficial do encerramento não favorece o adversário em pelo menos 3 × 0.")
    for r in res.ratings:
        if not 0.0 <= r.rating <= 10.0 or not 0.0 <= r.display <= 10.0:
            problems.append(f"Nota fora da faixa: {r}")
    if res.man_of_the_match is not None and res.man_of_the_match not in {r.player for r in res.ratings}:
        problems.append("Craque da Partida sem nota.")
    stats = compute_stats(ev)
    if stats != res.stats:
        problems.append("Estatísticas não correspondem aos eventos.")
    for key in ("home", "away"):
        s = stats[key]
        if s["goals"] > s["shots_on_target"] or s["shots_on_target"] > s["shots"]:
            problems.append(f"Estatísticas impossíveis ({key}): gols/no alvo/finalizações.")
        if s["big_chances"] > s["shots"] or s["xg"] < 0:
            problems.append(f"Estatísticas impossíveis ({key}): grandes chances/xG.")
        if s["red_cards"] > 11 or s["substitutions"] > params.max_substitutions:
            problems.append(f"Estatísticas impossíveis ({key}): cartões/substituições.")
    if abs(stats["home"]["possession_pct"] + stats["away"]["possession_pct"] - 100) > 0.2:
        problems.append("Posse de bola não soma 100%.")
    return problems
