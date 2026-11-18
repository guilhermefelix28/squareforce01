"""Carga, concorrência e simulações completas do leilão (inclui Liga de 20 e Copa de 32 com a base real).

Verificações independentes do motor: o vencedor de cada atleta é recalculado a partir do log de
lances aceitos; saldos, unicidade e elencos de 18 são conferidos ao final.
"""

from __future__ import annotations

import random
import threading
from collections import defaultdict

import pytest

from services.auction.engine import AuctionError, summary_ok
from services.auction.model import PERSONALITIES, BotProfile
from squadforce_shared.domain.competition import CompetitionFormat
from support.auction_fixtures import make_engine, make_pool, run_to_end
from support.fake_auction_model import FakeAuctionModel

pytestmark = pytest.mark.simulation
PASSIVE = BotProfile(1.0, 0.0, 1e12, 0.0, 1.0, 0.0, (0.0, 0.0), 0.0)


def test_concurrent_bids_keep_financial_logic_and_winners_correct():
    """32 clubes, 16 threads disparando lances enquanto outra thread avança o relógio."""
    s = make_engine(32, model=FakeAuctionModel(profiles={p: PASSIVE for p in PERSONALITIES}), pool=make_pool(200), seed=3)
    e, clock = s.engine, s.clock
    accepted: list = []  # (round, club, player, amount, accepted_at, seq)
    log_lock = threading.Lock()
    stop = threading.Event()
    errors: list[str] = []

    def bidder(worker: int):
        rng = random.Random(worker)
        n = 0
        while not stop.is_set():
            r = e.round
            if r is None:
                return
            club = rng.choice(s.clubs)
            pid = rng.choice(r.player_ids)
            amount = r.minimum_bids[pid] + rng.randrange(0, 40) * 100_000
            n += 1
            try:
                ack = e.place_bid(club, pid, amount, f"w{worker}-{n}", round_number=r.number)
            except AuctionError as exc:
                if exc.code not in {"BID_NOT_INCREASED", "INSUFFICIENT_FUNDS", "SQUAD_FULL", "STALE_ROUND",
                                    "ROUND_CLOSED", "AUCTION_NOT_RUNNING", "BELOW_MINIMUM_BID", "PLAYER_NOT_IN_ROUND"}:
                    errors.append(exc.code)
                continue
            with log_lock:
                accepted.append((ack.round, club, pid, ack.amount, ack.accepted_at, ack.seq))

    def ticker():
        for _ in range(400):
            with e.lock:
                clock.advance(0.5)
            e.tick()
            if e.phase != "running":
                break
        stop.set()

    threads = [threading.Thread(target=bidder, args=(i,)) for i in range(16)] + [threading.Thread(target=ticker)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    stop.set()
    while e.phase == "running":
        clock.advance(10)
        e.tick()

    assert not errors
    assert len(accepted) > 500
    seqs = [a[5] for a in accepted]
    assert len(seqs) == len(set(seqs))  # nenhuma aceitação duplicada

    # recalcula o vencedor de cada atleta a partir do lance ATIVO final de cada clube por rodada
    last_by_club: dict[tuple[int, int], tuple] = {}
    for a in sorted(accepted, key=lambda a: a[5]):
        last_by_club[(a[0], a[1])] = a
    bids_by_player: dict[tuple[int, int], list] = defaultdict(list)
    for (rnd, club), a in last_by_club.items():
        bids_by_player[(rnd, a[2])].append(a)
    expected = {}
    for (rnd, pid), bids in bids_by_player.items():
        win = min(bids, key=lambda a: (-a[3], a[4], a[5]))
        expected[pid] = (win[1], win[3])
    actual = {pid: (club, price) for r in e.results for pid, club, price in r.sales}
    assert actual == expected
    assert summary_ok(e) == []


def test_concurrent_ticks_are_safe():
    s = make_engine(8, pool=make_pool(120))
    e, clock = s.engine, s.clock

    def tick_many():
        for _ in range(300):
            e.tick()

    def advance():
        for _ in range(200):
            with e.lock:
                clock.advance(1.0)

    threads = [threading.Thread(target=tick_many) for _ in range(6)] + [threading.Thread(target=advance)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    run_to_end(s)
    numbers = [r.number for r in e.results]
    assert numbers == list(range(1, len(numbers) + 1))  # nenhuma rodada fechada duas vezes
    assert summary_ok(e) == []


def test_bid_throughput():
    import time

    s = make_engine(32, model=FakeAuctionModel(profiles={p: PASSIVE for p in PERSONALITIES}), pool=make_pool(100))
    e = s.engine
    pid = e.round.player_ids[0]
    mn = e.round.minimum_bids[pid]
    start = time.perf_counter()
    n = 0
    for i in range(2000):
        club = s.clubs[i % 32]
        try:
            e.place_bid(club, pid, mn + (i // 32 + 1) * 100_000, f"t{i}")
            n += 1
        except AuctionError:
            pass
    elapsed = time.perf_counter() - start
    assert n == 2000 and elapsed < 2.0, f"{n} lances em {elapsed:.2f}s"


# ------------------------------------------------------------------ base real
@pytest.fixture(scope="module")
def real_pool():
    from conftest import REAL_PLAYERS_XLSX

    if not REAL_PLAYERS_XLSX.exists():
        pytest.skip("Dados/jogadores.xlsx ausente")
    from services.data.importer import parse_clubs, parse_players, read_workbook
    from squadforce_shared.domain.players import PlayerProfile

    sheets = read_workbook(REAL_PLAYERS_XLSX.read_bytes(), "jogadores.xlsx")
    _, clubs = parse_clubs(sheets, "j")
    _, players = parse_players(sheets, "j", {c.club_uid for c in clubs})
    short = {c.club_uid: c.short_name for c in clubs}
    pool = [
        PlayerProfile(p.unique_id, p.name, p.age, p.club_uid, short[p.club_uid], tuple(p.natural_positions),
                      tuple(p.accomplished_positions), dict(p.familiarity), dict(p.attributes))
        for p in players
    ]
    return pool, [c.club_uid for c in clubs]


@pytest.mark.real_data
@pytest.mark.parametrize(
    "fmt,n",
    [(CompetitionFormat.LEAGUE, 20), (CompetitionFormat.CUP, 32), (CompetitionFormat.LEAGUE, 2),
     (CompetitionFormat.LEAGUE, 11), (CompetitionFormat.CUP, 16)],
)
def test_real_base_full_auction_every_club_ends_with_18(real_pool, fmt, n):
    import random as _r

    from services.auction.engine import AuctionEngine
    from support.auction_fixtures import EngineSetup, ManualClock

    pool, club_ids = real_pool
    clock = ManualClock()
    participants = club_ids[:n]
    e = AuctionEngine(participants=participants, user_club_uid=participants[0], fmt=fmt, num_clubs=n, pool=pool,
                      model=FakeAuctionModel(), rng=_r.Random(n), clock=clock)
    e.start()
    run_to_end(EngineSetup(e, clock, participants), step=1.0)
    assert e.phase == "completed"
    assert summary_ok(e) == []
    owners = [k.player_id for c in e.clubs.values() for k in c.contracts]
    assert len(owners) == 18 * n == len(set(owners))
    assert all(c.budget >= 0 and len(c.contracts) == 18 for c in e.clubs.values())
    assert e.finished_at <= e.ends_at
