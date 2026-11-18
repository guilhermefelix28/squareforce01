"""Notas individuais e Craque da Partida (GDD §14) — calculadas SOMENTE a partir dos eventos.

nota = base (6,0) + Σ efeitos das ações (positivas e negativas, ponderadas por dificuldade/importância:
       defesa de chute com xG alto vale mais; grande chance perdida pesa mais)
     + resultado da equipe × fração do tempo em campo
     + jogo sem sofrer gols (goleiro/defensores) × fração do tempo em campo
     − gols sofridos enquanto em campo (goleiro/defensores)
O overall não participa. Faixa 0,0–10,0; exibição com uma casa decimal; precisão interna preservada.
Craque: maior nota exibida → maior precisão interna → maior impacto decisivo (gols, assistências,
pênaltis defendidos, defesas em grandes chances) → [provisório] menor ID.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Sequence

from squadforce_shared.domain.positions import Position

from .params import MatchParams
from .types import Event, MatchInput, PlayerRating

DEFENSIVE_SLOTS = {Position.GK, Position.DR, Position.DL, Position.DC}


def event_deltas(ev: Event, p: MatchParams) -> list[tuple[int, float, float]]:
    """(jogador, efeito na nota, impacto decisivo) de um evento."""
    d = p.rating_deltas
    out: list[tuple[int, float, float]] = []
    t, data = ev.type, ev.data
    if t == "progression" and ev.player:
        out.append((ev.player, d["progression"], 0))
    elif t in ("tackle", "interception"):
        out.append((ev.player, d["tackle_won" if t == "tackle" else "interception"], 0))
        if ev.other:
            out.append((ev.other, d["possession_lost"] + (d["own_half_error"] if data.get("own_third_error") else 0), 0))
    elif t == "foul":
        out.append((ev.player, d["foul"] + (d["penalty_conceded"] if data.get("penalty") else 0), 0))
    elif t == "yellow_card":
        out.append((ev.player, d["yellow"], 0))
    elif t == "red_card":
        out.append((ev.player, d["red"], 0))
    elif t == "shot":
        if ev.other:
            out.append((ev.other, d["key_pass"], 0))
    elif t == "goal":
        out.append((ev.player, d["goal"], 1.0))
        if ev.other:
            out.append((ev.other, d["assist"], 0.6))
    elif t == "save":
        xg = float(data.get("xg", 0))
        if data.get("penalty"):
            out.append((ev.player, d["penalty_saved"], 0.8))
        else:
            out.append((ev.player, d["save"] * (0.5 + 2.0 * xg), 0.3 if xg >= p.big_chance_xg else 0.0))
        if ev.other:
            out.append((ev.other, d["shot_on_target"], 0))
    elif t == "miss":
        out.append((ev.player, d["shot_off_target"] + (d["big_chance_missed"] if data.get("big_chance") else 0), 0))
    elif t == "block":
        out.append((ev.player, d["block"], 0))
        if ev.other:
            out.append((ev.other, d["shot_off_target"] / 2, 0))
    return [(pid, delta, imp) for pid, delta, imp in out if pid is not None]


def live_rating(acc: dict[int, float], player: int, p: MatchParams) -> float:
    """Nota parcial (sem resultado/tempo) usada nas substituições por rendimento."""
    return p.rating_base + acc.get(player, 0.0)


def _display(v: float) -> float:
    return float(Decimal(str(v)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def compute_ratings(events: Sequence[Event], match: MatchInput, p: MatchParams, score: tuple[int, int]) -> list[PlayerRating]:
    lineups = events[0].data
    on_since: dict[int, float] = {}
    total: dict[int, float] = defaultdict(float)
    side_of: dict[int, int] = {}
    slot_of: dict[int, Position] = {}
    for side, key in ((0, "home"), (1, "away")):
        for pid, slot in lineups[key]:
            on_since[pid], side_of[pid], slot_of[pid] = 0.0, side, Position(slot)
    acc: dict[int, float] = defaultdict(float)
    impact: dict[int, float] = defaultdict(float)
    conceded: dict[int, int] = defaultdict(int)
    end = events[-1].second if events else 0.0
    for ev in events:
        for pid, delta, imp in event_deltas(ev, p):
            acc[pid] += delta
            impact[pid] += imp
        if ev.type == "substitution":
            off, on = ev.other, ev.player
            total[off] += ev.second - on_since.pop(off)
            on_since[on], side_of[on], slot_of[on] = ev.second, ev.side, Position(ev.data["slot"])
        elif ev.type in ("red_card", "player_off") and ev.player in on_since:
            total[ev.player] += ev.second - on_since.pop(ev.player)
        elif ev.type == "goal":
            for pid in on_since:
                if side_of[pid] != ev.side and slot_of[pid] in DEFENSIVE_SLOTS:
                    conceded[pid] += 1
    for pid, since in on_since.items():
        total[pid] += end - since
    duration = max(end, 1.0)
    ratings: list[PlayerRating] = []
    d = p.rating_deltas
    for pid in side_of:
        frac = min(1.0, total[pid] / duration)
        mine, theirs = score[side_of[pid]], score[1 - side_of[pid]]
        result = p.rating_result * (1 if mine > theirs else -1 if mine < theirs else 0) * frac
        defensive = slot_of[pid] in DEFENSIVE_SLOTS
        clean = p.rating_clean_sheet * frac if defensive and conceded[pid] == 0 and frac >= 0.5 else 0.0
        conceded_pen = conceded[pid] * (d["goal_conceded_gk"] if slot_of[pid] is Position.GK else d["goal_conceded_def"]) if defensive else 0.0
        r = max(0.0, min(10.0, p.rating_base + acc[pid] + result + clean + conceded_pen))
        ratings.append(PlayerRating(pid, side_of[pid], r, _display(r), round(total[pid] / 60, 2), impact[pid]))
    return sorted(ratings, key=lambda x: (x.side, x.player))


def man_of_the_match(ratings: Iterable[PlayerRating]) -> int | None:
    pool = [r for r in ratings if r.minutes > 0]
    if not pool:
        return None
    best = max(pool, key=lambda r: (r.display, r.rating, r.decisive_impact, -r.player))
    return best.player
