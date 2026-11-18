"""Lesões, suspensões por competição, folgas, emergenciais e escalação (GDD §9, §13)."""

from __future__ import annotations

import pytest

from services.match_engine.availability import AvailabilityLedger
from services.match_engine.engine import simulate
from services.match_engine.lineup import build_team_sheet, emergency_player
from services.match_engine.calibration import FORMATION_433
from services.match_engine.types import Card, Injury, MatchResult
from services.match_engine.validation import validate_result
from squadforce_shared.domain.positions import Position
from support.match_fixtures import match, params, player, team


def fake_result(competition="liga", injuries=(), cards=(), match_id="m1") -> MatchResult:
    return MatchResult(match_id, competition, "v", "p", 1, (), (0, 0), (0, 0), "completed", None, {}, (), None,
                       tuple(injuries), tuple(cards), ("equilibrada", "equilibrada"))


SQUADS = ({101, 102, 103}, {201, 202})
SHEETS = (team(1), team(2))


def test_injury_is_served_in_next_official_matches_of_any_competition():
    led = AvailabilityLedger()
    led.record_match(fake_result(injuries=[Injury(101, 0, 2, 100.0)]), SHEETS, SQUADS)
    assert not led.is_available(101, "liga") and not led.is_available(101, "copa")
    assert led.unavailable_reason(101, "liga") == "lesionado (2 jogo(s))"
    led.record_match(fake_result(competition="copa"), SHEETS, SQUADS)  # jogo da Copa conta para a lesão
    assert led.injuries[101] == 1
    led.record_match(fake_result(competition="liga"), SHEETS, SQUADS)
    assert led.is_available(101, "liga") and led.is_available(101, "copa")


def test_zero_match_injury_does_not_sideline():
    led = AvailabilityLedger()
    led.record_match(fake_result(injuries=[Injury(101, 0, 0, 10.0)]), SHEETS, SQUADS)
    assert led.is_available(101, "liga") and led.history[-1]["matches"] == 0


def test_suspension_is_per_competition():
    led = AvailabilityLedger(params(red_card_suspension_matches=1))
    led.record_match(fake_result(cards=[Card(102, 0, "red", 50.0)]), SHEETS, SQUADS)
    assert not led.is_available(102, "liga") and led.is_available(102, "copa")
    led.record_match(fake_result(competition="copa"), SHEETS, SQUADS)  # jogo de outra competição NÃO cumpre
    assert not led.is_available(102, "liga")
    led.record_match(fake_result(competition="liga"), SHEETS, SQUADS)
    assert led.is_available(102, "liga")


def test_bye_does_not_reduce_counters():
    led = AvailabilityLedger()
    led.record_match(fake_result(injuries=[Injury(101, 0, 1, 1.0)]), SHEETS, SQUADS)
    other_squads = ({901}, {902})  # rodada em que o clube folga: só outros clubes jogam
    led.record_match(fake_result(), SHEETS, other_squads)
    assert led.injuries[101] == 1


def test_yellow_accumulation_only_when_parameter_defined():
    led = AvailabilityLedger()  # padrão: acúmulo pendente (desligado)
    for i in range(5):
        led.record_match(fake_result(cards=[Card(103, 0, "yellow", 1.0)], match_id=f"y{i}"), SHEETS, SQUADS)
    assert led.is_available(103, "liga")
    strict = AvailabilityLedger(params(yellow_accumulation_threshold=3))
    for i in range(3):
        strict.record_match(fake_result(cards=[Card(103, 0, "yellow", 1.0)], match_id=f"y{i}"), SHEETS, SQUADS)
    assert not strict.is_available(103, "liga")


def test_emergency_players_never_enter_the_ledger():
    sheet = build_team_sheet(9, [player(900 + i, Position.MC) for i in range(8)], FORMATION_433)
    emergency = [p for p in sheet.starters if p.is_emergency]
    led = AvailabilityLedger()
    led.record_match(fake_result(injuries=[Injury(emergency[0].unique_id, 0, 3, 1.0)]), (sheet, team(2)), ({1}, {2}))
    assert emergency[0].unique_id not in led.injuries and not led.history


# ------------------------------------------------------------------ escalação e emergenciais
def test_unavailable_players_are_not_selected():
    squad = [player(500 + i, pos) for i, pos in enumerate(FORMATION_433 * 2)]
    led = AvailabilityLedger()
    led.injuries[500] = 2
    led.suspensions[("liga", 501)] = 1
    sheet = build_team_sheet(5, squad, FORMATION_433, led, "liga")
    chosen = {p.unique_id for p in (*sheet.starters, *sheet.bench)}
    assert 500 not in chosen and 501 not in chosen
    cup = build_team_sheet(5, squad, FORMATION_433, led, "copa")
    assert 501 in {p.unique_id for p in (*cup.starters, *cup.bench)}  # suspensão vale só na liga
    assert len(sheet.starters) == 11 and len(sheet.bench) <= 7


def test_emergency_players_only_when_fewer_than_eleven_available():
    full = build_team_sheet(5, [player(600 + i, p) for i, p in enumerate(FORMATION_433)], FORMATION_433)
    assert not any(p.is_emergency for p in full.starters)
    eight = [player(700 + i, p) for i, p in enumerate(FORMATION_433[:8])]
    sheet = build_team_sheet(7, eight, FORMATION_433)
    emerg = [p for p in sheet.starters if p.is_emergency]
    assert len(emerg) == 3 and not sheet.bench
    assert all(p.unique_id < 0 for p in emerg) and len({p.unique_id for p in sheet.starters}) == 11
    assert {p.unique_id for p in sheet.starters if not p.is_emergency} == {p.unique_id for p in eight}
    assert all(max(p.attributes.values()) <= 30 for p in emerg)  # baixa qualidade
    res = simulate(match(1, sheet, team(2)))
    assert validate_result(res, match(1, sheet, team(2))) == []
    assert res.events[0].data["emergency"] == [p.unique_id for p in emerg]


def test_emergency_goalkeeper_has_goalkeeping_attributes():
    gk = emergency_player(3, 1, Position.GK)
    out = emergency_player(3, 2, Position.DC)
    assert gk.attributes["attributes_reflexes"] == 30 and out.attributes["attributes_reflexes"] == 5
    assert gk.is_emergency and gk.familiarity[Position.GK] == 100


def test_team_sheet_rejects_invalid_lineups():
    from services.match_engine.types import TeamSheet

    with pytest.raises(ValueError):
        TeamSheet(1, FORMATION_433[:10], team(1).starters[:10])
    with pytest.raises(ValueError):
        TeamSheet(1, FORMATION_433, team(1).starters[:10] + (team(1).starters[0],))
    with pytest.raises(ValueError):
        TeamSheet(1, (Position.DC,) * 11, team(1).starters)
