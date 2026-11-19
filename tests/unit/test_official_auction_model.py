"""AuctionModel oficial (proposta aprovada em 2026-11-19: docs/architecture/proposta-auction-model.md)."""

from __future__ import annotations

import random
import statistics as st
from collections import Counter

import pytest

from services.auction.model import PERSONALITIES, load_auction_model
from services.auction.official_model import (
    APPROVED_BOT_PROFILES,
    APPROVED_TRADE_PROFILES,
    OfficialAuctionModel,
    market_value_for,
    minimum_bid_for,
)
from services.match_engine.params import GOALKEEPING, MENTAL, PHYSICAL, TECHNICAL
from squadforce_shared.domain.formations import OFFICIAL_FORMATIONS
from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import POSITION_ORDER, Position as P

ALL = (*TECHNICAL, *MENTAL, *PHYSICAL, *GOALKEEPING)


def pool(per_position: int = 40, seed: int = 3, start: int = 1) -> list[PlayerProfile]:
    rng = random.Random(seed)
    out, uid = [], start
    for pos in POSITION_ORDER:
        for _ in range(per_position):
            base = rng.gauss(55, 9)
            attrs = {a: max(1, min(100, int(base + rng.gauss(0, 6)))) for a in ALL}
            fam = {p: (100 if p is pos else rng.choice([1, 1, 40, 75])) for p in P}
            out.append(PlayerProfile(uid, f"A{uid}", rng.randint(17, 36), 1, "X", (pos,), (), fam, attrs))
            uid += 1
    return out


@pytest.fixture(scope="module")
def bound():
    players = pool()
    return OfficialAuctionModel().for_pool(players), players


# ------------------------------------------------------------------ PE-01 overall
def test_overall_median_is_70_per_position_and_clamped(bound):
    m, players = bound
    for pos in POSITION_ORDER:
        vals = [m.overall(p) for p in players if p.main_position is pos]
        assert st.median(vals) == pytest.approx(70.0, abs=0.01)
    assert all(30.0 <= m.overall(p) <= 99.0 for p in players)


def test_overall_grows_with_attributes(bound):
    m, players = bound
    p = next(x for x in players if x.main_position is P.STC)
    better = PlayerProfile(p.unique_id + 10_000, "B", p.age, 1, "X", p.natural_positions, (), p.familiarity,
                           {a: min(100, v + 10) for a, v in p.attributes.items()})
    assert m.overall(better) > m.overall(p)


def test_calibration_is_recomputed_for_each_pool():
    a = OfficialAuctionModel().for_pool(pool(seed=1))
    weaker = [PlayerProfile(p.unique_id, p.name, p.age, 1, "X", p.natural_positions, (), p.familiarity,
                            {k: max(1, v - 15) for k, v in p.attributes.items()}) for p in pool(seed=1)]
    b = OfficialAuctionModel().for_pool(weaker)
    assert st.median(b.overall(p) for p in weaker) == pytest.approx(70.0, abs=0.01)  # nova base, nova escala
    assert a.overall(weaker[0]) < b.overall(weaker[0])


def test_unbound_model_refuses_to_evaluate():
    with pytest.raises(RuntimeError):
        OfficialAuctionModel().overall(pool(per_position=1)[0])


# ------------------------------------------------------------------ PE-03 qualidade na posição
def test_positional_penalty_is_linear_up_to_35_percent(bound):
    m, players = bound
    p = next(x for x in players if x.main_position is P.DC)
    fam = lambda f: PlayerProfile(p.unique_id, p.name, p.age, 1, "X", (P.DC,), (), {**p.familiarity, P.DC: f}, p.attributes)
    q100, q1, q50 = (m.player_quality(fam(f), P.DC) for f in (100, 1, 50))
    assert q1 == pytest.approx(q100 * 0.65)
    assert q50 == pytest.approx(q100 * (1 - 0.35 * 50 / 99))
    assert m.player_quality(p, P.DC) == pytest.approx(m.overall(p))  # posição natural, familiaridade 100


# ------------------------------------------------------------------ PE-02 valor e lance mínimo
@pytest.mark.parametrize("ovr,expected", [(55, 100_000), (60, 200_000), (65, 900_000), (68, 1_800_000),
                                          (70, 3_000_000), (75, 5_500_000), (80, 10_200_000), (90, 35_000_000),
                                          (96, 50_000_000)])
def test_market_value_curve_steeper_below_median(ovr, expected):
    assert market_value_for(ovr, 26) == expected


def test_age_factor_and_minimum_bid():
    assert [market_value_for(80, a) for a in (20, 26, 30, 33, 35)] == \
           [11_300_000, 10_200_000, 8_700_000, 7_200_000, 5_600_000]
    assert minimum_bid_for(10_200_000) == 5_100_000
    assert minimum_bid_for(50_000_000) == 25_000_000
    assert minimum_bid_for(100_000) == 100_000


def test_model_prices_respect_gdd_limits(bound):
    m, players = bound
    for p in players:
        mv, mb, bp = m.market_value(p), m.minimum_bid(p), m.basic_price(p)
        assert 0 < mv <= 50_000_000 and 0 < mb <= 30_000_000 and 0 < bp <= 500_000
        assert bp == min(500_000, mb)


# ------------------------------------------------------------------ PM-01 formações
def test_eleven_official_formations():
    names = [f.name for f in OFFICIAL_FORMATIONS]
    assert names == ["4-2-2-2", "4-1-2-3", "4-2-3-1", "3-5-2", "3-4-3", "5-3-2", "4-1-4-1", "4-5-1", "4-3-2-1",
                     "4-3-1-2", "5-4-1"]
    for f in OFFICIAL_FORMATIONS:
        c = Counter(f.slots)
        assert len(f.slots) == 11 and c[P.GK] == 1
        back = int(f.name.split("-")[0])
        if back == 3:  # linha de 3: alas como LD/LE
            assert c[P.DC] == 3 and c[P.DR] == c[P.DL] == 1
        else:
            assert c[P.DR] + c[P.DL] + c[P.DC] == back
    assert len({f.slots for f in OFFICIAL_FORMATIONS}) == 11  # tuplas distintas: o nome é preservado
    assert list(OfficialAuctionModel().formations()) == list(OFFICIAL_FORMATIONS)


# ------------------------------------------------------------------ PE-05 e §5
def test_position_weights_need_availability_and_recency(bound):
    m, _ = bound
    elig = [P.GK, P.DC, P.STC]
    w = m.position_weights(elig, {P.GK: 0, P.DC: 10, P.STC: 10}, [], {P.GK: 20, P.DC: 20, P.STC: 20})
    assert w[P.DC] == w[P.STC] > w[P.GK] > 0
    w2 = m.position_weights(elig, {P.GK: 0, P.DC: 10, P.STC: 10}, [P.GK, P.DC], {P.GK: 20, P.DC: 20, P.STC: 20})
    assert w2[P.DC] == pytest.approx(0.4 * w[P.DC])
    w3 = m.position_weights(elig, {}, [P.DC, P.GK, P.GK, P.GK], {P.GK: 20, P.DC: 5, P.STC: 20})
    assert w3[P.DC] == pytest.approx(0.7 * 0.5 * w3[P.STC])  # 3ª rodada anterior e metade da disponibilidade


def test_round_players_favor_above_median_and_keep_variety(bound):
    m, players = bound
    cands = [p for p in players if p.main_position is P.MC]
    above = {p.unique_id for p in cands if m.overall(p) >= m.base_median}
    assert 0 < len(above) < len(cands)
    counts = []
    for s in range(400):
        picked = m.pick_round_players(cands, {}, random.Random(s), 5)
        assert len(set(picked)) == 5 and set(picked) <= {p.unique_id for p in cands}
        n_above = sum(pid in above for pid in picked)
        assert 1 <= n_above <= 4  # pelo menos um de cada grupo
        counts.append(n_above)
    assert st.mean(counts) > 3.5  # bem mais chance para quem está acima da mediana


def test_round_players_skip_twice_unsold_unless_short(bound):
    m, players = bound
    cands = [p for p in players if p.main_position is P.GK]
    tired = {p.unique_id: 2 for p in cands[:30]}
    picked = m.pick_round_players(cands, tired, random.Random(1), 5)
    assert not set(picked) & set(tired)
    all_tired = {p.unique_id: 2 for p in cands}
    assert len(m.pick_round_players(cands, all_tired, random.Random(1), 5)) == 5


# ------------------------------------------------------------------ PE-04 reservas
def test_reserves_basic_and_complementary(bound):
    m, players = bound
    num_clubs, slots = 8, 40
    r = m.build_reserves(players, slots, num_clubs)
    assert not set(r.basic) & set(r.complementary)
    assert len(r.basic) == 50  # vagas + 25%
    by_id = {p.unique_id: p for p in players}
    assert sum(by_id[i].main_position is P.GK for i in r.basic) >= num_clubs
    basic_ovr = st.median(m.overall(by_id[i]) for i in r.basic)
    comp_ovr = st.median(m.overall(by_id[i]) for i in r.complementary)
    assert basic_ovr < 70 < comp_ovr
    highlights = sum(m.overall(by_id[i]) >= m.highlight_threshold for i in r.complementary)
    assert highlights <= 2  # arred_cima(8 / 4)


# ------------------------------------------------------------------ PB-01 / PB-02
def test_approved_profiles():
    m = OfficialAuctionModel()
    assert set(APPROVED_BOT_PROFILES) == set(PERSONALITIES) == set(APPROVED_TRADE_PROFILES)
    a = m.bot_profile("aggressive")
    assert (a.value_multiplier, a.overbid_fraction, a.spend_ratio, a.decision_delay) == (2.0, 0.85, 2.0, (0.5, 3.0))
    c = m.trade_profile("conservative")
    assert (c.max_sport_loss, c.money_per_quality, c.min_gain_to_propose) == (0.2, 12_000_000, 0.8)
    assert all(p.response_delay[1] < 10 for p in APPROVED_TRADE_PROFILES.values())


# ------------------------------------------------------------------ carregamento padrão
def test_official_model_is_the_default(monkeypatch):
    monkeypatch.delenv("SQUADFORCE_AUCTION_MODEL", raising=False)
    assert isinstance(load_auction_model(), OfficialAuctionModel)
    monkeypatch.setenv("SQUADFORCE_AUCTION_MODEL", "none")
    assert load_auction_model() is None
