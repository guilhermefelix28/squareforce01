"""Fixtures comuns. Todos os testes usam bancos SQLite temporários — nunca database/squadforce.db."""

from __future__ import annotations

import io
import sqlite3
import uuid
from pathlib import Path
from typing import Any

import openpyxl
import pytest
from fastapi.testclient import TestClient

import services  # noqa: F401
from services.data import importer
from services.gateway.app import create_app
from services.gateway.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
REAL_PLAYERS_XLSX = ROOT / "Dados" / "jogadores.xlsx"

PLAYER_HEADER = (
    list(importer.PLAYER_IDENTITY_COLUMNS[:10])
    + ["club_name", "club_short_name", "club_nation_id", "club_reputation"]
    + list(importer.PLAYER_IDENTITY_COLUMNS[10:])
    + list(importer.ALL_ATTRIBUTE_COLUMNS)
    + list(importer.FAMILIARITY_COLUMNS)
)

CLUBS = {
    100: ("Clube Alfa FC", "Alfa", 189, 7000),
    200: ("Beta Esporte Clube", "Beta", 189, 6500),
    300: ("Gama Futebol Clube", "Gama", 189, 6000),
    400: ("Delta Atlético", "Delta", 189, 5500),
}


def club_row(uid: int) -> dict[str, Any]:
    name, short, nation, rep = CLUBS.get(uid, (f"Clube {uid}", f"C{uid}", 189, 5000))
    return {"club_uid": uid, "club_name": name, "club_short_name": short, "club_nation_id": nation, "club_reputation": rep}


def player_row(uid: int | None, club_uid: int = 100, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "unique_id": uid,
        "name": f"Jogador {uid}",
        "first_name": "Jogador",
        "last_name": str(uid),
        "full_name": f"Jogador Teste {uid}",
        "birth_date": "2000-01-15",
        "age": 25,
        "nation_id": 189,
        "height_cm": 180,
        "club_join_date": "2024-01-01",
        "natural_positions": "STC",
        "accomplished_positions": "MC",
        **club_row(club_uid),
    }
    for c in importer.ALL_ATTRIBUTE_COLUMNS:
        row[c] = 60
    for c in importer.FAMILIARITY_COLUMNS:
        row[c] = 1
    row["positions_stc"] = 100
    row["positions_mc"] = 70
    row.update(overrides)
    return row


def build_xlsx(rows: list[dict[str, Any]], header: list[str] | None = None, sheet: str = "Jogadores") -> bytes:
    header = header or PLAYER_HEADER
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append([r.get(h) for h in header])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def squad(n_per_club: int = 3, clubs: tuple[int, ...] = (100, 200, 300, 400)) -> list[dict[str, Any]]:
    rows, uid = [], 1000
    for c in clubs:
        for _ in range(n_per_club):
            uid += 1
            rows.append(player_row(uid, c))
    return rows


def key() -> str:
    return f"test-{uuid.uuid4().hex}"


def post_import(client: TestClient, base: str, content: bytes, idem: str | None = None, name: str = "base.xlsx"):
    headers = {"Idempotency-Key": idem or key()}
    return client.post(f"/api/imports/{base}", files={"file": (name, content)}, headers=headers)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    graphics = tmp_path / "Graphics"
    (graphics / "Clubes").mkdir(parents=True)
    (graphics / "Faces").mkdir(parents=True)
    return Settings(db_path=tmp_path / "test.db", graphics_dir=graphics)


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


TEST_DIVISIONS = {100: "A", 200: "A", 300: "B", 400: "B"}


def set_divisions(settings: Settings, divisions: dict[int, str]) -> None:
    """Divisões de referência para os clubes fictícios dos testes (a migração só traz os 40 reais)."""
    with sqlite3.connect(settings.db_path) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO club_divisions (club_uid, division, season, label) VALUES (?, ?, 2026, 'teste')",
            list(divisions.items()),
        )


@pytest.fixture
def loaded_client(client: TestClient, settings: Settings) -> TestClient:
    """Cliente com 4 clubes (2 da Série A, 2 da B) e 12 jogadores importados."""
    set_divisions(settings, TEST_DIVISIONS)
    rows = squad()
    assert post_import(client, "clubs", build_xlsx(rows)).status_code == 200
    assert post_import(client, "players", build_xlsx(rows)).status_code == 200
    return client


def create_session(client: TestClient, idem: str | None = None, **cfg: Any):
    body = {"format": "league", "num_clubs": 4, "user_club_uid": 100, "league_rounds": "single", **cfg}
    return client.post("/api/sessions", json=body, headers={"Idempotency-Key": idem or key()})
