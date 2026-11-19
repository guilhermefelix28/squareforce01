"""Partida ao vivo (GDD §11, §16): revelação progressiva, velocidades e determinismo das decisões."""

from __future__ import annotations

import pytest

from services.competition.live import LiveError, LiveMatch
from services.competition.season import events_digest
from services.competition.worker import play_fixture
from support.auction_fixtures import ManualClock
from support.season_fixtures import USER, make_season


def user_task(seed=3):
    s = make_season("league", 4, seed=seed)
    return s, s.user_task()


def test_only_events_up_to_the_clock_are_revealed():
    _, task = user_task()
    clock = ManualClock()
    live = LiveMatch.start(task, USER, "30s", clock)
    v0 = live.view()
    assert all(e.second <= 1 for e in v0["events"]) and not v0["finished"]
    clock.advance(10)  # 1/3 da apresentação de 30 s
    v1 = live.view()
    assert v1["events"] and max(e.second for e in v1["events"]) <= 10 * (96 * 60) / 30
    assert not any(e.type == "full_time" for e in v1["events"])
    clock.advance(25)
    v2 = live.view()
    assert v2["finished"] and any(e.type == "full_time" for e in v2["events"])
    full = play_fixture(task).result
    assert v2["score"] == full.score  # sem decisões: mesma partida da execução da rodada


@pytest.mark.parametrize("speed", ["15s", "30s", "60s", "instant"])
def test_speed_does_not_change_events_without_decisions(speed):
    _, task = user_task(5)
    clock = ManualClock()
    live = LiveMatch.start(task, USER, speed, clock)
    clock.advance(61)
    assert events_digest(live.result()) == events_digest(play_fixture(task).result)


def test_posture_change_is_reproduced_by_the_round_execution_at_any_speed():
    _, task = user_task(7)
    digests = []
    for speed, wait in (("15s", 7.5), ("60s", 30.0)):  # mesma decisão no mesmo tempo de jogo (≈ 48 min)
        clock = ManualClock()
        live = LiveMatch.start(task, USER, speed, clock)
        clock.advance(wait)
        live.view()
        second = live.change_posture("ataque_total")
        assert second >= 45 * 60
        clock.advance(120)
        res = live.result()
        replay = play_fixture(live.final_task()).result
        assert events_digest(res) == events_digest(replay)
        digests.append(events_digest(res))
    assert events_digest(play_fixture(task).result) != digests[0]  # a decisão mudou o jogo dali em diante


def test_change_speed_midway_keeps_game_time_and_events():
    _, task = user_task(9)
    clock = ManualClock()
    live = LiveMatch.start(task, USER, "60s", clock)
    clock.advance(20)
    before = live.view()["events"]
    live.set_speed("15s")
    after = live.view()["events"]
    assert after[: len(before)] == before
    clock.advance(20)
    assert events_digest(live.result()) == events_digest(play_fixture(task).result)


def test_errors_and_own_team_only_condition():
    _, task = user_task(11)
    clock = ManualClock()
    with pytest.raises(LiveError):
        LiveMatch.start(task, USER, "5s", clock)
    live = LiveMatch.start(task, USER, "30s", clock)
    with pytest.raises(LiveError):
        live.change_posture("equilibrada")  # já é a postura atual
    with pytest.raises(LiveError):
        live.result()  # ainda em andamento
    v = live.view()
    own_ids = {p.unique_id for p in (*live.task.home.starters, *live.task.home.bench)} if live.user_side == 0 else \
        {p.unique_id for p in (*live.task.away.starters, *live.task.away.bench)}
    assert {p["player"] for p in v["own_players"]} <= own_ids
    clock.advance(40)
    live.view()
    with pytest.raises(LiveError):
        live.change_posture("retranca")  # terminada
