"""Homologação (Entrega 9): cenários adversos de concorrência, isolamento, persistência, reconexão e entradas."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, post_import, set_divisions
from squadforce_shared.contracts import SeasonStateOut
from test_auction_api import big_squad
from test_season_api import boot, to_competition


def db_fingerprint(path) -> str:
    """Conteúdo lógico do SQLite (todas as tabelas, ordenadas) — independe de metadados do arquivo."""
    con = sqlite3.connect(path)
    try:
        h = hashlib.sha256()
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        for t in tables:
            h.update(t.encode())
            for row in con.execute(f'SELECT * FROM "{t}" ORDER BY 1'):
                h.update(repr(row).encode())
        return h.hexdigest()
    finally:
        con.close()


@pytest.fixture
def env(tmp_path):
    app, clock, settings = boot(tmp_path)
    with TestClient(app) as c:
        set_divisions(settings, TEST_DIVISIONS)
        rows = big_squad()
        post_import(c, "clubs", build_xlsx(rows))
        post_import(c, "players", build_xlsx(rows))
        sid = create_session(c, format="league", num_clubs=4, league_rounds="single").json()["id"]
        yield c, clock, settings, sid


def post(c, sid, path, body=None, idem=None):
    return c.post(f"/api/sessions/{sid}/season/{path}", json=body or {}, headers={"Idempotency-Key": idem or key()})


def test_no_persistence_of_competition_in_sqlite(env):
    """GDD §23: progresso só em memória. A base SQLite não muda durante leilão, mercado e temporada inteira."""
    c, clock, settings, sid = env
    before = db_fingerprint(settings.db_path)
    tables_before = {r[0] for r in sqlite3.connect(settings.db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    to_competition(c, clock, sid)
    post(c, sid, "start")
    while True:
        s = SeasonStateOut.model_validate(post(c, sid, "play").json())
        s = SeasonStateOut.model_validate(post(c, sid, "advance").json())
        if s.phase == "finished":
            break
    assert db_fingerprint(settings.db_path) == before
    tables_after = {r[0] for r in sqlite3.connect(settings.db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert tables_after == tables_before
    assert not any(k in t for t in tables_after for k in ("season", "match", "auction", "trade", "session"))


def test_concurrent_play_requests_consolidate_once(env):
    """Retransmissões e cliques simultâneos (chaves diferentes): uma única consolidação, demais recusadas."""
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    post(c, sid, "start")
    barrier = threading.Barrier(6)

    def fire(_):
        barrier.wait()
        return post(c, sid, "play").status_code

    with ThreadPoolExecutor(6) as ex:
        codes = list(ex.map(fire, range(6)))
    assert codes.count(200) == 1, codes
    assert all(code in (200, 409) for code in codes), codes
    season = c.app.state.container.seasons.get(sid)
    assert len(season.state.history) == 2
    assert sum(r.played for r in season.standings()) == 4


def test_same_key_retransmission_is_replayed_not_reexecuted(env):
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    post(c, sid, "start")
    k = key()
    first = post(c, sid, "play", idem=k)
    again = post(c, sid, "play", idem=k)
    assert first.status_code == again.status_code == 200
    assert again.headers.get("Idempotent-Replayed") == "true"
    assert first.json() == again.json()
    assert len(c.app.state.container.seasons.get(sid).state.history) == 2


def test_replaced_session_is_isolated(env):
    """Após substituir a sessão, a anterior não aceita comandos e seu estado em memória é descartado."""
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    post(c, sid, "start")
    new = create_session(c, format="cup", num_clubs=2, league_rounds=None, confirm_replace=True).json()
    assert new["id"] != sid
    assert c.get(f"/api/sessions/{sid}").json()["status"] == "closed"
    r = post(c, sid, "play")
    assert r.status_code == 404 and r.json()["error"]["code"] == "SEASON_NOT_FOUND"
    r = c.post(f"/api/sessions/{sid}/trading/proposals", json={"recipient_club_uid": 1, "offered_player_id": 1, "requested_player_id": 2},
               headers={"Idempotency-Key": key()})
    assert r.status_code in (404, 409)
    assert c.app.state.container.trading.get(sid) is None and c.app.state.container.auctions.get(sid) is None


@pytest.mark.parametrize("body", [
    {"formation": "4-3-3", "starters": [1] * 11, "bench": [], "posture": "xyz"},
    {"formation": "4-3-3", "starters": list(range(12)), "bench": []},
    {"formation": "4-3-3", "starters": list(range(11)), "bench": list(range(100, 108))},
    {"formation": 433, "starters": "abc"},
    {"formation": "4-3-3", "starters": list(range(11)), "extra": 1},
])
def test_lineup_input_validation(env, body):
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    post(c, sid, "start")
    r = post(c, sid, "lineup", body)
    assert r.status_code == 422 and r.json()["error"]["code"] in ("VALIDATION_ERROR", "INVALID_LINEUP")


def test_post_without_idempotency_key_is_rejected(env):
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    r = c.post(f"/api/sessions/{sid}/season/start")
    assert r.status_code in (400, 422) and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_websocket_reconnection_during_competition(env):
    """Reconexão no meio da temporada: o canal volta com o estado atual e eventos season.* chegam."""
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
        assert ws.receive_json()["type"] == "session.snapshot"
        post(c, sid, "start")
        assert ws.receive_json()["type"] == "season.started"
    # desconectado: a rodada é processada mesmo assim (o servidor não depende do cliente)
    post(c, sid, "play")
    with c.websocket_connect(f"/ws/sessions/{sid}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "session.snapshot" and snap["data"]["phase"] == "competition"
        post(c, sid, "advance")
        assert ws.receive_json()["type"] == "season.advanced"
    s = SeasonStateOut.model_validate(c.get(f"/api/sessions/{sid}/season").json())
    assert s.round_number == 2 and s.phase == "ready"


def test_imports_blocked_during_competition(env):
    c, clock, _, sid = env
    to_competition(c, clock, sid)
    post(c, sid, "start")
    r = post_import(c, "players", build_xlsx(big_squad()))
    assert r.status_code == 409 and r.json()["error"]["code"] == "IMPORT_BLOCKED_ACTIVE_COMPETITION"
