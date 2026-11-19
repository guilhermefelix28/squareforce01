"""Execução de Liga e Copa: snapshot, partidas paralelas, consolidação atômica e encerramento (GDD §17–§21)."""

from __future__ import annotations

import math
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from services.competition.season import SeasonError, match_seed
from services.competition.worker import FixtureOutcome, play_fixture
from services.match_engine.types import PostureChange
from squadforce_shared.domain.competition import LeagueRounds
from support.season_fixtures import USER, make_season, run_all


def summary(season):
    return [(pm.match_id, pm.result.score, pm.result.shootout, pm.result.winner_side, len(pm.result.events))
            for pm in season.state.history]


# ------------------------------------------------------------------ Liga
@pytest.mark.parametrize("n", [2, 3, 4, 5, 7, 8])
@pytest.mark.parametrize("mode", [LeagueRounds.SINGLE, LeagueRounds.DOUBLE])
def test_league_complete_any_size(n, mode):
    s = make_season("league", n, rounds=mode)
    run_all(s)
    per_club = (n - 1) * (1 if mode == LeagueRounds.SINGLE else 2)
    assert len(s.state.history) == n * per_club // 2
    table = s.standings()
    assert all(r.played == per_club for r in table)
    assert sum(r.wins for r in table) == sum(r.losses for r in table)
    assert sum(r.goals_for for r in table) == sum(r.goals_against for r in table)
    pts = sum(r.points for r in table)
    decisive = sum(1 for pm in s.state.history if pm.result.official_score[0] != pm.result.official_score[1])
    assert pts == 3 * decisive + 2 * (len(s.state.history) - decisive)
    ids = [pm.match_id for pm in s.state.history]
    assert len(ids) == len(set(ids))  # nenhum resultado consolidado duas vezes


def test_league_with_20_clubs_double_round_completes():
    s = make_season("league", 20, rounds=LeagueRounds.DOUBLE, seed=11)
    run_all(s, workers=8)
    assert len(s.state.history) == 380
    assert all(r.played == 38 for r in s.standings())
    champ, tied = s.champion()
    assert (champ is None) == bool(tied)


def test_byes_do_not_count_as_match_nor_reduce_absences():
    s = make_season("league", 5)
    with ThreadPoolExecutor(2) as ex:
        bye = s.snapshot.byes[0]
        member = s.squads[bye][0].unique_id
        s.state.ledger.injuries[member] = 2  # afastado antes da rodada de folga
        s.play(ex)
        assert s.state.club_matches[bye] == 0
        assert s.state.records[bye].played == 0
        assert s.state.ledger.injuries[member] == 2  # folga não cumpre afastamento


def test_standings_only_change_on_consolidation_and_snapshot_is_shared():
    s = make_season("league", 6)
    snap = s.snapshot
    assert {t.snapshot_id for t in snap.tasks} == {snap.snapshot_id}
    seen = []

    def runner(task):
        seen.append(sum(r.played for r in s.standings()))  # classificação oficial durante a rodada
        return play_fixture(task)

    s.runner = runner
    with ThreadPoolExecutor(3) as ex:
        s.play(ex)
    assert seen == [0, 0, 0]
    assert sum(r.played for r in s.standings()) == 6


def test_injuries_and_suspensions_are_consolidated_and_respected():
    s = make_season("league", 6, rounds=LeagueRounds.DOUBLE, seed=3)
    with ThreadPoolExecutor(3) as ex:
        while s.phase != "finished":
            snap = s.snapshot
            out = {i: n for i, n in snap.injuries}
            susp = {p for _, p, n in snap.suspensions if n > 0}
            for t in snap.tasks:
                for sheet in (t.home, t.away):
                    used = {p.unique_id for p in (*sheet.starters, *sheet.bench)}
                    assert not (used & set(out)), "lesionado escalado"
                    assert not (used & susp), "suspenso escalado"
            s.play(ex)
            s.advance()
    hist = s.state.ledger.history
    assert any(h["type"] == "injury" for h in hist) or any(h["type"].endswith("_card") for h in hist)


# ------------------------------------------------------------------ Copa
@pytest.mark.parametrize("n", [2, 4, 8, 16, 32])
def test_cup_complete_bracket(n):
    s = make_season("cup", n, seed=n)
    run_all(s, workers=8)
    assert len(s.state.history) == n - 1
    champ, _ = s.champion()
    assert champ in range(1, n + 1)
    # sem duplicação: cada clube é eliminado no máximo uma vez; só o campeão não é eliminado
    losers = [pm.away if pm.result.winner_side == 0 else pm.home for pm in s.state.history]
    assert len(losers) == len(set(losers)) == n - 1 and champ not in losers
    for pm in s.state.history:
        assert pm.result.winner_side is not None
        if pm.result.score[0] == pm.result.score[1]:
            assert pm.result.shootout is not None  # empate => pênaltis, sem prorrogação
        else:
            assert pm.result.shootout is None
        assert max(e.second for e in pm.result.events if e.type != "shootout_kick") < 110 * 60


def test_cup_penalties_recorded_separately_from_goals():
    s = make_season("cup", 32, seed=5)
    run_all(s, workers=8)
    shootouts = [pm for pm in s.state.history if pm.result.shootout]
    assert shootouts, "esperava ao menos uma disputa de pênaltis em 31 jogos"
    goals = sum(pm.result.score[0] + pm.result.score[1] for pm in s.state.history)
    assert sum(p.goals for p in s.state.players.values()) == goals  # pênaltis da disputa não entram na artilharia
    for pm in shootouts:
        b = next(m for r in s.state.bracket.rounds for m in r.matches if m.id == pm.match_id)
        assert b.decided_by == "penalties"


def test_user_eliminated_cup_continues_until_final():
    for seed in range(1, 40):
        s = make_season("cup", 8, seed=seed, levels={USER: 35})
        with ThreadPoolExecutor(4) as ex:
            s.play(ex)
            if s.eliminated(USER):
                break
    else:
        pytest.fail("o clube fraco do usuário nunca foi eliminado na 1ª fase")
    assert s.phase == "awaiting_advance"  # avanço manual, mesmo eliminado
    with ThreadPoolExecutor(4) as ex:
        while s.phase != "finished":
            s.advance()
            if s.phase == "finished":
                break
            assert all(USER not in (t.home_club, t.away_club) for t in s.snapshot.tasks)
            s.play(ex)
    assert s.champion()[0] not in (None, USER)
    assert len(s.state.history) == 7


# ------------------------------------------------------------------ paralelo, falhas, determinismo
def test_parallel_processes_match_threads_and_order_independence():
    a = make_season("league", 6, seed=9)
    with ProcessPoolExecutor(max_workers=2) as ex:
        while a.phase != "finished":
            a.play(ex)
            a.advance()
    b = make_season("league", 6, seed=9)
    run_all(b, workers=1)
    assert summary(a) == summary(b)


def test_seed_is_per_match_and_stable():
    assert match_seed(1, "liga", "L-R01-M01") == match_seed(1, "liga", "L-R01-M01")
    assert match_seed(1, "liga", "L-R01-M01") != match_seed(1, "liga", "L-R01-M02")
    s = make_season("league", 8)
    assert len({t.seed for t in s.snapshot.tasks}) == 4


def test_deterministic_reprocessing():
    a, b = make_season("cup", 16, seed=4), make_season("cup", 16, seed=4)
    run_all(a, workers=8)
    run_all(b, workers=2)
    assert summary(a) == summary(b)
    assert a.champion() == b.champion()


def test_failed_parallel_match_blocks_whole_round_and_retry_is_identical():
    calls = {"n": 0}

    def flaky(task):
        if task.match_id.endswith("M02") and calls["n"] == 0:
            calls["n"] += 1
            raise RuntimeError("queda do processo")
        return play_fixture(task)

    s = make_season("league", 6, seed=21, runner=flaky)
    ref = make_season("league", 6, seed=21)
    with ThreadPoolExecutor(3) as ex:
        with pytest.raises(SeasonError) as err:
            s.play(ex)
        assert err.value.code == "ROUND_FAILED" and err.value.details["failed"] == ["L-R01-M02"]
        assert s.state.history == [] and all(r.played == 0 for r in s.standings())  # nada consolidado
        assert s.phase == "ready"
        played = s.retry_failed(ex)  # só a falha é repetida, com a mesma tarefa
        ref.play(ex)
    assert calls["n"] == 1
    assert [(p.match_id, p.result.events) for p in played] == [(p.match_id, p.result.events) for p in ref.last_round]


def test_invalid_result_is_rejected():
    def bad(task):
        out = play_fixture(task)
        return FixtureOutcome(out.snapshot_id, out.match_id, out.result, None, ("placar divergente",))

    s = make_season("league", 4, runner=bad)
    with ThreadPoolExecutor(2) as ex, pytest.raises(SeasonError):
        s.play(ex)
    assert s.state.history == []


def test_identity_mismatch_is_rejected():
    def wrong(task):
        out = play_fixture(task)
        return FixtureOutcome("outro-snapshot", out.match_id, out.result)

    s = make_season("league", 4, runner=wrong)
    with ThreadPoolExecutor(2) as ex, pytest.raises(SeasonError) as err:
        s.play(ex)
    assert err.value.code == "CONSOLIDATION_IDENTITY"
    assert s.state.history == []


def test_consolidation_happens_once_and_advance_is_manual():
    s = make_season("league", 4)
    with ThreadPoolExecutor(2) as ex:
        s.play(ex)
        with pytest.raises(SeasonError):
            s.play(ex)  # mesma rodada não é jogada nem consolidada de novo
        assert len(s.state.history) == 2
        assert s.phase == "awaiting_advance" and s.round_index == 0  # não avança sozinho
        s.advance()
        assert s.round_index == 1 and s.phase == "ready"
        with pytest.raises(SeasonError):
            s.advance()


def test_user_decisions_are_part_of_the_fixed_task():
    s = make_season("league", 4, seed=2)
    mid = next(t.match_id for t in s.snapshot.tasks if USER in (t.home_club, t.away_club))
    s.set_user_decisions(mid, [PostureChange(600, 0 if s.snapshot.tasks[0].home_club == USER else 1, "ofensiva")])
    task = next(t for t in s.snapshot.tasks if t.match_id == mid)
    assert task.user_decisions
    user_side_ctx = task.home_context if task.home_club == USER else task.away_context
    assert user_side_ctx is None  # o lado do usuário não tem controlador automático


# ------------------------------------------------------------------ fim de competição
def test_awards_and_campaign():
    s = make_season("league", 6, rounds=LeagueRounds.DOUBLE, seed=13)
    run_all(s)
    aw = s.awards()
    players = s.state.players.values()
    assert aw["top_scorers"][0].goals == max(p.goals for p in players)
    assert aw["top_assists"][0].assists == max(p.assists for p in players)
    assert aw["most_motm"][0].motm == max(p.motm for p in players)
    total_motm = sum(p.motm for p in players)
    assert total_motm == sum(1 for pm in s.state.history if pm.result.man_of_the_match is not None)
    for p in aw["best_average"]:
        assert p.appearances >= math.ceil(s.state.club_matches[p.club] / 2)
    eligible = [p for p in players if p.appearances >= math.ceil(s.state.club_matches[p.club] / 2)]
    assert aw["best_average"][0].average_rating == pytest.approx(max(p.average_rating for p in eligible))
    camp = s.campaign(USER)
    assert len(camp) == 10
    rec = s.state.records[USER]
    assert sum(c["outcome"] == "V" for c in camp) == rec.wins
    assert sum(c["goals_for"] for c in camp) == rec.goals_for


def test_errors_for_invalid_setup():
    with pytest.raises(SeasonError):
        from services.competition.season import Season
        from support.season_fixtures import squad
        from services.competition.planner import build_cup_bracket
        import random
        Season(competition_id="c", structure=build_cup_bracket([1, 2], random.Random(1)),
               squads={1: squad(1), 2: squad(2)}, names={}, user_club=1, personalities={2: "balanced"},
               formations=(), seed=1)


def test_bot_matches_do_not_depend_on_the_user_match():
    """Confrontos simultâneos são independentes: mudar as decisões do usuário não altera os jogos entre bots."""
    a, b = make_season("league", 6, seed=17), make_season("league", 6, seed=17)
    task = next(t for t in b.snapshot.tasks if USER in (t.home_club, t.away_club))
    side = 0 if task.home_club == USER else 1
    b.set_user_decisions(task.match_id, [PostureChange(300, side, "ataque_total")])
    with ThreadPoolExecutor(3) as ex:
        ra, rb = a.play(ex), b.play(ex)
    others = lambda r: [(p.match_id, p.result.events) for p in r if USER not in (p.home, p.away)]
    assert others(ra) == others(rb)
    mine = lambda r: next(p.result.events for p in r if USER in (p.home, p.away))
    assert mine(ra) != mine(rb)


def test_failure_during_consolidation_leaves_state_untouched(monkeypatch):
    s = make_season("league", 6, seed=8)
    calls = {"n": 0}
    original = s._accumulate

    def boom(*args):
        calls["n"] += 1
        if calls["n"] == 2:  # falha no meio da aplicação dos resultados
            raise RuntimeError("falha crítica")
        return original(*args)

    monkeypatch.setattr(s, "_accumulate", boom)
    with ThreadPoolExecutor(3) as ex, pytest.raises(RuntimeError):
        s.play(ex)
    assert s.state.history == [] and all(r.played == 0 for r in s.standings())
    assert sum(p.appearances for p in s.state.players.values()) == 0
    assert s.state.ledger.history == []
    assert s.snapshot.snapshot_id not in s.consolidated_snapshots


def test_cup_final_decided_on_penalties():
    """Final empatada nos 90 min: campeão é o vencedor dos pênaltis, que não contam como gols."""
    for seed in range(1, 200):
        s = make_season("cup", 2, seed=seed)
        run_all(s, workers=1)
        final = s.state.history[-1]
        if final.result.shootout:
            break
    else:
        pytest.fail("nenhuma final foi aos pênaltis em 199 sementes")
    r = final.result
    assert r.score[0] == r.score[1]
    winner = final.home if r.shootout[0] > r.shootout[1] else final.away
    assert s.champion()[0] == winner == s.state.bracket.champion_club_uid
    assert s.state.bracket.rounds[-1].matches[0].decided_by == "penalties"
    assert sum(p.goals for p in s.state.players.values()) == sum(r.score)
