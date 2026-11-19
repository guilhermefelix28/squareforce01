"""Classificação: pontuação, empates sem critério (PC-01 pendente) e critérios configuráveis."""

import pytest

from services.competition.standings import ClubRecord, MatchScore, PointsSystem, apply_result, standings

NAMES = {1: "Alfa", 2: "Beta", 3: "Gama"}


def recs(*results):
    r = {c: ClubRecord(c) for c in NAMES}
    for m in results:
        apply_result(r, m, PointsSystem())
    return r


def test_points_goals_and_form():
    r = recs(MatchScore(1, 2, 2, 0), MatchScore(2, 3, 1, 1))
    assert (r[1].points, r[1].wins, r[1].goal_difference, r[1].form) == (3, 1, 2, ["V"])
    assert (r[2].points, r[2].played, r[2].goals_for, r[2].goals_against, r[2].form) == (1, 2, 1, 3, ["D", "E"])
    assert (r[3].points, r[3].draws) == (1, 1)


def test_without_official_tiebreakers_equal_points_stay_tied_and_flagged():
    # 2 e 3 têm 1 ponto, saldos diferentes: SEM critério oficial, não são separados (PC-01)
    r = recs(MatchScore(1, 2, 2, 0), MatchScore(2, 3, 1, 1), MatchScore(1, 3, 1, 0))
    rows = standings(r, NAMES)
    by = {x.club_uid: x for x in rows}
    assert by[1].position == 1 and by[1].tied_with == ()
    assert by[2].points == by[3].points == 1
    assert by[2].position == by[3].position == 2  # posição compartilhada
    assert by[2].tied_with == (3,) and by[3].tied_with == (2,)


def test_configured_criteria_are_applied_in_the_given_order():
    r = recs(MatchScore(1, 2, 2, 0), MatchScore(2, 3, 1, 1), MatchScore(1, 3, 1, 0))
    rows = standings(r, NAMES, tiebreakers=("goal_difference",))
    assert [x.club_uid for x in rows] == [1, 3, 2]
    assert [x.position for x in rows] == [1, 2, 3]
    assert all(x.tied_with == () for x in rows)


def test_head_to_head_and_unknown_criterion():
    res = [MatchScore(1, 2, 0, 1), MatchScore(1, 3, 5, 0), MatchScore(2, 3, 0, 1)]
    r = recs(*res)  # todos com 3 pontos; confronto direto não separa (ciclo)
    rows = standings(r, NAMES, ("head_to_head_points",), res)
    assert {x.position for x in rows} == {1}
    with pytest.raises(ValueError):
        standings(r, NAMES, ("sorteio",))


def test_custom_points_system():
    r = {c: ClubRecord(c) for c in NAMES}
    apply_result(r, MatchScore(1, 2, 1, 0), PointsSystem(win=2, draw=1))
    assert r[1].points == 2


# ---------------------------------------------------------------- PC-01: padrão Brasileirão (confirmado 2026-11-19)
from services.competition.standings import BRASILEIRAO_TIEBREAKERS  # noqa: E402

N4 = {1: "Alfa", 2: "Beta", 3: "Gama", 4: "Delta"}


def recs4(*results):
    r = {c: ClubRecord(c) for c in N4}
    for m in results:
        apply_result(r, m, PointsSystem())
    return r


def test_brasileirao_order_is_the_confirmed_one():
    assert BRASILEIRAO_TIEBREAKERS == ("wins", "goal_difference", "goals_for", "head_to_head_two_clubs",
                                       "fewer_red_cards", "fewer_yellow_cards", "draw")


def test_wins_come_before_goal_difference():
    # 1: V+D+D = 3 pts (1 vitória); 2: E+E+E = 3 pts (0 vitórias) com saldo melhor
    res = [MatchScore(1, 3, 1, 0), MatchScore(1, 4, 0, 5), MatchScore(1, 2, 0, 0)]
    r = recs4(*res)
    r[2].draws, r[2].points, r[2].played = 3, 3, 3
    r[1].draws, r[1].points = 0, 3
    rows = standings(r, N4, BRASILEIRAO_TIEBREAKERS, res, draw_seed=1)
    order = [x.club_uid for x in rows]
    assert order.index(1) < order.index(2)


def test_head_to_head_only_between_exactly_two_tied_clubs():
    # 1 e 2: mesmos pontos/vitórias/saldo/gols; 2 venceu o confronto direto
    res = [MatchScore(1, 2, 0, 1), MatchScore(1, 3, 2, 1), MatchScore(2, 4, 1, 2)]
    r = recs4(*res)
    assert (r[1].points, r[1].wins, r[1].goal_difference, r[1].goals_for) == \
           (r[2].points, r[2].wins, r[2].goal_difference, r[2].goals_for)
    rows = standings(r, N4, ("goal_difference", "head_to_head_two_clubs"), res)  # 4 sai pelo saldo
    order = [x.club_uid for x in rows]
    assert order.index(2) < order.index(1) and rows[order.index(2)].tied_with == ()


def test_head_to_head_is_skipped_for_three_tied_clubs():
    res = [MatchScore(1, 2, 0, 1), MatchScore(1, 3, 5, 0), MatchScore(2, 3, 0, 1)]
    r = recs(*res)
    rows = standings(r, NAMES, ("head_to_head_two_clubs",), res)
    assert {x.position for x in rows} == {1} and all(len(x.tied_with) == 2 for x in rows)


def test_fewer_red_then_fewer_yellow_cards():
    res = [MatchScore(1, 2, 1, 1, home_yellow=3, home_red=0, away_yellow=1, away_red=1),
           MatchScore(3, 4, 1, 1, home_yellow=2, home_red=0, away_yellow=4, away_red=0)]
    r = recs4(*res)
    assert (r[1].yellow_cards, r[1].red_cards, r[2].yellow_cards, r[2].red_cards) == (3, 0, 1, 1)
    rows = standings(r, N4, ("fewer_red_cards", "fewer_yellow_cards"), res)
    assert [x.club_uid for x in rows] == [3, 1, 4, 2]


def test_draw_always_separates_deterministically_by_seed():
    r = {c: ClubRecord(c) for c in N4}  # todos zerados: só o sorteio separa
    a = [x.club_uid for x in standings(r, N4, BRASILEIRAO_TIEBREAKERS, draw_seed=7)]
    b = [x.club_uid for x in standings(r, N4, BRASILEIRAO_TIEBREAKERS, draw_seed=7)]
    assert a == b and sorted(a) == [1, 2, 3, 4]
    assert [x.position for x in standings(r, N4, BRASILEIRAO_TIEBREAKERS, draw_seed=7)] == [1, 2, 3, 4]
    assert all(x.tied_with == () for x in standings(r, N4, BRASILEIRAO_TIEBREAKERS, draw_seed=7))
    orders = {tuple(x.club_uid for x in standings(r, N4, BRASILEIRAO_TIEBREAKERS, draw_seed=s)) for s in range(20)}
    assert len(orders) > 1  # a semente realmente sorteia
