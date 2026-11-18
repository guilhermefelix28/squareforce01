"""Planejamento de Liga e Copa (Entrega 2): seleção, calendário, chaveamento e progressão estrutural.

Cada cenário é verificado de forma INDEPENDENTE do validador interno (contagens recalculadas aqui),
e também se confirma que o validador rejeita estruturas corrompidas.
"""

from __future__ import annotations

import math
import random
from collections import Counter

import pytest

from services.competition.planner import (
    PlanningError,
    build_cup_bracket,
    build_league_schedule,
    draw_cup_participants,
    pending_cup_matches,
    plan_competition,
    register_cup_winner,
    select_league_participants,
    validate_cup_bracket,
    validate_league_schedule,
)
from squadforce_shared.contracts import CompetitionConfig
from squadforce_shared.domain.competition import EligibleClub, LeagueRounds

LEAGUE_SIZES = [2, 3, 5, 7, 10, 19, 20]
CUP_SIZES = [2, 4, 8, 16, 32]
SEEDS = [0, 1, 7, 42, 2026]
# 40 clubes como no catálogo real: 1..20 Série A, 21..40 Série B
ELIGIBLE = [EligibleClub(uid, "A" if uid <= 20 else "B") for uid in range(1, 41)]
DIV = {c.club_uid: c.division for c in ELIGIBLE}


def league(n: int, mode: LeagueRounds, seed: int, user: int = 25):
    rng = random.Random(seed)
    participants = select_league_participants(user, ELIGIBLE, n, rng)
    return participants, build_league_schedule(participants, mode, rng)


# ================================================================== Liga
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("mode", [LeagueRounds.SINGLE, LeagueRounds.DOUBLE])
@pytest.mark.parametrize("n", LEAGUE_SIZES)
def test_league_schedule_invariants(n, mode, seed):
    participants, s = league(n, mode, seed)
    turns = 1 if mode is LeagueRounds.SINGLE else 2
    matches = [m for r in s.rounds for m in r.matches]

    # inclusão do usuário, sem duplicações
    assert participants[0] == 25 and len(set(participants)) == n == len(s.participants)

    # quantidade de partidas e rodadas
    assert len(matches) == s.total_matches == n * (n - 1) // 2 * turns
    rounds_per_turn = n - 1 if n % 2 == 0 else n
    assert len(s.rounds) == s.total_rounds == rounds_per_turn * turns
    assert all(len(r.matches) == n // 2 for r in s.rounds)
    assert [r.turn for r in s.rounds] == [1] * rounds_per_turn + [2] * (rounds_per_turn if turns == 2 else 0)

    # cada clube joga contra cada adversário exatamente `turns` vezes; nunca contra si mesmo
    games = Counter()
    pairs = Counter()
    for m in matches:
        assert m.home_club_uid != m.away_club_uid
        assert {m.home_club_uid, m.away_club_uid} <= set(participants)
        games[m.home_club_uid] += 1
        games[m.away_club_uid] += 1
        pairs[frozenset((m.home_club_uid, m.away_club_uid))] += 1
    assert all(games[c] == (n - 1) * turns for c in participants)
    assert len(pairs) == n * (n - 1) // 2 and set(pairs.values()) == {turns}
    if turns == 2:  # um jogo em cada mando
        ordered = Counter((m.home_club_uid, m.away_club_uid) for m in matches)
        assert set(ordered.values()) == {1}

    # no máximo um jogo por clube por rodada; folga = quem não joga
    byes = Counter()
    for r in s.rounds:
        playing = [c for m in r.matches for c in (m.home_club_uid, m.away_club_uid)]
        assert len(playing) == len(set(playing))
        idle = set(participants) - set(playing)
        if n % 2:
            assert idle == {r.bye_club_uid}
            byes[r.bye_club_uid] += 1
        else:
            assert not idle and r.bye_club_uid is None
    if n % 2:  # folgas: exatamente uma por clube por turno
        assert all(byes[c] == turns for c in participants)
    else:
        assert not byes

    # mandos equilibrados
    homes = Counter(m.home_club_uid for m in matches)
    for c in participants:
        away = games[c] - homes[c]
        assert abs(homes[c] - away) <= (1 if turns == 1 else 0)

    # identificadores estáveis e únicos
    assert len({m.id for m in matches}) == len(matches)
    assert all(m.id.startswith(f"L-R{m.round:02d}-M") for m in matches)


@pytest.mark.parametrize("n", [n for n in LEAGUE_SIZES if n > 3])
def test_league_home_sequences_are_short(n):
    """Mandos alternados: no máximo 2 jogos seguidos com o mesmo mando no turno; 3 na virada do returno."""
    for mode, limit in ((LeagueRounds.SINGLE, 2), (LeagueRounds.DOUBLE, 3)):
        participants, s = league(n, mode, 3)
        for c in participants:
            seq = [m.home_club_uid == c for r in s.rounds for m in r.matches if c in (m.home_club_uid, m.away_club_uid)]
            run = best = 1
            for a, b in zip(seq, seq[1:]):
                run = run + 1 if a == b else 1
                best = max(best, run)
            assert best <= limit, (n, mode, c, seq)


def test_bye_is_not_an_official_match():
    _, s = league(7, LeagueRounds.SINGLE, 1)
    for r in s.rounds:
        assert all(r.bye_club_uid not in (m.home_club_uid, m.away_club_uid) for m in r.matches)
    assert s.total_matches == 21 and s.matches_per_club == 6


# ------------------------------------------------------------------ seleção (prioridade Série A)
@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", LEAGUE_SIZES)
def test_league_selection_prioritizes_serie_a(n, seed):
    for user in (5, 25):  # usuário da Série A e da Série B
        chosen = select_league_participants(user, ELIGIBLE, n, random.Random(seed))
        assert chosen[0] == user and len(set(chosen)) == n
        others = chosen[1:]
        a_slots = 20 - (1 if DIV[user] == "A" else 0)
        expected_a = min(n - 1, a_slots)
        assert sum(DIV[c] == "A" for c in others) == expected_a
        assert sum(DIV[c] == "B" for c in others) == n - 1 - expected_a


def test_league_falls_back_to_serie_b_when_a_is_short():
    eligible = [EligibleClub(1, "A"), EligibleClub(2, "A"), EligibleClub(3, "A"),
                EligibleClub(4, "B"), EligibleClub(5, "B"), EligibleClub(6, "B")]
    chosen = select_league_participants(6, eligible, 5, random.Random(0))
    assert chosen[0] == 6 and set(chosen[1:4]) == {1, 2, 3} and set(chosen[4:]) <= {4, 5}


def test_selection_errors():
    with pytest.raises(PlanningError, match="não é elegível"):
        select_league_participants(99, ELIGIBLE, 4, random.Random(0))
    with pytest.raises(PlanningError, match="insuficientes"):
        select_league_participants(1, ELIGIBLE[:5], 6, random.Random(0))
    with pytest.raises(PlanningError, match="duplicatas"):
        draw_cup_participants(1, ELIGIBLE + ELIGIBLE[:1], 4, random.Random(0))


@pytest.mark.parametrize("n", [1, 21])
def test_league_size_outside_rules_is_rejected(n):
    with pytest.raises(PlanningError):
        build_league_schedule(list(range(1, n + 1)), LeagueRounds.SINGLE, random.Random(0))


# ------------------------------------------------------------------ o validador detecta corrupção
def _corrupt(s, fn):
    bad = s.model_copy(deep=True)
    fn(bad)
    return bad


@pytest.mark.parametrize(
    "corruption",
    [
        lambda s: s.rounds[0].matches.pop(),  # partida faltando
        lambda s: s.rounds[1].matches.append(s.rounds[0].matches[0].model_copy()),  # duplicada
        lambda s: setattr(s.rounds[0].matches[0], "away_club_uid", s.rounds[0].matches[0].home_club_uid),
        lambda s: setattr(s.rounds[0], "bye_club_uid", None),  # folga sumiu
        lambda s: s.rounds.pop(),  # rodada faltando
        lambda s: s.participants.append(s.participants[0]),  # participante duplicado
    ],
)
def test_league_validator_rejects_corrupted_schedules(corruption):
    _, s = league(7, LeagueRounds.DOUBLE, 0)
    with pytest.raises(PlanningError):
        validate_league_schedule(_corrupt(s, corruption))


def test_league_validator_rejects_unbalanced_home():
    _, s = league(6, LeagueRounds.DOUBLE, 0)

    def swap_all_home(bad):
        for r in bad.rounds:
            for m in r.matches:
                if m.turn == 2:
                    m.home_club_uid, m.away_club_uid = m.away_club_uid, m.home_club_uid

    with pytest.raises(PlanningError):
        validate_league_schedule(_corrupt(s, swap_all_home))


# ================================================================== Copa
def cup(n: int, seed: int, user: int = 25):
    rng = random.Random(seed)
    participants = draw_cup_participants(user, ELIGIBLE, n, rng)
    return participants, build_cup_bracket(participants, rng)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", CUP_SIZES)
def test_cup_bracket_structure(n, seed):
    participants, b = cup(n, seed)
    assert participants[0] == 25 and len(set(participants)) == n
    assert set(participants) <= set(DIV)

    assert b.total_rounds == len(b.rounds) == int(math.log2(n))
    assert [len(r.matches) for r in b.rounds] == [n // 2**k for k in range(1, b.total_rounds + 1)]
    assert b.total_matches == n - 1
    assert b.rounds[-1].name == "Final" and len(b.rounds[-1].matches) == 1
    assert b.rules.single_match and b.rules.regulation_minutes == 90 and not b.rules.extra_time
    assert b.rules.draw_decided_by == "penalties" and b.rules.penalties_count_as_goals is False

    first = [c for m in b.rounds[0].matches for c in (m.club_a_uid, m.club_b_uid)]
    assert sorted(first) == sorted(participants)  # todos na 1ª fase, uma única vez
    for r in b.rounds[1:]:
        for m in r.matches:  # fases seguintes aguardam vencedores
            assert m.club_a_uid is None and m.club_b_uid is None and m.source_a and m.source_b
    ids = [m.id for r in b.rounds for m in r.matches]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("n", CUP_SIZES)
def test_cup_progresses_to_the_final_even_after_user_elimination(n, seed):
    participants, b = cup(n, seed)
    rng = random.Random(seed + 100)
    user = participants[0]
    eliminated: list[int] = []
    decided = 0
    while pending := pending_cup_matches(b):
        m = pending[0]
        if user in (m.club_a_uid, m.club_b_uid):  # usuário eliminado na primeira oportunidade
            winner = m.club_b_uid if m.club_a_uid == user else m.club_a_uid
        else:
            winner = rng.choice([m.club_a_uid, m.club_b_uid])
        loser = m.club_b_uid if winner == m.club_a_uid else m.club_a_uid
        b = register_cup_winner(b, m.id, winner, rng.choice(["regular_time", "penalties"]))
        eliminated.append(loser)
        decided += 1
    assert decided == n - 1  # todos os confrontos até a final
    assert b.champion_club_uid is not None and b.champion_club_uid != user
    assert user in eliminated
    assert len(eliminated) == len(set(eliminated)) == n - 1  # cada clube eliminado uma única vez
    assert set(eliminated) | {b.champion_club_uid} == set(participants)
    final = b.rounds[-1].matches[0]
    assert final.winner_club_uid == b.champion_club_uid


def test_register_winner_rules():
    _, b = cup(4, 0)
    semi = b.rounds[0].matches[0]
    final = b.rounds[1].matches[0]
    with pytest.raises(PlanningError, match="não tem os dois clubes"):
        register_cup_winner(b, final.id, semi.club_a_uid, "regular_time")
    with pytest.raises(PlanningError, match="não disputa"):
        register_cup_winner(b, semi.id, 999, "regular_time")
    with pytest.raises(PlanningError, match="inexistente"):
        register_cup_winner(b, "C-R9-M01", semi.club_a_uid, "regular_time")
    b2 = register_cup_winner(b, semi.id, semi.club_b_uid, "penalties")
    assert b.rounds[0].matches[0].winner_club_uid is None  # original intacto
    m = b2.rounds[0].matches[0]
    assert m.winner_club_uid == semi.club_b_uid and m.decided_by == "penalties"
    assert b2.rounds[1].matches[0].club_a_uid == semi.club_b_uid
    with pytest.raises(PlanningError, match="já decidido"):
        register_cup_winner(b2, semi.id, semi.club_a_uid, "regular_time")


@pytest.mark.parametrize("n", [3, 6, 12, 64])
def test_invalid_cup_sizes(n):
    with pytest.raises(PlanningError):
        build_cup_bracket(list(range(1, n + 1)), random.Random(0))


@pytest.mark.parametrize(
    "corruption",
    [
        lambda b: setattr(b.rounds[0].matches[0], "club_b_uid", b.rounds[0].matches[1].club_a_uid),
        lambda b: setattr(b.rounds[0].matches[0], "next_match_id", None),
        lambda b: setattr(b.rounds[1].matches[0], "source_a", b.rounds[1].matches[0].source_b),
        lambda b: b.rounds[0].matches.pop(),
        lambda b: setattr(b.rules, "extra_time", True),
    ],
)
def test_cup_validator_rejects_corrupted_brackets(corruption):
    _, b = cup(8, 0)
    with pytest.raises(PlanningError):
        validate_cup_bracket(_corrupt(b, corruption))


# ================================================================== determinismo e fachada
def test_same_seed_same_plan_and_different_seed_differs():
    cfg = CompetitionConfig(format="cup", num_clubs=16, user_club_uid=3)
    a = plan_competition(cfg, ELIGIBLE, random.Random(5))
    b = plan_competition(cfg, ELIGIBLE, random.Random(5))
    c = plan_competition(cfg, ELIGIBLE, random.Random(6))
    assert a == b and a != c


def test_cup_draw_uses_both_divisions():
    seen = set()
    for seed in range(20):
        participants, _ = cup(32, seed)
        seen |= {DIV[c] for c in participants}
    assert seen == {"A", "B"}
