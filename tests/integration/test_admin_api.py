"""Área oculta de dados (decisão do responsável DR-04): importações só com senha verificada no servidor."""

import sqlite3

from conftest import admin_token, build_xlsx, key, squad
from services.gateway.settings import Settings


def count(settings, table):
    with sqlite3.connect(settings.db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def login(client, password, idem=None):
    return client.post("/api/admin/login", json={"password": password}, headers={"Idempotency-Key": idem or key()})


def upload(client, token=None):
    headers = {"Idempotency-Key": key()}
    if token is not None:
        headers["X-Admin-Token"] = token
    return client.post("/api/imports/clubs", files={"file": ("a.xlsx", build_xlsx(squad(1)))}, headers=headers)


def test_default_password_is_9153_and_wrong_password_fails(client):
    assert Settings().admin_password == "9153"
    bad = login(client, "0000")
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "ADMIN_AUTH_FAILED"
    ok = login(client, "9153")
    assert ok.status_code == 200 and len(ok.json()["token"]) >= 32


def test_import_without_valid_token_is_rejected_and_changes_nothing(client, settings):
    before = count(settings, "clubs")
    for token in (None, "", "token-falso"):
        r = upload(client, token)
        assert r.status_code == 401 and r.json()["error"]["code"] == "ADMIN_AUTH_FAILED"
    assert count(settings, "clubs") == before


def test_import_with_token_works(client, settings):
    r = upload(client, admin_token(client))
    assert r.status_code == 200, r.json()
    assert count(settings, "clubs") > 0


def test_password_comes_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("SQUADFORCE_ADMIN_PASSWORD", "outra")
    assert Settings(db_path=tmp_path / "x.db").admin_password == "outra"
