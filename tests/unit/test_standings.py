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
