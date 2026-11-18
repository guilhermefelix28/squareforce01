"""Motor do leilão: lances, validações, desempate, relógio, encerramento, sigilo e idempotência."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from services.auction import rules
from services.auction.engine import AuctionEngine, AuctionError, summary_ok
from services.auction.model import PERSONALITIES, AuctionModelError, BotProfile
from squadforce_shared.domain.competition import CompetitionFormat
from squadforce_shared.domain.positions import POSITION_ORDER, Position
from support.auction_fixtures import ManualClock, make_engine, make_pool, run_to_end
from support.fake_auction_model import FakeAuctionModel

PASSIVE = BotProfile(1.0, 0.0, 1e12, 0.0, 1.0, 0.0, (0.0, 0.0), 0.0)  # bot que nunca disputa


def passive_model(**kw):
    return FakeAuctionModel(profiles={p: PASSIVE for p in PERSONALITIES}, **kw)


@pytest.fixture
def quiet():
    """4 clubes, bots passivos: só os lances do teste existem."""
    return make_engine(4, model=passive_model())


def fill(e: AuctionEngine, club: int, n: int) -> None:
    """Dá `n` contratos ao clube com atletas reais da base que não estão na rodada atual."""
    from services.auction.engine import Contract

    free = [pid for pid in e.players if pid not in e.sold and pid not in e.round.player_ids]
    for pid in free[:n]:
        e.clubs[club].contracts.append(Contract(pid, 0, "auction", 0))
        e.sold[pid] = club


def first_player(e: AuctionEngine) -> tuple[int, int]:
    pid = e.round.player_ids[0]
    return pid, e.round.minimum_bids[pid]


# ------------------------------------------------------------------ rodada e relógio
def test_round_shape_and_global_clock(quiet):
    e, clock = quiet.engine, quiet.clock
    r = e.round
    assert r.number == 1 and len(r.player_ids) == 5 == len(set(r.player_ids))
    assert {e.players[p].main_position for p in r.player_ids} == {r.position}
    assert r.ends_at - r.starts_at == 10
    assert e.ends_at - e.started_at == rules.auction_duration_seconds(CompetitionFormat.CUP, 4) == 600
    assert all(c.budget == 120_000_000 for c in e.clubs.values())
    clock.advance(10)
    e.tick()
    assert e.round.number == 2 and e.round.starts_at == r.ends_at  # contíguas: relógio não para


def test_rounds_are_contiguous_and_never_exceed_global_end():
    s = make_engine(4, model=passive_model())
    run_to_end(s, step=3.7)
    e = s.engine
    closes = [res.closed_at for res in e.results]
    assert closes[-1] == e.ends_at and e.finish_reason == "time_up"
    assert all(b - a == pytest.approx(10) for a, b in zip(closes, closes[1:]))
    assert len(e.results) == 60  # 600 s / 10 s


def test_tick_frequency_does_not_change_the_outcome():
    a, b = make_engine(4, seed=9), make_engine(4, seed=9)
    run_to_end(a, step=0.25)
    run_to_end(b, step=37.0)
    assert [r.sales for r in a.engine.results] == [r.sales for r in b.engine.results]


# ------------------------------------------------------------------ validação de lances
def test_valid_bid_and_winner_pays(quiet):
    e, clock = quiet.engine, quiet.clock
    user = quiet.clubs[0]
    pid, mn = first_player(e)
    ack = e.place_bid(user, pid, mn + 300_000, "op-1")
    assert ack.amount == mn + 300_000 and ack.seq == 1 and ack.replaced_player_id is None
    clock.advance(10)
    e.tick()
    assert e.sold[pid] == user
    assert e.clubs[user].budget == 120_000_000 - (mn + 300_000)
    assert e.results[0].sales == ((pid, user, mn + 300_000),)


@pytest.mark.parametrize(
    "mutate,code",
    [
        (lambda e, pid, mn: (pid, mn - 1), "BELOW_MINIMUM_BID"),
        (lambda e, pid, mn: (999_999, mn), "PLAYER_NOT_IN_ROUND"),
        (lambda e, pid, mn: (pid, 0), "INVALID_AMOUNT"),
        (lambda e, pid, mn: (pid, 120_000_000 - 17 * 500_000 + 1), "INSUFFICIENT_FUNDS"),
    ],
)
def test_invalid_bids_are_rejected(quiet, mutate, code):
    e = quiet.engine
    pid, mn = first_player(e)
    target, amount = mutate(e, pid, mn)
    with pytest.raises(AuctionError) as err:
        e.place_bid(quiet.clubs[0], target, amount, "op-x")
    assert err.value.code == code
    assert e.round.bids == {}


def test_reserve_boundary_is_exact(quiet):
    e = quiet.engine
    pid, _ = first_player(e)
    limit = 120_000_000 - 17 * 500_000
    assert e.place_bid(quiet.clubs[0], pid, limit, "op-max").amount == limit


def test_reserve_rule_with_partial_squad(quiet):
    e = quiet.engine
    club = e.clubs[quiet.clubs[0]]
    club.budget = 9_000_000
    fill(e, club.club_uid, 10)  # 10 contratados, 8 vagas
    pid, mn = first_player(e)
    limit = 9_000_000 - 7 * 500_000
    with pytest.raises(AuctionError) as err:
        e.place_bid(club.club_uid, pid, limit + 100_000, "a")
    assert err.value.details["max_bid"] == limit
    if mn <= limit:
        assert e.place_bid(club.club_uid, pid, limit, "b").amount == limit


def test_closed_round_and_stale_round(quiet):
    e, clock = quiet.engine, quiet.clock
    pid, mn = first_player(e)
    clock.advance(10)  # rodada 1 encerra exatamente aqui
    with pytest.raises(AuctionError) as err:
        e.place_bid(quiet.clubs[0], pid, mn, "late", round_number=1)
    assert err.value.code == "STALE_ROUND" and err.value.details["current_round"] == 2
    assert pid not in e.sold


def test_bid_at_last_instant_is_accepted_and_after_deadline_is_not(quiet):
    e, clock = quiet.engine, quiet.clock
    pid, mn = first_player(e)
    clock.advance(9.999)
    e.place_bid(quiet.clubs[0], pid, mn, "ok")
    clock.advance(0.001)
    e.tick()
    assert e.sold.get(pid) == quiet.clubs[0]


def test_raise_allowed_reduce_and_repeat_forbidden(quiet):
    e = quiet.engine
    u = quiet.clubs[0]
    pid, mn = first_player(e)
    e.place_bid(u, pid, mn + 1_000_000, "a")
    for amount in (mn + 1_000_000, mn + 500_000):
        with pytest.raises(AuctionError) as err:
            e.place_bid(u, pid, amount, f"r{amount}")
        assert err.value.code == "BID_NOT_INCREASED"
    assert e.place_bid(u, pid, mn + 1_100_000, "b").amount == mn + 1_100_000
    assert e.round.bids[u].amount == mn + 1_100_000


def test_change_target_is_atomic_and_failure_keeps_previous(quiet):
    e = quiet.engine
    u = quiet.clubs[0]
    a, b = e.round.player_ids[:2]
    e.place_bid(u, a, e.round.minimum_bids[a], "a")
    with pytest.raises(AuctionError):
        e.place_bid(u, b, e.round.minimum_bids[b] - 100_000, "bad")  # troca inválida
    assert e.round.bids[u].player_id == a  # lance anterior permanece
    ack = e.place_bid(u, b, e.round.minimum_bids[b], "good")
    assert ack.replaced_player_id == a and e.round.bids[u].player_id == b
    assert len([x for x in e.round.bids.values() if x.club_uid == u]) == 1  # um lance ativo


def test_change_target_can_lower_amount_on_another_player(quiet):
    e = quiet.engine
    u = quiet.clubs[0]
    a, b = e.round.player_ids[:2]
    e.place_bid(u, a, e.round.minimum_bids[a] + 5_000_000, "a")
    e.place_bid(u, b, e.round.minimum_bids[b], "b")  # proibição de reduzir vale só para o MESMO atleta
    assert e.round.bids[u].player_id == b


# ------------------------------------------------------------------ vencedor e desempate
def test_highest_bid_wins(quiet):
    e, clock = quiet.engine, quiet.clock
    u, b1, b2 = quiet.clubs[:3]
    pid, mn = first_player(e)
    e.place_bid(u, pid, mn + 100_000, "1")
    e.place_bid(b1, pid, mn + 900_000, "2")
    e.place_bid(b2, pid, mn + 500_000, "3")
    clock.advance(10)
    e.tick()
    assert e.sold[pid] == b1 and e.clubs[b1].budget == 120_000_000 - (mn + 900_000)
    assert e.clubs[u].budget == e.clubs[b2].budget == 120_000_000  # perdedores não pagam


def test_tie_goes_to_whoever_reached_the_final_value_first(quiet):
    e, clock = quiet.engine, quiet.clock
    u, b1 = quiet.clubs[:2]
    pid, mn = first_player(e)
    e.place_bid(b1, pid, mn, "b1-a")  # t=0
    clock.advance(2)
    e.place_bid(u, pid, mn + 1_000_000, "u-a")  # t=2 atinge o valor final
    clock.advance(3)
    e.place_bid(b1, pid, mn + 1_000_000, "b1-b")  # t=5 atinge o MESMO valor depois
    clock.advance(5)
    e.tick()
    assert e.sold[pid] == u


def test_same_timestamp_tie_uses_acceptance_sequence(quiet):
    e, clock = quiet.engine, quiet.clock
    u, b1, b2 = quiet.clubs[:3]
    pid, mn = first_player(e)
    clock.advance(1)  # mesmo instante para os três
    acks = [e.place_bid(c, pid, mn + 700_000, f"o{c}") for c in (b2, u, b1)]
    assert [a.accepted_at for a in acks] == [acks[0].accepted_at] * 3
    assert [a.seq for a in acks] == sorted(a.seq for a in acks)
    clock.advance(9)
    e.tick()
    assert e.sold[pid] == b2  # primeiro aceito pelo servidor


def test_each_club_wins_at_most_one_player_per_round(quiet):
    e, clock = quiet.engine, quiet.clock
    for i, c in enumerate(quiet.clubs):
        pid = e.round.player_ids[i]
        e.place_bid(c, pid, e.round.minimum_bids[pid], f"c{c}")
    clock.advance(10)
    e.tick()
    sales = e.results[0].sales
    assert len(sales) == 4 and len({c for _, c, _ in sales}) == 4


# ------------------------------------------------------------------ idempotência
def test_operation_id_prevents_duplicate_bids(quiet):
    e = quiet.engine
    u = quiet.clubs[0]
    pid, mn = first_player(e)
    a = e.place_bid(u, pid, mn, "same-op")
    b = e.place_bid(u, pid, mn, "same-op")
    assert b.replayed and (b.seq, b.amount) == (a.seq, a.amount)
    assert e._seq == 1  # nenhum lance novo foi aceito
    with pytest.raises(AuctionError) as err:
        e.place_bid(u, pid, mn + 100_000, "same-op")
    assert err.value.code == "OPERATION_ID_REUSED"


# ------------------------------------------------------------------ elenco cheio e encerramento antecipado
def test_full_squad_cannot_bid_and_early_finish_when_all_full(quiet):
    e, clock = quiet.engine, quiet.clock
    for c in quiet.clubs[1:]:
        fill(e, c, 18)
    user = quiet.clubs[0]
    fill(e, user, 17)
    pid, mn = first_player(e)
    with pytest.raises(AuctionError) as err:
        e.place_bid(quiet.clubs[1], pid, mn, "full")
    assert err.value.code == "SQUAD_FULL"
    e.place_bid(user, pid, mn, "last")
    clock.advance(10)
    e.tick()
    assert e.phase == "completed" and e.finish_reason == "all_squads_complete"
    assert e.finished_at < e.ends_at  # terminou antes do relógio global


# ------------------------------------------------------------------ jogadores da rodada
def test_sold_players_never_return_and_unsold_are_counted():
    s = make_engine(4)
    run_to_end(s)
    e = s.engine
    seen_after_sale = []
    sold_round = {}
    for res in e.results:
        for pid, _, _ in res.sales:
            sold_round[pid] = res.number
    # nenhum jogador aparece em rodada posterior à sua venda
    offered: dict[int, list[int]] = {}
    for res in e.results:
        for pid in [p for p, _, _ in res.sales] + list(res.unsold):
            offered.setdefault(pid, []).append(res.number)
    for pid, rounds_ in offered.items():
        if pid in sold_round:
            seen_after_sale += [r for r in rounds_ if r > sold_round[pid]]
    assert seen_after_sale == []
    unsold_total = Counter(p for res in e.results for p in res.unsold)
    for pid, n in unsold_total.items():
        assert e.unsold_counts[pid] == n


class StubbornModel(FakeAuctionModel):
    """Pesos quase todos numa só posição, para forçar a regra das 14 rodadas."""

    def position_weights(self, eligible, needs, recent, available):
        return {p: (1000.0 if p is Position.STC else 1e-6) for p in eligible}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_eligible_position_appears_in_every_window_of_14_rounds(seed):
    s = make_engine(4, model=StubbornModel(profiles={p: PASSIVE for p in PERSONALITIES}), pool=make_pool(200), seed=seed)
    run_to_end(s, step=5)
    log = s.engine.position_log
    assert len(log) == 60
    for i in range(len(log) - rules.POSITION_WINDOW + 1):
        assert set(log[i:i + rules.POSITION_WINDOW]) == set(POSITION_ORDER), (i, log[i:i + 14])
    assert Counter(log)[Position.STC] > 20  # o peso do modelo continua valendo fora das janelas


def test_position_with_fewer_than_five_players_is_not_eligible():
    pool = [p for p in make_pool(40) if p.main_position is not Position.GK] + [
        p for p in make_pool(40) if p.main_position is Position.GK
    ][:4]
    s = make_engine(4, pool=pool, model=passive_model())
    run_to_end(s, step=10)
    assert Position.GK not in s.engine.position_log


class BadPicker(FakeAuctionModel):
    def pick_round_players(self, candidates, unsold_counts, rng, k):
        return [candidates[0].unique_id] * k


def test_invalid_model_outputs_are_rejected():
    with pytest.raises(AuctionModelError):
        make_engine(4, model=BadPicker())

    class Pricey(FakeAuctionModel):
        def minimum_bid(self, p):
            return 30_000_001

    with pytest.raises(AuctionModelError, match="30 mi"):
        make_engine(4, model=Pricey(), start=False)

    class TooValuable(FakeAuctionModel):
        def market_value(self, p):
            return 50_000_001

    with pytest.raises(AuctionModelError, match="50 mi"):
        make_engine(4, model=TooValuable(), start=False)


# ------------------------------------------------------------------ sigilo e bots
def test_bot_view_has_no_rival_bids():
    s = make_engine(4)
    e = s.engine
    s.clock.advance(5)
    e.tick()
    view = e.bot_view(s.clubs[1], s.clock.now)
    fields = set(view.__dataclass_fields__)
    assert "bids" not in fields and not any("bid" in f and f != "own_bid" and f != "minimum_bids" for f in fields)
    own = e.round.bids.get(s.clubs[1])
    assert view.own_bid == ((own.player_id, own.amount) if own else None)


def test_bot_decision_does_not_depend_on_rival_secret_bids():
    from services.bot_ai.auction_bot import decide_bid

    a = make_engine(4, model=passive_model())
    e = a.engine
    bot = a.clubs[1]
    model = FakeAuctionModel()
    before = decide_bid(e.bot_view(bot, a.clock.now), model, model.bot_profile("balanced"))
    pid, mn = first_player(e)
    e.place_bid(a.clubs[2], pid, 80_000_000, "rival-secret")  # oferta sigilosa enorme de um rival
    after = decide_bid(e.bot_view(bot, a.clock.now), model, model.bot_profile("balanced"))
    assert before == after


def test_personalities_are_hidden_and_assigned_to_bots_only():
    s = make_engine(8)
    e = s.engine
    assert e.clubs[s.clubs[0]].personality is None
    assert all(e.clubs[c].personality in PERSONALITIES for c in s.clubs[1:])


def test_user_never_gets_bids_placed_on_its_behalf():
    s = make_engine(8)
    run_to_end(s)
    assert all(c != s.clubs[0] for res in s.engine.results for _, c, _ in res.sales)


# ------------------------------------------------------------------ simulação completa (base sintética)
@pytest.mark.parametrize("num_clubs,fmt", [(2, CompetitionFormat.CUP), (8, CompetitionFormat.CUP), (5, CompetitionFormat.LEAGUE)])
def test_full_auction_invariants(num_clubs, fmt):
    s = make_engine(num_clubs, fmt=fmt, pool=make_pool(120))
    run_to_end(s, step=2.5)
    e = s.engine
    assert e.phase == "completed"
    assert summary_ok(e) == []
    assert all(len(c.contracts) == 18 for c in e.clubs.values())
