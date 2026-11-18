"""Estresse do mercado: muitas threads propondo, aceitando, rejeitando e cancelando enquanto o relógio corre.

Ao final: 18 por clube, nenhum jogador duplicado, nenhum saldo negativo, dinheiro total conservado,
no máximo 3 trocas por clube, uma pendente por proponente, e cada troca do histórico corresponde a uma
proposta aceita exatamente uma vez.
"""

from __future__ import annotations

import random
import threading
from collections import Counter

import pytest

from services.trading.engine import TradingError, integrity_problems
from support.fake_auction_model import FakeAuctionModel
from support.trading_fixtures import make_market

pytestmark = pytest.mark.simulation
EXPECTED = {
    "PENDING_PROPOSAL_EXISTS", "TRADE_LIMIT_REACHED", "PLAYER_NOT_OWNED", "INSUFFICIENT_FUNDS", "PROPOSAL_NOT_PENDING",
    "PROPOSAL_INVALIDATED", "MARKET_NOT_RUNNING", "NOT_RECIPIENT", "NOT_PROPONENT", "PROPOSAL_NOT_FOUND",
}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_concurrent_market_operations_keep_integrity(seed):
    m = make_market(16, FakeAuctionModel(), seed=seed, budget=20_000_000)
    e = m.engine
    total = m.total_money()
    stop = threading.Event()
    unexpected: list[str] = []
    accepted_ops: list[str] = []
    lock = threading.Lock()

    def actor(worker: int):
        rng = random.Random(seed * 100 + worker)
        n = 0
        while not stop.is_set():
            n += 1
            club = rng.choice(m.clubs)
            try:
                action = rng.random()
                if action < 0.45:
                    to = rng.choice([c for c in m.clubs if c != club])
                    with e.lock:
                        give, take = rng.choice(m.roster(club)), rng.choice(m.roster(to))
                    e.propose(club, to, give, take, rng.choice([0, 0, 500_000, 3_000_000]), f"w{worker}-{n}")
                else:
                    with e.lock:
                        pending = [p for p in e.proposals.values() if p.status == "pending"]
                    if not pending:
                        continue
                    p = rng.choice(pending)
                    if action < 0.75:
                        r = e.respond(p.recipient, p.id, True, f"w{worker}-{n}")
                        if r.status == "accepted":
                            with lock:
                                accepted_ops.append(p.id)
                    elif action < 0.9:
                        e.respond(p.recipient, p.id, False, f"w{worker}-{n}")
                    else:
                        e.cancel(p.proponent, p.id, f"w{worker}-{n}")
            except TradingError as exc:
                if exc.code not in EXPECTED:
                    unexpected.append(exc.code)

    def clock():
        for _ in range(400):
            with e.lock:
                m.clock.advance(0.5)
            e.tick()
            if e.phase != "running":
                break
        stop.set()

    threads = [threading.Thread(target=actor, args=(i,)) for i in range(12)] + [threading.Thread(target=clock)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    stop.set()

    assert e.phase == "finished"
    assert not unexpected
    assert integrity_problems(e, total) == []
    statuses = Counter(p.status for p in e.proposals.values())
    assert statuses["pending"] == 0  # o fechamento decide todas
    assert statuses["accepted"] == len(e.history) > 0
    assert len(set(accepted_ops)) == len(accepted_ops)  # nenhuma proposta executada duas vezes
    assert {r.proposal_id for r in e.history} >= set(accepted_ops)
