"""Migrações e restrições de integridade do SQLite."""

import sqlite3

import pytest

from services.data import importer
from services.data.db import apply_migrations, connect


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "schema.db"
    assert apply_migrations(path) == 2
    conn = connect(path)
    yield path, conn
    conn.close()


def test_migrations_are_idempotent(db):
    path, conn = db
    assert apply_migrations(path) == 2
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2


def test_expected_tables_and_indexes(db):
    _, conn = db
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    assert {"clubs", "players", "player_attributes", "player_positions", "attribute_definitions",
            "club_divisions"} <= names
    assert {"idx_players_club", "idx_players_name", "idx_player_positions_natural"} <= names


def test_attribute_catalog_matches_importer(db):
    _, conn = db
    codes = {r[0] for r in conn.execute("SELECT code FROM attribute_definitions")}
    assert codes == set(importer.ALL_ATTRIBUTE_COLUMNS)


def test_club_divisions_reference_has_20_a_and_20_b(db):
    _, conn = db
    rows = dict(conn.execute("SELECT division, COUNT(*) FROM club_divisions GROUP BY division").fetchall())
    assert rows == {"A": 20, "B": 20}
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO club_divisions VALUES (1, 'C', 2026, 'X')")


def test_generated_id_flag_defaults_to_false(db):
    _, conn = db
    _club(conn)
    _player(conn)
    assert conn.execute("SELECT id_generated FROM players").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE players SET id_generated = 2")


def _club(conn, uid=1):
    conn.execute("INSERT INTO clubs VALUES (?, 'Clube', 'C', 189, 5000)", (uid,))


def _player(conn, uid=10, club=1, **kw):
    v = {"birth_date": "2000-01-01", "age": 25, "height_cm": 180, **kw}
    conn.execute(
        "INSERT INTO players (unique_id, name, full_name, birth_date, age, nation_id, height_cm, club_uid)"
        " VALUES (?, 'N', 'Nome', ?, ?, 189, ?, ?)",
        (uid, v["birth_date"], v["age"], v["height_cm"], club),
    )


def test_foreign_keys_enforced(db):
    _, conn = db
    with pytest.raises(sqlite3.IntegrityError):
        _player(conn, club=999)
    _club(conn)
    _player(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM clubs WHERE club_uid = 1")  # RESTRICT: clube em uso


def test_strict_types_and_checks(db):
    _, conn = db
    _club(conn)
    with pytest.raises(sqlite3.IntegrityError):
        _player(conn, age="vinte")  # STRICT
    with pytest.raises(sqlite3.IntegrityError):
        _player(conn, birth_date="2000-13-45")
    with pytest.raises(sqlite3.IntegrityError):
        _player(conn, height_cm=20)
    with pytest.raises(sqlite3.IntegrityError):
        _club(conn, 1)  # PK duplicada
    _player(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO player_positions VALUES (10, 'XX', 50, 0, 0)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO player_attributes VALUES (10, 'attributes_inexistente', 50)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO player_attributes VALUES (10, 'attributes_pace', 0)")


def test_cascade_removes_dependents(db):
    _, conn = db
    _club(conn)
    _player(conn)
    conn.execute("INSERT INTO player_attributes VALUES (10, 'attributes_pace', 70)")
    conn.execute("INSERT INTO player_positions VALUES (10, 'STC', 100, 1, 0)")
    conn.execute("DELETE FROM players")
    assert conn.execute("SELECT COUNT(*) FROM player_attributes").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM player_positions").fetchone()[0] == 0
