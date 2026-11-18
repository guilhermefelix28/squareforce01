"""Simulações de competições inteiras (Entrega 7): coerência estatística e integridade em lote."""

from __future__ import annotations

import pytest

from squadforce_shared.domain.competition import LeagueRounds
from support.season_fixtures import make_season, run_all

pytestmark = pytest.mark.simulation


def test_full_20_club_league_integrity_and_strength_signal():
    levels = {c: 45 + c for c in range(1, 21)}  # força crescente 46..65
    s = make_season("league", 20, rounds=LeagueRounds.DOUBLE, seed=99, levels=levels)
    run_all(s, workers=8)
    table = s.standings()
    assert len(s.state.history) == 380 and all(r.played == 38 for r in table)
    pts = {r.club_uid: r.points for r in table}
    strong = sum(pts[c] for c in range(16, 21)) / 5
    weak = sum(pts[c] for c in range(1, 6)) / 5
    assert strong > weak  # clubes mais fortes pontuam mais
    assert sum(r.goals_for for r in table) == sum(p.goals for p in s.state.players.values())


@pytest.mark.parametrize("seed", range(5))
def test_many_cups_of_32(seed):
    s = make_season("cup", 32, seed=100 + seed)
    run_all(s, workers=8)
    assert len(s.state.history) == 31
    assert s.state.bracket.champion_club_uid is not None
    assert all(m.winner_club_uid is not None for r in s.state.bracket.rounds for m in r.matches)
