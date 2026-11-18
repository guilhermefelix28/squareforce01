"""Sessões via API: criação, consulta, encerramento, rejeições e duplicidade."""

import pytest

from conftest import create_session, key


def test_create_get_and_close(loaded_client):
    r = create_session(loaded_client)
    assert r.status_code == 201
    s = r.json()
    assert s["status"] == "active" and s["phase"] == "setup" and s["version"] == 1
    assert s["config"] == {"format": "league", "num_clubs": 4, "user_club_uid": 100, "league_rounds": "single"}
    assert s["participants"] is None

    got = loaded_client.get(f"/api/sessions/{s['id']}")
    assert got.status_code == 200 and got.json() == s
    assert loaded_client.get("/api/health").json()["active_session"] is True

    closed = loaded_client.post(f"/api/sessions/{s['id']}/close", headers={"Idempotency-Key": key()})
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed" and closed.json()["version"] == 2
    assert loaded_client.get(f"/api/sessions/{s['id']}").json()["status"] == "closed"
    assert loaded_client.get("/api/health").json()["active_session"] is False


def test_cup_session(loaded_client):
    r = create_session(loaded_client, format="cup", num_clubs=4, league_rounds=None)
    assert r.status_code == 201 and r.json()["config"]["format"] == "cup"


@pytest.mark.parametrize(
    "cfg,code",
    [
        ({"num_clubs": 1}, "INVALID_COMPETITION_CONFIG"),
        ({"num_clubs": 21}, "INVALID_COMPETITION_CONFIG"),
        ({"num_clubs": 5}, "INVALID_COMPETITION_CONFIG"),  # só 4 clubes importados
        ({"league_rounds": None}, "INVALID_COMPETITION_CONFIG"),
        ({"format": "cup", "num_clubs": 3, "league_rounds": None}, "INVALID_COMPETITION_CONFIG"),
        ({"user_club_uid": 999}, "CLUB_NOT_FOUND"),
        ({"format": "torneio"}, "VALIDATION_ERROR"),
        ({"num_clubs": "quatro"}, "VALIDATION_ERROR"),
        ({"league_rounds": "triple"}, "VALIDATION_ERROR"),
        ({"extra": 1}, "VALIDATION_ERROR"),
    ],
)
def test_invalid_configs_are_rejected_without_creating_session(loaded_client, cfg, code):
    r = create_session(loaded_client, **cfg)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == code
    assert set(r.json()["error"]) == {"code", "message", "retryable", "details"}
    assert loaded_client.get("/api/health").json()["active_session"] is False


def test_session_requires_catalog(client):
    r = create_session(client)
    assert r.status_code == 409 and r.json()["error"]["code"] == "CATALOG_EMPTY"


def test_second_session_requires_confirmation(loaded_client):
    first = create_session(loaded_client).json()
    r = create_session(loaded_client)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "SESSION_ALREADY_ACTIVE"
    assert r.json()["error"]["details"]["active_session_id"] == first["id"]

    second = create_session(loaded_client, confirm_replace=True)
    assert second.status_code == 201 and second.json()["id"] != first["id"]
    assert loaded_client.get(f"/api/sessions/{first['id']}").json()["status"] == "closed"


def test_duplicate_create_command_returns_same_session(loaded_client):
    idem = key()
    a = create_session(loaded_client, idem=idem)
    b = create_session(loaded_client, idem=idem)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    assert b.headers["Idempotent-Replayed"] == "true"
    # nenhuma segunda sessão foi criada: a ativa é a mesma
    assert loaded_client.get(f"/api/sessions/{a.json()['id']}").json()["status"] == "active"


def test_duplicate_close_command_is_safe(loaded_client):
    sid = create_session(loaded_client).json()["id"]
    idem = key()
    a = loaded_client.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": idem})
    b = loaded_client.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": idem})
    assert a.json() == b.json() and a.json()["version"] == 2
    # nova chave sobre sessão já encerrada também não altera a versão
    c = loaded_client.post(f"/api/sessions/{sid}/close", headers={"Idempotency-Key": key()})
    assert c.status_code == 200 and c.json()["version"] == 2


def test_close_with_version_conflict(loaded_client):
    sid = create_session(loaded_client).json()["id"]
    r = loaded_client.post(
        f"/api/sessions/{sid}/close", json={"expected_version": 9}, headers={"Idempotency-Key": key()}
    )
    assert r.status_code == 409
    assert r.json()["error"] == {
        "code": "VERSION_CONFLICT",
        "message": r.json()["error"]["message"],
        "retryable": True,
        "details": {"expected_version": 9, "current_version": 1},
    }
    assert loaded_client.get(f"/api/sessions/{sid}").json()["status"] == "active"
    ok = loaded_client.post(
        f"/api/sessions/{sid}/close", json={"expected_version": 1}, headers={"Idempotency-Key": key()}
    )
    assert ok.status_code == 200


def test_unknown_session(loaded_client):
    r = loaded_client.get("/api/sessions/inexistente")
    assert r.status_code == 404 and r.json()["error"]["code"] == "SESSION_NOT_FOUND"
    r = loaded_client.post("/api/sessions/inexistente/close", headers={"Idempotency-Key": key()})
    assert r.status_code == 404


def test_commands_require_idempotency_key(loaded_client):
    r = loaded_client.post("/api/sessions", json={"format": "league", "num_clubs": 2, "user_club_uid": 100,
                                                  "league_rounds": "single"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert loaded_client.get("/api/health").json()["active_session"] is False


def test_state_is_memory_only_and_lost_on_restart(loaded_client, settings):
    """Novo processo (nova app) com o mesmo banco não conhece a sessão: não há persistência."""
    from fastapi.testclient import TestClient

    from services.gateway.app import create_app

    sid = create_session(loaded_client).json()["id"]
    with TestClient(create_app(settings)) as restarted:
        r = restarted.get(f"/api/sessions/{sid}")
        assert r.status_code == 404
        assert "não pode ser restaurada" in r.json()["error"]["message"]
        assert restarted.get("/api/catalog/clubs").json()["total"] == 4  # base SQLite permanece
