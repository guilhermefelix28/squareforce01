"""Tática do usuário antes do leilão (decisão do responsável DR-02, 2026-11-19)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIVISIONS, build_xlsx, create_session, key, post_import, set_divisions
from squadforce_shared.contracts import LineupOut, SessionOut
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
        yield c, clock, sid


def choose(c, sid, formation, idem=None):
    return c.post(f"/api/sessions/{sid}/formation", json={"formation": formation},
                  headers={"Idempotency-Key": idem or key()})


def test_formation_is_chosen_in_setup_and_used_by_the_automatic_lineup(env):
    c, clock, sid = env
    assert SessionOut.model_validate(c.get(f"/api/sessions/{sid}").json()).user_formation is None
    idem = key()
    r = choose(c, sid, "3-5-2", idem)
    assert r.status_code == 200, r.json()
    out = SessionOut.model_validate(r.json())
    assert out.user_formation == "3-5-2"
    assert choose(c, sid, "3-5-2", idem).json() == r.json()  # idempotente
    assert choose(c, sid, "4-1-2-3").json()["user_formation"] == "4-1-2-3"  # pode trocar enquanto em setup
    assert choose(c, sid, "3-5-2").status_code == 200
    to_competition(c, clock, sid)
    assert c.post(f"/api/sessions/{sid}/season/start", headers={"Idempotency-Key": key()}).status_code == 201
    lu = LineupOut.model_validate(c.get(f"/api/sessions/{sid}/season/lineup").json())
    assert lu.source == "auto" and lu.formation == "3-5-2"


def test_formation_rejected_outside_setup_or_unknown(env):
    c, clock, sid = env
    r = choose(c, sid, "2-4-4")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_FORMATION"
    assert c.post(f"/api/sessions/{sid}/auction/start", headers={"Idempotency-Key": key()}).status_code in (200, 201)
    r = choose(c, sid, "4-2-2-2")
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVALID_PHASE"
    assert choose(c, "nao-existe", "4-2-2-2").status_code == 404


def test_official_formations_are_listed_without_a_season(client):
    r = client.get("/api/formations")
    assert r.status_code == 200
    forms = r.json()
    assert [f["id"] for f in forms][:3] == ["4-2-2-2", "4-1-2-3", "4-2-3-1"] and len(forms) == 11
    assert all(len(f["positions"]) == 11 and f["positions"][0] == "GK" for f in forms)
