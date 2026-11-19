"""API do leilão (Entrega 3): bloqueio sem fórmulas, fases, lances, sigilo, idempotência, reconexão, resumo, WS."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, player_row, post_import, set_divisions
from services.gateway.app import create_app
from services.gateway.settings import Settings
from squadforce_shared.contracts import AuctionStateOut, AuctionSummaryOut
from squadforce_shared.domain.positions import POSITION_ORDER
from support.auction_fixtures import ManualClock
from support.fake_auction_model import FakeAuctionModel


def big_squad() -> list[dict]:
    """4 clubes × 35 atletas, 20 por posição, com atributos variados."""
    rows, uid = [], 5000
    clubs = list(TEST_DIVISIONS)
    for i, pos in enumerate(POSITION_ORDER * 20):
        uid += 1
        r = player_row(uid, clubs[i % 4], natural_positions=pos.value, accomplished_positions=None)
        for k in list(r):
            if k.startswith("attributes_"):
                r[k] = 30 + (uid * 7 + len(k)) % 60
        r[f"positions_{pos.value.lower()}"] = 100
        rows.append(r)
    return rows


def make_client(tmp_path, model, ticker=False, tick=0.1):
    clock = ManualClock()
    graphics = tmp_path / "Graphics"
    (graphics / "Faces").mkdir(parents=True)
    settings = Settings(db_path=tmp_path / "auction.db", graphics_dir=graphics, auction_ticker=ticker, auction_tick_seconds=tick)
    app = create_app(settings, clock=clock, auction_model=model)
    return app, clock, settings


@pytest.fixture
def env(tmp_path):
    app, clock, settings = make_client(tmp_path, FakeAuctionModel())
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        assert post_import(c, "clubs", build_xlsx(rows)).status_code == 200
        assert post_import(c, "players", build_xlsx(rows)).status_code == 200
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        yield c, clock, sid, app


def start(c, sid, idem=None):
    return c.post(f"/api/sessions/{sid}/auction/start", headers={"Idempotency-Key": idem or key()})


def state(c, sid) -> AuctionStateOut:
    r = c.get(f"/api/sessions/{sid}/auction")
    assert r.status_code == 200, r.json()
    return AuctionStateOut.model_validate(r.json())


def bid(c, sid, player_id, amount, round_number=None, idem=None):
    body = {"player_id": player_id, "amount": amount}
    if round_number is not None:
        body["round_number"] = round_number
    return c.post(f"/api/sessions/{sid}/auction/bids", json=body, headers={"Idempotency-Key": idem or key()})


# ------------------------------------------------------------------ modelo desligado / modelo oficial
def test_auction_is_blocked_when_model_is_disabled(tmp_path):
    app, _, settings = make_client(tmp_path, None)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        assert post_import(c, "clubs", build_xlsx(rows)).status_code == 200
        assert post_import(c, "players", build_xlsx(rows)).status_code == 200
        sid = create_session(c).json()["id"]
        r = start(c, sid)
        assert r.status_code == 409 and r.json()["error"]["code"] == "AUCTION_MODEL_NOT_CONFIGURED"
        assert c.get(f"/api/sessions/{sid}").json()["phase"] == "setup"  # nada mudou
        assert c.get("/api/health").json()["services"]["auction"] == "planned"


def test_official_model_is_loaded_by_default_and_runs_the_auction(tmp_path, monkeypatch):
    monkeypatch.delenv("SQUADFORCE_AUCTION_MODEL", raising=False)
    clock = ManualClock()
    graphics = tmp_path / "Graphics"
    (graphics / "Faces").mkdir(parents=True)
    settings = Settings(db_path=tmp_path / "official.db", graphics_dir=graphics, auction_ticker=False)
    with TestClient(create_app(settings, clock=clock)) as c:  # sem auction_model: carrega o padrão
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        assert post_import(c, "clubs", build_xlsx(rows)).status_code == 200
        assert post_import(c, "players", build_xlsx(rows)).status_code == 200
        assert c.get("/api/health").json()["services"]["auction"] == "ready"
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        assert start(c, sid).status_code == 201
        for _ in range(2000):
            clock.advance(1.0)
            if state(c, sid).phase == "completed":
                break
        summary = AuctionSummaryOut.model_validate(c.get(f"/api/sessions/{sid}/auction/summary").json())
        assert len(summary.squads) == 4
        assert all(len(sq.contracts) == 18 and sq.budget >= 0 for sq in summary.squads)


# ------------------------------------------------------------------ ciclo de vida
def test_start_moves_session_to_auction_phase(env):
    c, clock, sid, _ = env
    r = start(c, sid)
    assert r.status_code == 201
    s = AuctionStateOut.model_validate(r.json())
    assert s.phase == "running" and s.round.number == 1 and len(s.round.players) == 5
    assert s.budget == 120_000_000 and s.open_slots == 18
    assert s.max_bid == 120_000_000 - 17 * 500_000
    assert s.global_duration_ms == 600_000 and s.round.remaining_ms == 10_000
    assert s.bid_increments == [100_000, 500_000, 1_000_000]
    session = c.get(f"/api/sessions/{sid}").json()
    assert session["phase"] == "auction" and session["version"] == 2
    assert c.get("/api/health").json()["services"]["auction"] == "ready"


def test_start_is_idempotent_and_cannot_restart(env):
    c, _, sid, _ = env
    idem = key()
    a, b = start(c, sid, idem), start(c, sid, idem)
    assert a.status_code == b.status_code == 201 and b.headers["Idempotent-Replayed"] == "true"
    r = start(c, sid)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_PHASE"


def test_hidden_information_never_leaves_the_server(env):
    c, clock, sid, _ = env
    start(c, sid)
    clock.advance(8)  # bots já deram lances sigilosos
    raw = c.get(f"/api/sessions/{sid}/auction").text
    data = json.loads(raw)
    assert data["active_bid"] is None  # o usuário não deu lance: nenhum lance aparece
    forbidden = ("overall", "attributes", "market_value", "personality", "bids", "reputation")
    assert not any(word in raw for word in forbidden)
    player_keys = set(data["round"]["players"][0])
    assert player_keys == {"unique_id", "name", "age", "club_short_name", "club_uid", "position", "minimum_bid", "has_photo"}


# ------------------------------------------------------------------ lances
def test_bid_flow_errors_and_idempotency(env):
    c, clock, sid, _ = env
    s = AuctionStateOut.model_validate(start(c, sid).json())
    p = s.round.players[0]
    r = bid(c, sid, p.unique_id, p.minimum_bid - 1)
    assert r.status_code == 422 and r.json()["error"]["code"] == "BELOW_MINIMUM_BID"
    assert r.json()["error"]["details"]["minimum_bid"] == p.minimum_bid
    r = bid(c, sid, p.unique_id, s.max_bid + 100_000)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INSUFFICIENT_FUNDS"

    idem = key()
    ok = bid(c, sid, p.unique_id, p.minimum_bid + 1_000_000, s.round.number, idem)
    assert ok.status_code == 200 and ok.json()["amount"] == p.minimum_bid + 1_000_000
    again = bid(c, sid, p.unique_id, p.minimum_bid + 1_000_000, s.round.number, idem)
    assert again.json() == ok.json() and again.headers["Idempotent-Replayed"] == "true"
    other = bid(c, sid, p.unique_id, p.minimum_bid + 2_000_000, s.round.number, idem)
    assert other.status_code == 409 and other.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    same = bid(c, sid, p.unique_id, p.minimum_bid + 1_000_000)
    assert same.status_code == 422 and same.json()["error"]["code"] == "BID_UNCHANGED"
    lower = bid(c, sid, p.unique_id, p.minimum_bid + 500_000)  # redução permitida (decisão do responsável)
    assert lower.status_code == 200 and state(c, sid).active_bid.amount == p.minimum_bid + 500_000

    clock.advance(10)
    late = bid(c, sid, p.unique_id, p.minimum_bid + 3_000_000, s.round.number)
    assert late.status_code == 409 and late.json()["error"]["code"] == "STALE_ROUND"


def cancel(c, sid, round_number=None, idem=None):
    body = {} if round_number is None else {"round_number": round_number}
    return c.post(f"/api/sessions/{sid}/auction/bids/cancel", json=body, headers={"Idempotency-Key": idem or key()})


def test_user_can_cancel_own_bid_until_round_closes(env):
    """DR-07: o usuário pode retirar o próprio lance durante a rodada; sem lance, não compra ninguém."""
    c, clock, sid, _ = env
    s = AuctionStateOut.model_validate(start(c, sid).json())
    p = s.round.players[0]
    r = cancel(c, sid, s.round.number)
    assert r.status_code == 409 and r.json()["error"]["code"] == "NO_ACTIVE_BID"
    assert bid(c, sid, p.unique_id, p.minimum_bid, s.round.number).status_code == 200
    idem = key()
    ok = cancel(c, sid, s.round.number, idem)
    assert ok.status_code == 200, ok.json()
    assert ok.json() == {"round": s.round.number, "player_id": p.unique_id, "amount": p.minimum_bid, "replayed": False}
    again = cancel(c, sid, s.round.number, idem)
    assert again.headers["Idempotent-Replayed"] == "true"
    assert state(c, sid).active_bid is None
    # pode dar outro lance depois de cancelar
    assert bid(c, sid, p.unique_id, p.minimum_bid, s.round.number).status_code == 200
    assert cancel(c, sid, s.round.number).status_code == 200
    clock.advance(10)
    after = state(c, sid)
    assert after.squad == [] and all(sale.club_uid != after.user_club_uid for r in after.recent_results for sale in r.sales)
    late = cancel(c, sid, s.round.number)
    assert late.status_code == 409 and late.json()["error"]["code"] == "STALE_ROUND"


def test_reconnection_sees_authoritative_clock_and_own_bid(env):
    c, clock, sid, _ = env
    s = AuctionStateOut.model_validate(start(c, sid).json())
    p = s.round.players[2]
    bid(c, sid, p.unique_id, p.minimum_bid)
    clock.advance(4)
    again = state(c, sid)  # "reconexão": novo GET após 4 s sem contato
    assert again.round.number == 1 and again.round.remaining_ms == 6_000
    assert again.active_bid.player_id == p.unique_id
    clock.advance(37)  # desconectado por várias rodadas: o relógio não pausa
    later = state(c, sid)
    assert later.round.number == 5 and later.rounds_completed == 4
    assert later.global_remaining_ms == 600_000 - 41_000


def test_full_auction_reaches_summary_with_18_each(env):
    c, clock, sid, _ = env
    start(c, sid)
    r = c.get(f"/api/sessions/{sid}/auction/summary")
    assert r.status_code == 409 and r.json()["error"]["code"] == "AUCTION_NOT_FINISHED"
    for _ in range(61):
        clock.advance(10)
        state(c, sid)
    s = state(c, sid)
    assert s.phase == "completed" and s.finish_reason == "time_up" and s.round is None
    assert c.get(f"/api/sessions/{sid}").json()["phase"] == "squad_completion"
    summary = AuctionSummaryOut.model_validate(c.get(f"/api/sessions/{sid}/auction/summary").json())
    ids = [k.player_id for q in summary.squads for k in q.contracts]
    assert all(len(q.contracts) == 18 and q.budget >= 0 for q in summary.squads)
    assert len(ids) == len(set(ids)) == 72
    assert all(q.spent + q.budget == 120_000_000 for q in summary.squads)
    r = bid(c, sid, ids[0], 1_000_000)
    assert r.status_code == 409 and r.json()["error"]["code"] == "AUCTION_NOT_RUNNING"


def test_closing_the_session_discards_the_auction(env):
    c, _, sid, _ = env
    start(c, sid)
    c.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()})
    r = c.get(f"/api/sessions/{sid}/auction")
    assert r.status_code == 404 and r.json()["error"]["code"] == "AUCTION_NOT_FOUND"


def test_imports_stay_blocked_during_auction(env):
    c, _, sid, _ = env
    start(c, sid)
    r = post_import(c, "players", build_xlsx(big_squad()))
    assert r.status_code == 409 and r.json()["error"]["code"] == "IMPORT_BLOCKED_ACTIVE_COMPETITION"


def test_server_clock_publishes_round_events_over_websocket(tmp_path):
    app, clock, settings = make_client(tmp_path, FakeAuctionModel(), ticker=True, tick=0.01)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="cup", num_clubs=4, league_rounds=None).json()["id"]
        with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
            assert ws.receive_json()["type"] == "session.snapshot"
            start(c, sid)
            assert ws.receive_json()["type"] == "auction.started"
            clock.advance(10.5)
            types = set()
            for _ in range(3):
                msg = ws.receive_json()
                types.add(msg["type"])
                assert "bids" not in json.dumps(msg)
                if {"auction.round_closed", "auction.round_started"} <= types:
                    break
            assert {"auction.round_closed", "auction.round_started"} <= types
