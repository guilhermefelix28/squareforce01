"""Integração com a base REAL e lotes exploratórios do motor (não é calibração oficial — PM-02).

Verifica: escalações reais montadas por posição, sequência de partidas com registro de lesões e
suspensões, coerência estrutural de todas as partidas e estatísticas observadas dentro de limites
de sanidade amplos. As faixas preliminares ficam no relatório, não são critério de aprovação.
"""

from __future__ import annotations

import random

import pytest

from conftest import REAL_PLAYERS_XLSX
from services.match_engine.availability import AvailabilityLedger
from services.match_engine.calibration import FORMATION_433, FORMATION_442, run_batch
from services.match_engine.engine import simulate
from services.match_engine.lineup import build_team_sheet
from services.match_engine.types import MatchInput
from services.match_engine.validation import validate_result

pytestmark = [pytest.mark.simulation, pytest.mark.real_data,
              pytest.mark.skipif(not REAL_PLAYERS_XLSX.exists(), reason="Dados/jogadores.xlsx ausente")]


@pytest.fixture(scope="module")
def pool():
    from services.data.importer import parse_clubs, parse_players, read_workbook
    from squadforce_shared.domain.players import PlayerProfile

    sheets = read_workbook(REAL_PLAYERS_XLSX.read_bytes(), "jogadores.xlsx")
    _, clubs = parse_clubs(sheets, "j")
    _, players = parse_players(sheets, "j", {c.club_uid for c in clubs})
    short = {c.club_uid: c.short_name for c in clubs}
    out: dict[int, list] = {}
    for p in players:
        out.setdefault(p.club_uid, []).append(PlayerProfile(
            p.unique_id, p.name, p.age, p.club_uid, short[p.club_uid], tuple(p.natural_positions),
            tuple(p.accomplished_positions), dict(p.familiarity), dict(p.attributes)))
    return out


def test_exploratory_batch_is_coherent_and_plausible(pool):
    r = run_batch(pool, 300, seed=11)
    assert r.invalid == 0
    m = r.metrics
    # limites de SANIDADE (amplos), não calibração
    assert 1.5 < m["goals_per_match"] < 4.0
    assert 0.12 < m["draw_rate"] < 0.40
    assert 0 < m["nil_nil_rate"] < 0.2 and m["five_plus_goals_rate"] > 0
    assert 7 < m["shots_per_team"] < 22 and m["on_target_per_team"] < m["shots_per_team"]
    assert 0.05 < m["conversion_per_shot"] < 0.16
    assert m["reds_per_match"] < 0.6 and m["subs_per_team"] <= 5


def test_season_of_real_matches_with_ledger(pool):
    """10 rodadas entre 4 clubes reais com 18 atletas cada: lesionados/suspensos ficam fora e voltam."""
    rng = random.Random(3)
    clubs = sorted(pool)[:4]
    squads = {c: rng.sample(pool[c], 18) for c in clubs}
    ledger = AvailabilityLedger()
    seen_unavailable = 0
    for rnd in range(10):
        a, b = rng.sample(clubs, 2)
        comp = "liga" if rnd % 2 == 0 else "copa"
        sa = build_team_sheet(a, squads[a], FORMATION_433, ledger, comp)
        sb = build_team_sheet(b, squads[b], FORMATION_442, ledger, comp)
        for sheet in (sa, sb):
            for pl in (*sheet.starters, *sheet.bench):
                assert pl.is_emergency or ledger.is_available(pl.unique_id, comp)
        unavailable = [p for c in (a, b) for p in squads[c] if not ledger.is_available(p.unique_id, comp)]
        seen_unavailable += len(unavailable)
        m = MatchInput(f"R{rnd}", comp, sa, sb, seed=rnd)
        res = simulate(m)
        eligible = tuple({p.unique_id for p in squads[c] if ledger.is_available(p.unique_id, comp)} for c in (a, b))
        assert validate_result(res, m, eligible=eligible) == []
        ledger.record_match(res, (sa, sb), ({p.unique_id for p in squads[a]}, {p.unique_id for p in squads[b]}))
    assert any(h["type"] in ("injury", "yellow_card", "red_card") for h in ledger.history)
