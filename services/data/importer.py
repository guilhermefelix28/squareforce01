"""Leitura e validação de planilhas Excel (sem acesso ao banco).

Colunas mapeadas a partir dos cabeçalhos REAIS de Dados/jogadores.xlsx (aba "Jogadores",
83 colunas, inspecionada em 2026-11-18). Ver docs/architecture/importacao-excel.md.

Política de validação (confirmada pelo responsável em 2026-11-18):
- Erros CRÍTICOS rejeitam a importação inteira (base anterior preservada).
- Linha de jogador SEM unique_id recebe um ID genérico ESTÁVEL (derivado do conteúdo da linha) na
  faixa reservada >= GENERATED_ID_BASE, com aviso GENERATED_ID. O GDD manda preservar "todos os
  jogadores válidos".
- Linhas totalmente vazias são ignoradas.
O arquivo é lido apenas em memória: nenhuma cópia é gravada em disco.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

import openpyxl

from squadforce_shared.contracts import ImportIssue, ImportReport
from squadforce_shared.domain.positions import (
    FAMILIARITY_COLUMN,
    POSITION_ORDER,
    InvalidPositionError,
    Position,
    parse_position_list,
)

MAX_ISSUES_LISTED = 200
MAX_ROWS = 100_000
# Faixa reservada para IDs gerados (IDs reais da base vão até ~2,0 bilhões; cabe em 2^53 para o JS).
GENERATED_ID_BASE = 9_000_000_000
GENERATED_ID_SPAN = 999_999_999


def generated_player_id(full_name: object, birth_date: object, club_uid: object, name: object) -> int:
    """ID genérico estável: mesma linha (nome completo, nascimento, clube, nome) => mesmo ID em toda importação."""
    key = "|".join(str(v or "").strip().casefold() for v in (full_name, birth_date, club_uid, name))
    digest = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16)
    return GENERATED_ID_BASE + digest % GENERATED_ID_SPAN

# ------------------------------------------------------------------ esquema das colunas
CLUB_COLUMNS = ("club_uid", "club_name", "club_short_name", "club_nation_id", "club_reputation")

PLAYER_IDENTITY_COLUMNS = (
    "unique_id",
    "name",
    "first_name",
    "last_name",
    "full_name",
    "birth_date",
    "age",
    "nation_id",
    "height_cm",
    "club_uid",
    "club_join_date",
    "natural_positions",
    "accomplished_positions",
)

PERSONALITY_COLUMNS = (
    "personality_adaptability",
    "personality_pressure",
    "personality_professionalism",
    "personality_sportsmanship",
    "personality_temperament",
)

ATTRIBUTE_COLUMNS = tuple(
    "attributes_" + a
    for a in (
        "crossing dribbling finishing heading long_shots marking off_the_ball passing penalty_taking "
        "tackling vision handling aerial_reach command_of_area communication kicking throwing "
        "anticipation decisions one_on_ones positioning reflexes first_touch technique flair corners "
        "teamwork work_rate long_throws eccentricity rushing_out punching acceleration free_kick_taking "
        "strength stamina pace jumping_reach leadership dirtiness balance bravery consistency aggression "
        "agility important_matches injury_proneness versatility natural_fitness determination composure "
        "concentration"
    ).split()
)

FOOT_COLUMNS = ("left_foot", "right_foot")

# Todas as colunas gravadas em player_attributes (deve coincidir com attribute_definitions).
ALL_ATTRIBUTE_COLUMNS = PERSONALITY_COLUMNS + ATTRIBUTE_COLUMNS + FOOT_COLUMNS

FAMILIARITY_COLUMNS = tuple(FAMILIARITY_COLUMN[p] for p in POSITION_ORDER)

PLAYER_REQUIRED_COLUMNS = PLAYER_IDENTITY_COLUMNS + ALL_ATTRIBUTE_COLUMNS + FAMILIARITY_COLUMNS
# Colunas de clube presentes na planilha de jogadores: pertencem à base de clubes, ignoradas aqui.
PLAYER_IGNORED_COLUMNS = frozenset(CLUB_COLUMNS) - {"club_uid"}

# Limites de integridade dos valores (observados na base real; não são regras de jogo).
RANGES: dict[str, tuple[int, int]] = {
    "age": (10, 60),
    "height_cm": (100, 250),
    **{c: (1, 100) for c in ALL_ATTRIBUTE_COLUMNS},
    **{c: (1, 100) for c in FAMILIARITY_COLUMNS},
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ------------------------------------------------------------------ resultado
@dataclass
class ParsedClub:
    club_uid: int
    name: str
    short_name: str
    nation_id: int
    reputation: int


@dataclass
class ParsedPlayer:
    unique_id: int
    name: str
    first_name: str | None
    last_name: str | None
    full_name: str
    birth_date: str
    age: int
    nation_id: int
    height_cm: int
    club_uid: int
    club_join_date: str | None
    natural_positions: list[Position]
    accomplished_positions: list[Position]
    attributes: dict[str, int]
    familiarity: dict[Position, int]
    id_generated: bool = False


@dataclass
class IssueCollector:
    critical: list[ImportIssue] = field(default_factory=list)
    warnings: list[ImportIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0

    def error(self, code: str, message: str, row: int | None = None, column: str | None = None) -> None:
        self.critical_count += 1
        if len(self.critical) < MAX_ISSUES_LISTED:
            self.critical.append(ImportIssue(row=row, column=column, code=code, message=message))

    def warn(self, code: str, message: str, row: int | None = None, column: str | None = None) -> None:
        self.warning_count += 1
        if len(self.warnings) < MAX_ISSUES_LISTED:
            self.warnings.append(ImportIssue(row=row, column=column, code=code, message=message))

    def fill(self, report: ImportReport) -> ImportReport:
        report.critical_errors = self.critical
        report.critical_error_count = self.critical_count
        report.warnings = self.warnings
        report.warning_count = self.warning_count
        report.status = "rejected" if self.critical_count else "imported"
        return report


class WorkbookError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class _ValueError(ValueError):
    pass


# ------------------------------------------------------------------ conversores
def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def to_int(v: Any) -> int | None:
    """Inteiro estrito: aceita int, float integral e texto numérico ('189'). Rejeita bool e frações."""
    if _is_blank(v):
        return None
    if isinstance(v, bool):
        raise _ValueError("valor lógico não é inteiro")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return int(v)
        raise _ValueError(f"{v} não é inteiro")
    if isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip()):
        return int(v.strip())
    raise _ValueError(f"{v!r} não é um número inteiro")


def to_date(v: Any) -> str | None:
    if _is_blank(v):
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str) and _DATE_RE.match(v.strip()):
        try:
            return date.fromisoformat(v.strip()).isoformat()
        except ValueError as exc:
            raise _ValueError(f"{v!r} não é uma data válida") from exc
    raise _ValueError(f"{v!r} não é uma data no formato AAAA-MM-DD")


def to_text(v: Any) -> str | None:
    if _is_blank(v):
        return None
    if isinstance(v, bool):
        raise _ValueError("valor lógico não é texto")
    if isinstance(v, (int, float, str)):
        return str(v).strip()
    raise _ValueError(f"{v!r} não é texto")


# ------------------------------------------------------------------ leitura do arquivo
@dataclass
class Sheet:
    title: str
    header: list[str]
    rows: list[tuple[Any, ...]]


def read_workbook(content: bytes, file_name: str) -> list[Sheet]:
    if not file_name.lower().endswith(".xlsx"):
        raise WorkbookError("UNSUPPORTED_FILE", "Apenas arquivos .xlsx são aceitos.")
    if not content.startswith(b"PK"):
        raise WorkbookError("INVALID_WORKBOOK", "O arquivo não é uma planilha .xlsx válida.")
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise WorkbookError("INVALID_WORKBOOK", f"Não foi possível ler a planilha: {exc}") from exc
    sheets: list[Sheet] = []
    try:
        for ws in wb.worksheets:
            it = ws.iter_rows(values_only=True)
            first = next(it, None)
            if first is None:
                sheets.append(Sheet(ws.title, [], []))
                continue
            header = ["" if h is None else str(h).strip() for h in first]
            rows: list[tuple[Any, ...]] = []
            for r in it:
                rows.append(r)
                if len(rows) > MAX_ROWS:
                    raise WorkbookError("INVALID_WORKBOOK", f"A aba {ws.title!r} excede {MAX_ROWS} linhas.")
            sheets.append(Sheet(ws.title, header, rows))
    finally:
        wb.close()
    return sheets


def _pick_sheet(sheets: list[Sheet], required: Iterable[str], issues: IssueCollector) -> Sheet | None:
    required = list(required)
    best: tuple[int, Sheet] | None = None
    for s in sheets:
        missing = [c for c in required if c not in s.header]
        if not missing:
            dups = sorted({h for h in s.header if h and s.header.count(h) > 1})
            if dups:
                issues.error("DUPLICATE_COLUMN", f"Colunas repetidas na aba {s.title!r}: {', '.join(dups)}")
                return None
            return s
        if best is None or len(missing) < best[0]:
            best = (len(missing), s)
    if best is None:
        issues.error("EMPTY_WORKBOOK", "A planilha não contém abas.")
    else:
        s = best[1]
        missing = [c for c in required if c not in s.header]
        issues.error(
            "MISSING_COLUMNS",
            f"Colunas obrigatórias ausentes (aba mais próxima: {s.title!r}): {', '.join(missing)}",
        )
    return None


def _row_dict(header: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {h: (row[i] if i < len(row) else None) for i, h in enumerate(header) if h}


# ------------------------------------------------------------------ clubes
def parse_clubs(sheets: list[Sheet], file_name: str) -> tuple[ImportReport, list[ParsedClub]]:
    """Extrai clubes de uma aba com as colunas club_*.

    Aceita tanto uma planilha dedicada de clubes quanto a própria jogadores.xlsx (cada linha
    repete os dados do clube do atleta). Dados divergentes para o mesmo club_uid são críticos.
    """
    issues = IssueCollector()
    report = ImportReport(base="clubs", status="rejected", file_name=file_name)
    sheet = _pick_sheet(sheets, CLUB_COLUMNS, issues)
    if sheet is None:
        return issues.fill(report), []
    report.sheet = sheet.title
    clubs: dict[int, ParsedClub] = {}
    first_row: dict[int, int] = {}
    for idx, raw in enumerate(sheet.rows, start=2):
        if all(_is_blank(v) for v in raw):
            continue
        report.rows_read += 1
        row = _row_dict(sheet.header, raw)
        try:
            uid = to_int(row["club_uid"])
        except _ValueError as e:
            issues.error("INVALID_TYPE", f"club_uid inválido: {e}", idx, "club_uid")
            continue
        if uid is None:
            issues.error("MISSING_VALUE", "club_uid ausente.", idx, "club_uid")
            continue
        if uid <= 0:
            issues.error("OUT_OF_RANGE", "club_uid deve ser positivo.", idx, "club_uid")
            continue
        values: dict[str, Any] = {}
        ok = True
        for col, conv in (
            ("club_name", to_text),
            ("club_short_name", to_text),
            ("club_nation_id", to_int),
            ("club_reputation", to_int),
        ):
            try:
                v = conv(row[col])
            except _ValueError as e:
                issues.error("INVALID_TYPE", f"{col}: {e}", idx, col)
                ok = False
                continue
            if v is None:
                issues.error("MISSING_VALUE", f"{col} ausente.", idx, col)
                ok = False
            elif isinstance(v, int) and v < 0:
                issues.error("OUT_OF_RANGE", f"{col} não pode ser negativo.", idx, col)
                ok = False
            values[col] = v
        if not ok:
            continue
        club = ParsedClub(
            uid, values["club_name"], values["club_short_name"], values["club_nation_id"], values["club_reputation"]
        )
        if uid in clubs:
            if clubs[uid] != club:
                issues.error(
                    "INCONSISTENT_CLUB_DATA",
                    f"club_uid {uid} tem dados diferentes da linha {first_row[uid]}.",
                    idx,
                    "club_uid",
                )
            continue
        clubs[uid] = club
        first_row[uid] = idx

    if not clubs and not issues.critical_count:
        issues.error("EMPTY_SHEET", "Nenhum clube encontrado na planilha.")
    report.rows_imported = 0 if issues.critical_count else len(clubs)
    return issues.fill(report), list(clubs.values())


def _safe_text(v: Any) -> str | None:
    try:
        return to_text(v)
    except _ValueError:
        return None


# ------------------------------------------------------------------ jogadores
def parse_players(
    sheets: list[Sheet], file_name: str, known_club_uids: set[int]
) -> tuple[ImportReport, list[ParsedPlayer]]:
    issues = IssueCollector()
    report = ImportReport(base="players", status="rejected", file_name=file_name)
    sheet = _pick_sheet(sheets, PLAYER_REQUIRED_COLUMNS, issues)
    if sheet is None:
        return issues.fill(report), []
    report.sheet = sheet.title

    known = set(PLAYER_REQUIRED_COLUMNS) | PLAYER_IGNORED_COLUMNS
    for h in sheet.header:
        if h and h not in known:
            issues.warn("UNKNOWN_COLUMN", f"Coluna {h!r} não é utilizada e foi ignorada.", column=h)

    if not known_club_uids:
        issues.error(
            "CLUBS_NOT_IMPORTED",
            "Não há clubes na base. Importe a base de clubes antes da base de jogadores.",
        )
        return issues.fill(report), []

    players: list[ParsedPlayer] = []
    seen: dict[int, int] = {}
    persons: dict[tuple[str, str], list[ParsedPlayer]] = {}
    rows_of: dict[int, int] = {}
    for idx, raw in enumerate(sheet.rows, start=2):
        if all(_is_blank(v) for v in raw):
            continue
        report.rows_read += 1
        row = _row_dict(sheet.header, raw)
        before = issues.critical_count

        def get(col: str, conv, required: bool = True):
            try:
                v = conv(row[col])
            except _ValueError as e:
                issues.error("INVALID_TYPE", f"{col}: {e}", idx, col)
                return None
            if v is None:
                if required:
                    issues.error("MISSING_VALUE", f"{col} ausente.", idx, col)
                return None
            if col in RANGES and isinstance(v, int):
                lo, hi = RANGES[col]
                if not lo <= v <= hi:
                    issues.error("OUT_OF_RANGE", f"{col}={v} fora do intervalo {lo}–{hi}.", idx, col)
                    return None
            return v

        # Identificador: ausente -> ID genérico estável; inválido -> crítico.
        try:
            uid = to_int(row["unique_id"])
        except _ValueError as e:
            issues.error("INVALID_TYPE", f"unique_id: {e}", idx, "unique_id")
            continue
        id_generated = uid is None
        if id_generated:
            uid = generated_player_id(row.get("full_name"), row.get("birth_date"), row.get("club_uid"), row.get("name"))
            issues.warn(
                "GENERATED_ID",
                f"Jogador {_safe_text(row.get('name'))!r} sem unique_id recebeu o ID genérico {uid}.",
                idx,
                "unique_id",
            )
        elif uid <= 0:
            issues.error("OUT_OF_RANGE", "unique_id deve ser positivo.", idx, "unique_id")
            continue
        elif uid >= GENERATED_ID_BASE:
            issues.error(
                "OUT_OF_RANGE", f"unique_id {uid} está na faixa reservada a IDs gerados (>= {GENERATED_ID_BASE}).",
                idx, "unique_id",
            )
            continue
        if uid in seen:
            msg = (
                f"ID genérico {uid} coincide com o da linha {seen[uid]} (linhas idênticas sem unique_id)."
                if id_generated else f"unique_id {uid} repetido (primeira ocorrência na linha {seen[uid]})."
            )
            issues.error("DUPLICATE_ID", msg, idx, "unique_id")
            continue
        seen[uid] = idx

        name = get("name", to_text)
        first_name = get("first_name", to_text, required=False)
        last_name = get("last_name", to_text, required=False)
        full_name = get("full_name", to_text)
        birth_date = get("birth_date", to_date)
        age = get("age", to_int)
        nation_id = get("nation_id", to_int)
        if nation_id is not None and nation_id < 0:
            issues.error("OUT_OF_RANGE", "nation_id não pode ser negativo.", idx, "nation_id")
        height = get("height_cm", to_int)
        club_uid = get("club_uid", to_int)
        if club_uid is not None and club_uid not in known_club_uids:
            issues.error(
                "INVALID_RELATIONSHIP",
                f"club_uid {club_uid} não existe na base de clubes.",
                idx,
                "club_uid",
            )
        join_date = get("club_join_date", to_date, required=False)

        naturals: list[Position] = []
        accomplished: list[Position] = []
        try:
            naturals = parse_position_list(row["natural_positions"])
            if not naturals:
                issues.error("MISSING_VALUE", "natural_positions ausente.", idx, "natural_positions")
        except InvalidPositionError as e:
            issues.error("INVALID_POSITION", str(e), idx, "natural_positions")
        try:
            accomplished = parse_position_list(row["accomplished_positions"])
        except InvalidPositionError as e:
            issues.error("INVALID_POSITION", str(e), idx, "accomplished_positions")

        attrs: dict[str, int] = {}
        for col in ALL_ATTRIBUTE_COLUMNS:
            v = get(col, to_int)
            if v is not None:
                attrs[col] = v
        fam: dict[Position, int] = {}
        for pos in POSITION_ORDER:
            v = get(FAMILIARITY_COLUMN[pos], to_int)
            if v is not None:
                fam[pos] = v

        if issues.critical_count != before:
            continue
        players.append(
            ParsedPlayer(
                unique_id=uid,
                name=name,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                birth_date=birth_date,
                age=age,
                nation_id=nation_id,
                height_cm=height,
                club_uid=club_uid,
                club_join_date=join_date,
                natural_positions=naturals,
                accomplished_positions=[p for p in accomplished if p not in naturals],
                attributes=attrs,
                familiarity=fam,
                id_generated=id_generated,
            )
        )
        rows_of[uid] = idx
        persons.setdefault((full_name.casefold(), birth_date), []).append(players[-1])

    # Mesma pessoa (nome completo + nascimento) mais de uma vez: mantém SOMENTE um registro
    # (decisão do responsável, 2026-11-18): prefere ID real ao gerado; depois, a primeira linha.
    dropped: set[int] = set()
    for (_, birth), same in persons.items():
        if len(same) < 2:
            continue
        keep = sorted(same, key=lambda pl: (pl.id_generated, rows_of[pl.unique_id]))[0]
        for pl in same:
            if pl is keep:
                continue
            dropped.add(pl.unique_id)
            report.rows_skipped += 1
            issues.warn(
                "DUPLICATE_PERSON_REMOVED",
                f"{pl.full_name!r} ({birth}) repetido: mantido o registro {keep.unique_id} "
                f"(linha {rows_of[keep.unique_id]}); esta linha foi descartada.",
                rows_of[pl.unique_id],
                "full_name",
            )
    if dropped:
        players = [pl for pl in players if pl.unique_id not in dropped]

    if not players and not issues.critical_count:
        issues.error("EMPTY_SHEET", "Nenhum jogador válido encontrado na planilha.")
    report.rows_imported = 0 if issues.critical_count else len(players)
    return issues.fill(report), players
