"""Avaliação 80/20, escalação ótima, decisões dos bots e complementação dos elencos (GDD §6, §7)."""

from __future__ import annotations

import itertools
import random
from collections import Counter

import pytest

from services.auction import rules
from services.auction.completion import improvement_price
from services.auction.engine import Contract, summary_ok
from services.auction.model import PERSONALITIES, AuctionModelError, Formation, Reserves
from services.bot_ai.auction_bot import BotAuctionView, decide_bid
from services.bot_ai.evaluation import _hungarian_max, marginal_gain, squad_quality
from squadforce_shared.domain.competition import CompetitionFormat
from squadforce_shared.domain.positions import Position
from support.auction_fixtures import make_engine, make_pool, run_to_end
from support.fake_auction_model import FakeAuctionModel


# ------------------------------------------------------------------ atribuição ótima
@pytest.mark.parametrize("seed", range(8))
def test_hungarian_matches_brute_force(seed):
    rng = random.Random(seed)
    rows, cols = 4, 6
    w = [[rng.uniform(0, 10) for _ in range(cols)] for _ in range(rows)]
    total, assign = _hungarian_max(w)
    brute = max(sum(w[i][c] for i, c in enumerate(perm)) for perm in itertools.permutations(range(cols), rows))
    assert total == pytest.approx(brute)
    assert len(set(assign)) == rows


def test_marginal_gain_is_80_percent_starters_20_percent_reserves():
    model = FakeAuctionModel()
    pool = make_pool(20, seed=4)
    squad = pool[:9]
    cand = pool[60]
    b, a = squad_quality(squad, model), squad_quality([*squad, cand], model)
    expected = 0.8 * (a.starters - b.starters) + 0.2 * (a.reserves - b.reserves)
    assert marginal_gain(squad, cand, model) == pytest.approx(expected)


def test_squad_quality_uses_best_formation_and_empty_slots_count_zero():
    two = FakeAuctionModel(formations=[
        Formation("A", (Position.GK,) + (Position.STC,) * 10),
        Formation("B", (Position.GK,) + (Position.DC,) * 10),
    ])
    pool = make_pool(5)
    gk = [p for p in pool if p.main_position is Position.GK][0]
    dcs = [p for p in pool if p.main_position is Position.DC][:3]
    q = squad_quality([gk, *dcs], two)
    assert q.formation == "B" and q.lineup.count(None) == 7
    assert q.reserves == 0.0


# ------------------------------------------------------------------ bots
def _view(engine, club):
    return engine.bot_view(club, engine.clock())


def test_aggressive_bids_at_least_as_much_as_conservative():
    s = make_engine(4)
    e = s.engine
    model = FakeAuctionModel()
    view = _view(e, s.clubs[1])
    agg = decide_bid(view, model, model.bot_profile("aggressive"))
    con = decide_bid(view, model, model.bot_profile("conservative"))
    assert agg is not None
    if con is not None and con.player_id == agg.player_id:
        assert agg.amount >= con.amount


def test_bot_bids_respect_minimum_and_reserve_rule():
    s = make_engine(8)
    e = s.engine
    model = FakeAuctionModel()
    for club in s.clubs[1:]:
        for name in PERSONALITIES:
            intent = decide_bid(_view(e, club), model, model.bot_profile(name))
            if intent:
                c = e.clubs[club]
                assert intent.amount >= e.round.minimum_bids[intent.player_id]
                assert intent.amount <= rules.max_affordable_bid(c.budget, len(c.contracts))
                assert intent.amount % 100_000 == 0


def test_bot_considers_public_competition_and_avoids_the_crowded_target():
    """§6: concorrência estimada SÓ com informação pública (vagas e saldos dos rivais, lances mínimos)."""
    from dataclasses import replace

    s = make_engine(4)
    e = s.engine
    model = FakeAuctionModel()
    prof = model.bot_profile("balanced")
    alone = replace(_view(e, s.clubs[1]), rivals_open_slots={}, rivals_budgets={})
    solo = decide_bid(alone, model, prof)
    assert solo is not None
    crowd_slots = {9000 + i: 18 for i in range(30)}
    crowd = replace(alone, rivals_open_slots=crowd_slots, rivals_budgets={u: 120_000_000 for u in crowd_slots})
    contested = decide_bid(crowd, model, prof)
    assert contested is not None
    mb = alone.minimum_bids
    # sem rivais: o maior ganho; com 30 rivais: um alvo menos disputado (lance mínimo menor)
    assert mb[contested.player_id] < mb[solo.player_id]
    # rivais sem vagas ou sem saldo não contam como concorrência
    idle = replace(alone, rivals_open_slots={u: 0 for u in crowd_slots}, rivals_budgets={u: 120_000_000 for u in crowd_slots})
    assert decide_bid(idle, model, prof) == solo
    broke = replace(alone, rivals_open_slots=crowd_slots, rivals_budgets={u: 0 for u in crowd_slots})
    assert decide_bid(broke, model, prof) == solo


def test_full_squad_bot_does_not_bid():
    s = make_engine(4)
    e = s.engine
    club = s.clubs[1]
    free = [pid for pid in e.players if pid not in e.round.player_ids][:18]
    e.clubs[club].contracts[:] = [Contract(pid, 0, "auction", 0) for pid in free]
    assert decide_bid(_view(e, club), FakeAuctionModel(), FakeAuctionModel().bot_profile("aggressive")) is None


def test_bot_view_fields_are_public_only():
    assert set(BotAuctionView.__dataclass_fields__) == {
        "club_uid", "budget", "squad", "round_players", "minimum_bids", "global_progress",
        "own_bid", "rivals_open_slots", "rivals_budgets",
    }


# ------------------------------------------------------------------ complementação
@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_completion_rules(seed):
    s = make_engine(8, pool=make_pool(150, seed=seed), seed=seed)
    run_to_end(s, step=5)
    e = s.engine
    comp = e.completion
    assert summary_ok(e) == []
    for uid, club in e.clubs.items():
        c = comp.auction_signings[uid]
        assert comp.improvement_limits[uid] == min(18 - c, c // 4)
        picks = [p for p in comp.picks if p.club_uid == uid]
        improvements = [p for p in picks if p.kind == "improvement"]
        assert len(picks) == 18 - c
        assert len(improvements) <= comp.improvement_limits[uid]
        assert sum(p.highlight for p in improvements) <= 1
        for p in improvements:
            assert p.price == improvement_price(e, p.player_id)
            assert p.highlight == e.is_highlight(p.player_id)
        for p in picks:
            if p.kind == "basic":
                assert 0 < p.price <= 500_000
        assert club.budget >= 0
    # sem compensação: ninguém recebe dinheiro
    assert all(c.budget <= rules.INITIAL_BUDGET for c in e.clubs.values())
    # todas as complementações vieram de não vendidos no leilão
    auction_sold = {pid for r in e.results for pid, _, _ in r.sales}
    assert not auction_sold & {p.player_id for p in comp.picks}


def test_completion_order_has_no_fixed_priority():
    """Todos os clubes chegam à complementação (bots passivos); a ordem de cada turno é sorteada."""
    from services.auction.model import BotProfile

    passive = BotProfile(1.0, 0.0, 1e12, 0.0, 1.0, 0.0, (0.0, 0.0), 0.0)
    model = FakeAuctionModel(profiles={p: passive for p in PERSONALITIES})
    first_pickers = Counter()
    for seed in range(12):
        s = make_engine(6, fmt=CompetitionFormat.LEAGUE, model=model, pool=make_pool(120, seed=seed), seed=seed)
        run_to_end(s, step=50)
        turn1 = [p.club_uid for p in s.engine.completion.picks if p.turn == 1]
        assert sorted(turn1) == sorted(s.clubs)  # cada clube escolhe exatamente uma vez por turno
        first_pickers[turn1[0]] += 1
    assert len(first_pickers) > 1


def test_highlight_threshold_is_85th_percentile_of_full_base():
    s = make_engine(4, start=False)
    e = s.engine
    values = sorted(e.overall.values())
    above = sum(v >= e.highlight_threshold for v in values)
    assert 0.14 * len(values) <= above <= 0.16 * len(values) + 1


class TinyReserve(FakeAuctionModel):
    def build_reserves(self, unsold, slots_to_fill, num_clubs):
        return Reserves(tuple(p.unique_id for p in unsold[: slots_to_fill - 1]), ())


class OverlappingReserve(FakeAuctionModel):
    def build_reserves(self, unsold, slots_to_fill, num_clubs):
        ids = tuple(p.unique_id for p in unsold[:slots_to_fill + 5])
        return Reserves(ids, ids[:2])


@pytest.mark.parametrize("model,match", [(TinyReserve(), "insuficiente"), (OverlappingReserve(), "distintas")])
def test_invalid_reserves_are_rejected(model, match):
    s = make_engine(4, model=model)
    with pytest.raises(AuctionModelError, match=match):
        run_to_end(s, step=50)
