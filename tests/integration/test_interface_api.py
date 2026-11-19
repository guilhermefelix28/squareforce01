"""API da integração da interface (Entrega 8): elenco, escalação, partida ao vivo, estatísticas e calendário."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, post_import, set_divisions
from squadforce_shared.contracts import (
    CalendarOut,
    LineupOut,
    LiveStateOut,
    MatchReportOut,
    SeasonStateOut,
    SeasonStatsOut,
    SquadPlayerOut,
)
from test_auction_api import big_squad
from test_season_api import boot, to_competition


@pytest.fixture
def env(tmp_path):
    app, clock, settings = boot(tmp_path)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="league", num_clubs=4, league_rounds="single").json()["id"]
        to_competition(c, clock, sid)
        assert c.post(f"/api/sessions/{sid}/season/start", headers={"Idempotency-Key": key()}).status_code == 201
        yield c, clock, sid


def post(c, sid, path, body=None, idem=None):
    return c.post(f"/api/sessions/{sid}/season/{path}", json=body or {}, headers={"Idempotency-Key": idem or key()})


def get(c, sid, path):
    r = c.get(f"/api/sessions/{sid}/season/{path}")
    assert r.status_code == 200, r.json()
    return r.json()


def test_squad_and_formations(env):
    c, _, sid = env
    squad = [SquadPlayerOut.model_validate(x) for x in get(c, sid, "squad")]
    assert len(squad) == 18 and all(p.available for p in squad)
    assert all(p.fit[p.position] == "natural" for p in squad)
    forms = get(c, sid, "formations")
    assert {f["id"] for f in forms} == {"4-3-3", "4-4-2", "5-3-2"} and all(len(f["positions"]) == 11 for f in forms)
    assert "attributes" not in str(squad[0].model_dump())  # atributos não são expostos


def test_lineup_set_validate_and_used_in_the_match(env):
    c, clock, sid = env
    lu = LineupOut.model_validate(get(c, sid, "lineup"))
    assert lu.has_match and lu.source == "auto" and len(lu.starters) == 11 and lu.opponent is not None
    squad = [SquadPlayerOut.model_validate(x) for x in get(c, sid, "squad")]
    form = next(f for f in get(c, sid, "formations") if f["id"] == "4-4-2")
    # posicionamento livre: titulares fora da posição natural são permitidos
    starters = [p.player for p in squad[:11]]
    bench = [p.player for p in squad[11:18]]
    r = post(c, sid, "lineup", {"formation": "4-4-2", "starters": starters, "bench": bench, "posture": "ofensiva"})
    assert r.status_code == 200, r.json()
    lu = LineupOut.model_validate(r.json())
    assert lu.source == "user" and lu.formation == "4-4-2" and lu.posture == "ofensiva"
    assert [s.player for s in lu.starters] == starters and [s.position for s in lu.starters] == form["positions"]
    assert any(s.fit != "natural" for s in lu.starters)  # indicadores de adequação
    # erros
    bad = post(c, sid, "lineup", {"formation": "4-4-2", "starters": starters[:10] + [starters[0]], "bench": []})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_LINEUP"
    bad = post(c, sid, "lineup", {"formation": "3-5-2", "starters": starters, "bench": []})
    assert bad.status_code == 422
    bad = post(c, sid, "lineup", {"formation": "4-4-2", "starters": starters[:10] + [999999], "bench": []})
    assert bad.status_code == 422
    # a escalação do usuário é a usada na partida
    s = SeasonStateOut.model_validate(post(c, sid, "play").json())
    mine = next(f for f in s.fixtures if f.is_user_match)
    rep = MatchReportOut.model_validate(get(c, sid, f"matches/{mine.match_id}"))
    own = next(x for x in rep.lineups if x.club_uid == s.user_club_uid)
    assert own.formation == "4-4-2" and [p.player for p in own.starters] == starters
    assert own.initial_posture == "ofensiva" and len(rep.lineups) == 2


def test_lineup_rejects_unavailable_player(env):
    c, _, sid = env
    season = c.app.state.container.seasons.get(sid)
    squad = [SquadPlayerOut.model_validate(x) for x in get(c, sid, "squad")]
    season.state.ledger.injuries[squad[0].player] = 2
    sq = [SquadPlayerOut.model_validate(x) for x in get(c, sid, "squad")]
    assert not sq[0].available and "lesionado" in sq[0].unavailable_reason
    r = post(c, sid, "lineup", {"formation": "4-3-3", "starters": [p.player for p in squad[:11]], "bench": []})
    assert r.status_code == 422 and "Indisponíveis" in r.json()["error"]["message"]


def test_live_match_flow_reveals_progressively_and_round_reproduces_it(env):
    c, clock, sid = env
    assert c.get(f"/api/sessions/{sid}/season/live").json()["error"]["code"] == "LIVE_NOT_FOUND"
    idem = key()
    r = post(c, sid, "live/start", {"speed": "60s"}, idem)
    assert r.status_code == 201
    assert post(c, sid, "live/start", {"speed": "60s"}, idem).json() == r.json()  # sem comando duplicado
    st = LiveStateOut.model_validate(r.json())
    assert st.minute <= 1 and not st.finished and len(st.own_players) == 11
    # escalação fechada depois do início
    lu = LineupOut.model_validate(get(c, sid, "lineup"))
    assert lu.locked
    r = post(c, sid, "lineup", {"formation": "4-3-3", "starters": [s.player for s in lu.starters], "bench": []})
    assert r.status_code == 409 and r.json()["error"]["code"] == "MATCH_IN_PROGRESS"
    # play bloqueado durante a apresentação
    r = post(c, sid, "play")
    assert r.status_code == 409 and r.json()["error"]["code"] == "MATCH_IN_PROGRESS"
    clock.advance(30)  # metade da apresentação de 60 s
    st = LiveStateOut.model_validate(get(c, sid, "live"))
    assert 40 <= st.minute <= 52 and not any(e.type == "full_time" for e in st.events)
    assert all(e.second <= st.game_second + 1e-6 for e in st.events)
    assert any(p.condition < 100 for p in st.own_players)  # desgaste visível
    r = post(c, sid, "live/posture", {"posture": "ataque_total"})
    assert r.status_code == 200
    user_side = st.user_side
    assert LiveStateOut.model_validate(r.json()).postures[user_side] in ("equilibrada", "ataque_total")
    assert post(c, sid, "live/posture", {"posture": "ataque_total"}).status_code == 409  # já é a postura
    r = post(c, sid, "live/speed", {"speed": "instant"})
    final = LiveStateOut.model_validate(r.json())
    assert final.finished and final.postures[user_side] == "ataque_total"
    assert any(e.type == "posture_change" and e.side == user_side for e in final.events)
    s = SeasonStateOut.model_validate(post(c, sid, "play").json())
    mine = next(f for f in s.fixtures if f.is_user_match)
    assert tuple(mine.score) == tuple(final.score)  # a rodada reproduz exatamente a partida ao vivo
    rep = MatchReportOut.model_validate(get(c, sid, f"matches/{mine.match_id}"))
    assert [e.seq for e in rep.events if e.type == "goal"] == [e.seq for e in final.events if e.type == "goal"]
    post(c, sid, "advance")
    assert c.get(f"/api/sessions/{sid}/season/live").status_code == 404  # nova rodada, nova partida


def test_live_invalid_speed(env):
    c, _, sid = env
    r = post(c, sid, "live/start", {"speed": "5s"})
    assert r.status_code == 422


def test_stats_and_calendar(env):
    c, _, sid = env
    cal = CalendarOut.model_validate(get(c, sid, "calendar"))
    assert cal.kind == "league" and len(cal.rounds) == 3 and cal.current_round == 1
    assert not any(f.played for r in cal.rounds for f in r.fixtures)
    post(c, sid, "play")
    cal = CalendarOut.model_validate(get(c, sid, "calendar"))
    assert all(f.played for f in cal.rounds[0].fixtures) and not any(f.played for f in cal.rounds[1].fixtures)
    st = SeasonStatsOut.model_validate(get(c, sid, "stats"))
    assert st.matches_played == 2 and len(st.clubs) == 4
    goals = sum(p.goals for p in st.players)
    assert goals == sum(cl.goals_for for cl in st.clubs) == sum(cl.totals["shots"] * 0 + cl.goals_for for cl in st.clubs)
    assert all(cl.played == 1 for cl in st.clubs)
    assert all(0 <= cl.totals["possession_pct"] <= 100 for cl in st.clubs)
    assert any(p.rating_eligible for p in st.players)


def test_clock_scale_is_opt_in_and_only_speeds_up_server_time(tmp_path):
    """SQUADFORCE_CLOCK_SCALE (somente testes/demonstração): padrão 1 = relógio real."""
    from services.gateway.container import build_container
    from services.gateway.settings import Settings
    from support.auction_fixtures import ManualClock

    assert Settings(db_path=tmp_path / "a.db").clock_scale == 1.0
    base = ManualClock()
    c = build_container(Settings(db_path=tmp_path / "b.db", clock_scale=10.0), clock=base, auction_model=None)
    t0 = c.clock()
    base.advance(2)
    assert c.clock() - t0 == pytest.approx(20)
    assert c.trading.clock is c.clock and c.auctions.clock is c.clock
    normal = build_container(Settings(db_path=tmp_path / "c.db"), clock=base, auction_model=None)
    assert normal.clock is base
