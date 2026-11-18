"""API de competição (Entrega 2): GET /api/sessions/{id}/competition, divisões e elegibilidade."""

import pytest

from conftest import REAL_PLAYERS_XLSX, create_session, key, post_import, set_divisions
from squadforce_shared.contracts import CompetitionOut


def competition(client, sid):
    r = client.get(f"/api/sessions/{sid}/competition")
    assert r.status_code == 200, r.json()
    return CompetitionOut.model_validate(r.json())


def test_league_structure_is_exposed(loaded_client):
    s = create_session(loaded_client, num_clubs=4, league_rounds="double").json()
    c = competition(loaded_client, s["id"])
    st = c.structure
    assert c.session_id == s["id"] and c.version == s["version"] and c.user_club_uid == 100
    assert st.kind == "league" and st.participants == s["participants"]
    assert st.total_rounds == 6 and st.total_matches == 12 and st.matches_per_club == 6
    assert all(r.bye_club_uid is None for r in st.rounds)


def test_odd_league_has_byes(loaded_client):
    s = create_session(loaded_client, num_clubs=3, league_rounds="single").json()
    st = competition(loaded_client, s["id"]).structure
    assert st.total_rounds == 3 and st.total_matches == 3
    assert sorted(r.bye_club_uid for r in st.rounds) == sorted(s["participants"])


def test_league_prioritizes_serie_a_with_test_clubs(loaded_client):
    # 100 e 200 = Série A; 300 e 400 = Série B. Usuário 400 com 3 clubes => 100 e 200.
    s = create_session(loaded_client, num_clubs=3, user_club_uid=400).json()
    assert s["participants"][0] == 400 and sorted(s["participants"][1:]) == [100, 200]


def test_cup_structure_is_exposed(loaded_client):
    s = create_session(loaded_client, format="cup", num_clubs=4, league_rounds=None).json()
    st = competition(loaded_client, s["id"]).structure
    assert st.kind == "cup" and st.total_rounds == 2 and st.total_matches == 3
    assert [r.name for r in st.rounds] == ["Semifinal", "Final"]
    assert st.rules.extra_time is False and st.rules.draw_decided_by == "penalties"
    assert st.champion_club_uid is None


def test_competition_of_unknown_session(loaded_client):
    r = loaded_client.get("/api/sessions/nao-existe/competition")
    assert r.status_code == 404 and r.json()["error"]["code"] == "SESSION_NOT_FOUND"


def test_competition_remains_readable_after_close(loaded_client):
    sid = create_session(loaded_client).json()["id"]
    before = competition(loaded_client, sid).structure
    loaded_client.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()})
    after = competition(loaded_client, sid)
    assert after.version == 2 and after.structure == before


def test_duplicate_create_returns_same_draw(loaded_client):
    idem = key()
    a = create_session(loaded_client, idem=idem, format="cup", num_clubs=4, league_rounds=None).json()
    b = create_session(loaded_client, idem=idem, format="cup", num_clubs=4, league_rounds=None).json()
    assert a == b
    assert competition(loaded_client, a["id"]).structure.participants == a["participants"]


def test_club_without_division_is_not_eligible(client, settings):
    from conftest import build_xlsx, squad

    set_divisions(settings, {100: "A", 200: "A", 300: "B"})  # 400 sem divisão
    rows = squad()
    clubs = post_import(client, "clubs", build_xlsx(rows)).json()
    assert [w["code"] for w in clubs["warnings"]] == ["CLUB_WITHOUT_DIVISION"]
    post_import(client, "players", build_xlsx(rows))
    r = create_session(client, user_club_uid=400, num_clubs=2)
    assert r.status_code == 422 and r.json()["error"]["code"] == "CLUB_NOT_ELIGIBLE"
    r = create_session(client, num_clubs=4)  # só 3 elegíveis
    assert r.status_code == 422 and "3 clubes elegíveis" in r.json()["error"]["message"]
    opts = client.get("/api/competitions/options").json()
    assert opts["available_clubs"] == 4 and opts["eligible_clubs"] == 3
    assert opts["division_counts"] == {"A": 2, "B": 1}
    divisions = {c["club_uid"]: c["division"] for c in client.get("/api/catalog/clubs").json()["items"]}
    assert divisions == {100: "A", 200: "A", 300: "B", 400: None}


# ------------------------------------------------------------------ base real (somente leitura)
real = pytest.mark.skipif(not REAL_PLAYERS_XLSX.exists(), reason="Dados/jogadores.xlsx ausente")


@pytest.fixture
def real_client(client):
    content = REAL_PLAYERS_XLSX.read_bytes()
    post_import(client, "clubs", content)
    post_import(client, "players", content)
    return client


def _divisions(client):
    return {c["club_uid"]: c["division"] for c in client.get("/api/catalog/clubs").json()["items"]}


@real
@pytest.mark.real_data
def test_real_league_of_20_with_serie_b_user(real_client):
    div = _divisions(real_client)
    goias = 102496
    assert div[goias] == "B"
    s = create_session(real_client, num_clubs=20, user_club_uid=goias, league_rounds="double").json()
    assert s["participants"][0] == goias
    assert sorted(div[c] for c in s["participants"][1:]) == ["A"] * 19
    st = competition(real_client, s["id"]).structure
    assert st.total_rounds == 38 and st.total_matches == 380


@real
@pytest.mark.real_data
def test_real_league_of_20_with_serie_a_user_is_the_whole_serie_a(real_client):
    div = _divisions(real_client)
    s = create_session(real_client, num_clubs=20, user_club_uid=322, league_rounds="single").json()
    assert sorted(s["participants"]) == sorted(c for c, d in div.items() if d == "A")


@real
@pytest.mark.real_data
def test_real_cup_of_32(real_client):
    s = create_session(real_client, format="cup", num_clubs=32, user_club_uid=900205, league_rounds=None).json()
    assert s["participants"][0] == 900205 and len(set(s["participants"])) == 32
    st = competition(real_client, s["id"]).structure
    assert [r.name for r in st.rounds] == [
        "Dezesseis-avos de final", "Oitavas de final", "Quartas de final", "Semifinal", "Final",
    ]
