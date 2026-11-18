"""Estatísticas da partida DERIVADAS dos eventos simulados (nenhum número é gerado à parte)."""

from __future__ import annotations

from typing import Any, Sequence

from .types import Event

COUNTED = {
    "goal": "goals", "shot": "shots", "save": "saves_made", "miss": "shots_off_target", "block": "blocks_made",
    "corner": "corners", "foul": "fouls", "yellow_card": "yellow_cards", "red_card": "red_cards",
    "substitution": "substitutions", "injury": "injuries", "progression": "progressions",
    "tackle": "tackles", "interception": "interceptions", "penalty_awarded": "penalties",
}


def compute_stats(events: Sequence[Event]) -> dict[str, Any]:
    sides: list[dict[str, Any]] = [
        {k: 0 for k in set(COUNTED.values())} | {"xg": 0.0, "big_chances": 0, "big_chances_missed": 0,
                                                  "shots_on_target": 0, "shots_blocked": 0, "possession_seconds": 0.0,
                                                  "possessions": 0, "woodwork": 0}
        for _ in range(2)
    ]
    last_poss: tuple[int, float] | None = None
    last_shot_big = [False, False]
    big_scored = [0, 0]
    for i, ev in enumerate(events):
        if ev.type in ("possession", "half_time", "full_time", "abandoned"):
            if last_poss is not None:
                sides[last_poss[0]]["possession_seconds"] += max(0.0, ev.second - last_poss[1])
            last_poss = (ev.side, ev.second) if ev.type == "possession" else None
            if ev.type == "possession":
                sides[ev.side]["possessions"] += 1
        if ev.side is None:
            continue
        s = sides[ev.side]
        if ev.type in COUNTED:
            s[COUNTED[ev.type]] += 1
        if ev.type == "shot":
            s["xg"] += float(ev.data.get("xg", 0.0))
            s["big_chances"] += 1 if ev.data.get("big_chance") else 0
            last_shot_big[ev.side] = bool(ev.data.get("big_chance"))
        elif ev.type == "goal":
            s["shots_on_target"] += 1
            big_scored[ev.side] += 1 if last_shot_big[ev.side] else 0
        elif ev.type == "save":
            sides[1 - ev.side]["shots_on_target"] += 1
        elif ev.type == "block":
            sides[1 - ev.side]["shots_blocked"] += 1
        elif ev.type == "miss":
            s["woodwork"] += 1 if ev.data.get("woodwork") else 0
    for i, s in enumerate(sides):
        s["big_chances_missed"] = s["big_chances"] - big_scored[i]
    total = sum(s["possession_seconds"] for s in sides) or 1.0
    for s in sides:
        s["xg"] = round(s["xg"], 3)
        s["possession_pct"] = round(100 * s["possession_seconds"] / total, 1)
        s["possession_seconds"] = round(s["possession_seconds"], 1)
    return {"home": sides[0], "away": sides[1]}
