"""Validação de planilhas (sem banco): tipos, duplicatas, relacionamentos, colunas."""

import pytest

from conftest import build_xlsx, player_row, squad
from services.data import importer

KNOWN = {100, 200, 300, 400}


def parse_players(rows, header=None, known=KNOWN):
    sheets = importer.read_workbook(build_xlsx(rows, header), "jogadores.xlsx")
    return importer.parse_players(sheets, "jogadores.xlsx", known)


def codes(report):
    return [e.code for e in report.critical_errors]


def test_valid_players_parse_with_typed_values():
    report, players = parse_players(squad(2))
    assert report.status == "imported"
    assert report.rows_imported == len(players) == 8
    p = players[0]
    assert isinstance(p.unique_id, int) and isinstance(p.age, int)
    assert p.natural_positions[0].value == "STC"
    assert len(p.attributes) == len(importer.ALL_ATTRIBUTE_COLUMNS)
    assert len(p.familiarity) == 7


def test_numeric_text_is_accepted_like_the_real_file():
    # A planilha real mistura números e textos numéricos ('189').
    report, players = parse_players([player_row("1234", 100, age="25", nation_id="189", height_cm="180")])
    assert report.status == "imported"
    assert players[0].unique_id == 1234 and players[0].age == 25


def test_display_positions_are_normalized_on_import():
    report, players = parse_players([player_row(1, 100, natural_positions="ATA", accomplished_positions="ME")])
    assert report.status == "imported"
    assert [p.value for p in players[0].natural_positions] == ["STC"]
    assert [p.value for p in players[0].accomplished_positions] == ["MC"]


def test_duplicate_ids_are_critical():
    report, _ = parse_players([player_row(5), player_row(5, 200)])
    assert report.status == "rejected"
    assert codes(report) == ["DUPLICATE_ID"]
    assert report.critical_errors[0].row == 3


@pytest.mark.parametrize(
    "field,value",
    [("age", "vinte"), ("height_cm", 180.5), ("attributes_pace", "rápido"), ("birth_date", "15/01/2000"),
     ("unique_id", "AB12"), ("positions_gk", True)],
)
def test_invalid_types_are_critical(field, value):
    report, players = parse_players([player_row(1, **{field: value})])
    assert report.status == "rejected"
    assert "INVALID_TYPE" in codes(report)
    assert report.rows_imported == 0


@pytest.mark.parametrize("field,value", [("age", 5), ("attributes_pace", 101), ("positions_mc", 0), ("height_cm", 300)])
def test_out_of_range_values_are_critical(field, value):
    report, _ = parse_players([player_row(1, **{field: value})])
    assert codes(report) == ["OUT_OF_RANGE"]


def test_invalid_relationship_is_critical():
    report, _ = parse_players([player_row(1, 100), player_row(2, 999)])
    assert report.status == "rejected"
    assert "INVALID_RELATIONSHIP" in codes(report)


def test_invalid_position_is_critical():
    report, _ = parse_players([player_row(1, natural_positions="XYZ")])
    assert codes(report) == ["INVALID_POSITION"]


def test_missing_natural_position_is_critical():
    report, _ = parse_players([player_row(1, natural_positions=None)])
    assert codes(report) == ["MISSING_VALUE"]


def test_row_without_id_gets_stable_generated_id():
    report, players = parse_players([player_row(1), player_row(None, 200, full_name="Sem Id", name="Sem")])
    assert report.status == "imported"
    assert report.rows_skipped == 0 and report.rows_imported == 2
    assert [w.code for w in report.warnings] == ["GENERATED_ID"]
    generated = players[1]
    assert generated.id_generated and not players[0].id_generated
    assert generated.unique_id >= importer.GENERATED_ID_BASE
    # estável: a mesma linha gera o mesmo ID em outra importação
    _, again = parse_players([player_row(None, 200, full_name="Sem Id", name="Sem")])
    assert again[0].unique_id == generated.unique_id


def test_generated_ids_differ_for_different_rows():
    _, players = parse_players([player_row(None, 100, full_name="A B"), player_row(None, 100, full_name="C D")])
    assert players[0].unique_id != players[1].unique_id


def test_identical_rows_without_id_are_duplicates():
    row = player_row(None, 100, full_name="Igual")
    report, _ = parse_players([row, dict(row)])
    assert "DUPLICATE_ID" in codes(report)


def test_real_id_in_reserved_range_is_rejected():
    report, _ = parse_players([player_row(importer.GENERATED_ID_BASE + 5)])
    assert codes(report) == ["OUT_OF_RANGE"]


def test_same_person_twice_keeps_only_the_real_id():
    report, players = parse_players([player_row(None, 200, full_name="Fulano"), player_row(1, full_name="Fulano")])
    assert report.status == "imported" and [p.unique_id for p in players] == [1]
    assert report.rows_skipped == 1 and report.rows_imported == 1
    assert "DUPLICATE_PERSON_REMOVED" in [w.code for w in report.warnings]


def test_same_person_twice_with_real_ids_keeps_the_first_row():
    report, players = parse_players([player_row(7, full_name="Ciclano"), player_row(8, 200, full_name="Ciclano")])
    assert [p.unique_id for p in players] == [7] and report.rows_skipped == 1


def test_homonyms_with_different_birth_dates_are_kept():
    _, players = parse_players([player_row(1, full_name="Beltrano"), player_row(2, full_name="Beltrano", birth_date="1999-05-05")])
    assert len(players) == 2


def test_missing_columns_are_critical():
    header = [h for h in build_header() if h != "attributes_pace"]
    report, _ = parse_players([player_row(1)], header=header)
    assert codes(report) == ["MISSING_COLUMNS"]
    assert "attributes_pace" in report.critical_errors[0].message


def test_unknown_columns_only_warn():
    header = build_header() + ["coluna_extra"]
    report, _ = parse_players([player_row(1)], header=header)
    assert report.status == "imported"
    assert [w.code for w in report.warnings] == ["UNKNOWN_COLUMN"]


def test_players_require_clubs_base():
    report, _ = parse_players([player_row(1)], known=set())
    assert codes(report) == ["CLUBS_NOT_IMPORTED"]


def test_blank_rows_are_ignored():
    report, players = parse_players([player_row(1), {}, player_row(2)])
    assert report.rows_read == 2 and len(players) == 2


def test_clubs_are_extracted_and_deduplicated_from_player_sheet():
    sheets = importer.read_workbook(build_xlsx(squad(3)), "jogadores.xlsx")
    report, clubs = importer.parse_clubs(sheets, "jogadores.xlsx")
    assert report.status == "imported"
    assert sorted(c.club_uid for c in clubs) == [100, 200, 300, 400]


def test_inconsistent_club_data_is_critical():
    rows = [player_row(1, 100), player_row(2, 100, club_name="Outro Nome")]
    report, _ = importer.parse_clubs(importer.read_workbook(build_xlsx(rows), "x.xlsx"), "x.xlsx")
    assert report.status == "rejected"
    assert codes(report) == ["INCONSISTENT_CLUB_DATA"]


def test_non_xlsx_files_are_rejected():
    with pytest.raises(importer.WorkbookError) as e:
        importer.read_workbook(b"a,b,c", "dados.csv")
    assert e.value.code == "UNSUPPORTED_FILE"
    with pytest.raises(importer.WorkbookError) as e:
        importer.read_workbook(b"isto nao e zip", "dados.xlsx")
    assert e.value.code == "INVALID_WORKBOOK"
    with pytest.raises(importer.WorkbookError) as e:
        importer.read_workbook(b"PK\x03\x04corrompido", "dados.xlsx")
    assert e.value.code == "INVALID_WORKBOOK"


def build_header():
    from conftest import PLAYER_HEADER

    return list(PLAYER_HEADER)
