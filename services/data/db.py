"""Conexão SQLite e execução de migrações (somente aditivas, sem operações destrutivas)."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=10, isolation_level=None)  # autocommit; transações explícitas
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


@contextmanager
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def apply_migrations(db_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Aplica, em ordem, as migrações ainda não registradas. Retorna a versão final do esquema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now'))) STRICT"
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        for file in sorted(migrations_dir.glob("*.sql")):
            version = int(file.name.split("_", 1)[0])
            if version in applied:
                continue
            sql = file.read_text(encoding="utf-8")
            # executescript faz COMMIT implícito antes; envolvemos tudo em uma transação própria.
            try:
                conn.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + sql
                    + f"\nINSERT INTO schema_migrations (version, name) VALUES ({version}, '{file.name}');\nCOMMIT;"
                )
            except sqlite3.Error:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)
