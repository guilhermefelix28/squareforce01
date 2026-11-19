"""Motor esportivo (Entrega 5): coerência dos eventos, regras do GDD §9–§16 e determinismo."""

from __future__ import annotations

import dataclasses
from collections import Counter

import pytest

from services.match_engine.engine import MatchSimulation, contextual_xg, is_big_chance, simulate
from services.match_engine.params import DEFAULT_PARAMS, POSTURES
from services.match_engine.presentation import LivePresentation
from services.match_engine.ratings import compute_ratings, man_of_the_match
from services.match_engine.stats import compute_stats
from services.match_engine.types import Event, MatchInput, PlayerRating, PostureChange
from services.match_engine.validation import validate_result
from support.match_fixtures import match, params, team

P = DEFAULT_PARAMS
SEEDS = range(1, 41)


def run(m: MatchInput, prm=P, decisions=()):
    res = simulate(m, prm, decisions)
    assert validate_result(res, m, prm) == [], validate_result(res, m, prm)
    return res


# ------------------------------------------------------------------ coerência estrutural
@pytest.mark.parametrize("seed", SEEDS)
def test_every_match_is_structurally_valid(seed):
    res = run(match(seed))
    assert res.events[0].type == "lineups" and res.events[-1].type in ("full_time", "abandoned")
    assert [e.seq for e in res.events] == list(range(1, len(res.events) + 1))  # sem duplicação


def test_goals_come_only_from_shot_events_and_match_the_score():
    for seed in SEEDS:
        res = run(match(seed))
        goals = [e for e in res.events if e.type == "goal"]
        assert (sum(1 for g in goals if g.side == 0), sum(1 for g in goals if g.side == 1)) == res.score
        for g in goals:
            prior = [e for e in res.events if e.seq < g.seq and e.type == "shot"][-1]
            assert prior.player == g.player and prior.side == g.side
            assert g.data["score"] == list(res.score) or g.data["score"][g.side] <= res.score[g.side]


def test_statistics_are_derived_from_events():
    res = run(match(3))
    assert compute_stats(res.events) == res.stats
    s = res.stats["home"]
    shots = sum(1 for e in res.events if e.type == "shot" and e.side == 0)
    assert s["shots"] == shots
    assert s["xg"] == pytest.approx(sum(e.data["xg"] for e in res.events if e.type == "shot" and e.side == 0), abs=1e-3)
    assert res.stats["home"]["possession_pct"] + res.stats["away"]["possession_pct"] == pytest.approx(100, abs=0.2)
    assert s["shots_on_target"] == res.score[0] + sum(1 for e in res.events if e.type == "save" and e.side == 1)


def test_score_is_not_predetermined():
    scores = Counter(run(match(seed)).score for seed in SEEDS)
    assert len(scores) >= 8  # placares variados com times iguais


# ------------------------------------------------------------------ determinismo
def test_same_input_reproduces_same_events():
    a, b = simulate(match(11)), simulate(match(11))
    assert a.events == b.events and a.score == b.score and a.ratings == b.ratings
    assert simulate(match(12)).events != a.events
    assert a.engine_version and a.params_version == P.version and a.seed == 11


def test_changing_parameters_changes_version_contract():
    other = params(version="outra")
    assert simulate(match(5), other).params_version == "outra"


def test_stepwise_and_presentation_speeds_reproduce_identical_events():
    decisions = [PostureChange(1800.0, 0, "ofensiva"), PostureChange(4000.0, 1, "retranca")]
    batch = simulate(match(21), P, decisions)
    step = MatchSimulation(match(21))
    for target in (300, 1799, 1800, 2500, 3999):
        step.advance_to(target)
        if target == 1800:
            step.set_posture(0, "ofensiva")
    # mesma decisão no mesmo tempo de jogo, aplicada ao vivo
    step2 = MatchSimulation(match(21), P, [PostureChange(4000.0, 1, "retranca")])
    step2.advance_to(1800.0)
    step2.set_posture(0, "ofensiva")
    t_applied = step2.t
    res_live = step2.run()
    replay = simulate(match(21), P, [PostureChange(t_applied, 0, "ofensiva"), PostureChange(4000.0, 1, "retranca")])
    assert res_live.events == replay.events
    # a apresentação em qualquer velocidade usa o mesmo motor: sem decisões, eventos idênticos
    base = simulate(match(22)).events
    for speed in ("15s", "30s", "60s", "instant"):
        live = LivePresentation(MatchSimulation(match(22)), speed)
        for screen in (1, 3, 7, 12, 200):
            live.reveal(screen)
        live.sim.advance_to(float("inf"))
        assert tuple(live.sim.events) == base, speed
    assert batch.final_postures == ("ofensiva", "retranca")


def test_posture_change_only_affects_future_events():
    plain = simulate(match(31))
    changed = simulate(match(31), P, [PostureChange(2700.0, 0, "ataque_total")])
    cut = next(e.seq for e in changed.events if e.type == "posture_change")
    assert changed.events[:cut - 1] == plain.events[:cut - 1]  # passado intocado
    assert changed.events[cut - 1].second >= 2700.0
    assert changed.events[cut:] != plain.events[cut - 1:]


def test_invalid_posture_is_rejected():
    with pytest.raises(ValueError):
        simulate(match(1), P, [PostureChange(10, 0, "suicida")])
    with pytest.raises(ValueError):
        MatchSimulation(match(1)).set_posture(1, "x")
    assert set(POSTURES) == {"retranca", "defensiva", "equilibrada", "ofensiva", "ataque_total"}


# ------------------------------------------------------------------ xG, finalizações e goleiros
def test_contextual_xg_depends_only_on_context():
    close = contextual_xg(P, "through_ball", 8, 0.9, 0.2)
    far = contextual_xg(P, "through_ball", 25, 0.9, 0.2)
    pressured = contextual_xg(P, "through_ball", 8, 0.9, 0.9)
    header = contextual_xg(P, "cross_header", 8, 0.9, 0.2)
    wide = contextual_xg(P, "through_ball", 8, 0.2, 0.2)
    assert close > far and close > pressured and close > header and close > wide
    assert contextual_xg(P, "penalty", 11, 1, 0) == P.xg_penalty
    assert 0 < far < close < 1
    assert is_big_chance(P, 0.4, 0.3) and not is_big_chance(P, 0.4, 0.9) and not is_big_chance(P, 0.1, 0.0)


SHOOTING = ("finishing", "composure", "technique", "first_touch", "heading", "long_shots", "free_kick_taking",
            "penalty_taking", "jumping_reach", "bravery")


def _conversion(level_key: str, value: int, n: int = 60):
    shots = goals = xg = 0.0
    for seed in range(n):
        home = team(1, **{k: value for k in SHOOTING}) if level_key != "gk" else team(1)
        away = team(2)
        if level_key == "gk":
            away = team(2, reflexes=value, handling=value, one_on_ones=value, positioning=value,
                         aerial_reach=value, command_of_area=value)
        res = simulate(match(seed, home, away))
        hs = [e for e in res.events if e.type == "shot" and e.side == 0]
        shots += len(hs)
        xg += sum(e.data["xg"] for e in hs)
        goals += res.score[0]
    return goals / shots, xg / shots


def test_shooter_skill_changes_conversion_not_xg():
    good, good_xg = _conversion("finishing", 90)
    bad, bad_xg = _conversion("finishing", 25)
    assert good > bad * 1.3
    assert good_xg == pytest.approx(bad_xg, rel=0.12)  # sem dupla contagem: xG não usa o finalizador


def test_goalkeeper_skill_reduces_goals_without_changing_xg():
    # amostra de 200 jogos: com 60 o ruído do xG/finalização chegava a ~13% (Entrega 9)
    vs_bad = _conversion("gk", 20, n=200)
    vs_good = _conversion("gk", 95, n=200)
    assert vs_good[0] < vs_bad[0]
    assert vs_good[1] == pytest.approx(vs_bad[1], rel=0.12)


def test_saves_are_made_by_the_defending_goalkeeper():
    for seed in range(10):
        m = match(seed)
        res = run(m)
        gk = {0: m.home.starters[0].unique_id, 1: m.away.starters[0].unique_id}
        for e in res.events:
            if e.type == "save":
                assert e.player == gk[e.side] or any(
                    x.type == "substitution" and x.player == e.player for x in res.events)


# ------------------------------------------------------------------ faltas, cartões, expulsões, lesões
def test_second_yellow_is_red_and_sent_off_player_never_acts_or_is_replaced():
    prm = params(foul_base=0.5, yellow_prob=0.7, booked_caution=1.0)
    seen_red = False
    for seed in range(10):
        m = match(seed)
        res = run(m, prm)
        for e in res.events:
            if e.type == "red_card":
                seen_red = True
                # depois da expulsão o jogador não age; `penalty_awarded` apenas cita o infrator da própria falta
                later = [x for x in res.events if x.seq > e.seq and e.player in (x.player, x.other)
                         and x.type not in ("substitution", "penalty_awarded")]
                assert not later
                assert not any(x.type == "substitution" and x.other == e.player for x in res.events)
                if e.data["second_yellow"]:
                    assert sum(1 for c in res.cards if c.player == e.player and c.color == "yellow") == 2
    assert seen_red


def test_fewer_than_seven_players_abandons_with_official_3_0():
    prm = params(foul_base=0.6, direct_red_prob=0.35)
    abandoned = 0
    for seed in range(15):
        m = match(seed)
        res = run(m, prm)
        if res.status == "abandoned":
            abandoned += 1
            loser = res.abandoned_side
            assert res.events[-1].type == "abandoned"
            assert res.official_score[1 - loser] - res.official_score[loser] >= 3
            assert res.official_score[1 - loser] >= 3
            if res.official_score != res.score:
                assert res.official_score in ((3, 0), (0, 3))
    assert abandoned > 0


def test_injuries_have_0_to_3_matches_and_injured_leave_the_pitch():
    prm = params(injury_per_contact=0.06)
    total = 0
    for seed in range(10):
        res = run(match(seed), prm)
        for inj in res.injuries:
            total += 1
            assert 0 <= inj.matches <= 3
            ev = next(e for e in res.events if e.type == "injury" and e.player == inj.player)
            nxt = res.events[ev.seq]  # evento seguinte: substituição ou saída
            assert nxt.type in ("substitution", "player_off", "abandoned") and inj.player in (nxt.other, nxt.player) or nxt.type == "abandoned"
    assert total > 0


def test_injury_without_substitutes_leaves_team_short():
    prm = params(injury_per_contact=0.08)
    m = match(4, team(1, bench_size=0), team(2, bench_size=0))
    res = run(m, prm)
    offs = [e for e in res.events if e.type == "player_off"]
    assert offs and not any(e.type == "substitution" for e in res.events)


# ------------------------------------------------------------------ substituições e desgaste
def test_at_most_five_substitutions_and_no_return():
    prm = params(fatigue_per_minute=1.5, sub_condition_threshold=80)
    for seed in range(10):
        res = run(match(seed), prm)
        for side in (0, 1):
            subs = [e for e in res.events if e.type == "substitution" and e.side == side]
            assert len(subs) <= 5
            assert [e.data["number"] for e in subs] == list(range(1, len(subs) + 1))
            off = {e.other for e in subs}
            assert not off & {e.player for e in subs}  # quem saiu não volta


def test_fatigue_grows_during_match_and_depends_on_posture():
    def final_condition(posture):
        sim = MatchSimulation(match(8, team(1, posture=posture), team(2)), params(max_substitutions=0))
        assert all(p.condition == 100 for t in sim.teams for p in t.players)  # 100% no início de cada partida
        sim.run()
        return sum(p.condition for p in sim.teams[0].players) / 11

    calm, intense = final_condition("retranca"), final_condition("ataque_total")
    assert intense < calm < 100


def test_postures_change_attack_moderately():
    def shots(posture):
        return sum(simulate(match(s, team(1, posture=posture), team(2))).stats["home"]["shots"] for s in range(40))

    ret, bal, att = shots("retranca"), shots("equilibrada"), shots("ataque_total")
    assert ret < bal < att
    assert att < ret * 2.2  # moderado: não multiplica a criação


# ------------------------------------------------------------------ força, surpresas, 0×0 e goleadas
def test_stronger_team_wins_more_but_upsets_happen():
    wins = draws_or_upsets = 0
    for seed in range(60):
        res = simulate(match(seed, team(1, level=70), team(2, level=58)))  # diferença comparável a Série A × B
        if res.score[0] > res.score[1]:
            wins += 1
        else:
            draws_or_upsets += 1
    assert wins > 30 and draws_or_upsets >= 5


def test_nil_nil_and_thrashings_are_possible():
    scores = [simulate(match(s)).score for s in range(150)]
    assert any(s == (0, 0) for s in scores)
    lopsided = [simulate(match(s, team(1, level=80), team(2, level=40))).score for s in range(60)]
    assert any(abs(a - b) >= 4 for a, b in lopsided)


# ------------------------------------------------------------------ notas e Craque
def test_ratings_in_range_with_one_decimal_and_motm_is_best():
    for seed in range(15):
        res = run(match(seed))
        for r in res.ratings:
            assert 0 <= r.rating <= 10 and r.display == round(r.display, 1)
        best = max(res.ratings, key=lambda r: (r.display, r.rating))
        motm = next(r for r in res.ratings if r.player == res.man_of_the_match)
        assert (motm.display, motm.rating) == (best.display, best.rating)


def test_ratings_depend_on_events_not_on_overall():
    m = match(9)
    res = simulate(m)
    stronger = dataclasses.replace(m, home=team(1, level=95))  # atributos diferentes, MESMOS eventos
    assert compute_ratings(res.events, stronger, P, res.score) == list(res.ratings)


def test_goal_raises_rating_and_red_card_lowers_it():
    lineup = Event(1, 0, 1, "lineups", data={"home": [(1, "STC"), (2, "GK")], "away": [(3, "GK"), (4, "DC")],
                                             "home_bench": [], "away_bench": []})
    evs = [lineup,
           Event(2, 100, 1, "shot", 0, 1, None, {"xg": 0.3}),
           Event(3, 101, 1, "goal", 0, 1, None, {"xg": 0.3}),
           Event(4, 200, 1, "red_card", 1, 4, None, {"second_yellow": False}),
           Event(5, 5700, 2, "full_time")]
    ratings = {r.player: r for r in compute_ratings(evs, match(1), P, (1, 0))}
    assert ratings[1].rating > 7 and ratings[4].rating < 5
    assert ratings[3].rating < P.rating_base  # goleiro sofreu gol e perdeu
    assert man_of_the_match(ratings.values()) == 1


def test_motm_tie_breaks_internal_precision_then_decisive_impact():
    a = PlayerRating(1, 0, 7.84, 7.8, 90, 0.0)
    b = PlayerRating(2, 1, 7.81, 7.8, 90, 2.0)
    assert man_of_the_match([a, b]) == 1  # mesma nota exibida: maior precisão interna
    c = PlayerRating(3, 0, 7.81, 7.8, 90, 1.0)
    assert man_of_the_match([b, c]) == 2  # empate total na nota: impacto decisivo


def test_short_cameo_counts_less_than_full_match():
    res = run(match(14), params(fatigue_per_minute=1.6, sub_condition_threshold=85))
    subs_on = {e.player for e in res.events if e.type == "substitution"}
    for r in res.ratings:
        if r.player in subs_on:
            assert r.minutes < 60


# ------------------------------------------------------------------ Copa: pênaltis sem prorrogação
def test_knockout_draw_goes_to_penalties_recorded_separately():
    found = 0
    for seed in range(60):
        m = dataclasses.replace(match(seed), knockout=True)
        res = run(m)
        assert res.winner_side is not None  # eliminatório sempre tem vencedor
        if res.shootout:
            found += 1
            assert res.score[0] == res.score[1]  # pênaltis não entram no placar nem na artilharia
            assert res.shootout[0] != res.shootout[1]
            assert res.winner_side == (0 if res.shootout[0] > res.shootout[1] else 1)
            assert sum(1 for e in res.events if e.type == "goal") == sum(res.score)
            assert res.stats["home"]["goals"] + res.stats["away"]["goals"] == sum(res.score)
            assert not any(e.type == "goal" for e in res.events if e.seq > next(x.seq for x in res.events if x.type == "full_time"))
        else:
            assert res.score[0] != res.score[1]
    assert found > 0


def test_league_draw_has_no_penalties():
    for seed in range(30):
        res = run(match(seed))
        assert res.shootout is None
        if res.score[0] == res.score[1]:
            assert res.winner_side is None


# ------------------------------------------------------------------ desgaste do goleiro (decisão DR-03)
def test_goalkeepers_tire_much_less_than_outfield_players():
    """Decisão do responsável (2026-11-19): goleiros cansam pouco durante o jogo."""
    from squadforce_shared.domain.positions import Position

    assert P.gk_fatigue_multiplier == 0.35
    gk_final, outfield = [], []
    for seed in range(1, 21):
        sim = MatchSimulation(match(seed))
        sim.advance_to(10_000)
        for team_state in sim.teams:
            for pl in team_state.players:
                if pl.active and pl.slot is Position.GK:
                    gk_final.append(pl.condition)
                elif pl.active:
                    outfield.append(pl.condition)
    assert min(gk_final) >= 85
    assert sum(gk_final) / len(gk_final) > sum(outfield) / len(outfield) + 10
