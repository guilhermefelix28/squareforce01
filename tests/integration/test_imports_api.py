"""Importações via API, verificando os EFEITOS no banco (não apenas o status HTTP)."""

import sqlite3

import pytest

from conftest import build_xlsx, club_row, create_session, key, player_row, post_import, squad
from services.data import service as data_service


def count(settings, table):
    with sqlite3.connect(settings.db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def player_ids(client):
    return sorted(p["unique_id"] for p in client.get("/api/catalog/players?limit=200").json()["items"])


def test_valid_import_creates_queryable_clubs_and_players(client, settings):
    rows = squad(3)
    r = post_import(client, "clubs", build_xlsx(rows))
    assert r.status_code == 200 and r.json()["rows_imported"] == 4
    r = post_import(client, "players", build_xlsx(rows))
    body = r.json()
    assert r.status_code == 200 and body["status"] == "imported" and body["rows_imported"] == 12

    clubs = client.get("/api/catalog/clubs").json()
    assert clubs["total"] == 4
    assert {c["club_uid"]: c["player_count"] for c in clubs["items"]} == {100: 3, 200: 3, 300: 3, 400: 3}
    assert "reputation" not in clubs["items"][0]  # ranking interno oculto

    players = client.get("/api/catalog/players", params={"club_uid": 200}).json()
    assert players["total"] == 3
    assert players["items"][0]["natural_positions"] == ["STC"]
    assert players["items"][0]["accomplished_positions"] == ["MC"]

    # efeitos reais no SQLite
    assert count(settings, "players") == 12
    assert count(settings, "player_attributes") == 12 * 59
    assert count(settings, "player_positions") == 12 * 7


def test_catalog_filters_by_display_position_and_search(loaded_client):
    by_display = loaded_client.get("/api/catalog/players", params={"position": "ATA"}).json()
    by_internal = loaded_client.get("/api/catalog/players", params={"position": "STC"}).json()
    assert by_display["total"] == by_internal["total"] == 12
    assert loaded_client.get("/api/catalog/players", params={"position": "GOL"}).json()["total"] == 0
    assert loaded_client.get("/api/catalog/players", params={"search": "1001"}).json()["total"] == 1
    bad = loaded_client.get("/api/catalog/players", params={"position": "XX"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "VALIDATION_ERROR"


def test_pagination(loaded_client):
    page = loaded_client.get("/api/catalog/players", params={"limit": 5, "offset": 10}).json()
    assert page["total"] == 12 and len(page["items"]) == 2 and page["offset"] == 10
    assert loaded_client.get("/api/catalog/players", params={"limit": 500}).status_code == 422


def test_reimport_replaces_only_the_players_base(loaded_client, settings):
    before_clubs = loaded_client.get("/api/catalog/clubs").json()
    new_rows = [player_row(9001, 100), player_row(9002, 300)]
    r = post_import(loaded_client, "players", build_xlsx(new_rows))
    assert r.status_code == 200 and r.json()["previous_count"] == 12
    assert player_ids(loaded_client) == [9001, 9002]
    assert loaded_client.get("/api/catalog/clubs").json()["total"] == before_clubs["total"]
    assert count(settings, "player_attributes") == 2 * 59  # dependentes antigos removidos


@pytest.mark.parametrize(
    "bad_rows,code",
    [
        ([player_row(1), player_row(1)], "DUPLICATE_ID"),
        ([player_row(1, age="abc")], "INVALID_TYPE"),
        ([player_row(1, club_uid=777)], "INVALID_RELATIONSHIP"),
        ([player_row(1, natural_positions="QQ")], "INVALID_POSITION"),
    ],
)
def test_invalid_import_preserves_previous_base(loaded_client, settings, bad_rows, code):
    before = player_ids(loaded_client)
    attrs_before = count(settings, "player_attributes")
    r = post_import(loaded_client, "players", build_xlsx(bad_rows))
    err = r.json()["error"]
    assert r.status_code == 422
    assert err["code"] == "IMPORT_VALIDATION_FAILED" and err["retryable"] is False
    assert code in [e["code"] for e in err["details"]["report"]["critical_errors"]]
    assert player_ids(loaded_client) == before
    assert count(settings, "player_attributes") == attrs_before


def test_failure_during_write_rolls_back_completely(loaded_client, settings, monkeypatch):
    """Falha no meio da gravação (após o DELETE e inserções parciais) -> rollback integral."""
    before = player_ids(loaded_client)
    original = data_service._insert_players

    def broken(conn, players):
        original(conn, players[:1])  # grava parcialmente
        raise sqlite3.OperationalError("disco cheio (simulado)")

    monkeypatch.setattr(data_service, "_insert_players", broken)
    r = post_import(loaded_client, "players", build_xlsx([player_row(5001), player_row(5002)]))
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "IMPORT_FAILED" and r.json()["error"]["retryable"] is True
    assert player_ids(loaded_client) == before
    assert count(settings, "player_attributes") == len(before) * 59


def test_clubs_failure_during_write_rolls_back(loaded_client, monkeypatch):
    before = loaded_client.get("/api/catalog/clubs").json()

    def broken(conn, clubs):
        conn.execute("UPDATE clubs SET name = 'CORROMPIDO'")
        raise sqlite3.OperationalError("falha simulada")

    monkeypatch.setattr(data_service, "_upsert_clubs", broken)
    rows = [player_row(1, c) for c in (100, 200, 300, 400)]
    r = post_import(loaded_client, "clubs", build_xlsx(rows))
    assert r.status_code == 500
    assert loaded_client.get("/api/catalog/clubs").json() == before


def test_clubs_reimport_cannot_orphan_players(loaded_client):
    rows = [player_row(1, 100), player_row(2, 200)]  # remove 300 e 400, ainda usados
    r = post_import(loaded_client, "clubs", build_xlsx(rows))
    assert r.status_code == 422
    report = r.json()["error"]["details"]["report"]
    assert {e["code"] for e in report["critical_errors"]} == {"INVALID_RELATIONSHIP"}
    assert loaded_client.get("/api/catalog/clubs").json()["total"] == 4


def test_clubs_reimport_updates_and_adds(loaded_client):
    rows = [player_row(i, c) for i, c in enumerate((100, 200, 300, 400), 1)]
    rows[0]["club_short_name"] = "Alfa Novo"
    rows.append({**player_row(99), "club_uid": 500, "club_name": "Novo", "club_short_name": "Novo",
                 "club_nation_id": 189, "club_reputation": 1})
    r = post_import(loaded_client, "clubs", build_xlsx(rows))
    assert r.status_code == 200
    names = {c["club_uid"]: c["short_name"] for c in loaded_client.get("/api/catalog/clubs").json()["items"]}
    assert names[100] == "Alfa Novo" and names[500] == "Novo" and len(names) == 5


def test_players_import_without_clubs_is_rejected(client):
    r = post_import(client, "players", build_xlsx(squad(1)))
    assert r.status_code == 422
    assert r.json()["error"]["details"]["report"]["critical_errors"][0]["code"] == "CLUBS_NOT_IMPORTED"


def test_dedicated_clubs_sheet_is_supported(client):
    header = ["club_uid", "club_name", "club_short_name", "club_nation_id", "club_reputation"]
    content = build_xlsx([club_row(100), club_row(200)], header=header, sheet="Clubes")
    r = post_import(client, "clubs", content)
    assert r.status_code == 200 and r.json()["sheet"] == "Clubes" and r.json()["rows_imported"] == 2


def test_unsupported_and_corrupted_files(client):
    r = post_import(client, "clubs", b"a;b;c", name="clubes.csv")
    assert r.status_code == 415 and r.json()["error"]["code"] == "UNSUPPORTED_FILE"
    r = post_import(client, "players", b"PK\x03\x04lixo", name="jogadores.xlsx")
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_WORKBOOK"


def test_upload_size_limit(settings):
    from fastapi.testclient import TestClient

    from services.gateway.app import create_app
    from services.gateway.settings import Settings

    small = Settings(db_path=settings.db_path, graphics_dir=settings.graphics_dir, max_upload_mb=0)
    with TestClient(create_app(small)) as c:
        r = post_import(c, "clubs", build_xlsx(squad(1)))
    assert r.status_code == 413 and r.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_imports_blocked_while_competition_active(loaded_client, settings):
    sid = create_session(loaded_client).json()["id"]
    before = player_ids(loaded_client)
    for base in ("clubs", "players"):
        r = post_import(loaded_client, base, build_xlsx([player_row(1)]))
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "IMPORT_BLOCKED_ACTIVE_COMPETITION"
        assert r.json()["error"]["details"]["active_session_id"] == sid
    assert player_ids(loaded_client) == before
    assert loaded_client.get("/api/competitions/options").json()["imports_blocked"] is True

    loaded_client.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()})
    r = post_import(loaded_client, "players", build_xlsx([player_row(1)]))
    assert r.status_code == 200  # liberado após o encerramento


def test_duplicate_import_command_is_replayed_not_reexecuted(loaded_client, monkeypatch):
    idem = key()
    content = build_xlsx([player_row(7001), player_row(7002)])
    first = post_import(loaded_client, "players", content, idem)
    assert first.headers["Idempotent-Replayed"] == "false"

    calls = []
    monkeypatch.setattr(data_service, "_insert_players", lambda *a: calls.append(a))
    second = post_import(loaded_client, "players", content, idem)
    assert second.status_code == 200 and second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert calls == []  # não regravou

    other = post_import(loaded_client, "players", build_xlsx([player_row(1)]), idem)
    assert other.status_code == 409 and other.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_import_requires_idempotency_key(client):
    r = client.post("/api/imports/clubs", files={"file": ("a.xlsx", build_xlsx(squad(1)))})
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
