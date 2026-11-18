"""API do mercado de negociações (Entrega 4): fases, propostas, decisões, idempotência, reconexão, WS."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, post_import, set_divisions
from squadforce_shared.contracts import ProposalOut, TradingSquadOut, TradingStateOut
from test_auction_api import big_squad, make_client
from support.fake_auction_model import FakeAuctionModel
from support.trading_fixtures import SILENT, model_with


def finish_auction(c, clock, sid):
    assert c.post(f"/api/sessions/{sid}/auction/start", headers={"Idempotency-Key": key()}).status_code == 201
    for _ in range(61):
        clock.advance(10)
        c.get(f"/api/sessions/{sid}/auction")
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "squad_completion"


def boot(tmp_path, model, ticker=False, tick=0.1):
    app, clock, settings = make_client(tmp_path, model, ticker=ticker, tick=tick)
    return app, clock, settings


@pytest.fixture
def env(tmp_path):
    app, clock, settings = boot(tmp_path, model_with(SILENT))
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        finish_auction(c, clock, sid)
        yield c, clock, sid


def start(c, sid, idem=None):
    return c.post(f"/api/sessions/{sid}/trading/start", headers={"Idempotency-Key": idem or key()})


def state(c, sid) -> TradingStateOut:
    r = c.get(f"/api/sessions/{sid}/trading")
    assert r.status_code == 200, r.json()
    return TradingStateOut.model_validate(r.json())


def squads(c, sid, **params) -> list[TradingSquadOut]:
    r = c.get(f"/api/sessions/{sid}/trading/squads", params=params)
    assert r.status_code == 200, r.json()
    return [TradingSquadOut.model_validate(x) for x in r.json()]


def propose(c, sid, to, give, take, money=0, idem=None):
    return c.post(f"/api/sessions/{sid}/trading/proposals",
                  json={"recipient_club_uid": to, "offered_player_id": give, "requested_player_id": take, "money": money},
                  headers={"Idempotency-Key": idem or key()})


def act(c, sid, pid, action, idem=None):
    return c.post(f"/api/sessions/{sid}/trading/proposals/{pid}/{action}", headers={"Idempotency-Key": idem or key()})


def first_pair(c, sid):
    sq = {s.club_uid: s for s in squads(c, sid)}
    user = next(s for s in sq.values() if s.is_user)
    other = next(s for s in sq.values() if not s.is_user)
    return user, other


# ------------------------------------------------------------------ fases
def test_market_requires_completed_auction(loaded_client):
    sid = create_session(loaded_client).json()["id"]
    r = start(loaded_client, sid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_PHASE"
    r = loaded_client.get(f"/api/sessions/{sid}/trading")
    assert r.status_code == 404 and r.json()["error"]["code"] == "MARKET_NOT_FOUND"


def test_start_only_by_user_and_once(env):
    c, clock, sid = env
    clock.advance(30)  # sem clicar em "Iniciar negociações" o mercado não existe
    assert c.get(f"/api/sessions/{sid}/trading").status_code == 404
    idem = key()
    r = start(c, sid, idem)
    assert r.status_code == 201
    s = TradingStateOut.model_validate(r.json())
    assert s.phase == "running" and s.remaining_ms == 180_000 and s.max_trades == 3 and s.completed_trades == 0
    assert start(c, sid, idem).headers["Idempotent-Replayed"] == "true"
    again = start(c, sid)
    assert again.status_code == 409 and again.json()["error"]["code"] == "INVALID_PHASE"
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "trading"


def test_squads_are_public_and_filterable(env):
    c, _, sid = env
    start(c, sid)
    all_sq = squads(c, sid)
    assert len(all_sq) == 4 and all(len(s.players) == 18 for s in all_sq)
    raw = c.get(f"/api/sessions/{sid}/trading/squads").text
    assert not any(w in raw for w in ("overall", "attributes", "market_value", "personality", "reputation"))
    some = all_sq[1].players[0]
    by_name = squads(c, sid, search=some.name)
    assert any(p.unique_id == some.unique_id for s in by_name for p in s.players)
    gk = squads(c, sid, position="GOL")
    assert all(p.position == "GK" for s in gk for p in s.players)
    one = squads(c, sid, club_uid=all_sq[2].club_uid)
    assert [s.club_uid for s in one] == [all_sq[2].club_uid]
    bad = c.get(f"/api/sessions/{sid}/trading/squads", params={"position": "XX"})
    assert bad.status_code == 422


# ------------------------------------------------------------------ propostas
def test_proposal_lifecycle_and_errors(env):
    c, clock, sid = env
    start(c, sid)
    user, other = first_pair(c, sid)
    give, take = user.players[0].unique_id, other.players[0].unique_id

    r = propose(c, sid, other.club_uid, give, take, money=user.budget + 1)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INSUFFICIENT_FUNDS"
    r = propose(c, sid, other.club_uid, take, give)
    assert r.status_code == 422 and r.json()["error"]["code"] == "PLAYER_NOT_OWNED"
    r = propose(c, sid, user.club_uid, give, take)
    assert r.status_code == 422 and r.json()["error"]["code"] == "SAME_CLUB"
    r = c.post(f"/api/sessions/{sid}/trading/proposals",
               json={"recipient_club_uid": other.club_uid, "offered_player_id": give, "requested_player_id": take, "money": -5},
               headers={"Idempotency-Key": key()})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"

    idem = key()
    p = ProposalOut.model_validate(propose(c, sid, other.club_uid, give, take, 1_000_000, idem).json())
    assert p.status == "pending" and p.direction == "outgoing" and p.remaining_ms == 10_000
    replay = propose(c, sid, other.club_uid, give, take, 1_000_000, idem)
    assert replay.headers["Idempotent-Replayed"] == "true" and replay.json()["id"] == p.id
    second = propose(c, sid, other.club_uid, user.players[1].unique_id, other.players[1].unique_id)
    assert second.status_code == 409 and second.json()["error"]["code"] == "PENDING_PROPOSAL_EXISTS"

    s = state(c, sid)
    assert s.outgoing.id == p.id and s.budget == user.budget  # nada é pago antes da conclusão
    r = act(c, sid, p.id, "accept")
    assert r.status_code == 403 and r.json()["error"]["code"] == "NOT_RECIPIENT"
    cancel = act(c, sid, p.id, "cancel")
    assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
    assert state(c, sid).outgoing is None
    assert state(c, sid).recent_decisions[0].status == "cancelled"


def test_incoming_proposal_accept_executes_trade_once(env):
    c, clock, sid = env
    start(c, sid)
    app_engine = c.app.state.container.trading.get(sid)
    user, other = first_pair(c, sid)
    money = min(2_000_000, other.budget)  # o bot só pode pagar o que tem
    p = app_engine.propose(other.club_uid, user.club_uid, other.players[0].unique_id, user.players[0].unique_id,
                           money, "bot-proposal")
    s = state(c, sid)
    assert [x.id for x in s.incoming] == [p.id] and s.incoming[0].direction == "incoming"
    clock.advance(3)
    assert state(c, sid).incoming[0].remaining_ms == 7_000

    idem = key()
    a = act(c, sid, p.id, "accept", idem)
    b = act(c, sid, p.id, "accept", idem)  # reenvio do mesmo comando
    d = act(c, sid, p.id, "accept")  # nova tentativa de aceitar
    assert a.status_code == 200 and a.json()["status"] == "accepted"
    assert b.json() == a.json() and b.headers["Idempotent-Replayed"] == "true"
    assert d.status_code == 409 and d.json()["error"]["code"] == "PROPOSAL_NOT_PENDING"

    s = state(c, sid)
    assert s.completed_trades == 1 and s.budget == user.budget + money
    assert len(s.history) == 1 and s.history[0].money == money
    after = {x.club_uid: x for x in squads(c, sid)}
    assert other.players[0].unique_id in {p.unique_id for p in after[user.club_uid].players}
    assert user.players[0].unique_id in {p.unique_id for p in after[other.club_uid].players}
    assert all(len(x.players) == 18 for x in after.values())
    assert after[other.club_uid].budget == other.budget - money


def test_expiration_reconnection_and_market_end(env):
    c, clock, sid = env
    start(c, sid)
    user, other = first_pair(c, sid)
    engine = c.app.state.container.trading.get(sid)
    p = engine.propose(other.club_uid, user.club_uid, other.players[0].unique_id, user.players[0].unique_id, 0, "x")
    clock.advance(12)  # "desconectado": ninguém consultou durante 12 s
    s = state(c, sid)
    assert s.incoming == [] and s.recent_decisions[0].status == "expired"
    assert s.remaining_ms == 168_000
    r = act(c, sid, p.id, "accept")
    assert r.status_code == 409 and r.json()["error"]["code"] == "PROPOSAL_NOT_PENDING"
    clock.advance(170)
    s = state(c, sid)
    assert s.phase == "finished" and s.remaining_ms == 0
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "competition"
    r = propose(c, sid, other.club_uid, user.players[1].unique_id, other.players[1].unique_id)
    assert r.status_code == 409 and r.json()["error"]["code"] == "MARKET_NOT_RUNNING"


def test_hidden_information_and_privacy_of_proposals(env):
    c, clock, sid = env
    start(c, sid)
    engine = c.app.state.container.trading.get(sid)
    bots = [u for u in engine.clubs if u != engine.user_club_uid]
    engine.propose(bots[0], bots[1], engine.clubs[bots[0]].contracts[0].player_id,
                   engine.clubs[bots[1]].contracts[0].player_id, 0, "bot-bot")
    raw = c.get(f"/api/sessions/{sid}/trading").text
    data = json.loads(raw)
    assert data["incoming"] == [] and data["outgoing"] is None  # proposta entre bots não aparece
    assert not any(w in raw for w in ("overall", "attributes", "market_value", "personality"))


def test_closing_the_session_discards_the_market(env):
    c, _, sid = env
    start(c, sid)
    c.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()})
    r = c.get(f"/api/sessions/{sid}/trading")
    assert r.status_code == 404 and r.json()["error"]["code"] == "MARKET_NOT_FOUND"


def test_websocket_events_from_server_clock(tmp_path):
    app, clock, settings = boot(tmp_path, FakeAuctionModel(), ticker=True, tick=0.01)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        finish_auction(c, clock, sid)
        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            assert ws.receive_json()["type"] == "session.snapshot"
            start(c, sid)
            types = []
            while "trading.started" not in types:
                types.append(ws.receive_json()["type"])
            clock.advance(181)
            while "trading.finished" not in types:
                msg = ws.receive_json()
                types.append(msg["type"])
                assert "money" not in json.dumps(msg)
        assert c.get(f"/api/sessions/{sid}").json()["phase"] == "competition"
