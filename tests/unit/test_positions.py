"""Normalização posicional (GDD v5.2, seção 3)."""

import pytest

from squadforce_shared.domain.positions import (
    DISPLAY_TO_INTERNAL,
    InvalidPositionError,
    Position,
    normalize_position,
    parse_position_list,
)

OFFICIAL = {"GOL": "GK", "LD": "DR", "LE": "DL", "ZAG": "DC", "VOL": "DM", "ME": "MC", "ATA": "STC"}


@pytest.mark.parametrize("display,internal", OFFICIAL.items())
def test_display_codes_map_to_internal(display, internal):
    assert normalize_position(display) is Position(internal)
    assert normalize_position(display.lower()) is Position(internal)


@pytest.mark.parametrize("internal", OFFICIAL.values())
def test_internal_codes_are_kept(internal):
    assert normalize_position(f" {internal} ") is Position(internal)


def test_table_is_exactly_the_official_one():
    assert {k: v.value for k, v in DISPLAY_TO_INTERNAL.items()} == OFFICIAL
    assert len(Position) == 7


@pytest.mark.parametrize("bad", ["", "XX", "AMC", "ST", "GOLEIRO", "D C", None])
def test_unknown_positions_are_rejected(bad):
    with pytest.raises(InvalidPositionError):
        normalize_position(bad)


def test_parse_list_handles_separators_and_duplicates():
    assert parse_position_list("STC, MC/ata;GOL") == [Position.STC, Position.MC, Position.GK]
    assert parse_position_list(None) == []
    assert parse_position_list("   ") == []


def test_parse_list_rejects_any_invalid_token():
    with pytest.raises(InvalidPositionError):
        parse_position_list("STC, XYZ")
