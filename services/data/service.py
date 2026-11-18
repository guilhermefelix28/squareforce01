"""DataService: único ponto de acesso ao SQLite.

Importações:
1. Obtêm a trava de importação do serviço de sessão (bloqueia se houver competição ativa
   e serializa importações concorrentes).
2. Leem e validam a planilha em memória.
3. Substituem SOMENTE a base correspondente em uma única transação SQLite.
4. Qualquer falha crítica -> ROLLBACK integral; a base anterior permanece intacta.
Não há backups, versionamento ou cópia do arquivo Excel.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable

from squadforce_shared.contracts import ClubOut, ClubPage, ImportReport, PlayerOut, PlayerPage
from squadforce_shared.domain.positions import Position, normalize_position, InvalidPositionError
from squadforce_shared.errors import AppError, ErrorCode

from . import importer
from .db import apply_migrations, connection, schema_version

log = logging.getLogger("squadforce.data")

ImportGuard = Callable[[], AbstractContextManager[None]]


def _like(term: str) -> str:
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ------------------------------------------------------------------ escrita (funções isoladas para teste de falha)
def _upsert_clubs(conn: sqlite3.Connection, clubs: list[importer.ParsedClub]) -> None:
    conn.executemany(
        "INSERT INTO clubs (club_uid, name, short_name, nation_id, reputation) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (club_uid) DO UPDATE SET name = excluded.name, short_name = excluded.short_name, "
        "nation_id = excluded.nation_id, reputation = excluded.reputation",
        [(c.club_uid, c.name, c.short_name, c.nation_id, c.reputation) for c in clubs],
    )


def _insert_players(conn: sqlite3.Connection, players: list[importer.ParsedPlayer]) -> None:
    conn.executemany(
        "INSERT INTO players (unique_id, name, first_name, last_name, full_name, birth_date, age, nation_id,"
        " height_cm, club_uid, club_join_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                p.unique_id, p.name, p.first_name, p.last_name, p.full_name, p.birth_date, p.age,
                p.nation_id, p.height_cm, p.club_uid, p.club_join_date,
            )
            for p in players
        ],
    )
    conn.executemany(
        "INSERT INTO player_attributes (player_id, attribute, value) VALUES (?, ?, ?)",
        [(p.unique_id, k, v) for p in players for k, v in p.attributes.items()],
    )
    conn.executemany(
        "INSERT INTO player_positions (player_id, position, familiarity, is_natural, is_accomplished)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (
                p.unique_id, pos.value, fam,
                int(pos in p.natural_positions), int(pos in p.accomplished_positions),
            )
            for p in players
            for pos, fam in p.familiarity.items()
        ],
    )


class DataService:
    def __init__(self, db_path: Path, import_guard: ImportGuard, max_upload_bytes: int = 25 * 1024 * 1024):
        self.db_path = db_path
        self._import_guard = import_guard
        self.max_upload_bytes = max_upload_bytes

    # -------------------------------------------------------------- ciclo de vida
    def initialize(self) -> int:
        return apply_migrations(self.db_path)

    def health(self) -> dict:
        try:
            with connection(self.db_path) as conn:
                return {
                    "status": "ok",
                    "schema_version": schema_version(conn),
                    "clubs": conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0],
                    "players": conn.execute("SELECT COUNT(*) FROM players").fetchone()[0],
                }
        except sqlite3.Error as exc:
            log.error("database health check failed: %s", exc)
            return {"status": "error"}

    # -------------------------------------------------------------- importações
    def _check_upload(self, content: bytes, file_name: str) -> list[importer.Sheet]:
        if len(content) > self.max_upload_bytes:
            raise AppError(
                413, ErrorCode.FILE_TOO_LARGE,
                f"Arquivo excede o limite de {self.max_upload_bytes // (1024 * 1024)} MB.",
            )
        try:
            return importer.read_workbook(content, file_name)
        except importer.WorkbookError as exc:
            code = ErrorCode.UNSUPPORTED_FILE if exc.code == "UNSUPPORTED_FILE" else ErrorCode.INVALID_WORKBOOK
            raise AppError(415 if code is ErrorCode.UNSUPPORTED_FILE else 422, code, exc.message) from exc

    @staticmethod
    def _reject(report: ImportReport) -> AppError:
        return AppError(
            422,
            ErrorCode.IMPORT_VALIDATION_FAILED,
            f"Importação rejeitada: {report.critical_error_count} erro(s) crítico(s). A base anterior foi preservada.",
            details={"report": report.model_dump(mode="json")},
        )

    def import_clubs(self, content: bytes, file_name: str) -> ImportReport:
        with self._import_guard():
            sheets = self._check_upload(content, file_name)
            report, clubs = importer.parse_clubs(sheets, file_name)
            if report.status == "rejected":
                raise self._reject(report)
            new_ids = {c.club_uid for c in clubs}
            with connection(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    report.previous_count = conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
                    in_use = conn.execute(
                        "SELECT club_uid, COUNT(*) FROM players GROUP BY club_uid"
                    ).fetchall()
                    orphaned = sorted((r[0], r[1]) for r in in_use if r[0] not in new_ids)
                    if orphaned:
                        conn.execute("ROLLBACK")
                        for uid, n in orphaned[: importer.MAX_ISSUES_LISTED]:
                            report.critical_errors.append(
                                importer.ImportIssue(
                                    code="INVALID_RELATIONSHIP",
                                    column="club_uid",
                                    message=f"Clube {uid} ausente na nova base, mas referenciado por {n} jogador(es).",
                                )
                            )
                        report.critical_error_count += len(orphaned)
                        report.status = "rejected"
                        report.rows_imported = 0
                        raise self._reject(report)
                    _upsert_clubs(conn, clubs)
                    placeholders = ",".join("?" * len(new_ids))
                    conn.execute(f"DELETE FROM clubs WHERE club_uid NOT IN ({placeholders})", tuple(new_ids))
                    conn.execute("COMMIT")
                except AppError:
                    raise
                except Exception as exc:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    log.exception("clubs import failed; rolled back")
                    raise AppError(
                        500, ErrorCode.IMPORT_FAILED,
                        "Falha ao gravar a base de clubes. Nenhuma alteração foi aplicada.",
                        retryable=True, details={"reason": type(exc).__name__},
                    ) from exc
            return report

    def import_players(self, content: bytes, file_name: str) -> ImportReport:
        with self._import_guard():
            sheets = self._check_upload(content, file_name)
            with connection(self.db_path) as conn:
                known = {r[0] for r in conn.execute("SELECT club_uid FROM clubs")}
            report, players = importer.parse_players(sheets, file_name, known)
            if report.status == "rejected":
                raise self._reject(report)
            with connection(self.db_path) as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    report.previous_count = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
                    conn.execute("DELETE FROM players")  # CASCADE remove atributos e posições
                    _insert_players(conn, players)
                    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                    if violations:
                        raise sqlite3.IntegrityError(f"{len(violations)} violações de chave estrangeira")
                    conn.execute("COMMIT")
                except Exception as exc:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    log.exception("players import failed; rolled back")
                    raise AppError(
                        500, ErrorCode.IMPORT_FAILED,
                        "Falha ao gravar a base de jogadores. Nenhuma alteração foi aplicada.",
                        retryable=True, details={"reason": type(exc).__name__, "message": str(exc)},
                    ) from exc
            return report

    # -------------------------------------------------------------- consultas
    def club_count(self) -> int:
        with connection(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]

    def club_exists(self, club_uid: int) -> bool:
        with connection(self.db_path) as conn:
            return conn.execute("SELECT 1 FROM clubs WHERE club_uid = ?", (club_uid,)).fetchone() is not None

    def catalog_ready(self) -> bool:
        with connection(self.db_path) as conn:
            clubs = conn.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
            players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
            return clubs >= 2 and players > 0

    def list_clubs(self, search: str | None, limit: int, offset: int) -> ClubPage:
        where, params = "", []
        if search:
            where = "WHERE c.name LIKE ? ESCAPE '\\' OR c.short_name LIKE ? ESCAPE '\\'"
            params = [_like(search), _like(search)]
        with connection(self.db_path) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM clubs c {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT c.club_uid, c.name, c.short_name, c.nation_id,"
                f" (SELECT COUNT(*) FROM players p WHERE p.club_uid = c.club_uid) AS player_count"
                f" FROM clubs c {where} ORDER BY c.short_name COLLATE NOCASE LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return ClubPage(items=[ClubOut(**dict(r)) for r in rows], total=total, limit=limit, offset=offset)

    def list_players(
        self, club_uid: int | None, position: str | None, search: str | None, limit: int, offset: int
    ) -> PlayerPage:
        clauses, params = [], []
        if club_uid is not None:
            clauses.append("p.club_uid = ?")
            params.append(club_uid)
        if position:
            try:
                pos = normalize_position(position)
            except InvalidPositionError as exc:
                raise AppError(422, ErrorCode.VALIDATION_ERROR, str(exc), details={"field": "position"}) from exc
            clauses.append(
                "EXISTS (SELECT 1 FROM player_positions pp WHERE pp.player_id = p.unique_id"
                " AND pp.position = ? AND pp.is_natural = 1)"
            )
            params.append(pos.value)
        if search:
            clauses.append("(p.name LIKE ? ESCAPE '\\' OR p.full_name LIKE ? ESCAPE '\\')")
            params += [_like(search), _like(search)]
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with connection(self.db_path) as conn:
            total = conn.execute(f"SELECT COUNT(*) FROM players p {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT p.unique_id, p.name, p.full_name, p.birth_date, p.age, p.nation_id, p.height_cm,"
                f" p.club_uid, c.short_name AS club_short_name FROM players p JOIN clubs c ON c.club_uid = p.club_uid"
                f" {where} ORDER BY p.name COLLATE NOCASE, p.unique_id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            ids = [r["unique_id"] for r in rows]
            positions: dict[int, tuple[list[Position], list[Position]]] = {i: ([], []) for i in ids}
            if ids:
                ph = ",".join("?" * len(ids))
                for r in conn.execute(
                    f"SELECT player_id, position, is_natural, is_accomplished FROM player_positions"
                    f" WHERE player_id IN ({ph}) AND (is_natural = 1 OR is_accomplished = 1)",
                    ids,
                ):
                    nat, acc = positions[r["player_id"]]
                    (nat if r["is_natural"] else acc).append(Position(r["position"]))
        items = [
            PlayerOut(**dict(r), natural_positions=positions[r["unique_id"]][0],
                      accomplished_positions=positions[r["unique_id"]][1])
            for r in rows
        ]
        return PlayerPage(items=items, total=total, limit=limit, offset=offset)
