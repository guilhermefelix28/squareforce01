"""API da temporada (Entrega 7): início após o mercado, rodadas paralelas, avanço manual, pós-partida,
falhas sem consolidação parcial, repetição segura e encerramento."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, post_import, set_divisions
from services.competition.worker import play_fixture
from services.gateway.app import create_app
from services.gateway.settings import Settings
from squadforce_shared.contracts import MatchReportOut, SeasonStateOut, SeasonSummaryOut
from support.auction_fixtures import ManualClock
from support.trading_fixtures import SILENT, model_with
from test_auction_api import big_squad
from test_trading_api import finish_auction


def boot(tmp_path, executor="thread"):
    clock = ManualClock()
    graphics = tmp_path / "Graphics"
    (graphics / "Faces").mkdir(parents=True)
    settings = Settings(db_path=tmp_path / "season.db", graphics_dir=graphics, auction_ticker=False,
                        match_executor=executor, match_workers=2)
    return create_app(settings, clock=clock, auction_model=model_with(SILENT)), clock, settings


def to_competition(c, clock, sid):
    finish_auction(c, clock, sid)
    assert c.post(f"/api/sessions/{sid}/trading/start", headers={"Idempotency-Key": key()}).status_code == 201
    clock.advance(181)
    c.get(f"/api/sessions/{sid}/trading")
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "competition"


@pytest.fixture(params=[("league", 4, "double"), ("cup", 4, None)], ids=["liga", "copa"])
def env(request, tmp_path):
    fmt, n, rounds = request.param
    app, clock, settings = boot(tmp_path)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format=fmt, num_clubs=n, league_rounds=rounds).json()["id"]
        to_competition(c, clock, sid)
        yield c, sid, fmt


def post(c, sid, path, idem=None):
    return c.post(f"/api/sessions/{sid}/season/{path}", headers={"Idempotency-Key": idem or key()})


def state(c, sid) -> SeasonStateOut:
    r = c.get(f"/api/sessions/{sid}/season")
    assert r.status_code == 200, r.json()
    return SeasonStateOut.model_validate(r.json())


def test_season_requires_finished_market(tmp_path):
    app, clock, settings = boot(tmp_path)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c).json()["id"]
        r = post(c, sid, "start")
        assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_PHASE"
        r = c.get(f"/api/sessions/{sid}/season")
        assert r.status_code == 404 and r.json()["error"]["code"] == "SEASON_NOT_FOUND"


def test_full_competition_flow(env):
    c, sid, fmt = env
    idem = key()
    r = post(c, sid, "start", idem)
    assert r.status_code == 201
    assert post(c, sid, "start", idem).json() == r.json()  # idempotente
    assert post(c, sid, "start").status_code == 409  # uma única temporada
    s = SeasonStateOut.model_validate(r.json())
    assert s.phase == "ready" and s.round_number == 1 and not any(f.played for f in s.fixtures)
    assert post(c, sid, "advance").status_code == 409  # não avança sem jogar
    rounds = 0
    while True:
        idem = key()
        r = post(c, sid, "play", idem)
        assert r.status_code == 200, r.json()
        assert post(c, sid, "play", idem).json() == r.json()  # repetição da mesma chave não rejoga
        s = SeasonStateOut.model_validate(r.json())
        rounds += 1
        assert s.phase == "awaiting_advance" and all(f.played for f in s.fixtures)
        assert post(c, sid, "play").status_code == 409  # rodada não é consolidada duas vezes
        # pós-partida de cada confronto
        for f in s.fixtures:
            rep = c.get(f"/api/sessions/{sid}/season/matches/{f.match_id}")
            assert rep.status_code == 200
            m = MatchReportOut.model_validate(rep.json())
            assert m.score == f.score and m.ratings and m.stats["home"]["goals"] == m.score[0]
            assert m.man_of_the_match is None or m.man_of_the_match.player in {x.player for x in m.ratings}
            assert any(e.type == "full_time" for e in m.events)
            if fmt == "cup":
                assert m.winner_club_uid is not None
                assert (m.shootout is not None) == (m.score[0] == m.score[1])
        if fmt == "league":
            assert sum(row.played for row in s.standings) == 2 * sum(1 for _ in s.fixtures) * rounds
        s = SeasonStateOut.model_validate(post(c, sid, "advance").json())
        if s.phase == "finished":
            break
    assert rounds == (6 if fmt == "league" else 2)
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "finished"
    assert s.champion_club_uid is not None or s.tied_champions
    summ = SeasonSummaryOut.model_validate(c.get(f"/api/sessions/{sid}/season/summary").json())
    assert summ.finished and summ.champion_club_uid == s.champion_club_uid
    assert len(summ.history) == (12 if fmt == "league" else 3)
    assert summ.user_campaign.club_uid == s.user_club_uid
    assert summ.top_scorers and summ.most_man_of_the_match
    assert c.get(f"/api/sessions/{sid}/season/matches/NOPE").json()["error"]["code"] == "MATCH_NOT_FOUND"


def test_failed_match_blocks_consolidation_and_retry_replays_only_failures(env):
    c, sid, fmt = env
    post(c, sid, "start")
    season = c.app.state.container.seasons.get(sid)
    first = season.snapshot.tasks[0].match_id
    calls = []

    def flaky(task):
        calls.append(task.match_id)
        if task.match_id == first and calls.count(first) == 1:
            raise RuntimeError("falha simulada")
        return play_fixture(task)

    season.runner = flaky
    r = post(c, sid, "play")
    assert r.status_code == 500
    err = r.json()["error"]
    assert err["code"] == "ROUND_FAILED" and err["retryable"] and err["details"]["failed"] == [first]
    s = state(c, sid)
    assert s.phase == "ready" and s.failed_matches == [first] and not any(f.played for f in s.fixtures)
    assert all(row.played == 0 for row in s.standings)  # nada consolidado
    n = len(calls)
    r = post(c, sid, "play")
    assert r.status_code == 200
    assert calls[n:] == [first]  # só a partida falha foi repetida
    assert all(f.played for f in SeasonStateOut.model_validate(r.json()).fixtures)


def test_closing_session_discards_season(env):
    c, sid, _ = env
    post(c, sid, "start")
    assert c.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()}).status_code == 200
    assert c.app.state.container.seasons.get(sid) is None


def test_real_process_pool_round(tmp_path):
    app, clock, settings = boot(tmp_path, executor="process")
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        to_competition(c, clock, sid)
        post(c, sid, "start")
        r = post(c, sid, "play")
        assert r.status_code == 200, r.json()
        assert all(f.played for f in SeasonStateOut.model_validate(r.json()).fixtures)
