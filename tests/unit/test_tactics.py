"""IA tática dos bots (Entrega 6): modelo de utilidade, decisões por situação, estabilidade, escalação."""

from __future__ import annotations

import dataclasses

import pytest

from services.bot_ai.tactics import (
    CompetitionSituation,
    OpponentHistory,
    PreMatchContext,
    TacticalBot,
    choose_lineup,
    league_situation,
    outcome_probabilities,
)
from services.match_engine.availability import AvailabilityLedger
from services.match_engine.calibration import FORMATION_433, FORMATION_442, FORMATION_532
from services.match_engine.engine import MatchSimulation, simulate
from services.match_engine.params import POSTURES
from services.match_engine.types import OwnPlayerState, TacticalObservation
from services.match_engine.validation import validate_result
from squadforce_shared.domain.positions import Position
from support.match_fixtures import match, player, team

ORD = {p: i for i, p in enumerate(POSTURES)}  # 0 = retranca ... 4 = ataque_total


def obs(remaining=0.5, gf=0, ga=0, players_for=11, players_against=11, posture="equilibrada", opp="equilibrada",
        condition=90.0, level=60, triggers=(), xg_for=None, xg_against=None, second=None, knockout=False):
    squad = team(1, level=level)
    own = tuple(OwnPlayerState(p.unique_id, s, condition, 0, p) for p, s in zip(squad.starters, squad.formation))
    own = own[:players_for]
    elapsed = 1 - remaining
    return TacticalObservation(
        side=0, second=second if second is not None else elapsed * 5700, period=1 if elapsed < 0.5 else 2,
        remaining_fraction=remaining, goals_for=gf, goals_against=ga, players_for=players_for,
        players_against=players_against, own_posture=posture, opponent_posture=opp, own_players=own,
        bench=squad.bench, substitutions_left=5,
        stats_for={"xg": 1.15 * elapsed if xg_for is None else xg_for},
        stats_against={"xg": 1.15 * elapsed if xg_against is None else xg_against},
        triggers=tuple(triggers), knockout=knockout,
    )


def bot(situation=None, personality="balanced", opponent=OpponentHistory()):
    return TacticalBot(PreMatchContext(situation or CompetitionSituation.league(), personality, opponent))


def best(b: TacticalBot, o: TacticalObservation) -> str:
    u = b.utilities(o)
    return max(POSTURES, key=lambda p: (u[p], -ORD[p]))


# ------------------------------------------------------------------ modelo probabilístico
def test_outcome_probabilities_are_a_distribution():
    for diff, f, a in [(0, 1.0, 1.0), (1, 0.2, 0.5), (-2, 2.0, 0.1), (0, 0.0, 0.0)]:
        w, d, l = outcome_probabilities(diff, f, a)
        assert w + d + l == pytest.approx(1.0)
    assert outcome_probabilities(1, 0, 0) == (1.0, 0.0, 0.0)
    w1, _, _ = outcome_probabilities(0, 1.5, 1.0)
    w2, _, _ = outcome_probabilities(0, 1.0, 1.0)
    assert w1 > w2


def test_rates_use_posture_multipliers_and_numbers():
    b = bot()
    o = obs()
    f_bal, a_bal = b.rates(o, "equilibrada")
    f_att, a_att = b.rates(o, "ataque_total")
    f_ret, a_ret = b.rates(o, "retranca")
    assert f_att > f_bal > f_ret and a_att > a_bal > a_ret
    f10, a10 = b.rates(obs(players_for=10), "equilibrada")
    assert f10 < f_bal and a10 > a_bal


# ------------------------------------------------------------------ situações obrigatórias
def test_losing_near_the_end_goes_on_the_attack():
    assert ORD[best(bot(), obs(remaining=0.1, gf=0, ga=1))] >= ORD["ofensiva"]


def test_winning_by_minimum_margin_late_protects_the_lead():
    assert ORD[best(bot(), obs(remaining=0.12, gf=1, ga=0))] <= ORD["defensiva"]


def test_red_card_makes_the_team_more_cautious_when_ahead():
    eleven = best(bot(), obs(remaining=0.4, gf=1, ga=0))
    ten = best(bot(), obs(remaining=0.4, gf=1, ga=0, players_for=10))
    assert ORD[ten] <= ORD[eleven]
    u = bot().utilities(obs(remaining=0.4, gf=1, ga=0, players_for=10))
    assert u["retranca"] > u["ataque_total"]


def test_heavy_fatigue_penalizes_intense_postures():
    fresh = bot().utilities(obs(remaining=0.3, gf=0, ga=1, condition=95))
    tired = bot().utilities(obs(remaining=0.3, gf=0, ga=1, condition=40))
    assert tired["ataque_total"] - tired["equilibrada"] < fresh["ataque_total"] - fresh["equilibrada"]


def test_must_win_title_race_attacks_when_drawing():
    o = obs(remaining=0.25)
    must = best(bot(CompetitionSituation.must_win()), o)
    normal = best(bot(CompetitionSituation.league()), o)
    assert ORD[must] >= ORD["ofensiva"] and ORD[must] >= ORD[normal]


def test_avoid_defeat_protects_the_draw():
    o = obs(remaining=0.25)
    avoid = best(bot(CompetitionSituation.avoid_defeat()), o)
    must = best(bot(CompetitionSituation.must_win()), o)
    assert ORD[avoid] <= ORD["equilibrada"] < ORD[must]


def test_cup_elimination_risk_trailing_attacks():
    assert ORD[best(bot(CompetitionSituation.cup()), obs(remaining=0.15, gf=0, ga=1, knockout=True))] >= ORD["ofensiva"]


def test_cup_draw_superior_presses_inferior_waits_for_penalties():
    strong = best(bot(CompetitionSituation.cup()), obs(remaining=0.2, level=75, knockout=True))
    weak = best(bot(CompetitionSituation.cup()), obs(remaining=0.2, level=45, knockout=True))
    assert ORD[strong] > ORD[weak]


def test_much_stronger_and_much_weaker_teams_choose_different_starts():
    strong_ctx = PreMatchContext(CompetitionSituation.league(), "balanced",
                                 OpponentHistory(matches=5, goals_for=3.0, goals_against=12.0))
    weak_ctx = PreMatchContext(CompetitionSituation.league(), "balanced",
                               OpponentHistory(matches=5, goals_for=12.0, goals_against=3.0))
    strong_sheet = team(1, level=78)
    weak_sheet = team(1, level=45)
    s = TacticalBot(strong_ctx).initial_posture(list(zip(strong_sheet.starters, strong_sheet.formation)))
    w = TacticalBot(weak_ctx).initial_posture(list(zip(weak_sheet.starters, weak_sheet.formation)))
    assert ORD[s] >= ORD[w]


PERSONALITIES = ("aggressive", "balanced", "opportunist", "conservative")


def test_personality_moderately_shifts_risk_appetite():
    # situações claras: todas as personalidades concordam
    for o, side in ((obs(remaining=0.12, gf=0, ga=1), "attack"), (obs(remaining=0.15, gf=1, ga=0), "defend"),
                    (obs(remaining=0.5, gf=0, ga=1), "attack")):
        picks = {best(bot(personality=p), o) for p in PERSONALITIES}
        assert all((ORD[x] > 2) if side == "attack" else (ORD[x] < 2) for x in picks), picks
    # situação limítrofe (empate aos 70'): a personalidade desloca a decisão, de forma moderada
    o = obs(remaining=0.25)
    picks = {p: ORD[best(bot(personality=p), o)] for p in PERSONALITIES}
    assert picks["aggressive"] >= picks["balanced"] >= picks["conservative"]
    assert max(picks.values()) - min(picks.values()) <= 2


def test_opportunist_presses_against_ten_men():
    o = obs(remaining=0.4, players_against=10)
    assert ORD[best(bot(personality="opportunist"), o)] >= ORD[best(bot(personality="balanced"), o)]


def test_league_situation_rule():
    assert league_situation(40, 43, None, 2).label == "precisa_vencer"
    assert league_situation(30, 50, 28, 2).label == "evitar_derrota"
    assert league_situation(30, 50, 10, 10).label == "liga"


# ------------------------------------------------------------------ estabilidade e histerese
def test_stability_interval_and_decisive_exceptions():
    b = bot()
    first = b.decide(obs(remaining=0.3, gf=0, ga=1, second=4000))
    assert first is not None
    # nova avaliação 2 min depois, sem acontecimento decisivo: não troca
    assert b.decide(obs(remaining=0.28, gf=1, ga=1, posture=first, second=4120)) is None
    # com gol (acontecimento decisivo) a troca pode ocorrer imediatamente
    after_goal = b.decide(obs(remaining=0.28, gf=1, ga=1, posture=first, second=4120, triggers=("goal_for",)))
    assert after_goal is None or after_goal != first


def test_small_gains_do_not_trigger_changes():
    b = bot()
    assert b.decide(obs(remaining=0.9, second=600)) is None  # 0 × 0 cedo: ganho pequeno
    u = b.utilities(obs(remaining=0.9))
    assert max(u.values()) - u["equilibrada"] < b.tp.min_benefit * (b.tp.late_scale_floor + 0.9)


def test_hysteresis_makes_reverting_harder():
    b = bot()
    b.previous, b.last_change = "equilibrada", 3000.0
    o = obs(remaining=0.4, posture="ofensiva", second=3700, triggers=("goal_for",))
    u = b.utilities(o)
    gain = u["equilibrada"] - u["ofensiva"]
    threshold = (b.tp.min_benefit + b.tp.hysteresis) * (b.tp.late_scale_floor + 0.4)
    decision = b.decide(o)
    if gain < threshold:
        assert decision != "equilibrada"


# ------------------------------------------------------------------ partidas completas
def _controllers(personalities=("balanced", "balanced"), situations=None):
    situations = situations or (CompetitionSituation.league(), CompetitionSituation.league())
    return {i: TacticalBot(PreMatchContext(situations[i], personalities[i])) for i in (0, 1)}


def test_decisions_are_deterministic():
    a = simulate(match(5), controllers=_controllers())
    b = simulate(match(5), controllers=_controllers())
    assert a.events == b.events


def test_passive_controller_does_not_touch_engine_probabilities():
    class Passive:
        eval_interval = 120.0

        def decide(self, obs):
            return None

        def substitution_bias(self, obs):
            return None

    for seed in (1, 2, 3):
        assert simulate(match(seed), controllers={0: Passive(), 1: Passive()}).events == simulate(match(seed)).events


def test_no_excessive_changes_and_valid_matches_with_bots():
    for seed in range(25):
        m = match(seed)
        sim = MatchSimulation(m, controllers=_controllers(("aggressive", "conservative")))
        res = sim.run()
        assert validate_result(res, m) == []
        for side in (0, 1):
            ctrl = sim.controllers[side]
            changes = ctrl.decisions
            assert len(changes) <= 8
            for (t1, *_), (t2, *_rest) in zip(changes, changes[1:]):
                decisive = any(e.type in ("goal", "red_card", "player_off") and t1 <= e.second <= t2 for e in res.events)
                assert decisive or t2 - t1 >= ctrl.tp.stability_seconds
        pcs = [e for e in res.events if e.type == "posture_change"]
        assert len(pcs) == sum(len(sim.controllers[s].decisions) for s in (0, 1))


def test_observation_exposes_only_own_team_and_this_match():
    sim = MatchSimulation(match(3))
    sim.advance_to(1200)
    o = sim.observation(0)
    own_ids = {p.unique_id for p in match(3).home.starters} | {p.unique_id for p in match(3).home.bench}
    assert {p.unique_id for p in o.own_players} <= own_ids and {b.unique_id for b in o.bench} <= own_ids
    fields = set(TacticalObservation.__dataclass_fields__)
    assert not fields & {"rng", "seed", "events", "decisions", "opponent_players", "opponent_bench"}


def test_bot_cannot_see_user_future_decisions():
    from services.match_engine.types import PostureChange

    seen: list[str] = []

    class Spy:
        eval_interval = 300.0

        def decide(self, obs):
            seen.append(obs.opponent_posture)
            return None

        def substitution_bias(self, obs):
            return None

    simulate(match(8), decisions=[PostureChange(4000.0, 0, "ataque_total")], controllers={1: Spy()})
    # até o minuto ~66 o bot só vê a postura atual (equilibrada); a decisão futura do usuário não vaza
    assert seen[0] == "equilibrada" and "ataque_total" in seen


def test_tactical_substitutions_are_legal():
    for seed in range(15):
        m = match(seed)
        res = simulate(m, controllers=_controllers(("aggressive", "aggressive")))
        assert validate_result(res, m) == []
        subs = [e for e in res.events if e.type == "substitution"]
        for side in (0, 1):
            assert len([e for e in subs if e.side == side]) <= 5
        assert len({e.player for e in subs}) == len(subs)  # ninguém entra duas vezes


# ------------------------------------------------------------------ formação e escalação
def ctx(**kw):
    return PreMatchContext(CompetitionSituation.league(), "balanced", **kw)


def squad_for_tests():
    s = team(4)
    return list(s.starters) + list(s.bench) + [player(480 + i, p) for i, p in enumerate(
        [Position.DC, Position.DC, Position.DM, Position.MC, Position.STC, Position.DR, Position.DL])]


def test_lineup_excludes_unavailable_and_respects_formation():
    squad = squad_for_tests()
    led = AvailabilityLedger()
    led.injuries[squad[0].unique_id] = 2  # goleiro titular lesionado
    led.suspensions[("liga", squad[8].unique_id)] = 1
    choice = choose_lineup(4, squad, [FORMATION_433, FORMATION_442], ctx(), led, "liga")
    chosen = {p.unique_id for p in (*choice.sheet.starters, *choice.sheet.bench)}
    assert squad[0].unique_id not in chosen and squad[8].unique_id not in chosen
    assert choice.sheet.formation in (FORMATION_433, FORMATION_442)
    assert choice.sheet.starters[choice.sheet.formation.index(Position.GK)].natural_position is Position.GK
    assert len(choice.sheet.bench) <= 7 and not any(p.is_emergency for p in choice.sheet.starters)


def test_lineup_prefers_positional_fit_over_raw_attributes():
    gk = player(901, Position.GK, level=60)
    star = player(902, Position.STC, level=85)  # atributos altos, mas não é goleiro
    others = [player(903 + i, p) for i, p in enumerate(FORMATION_433[1:])]
    choice = choose_lineup(9, [gk, star, *others], [FORMATION_433], ctx())
    assert choice.sheet.starters[0].unique_id == 901


def test_recent_performance_breaks_ties():
    a, b = player(951, Position.STC), player(952, Position.STC)
    base = [player(960 + i, p) for i, p in enumerate(FORMATION_433[:-1])]
    f = FORMATION_433[:-1] + (Position.STC,)
    pick = lambda r: {p.unique_id for p in choose_lineup(9, [*base, a, b], [f], ctx(), recent_ratings=r).sheet.starters}
    assert 952 in pick({951: 5.6, 952: 7.4}) and 951 in pick({951: 7.6, 952: 5.5})


def test_reference_formation_and_opponent_history_shape_the_choice():
    squad = squad_for_tests()
    neutral = choose_lineup(4, squad, [FORMATION_433, FORMATION_532], ctx(), reference_formation=FORMATION_532)
    assert neutral.sheet.formation == FORMATION_532
    strong_attack = OpponentHistory(matches=6, goals_for=18.0, goals_against=4.0)
    weak_attack = OpponentHistory(matches=6, goals_for=2.0, goals_against=15.0)
    s1 = choose_lineup(4, squad, [FORMATION_433, FORMATION_532], ctx(opponent=strong_attack)).formation_scores
    s2 = choose_lineup(4, squad, [FORMATION_433, FORMATION_532], ctx(opponent=weak_attack)).formation_scores
    assert (s1[FORMATION_532] - s1[FORMATION_433]) > (s2[FORMATION_532] - s2[FORMATION_433])


def test_emergency_players_only_below_eleven_available():
    few = [player(990 + i, p) for i, p in enumerate(FORMATION_433[:9])]
    choice = choose_lineup(9, few, [FORMATION_433], ctx())
    assert sum(p.is_emergency for p in choice.sheet.starters) == 2
    full = choose_lineup(4, squad_for_tests(), [FORMATION_433], ctx())
    assert not any(p.is_emergency for p in full.sheet.starters)


def test_no_formations_is_an_explicit_error():
    with pytest.raises(ValueError, match="Nenhuma formação"):
        choose_lineup(1, squad_for_tests(), [], ctx())


def test_full_match_with_bot_lineups_is_valid():
    sa = choose_lineup(1, list(team(1).starters) + list(team(1).bench), [FORMATION_433, FORMATION_442], ctx()).sheet
    sb = choose_lineup(2, list(team(2, level=55).starters) + list(team(2, level=55).bench), [FORMATION_433, FORMATION_532], ctx()).sheet
    m = dataclasses.replace(match(1), home=sa, away=sb)
    res = simulate(m, controllers=_controllers())
    assert validate_result(res, m) == []
