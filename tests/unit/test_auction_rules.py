"""Regras aprovadas do leilão (GDD §4, §5, §7)."""

import pytest

from services.auction import rules
from squadforce_shared.domain.competition import CompetitionFormat

L, C = CompetitionFormat.LEAGUE, CompetitionFormat.CUP


@pytest.mark.parametrize(
    "fmt,n,minutes",
    [(L, 2, 10), (L, 10, 10), (L, 11, 15), (L, 20, 15), (C, 2, 10), (C, 4, 10), (C, 8, 10), (C, 16, 15), (C, 32, 20)],
)
def test_global_duration_table(fmt, n, minutes):
    assert rules.auction_duration_seconds(fmt, n) == minutes * 60


@pytest.mark.parametrize("fmt,n", [(L, 1), (L, 21), (C, 3), (C, 64)])
def test_duration_undefined_configurations(fmt, n):
    with pytest.raises(ValueError):
        rules.auction_duration_seconds(fmt, n)


@pytest.mark.parametrize("c,expected", [(0, 0), (3, 0), (4, 1), (7, 1), (8, 2), (12, 3), (14, 3), (15, 3), (16, 2), (17, 1), (18, 0)])
def test_improvement_limit_formula(c, expected):
    # min(18 − C, piso(C / 4))
    assert rules.improvement_limit(c) == expected == min(18 - c, c // 4)


def test_constants_match_game_design():
    assert rules.INITIAL_BUDGET == 120_000_000
    assert (rules.SQUAD_SIZE, rules.STARTERS, rules.RESERVES) == (18, 11, 7)
    assert (rules.ROUND_SECONDS, rules.PLAYERS_PER_ROUND) == (10.0, 5)
    assert rules.MIN_RESERVE_PER_SLOT == 500_000
    assert rules.POSITION_WINDOW == 14
    assert (rules.STARTERS_WEIGHT, rules.RESERVES_WEIGHT) == (0.8, 0.2)
    assert rules.BID_INCREMENTS == (100_000, 500_000, 1_000_000)
    assert rules.HIGHLIGHT_PERCENTILE == 85


@pytest.mark.parametrize("budget,count,expected", [
    (120_000_000, 0, 120_000_000 - 17 * 500_000),
    (120_000_000, 17, 120_000_000),  # última vaga: não há vaga restante após a compra
    (10_000_000, 10, 10_000_000 - 7 * 500_000),
])
def test_max_affordable_bid_preserves_500k_per_remaining_slot(budget, count, expected):
    assert rules.max_affordable_bid(budget, count) == expected
