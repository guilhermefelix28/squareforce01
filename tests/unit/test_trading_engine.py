"""Motor do mercado de negociações (GDD §8): propostas, decisões únicas, trocas atômicas e limites."""

from __future__ import annotations

import threading
from collections import Counter

import pytest

from services.bot_ai.trade_bot import evaluate_offer
from services.trading import rules
from services.trading.engine import TradingError, integrity_problems
from support.trading_fixtures import ALWAYS_ACCEPT, ALWAYS_REJECT, SILENT, make_market, model_with
from support.fake_auction_model import FakeAuctionModel


def force_bots(monkeypatch, accept: bool):
    """Substitui a avaliação dos bots por uma decisão fixa (para testar o motor isoladamente)."""
    from services.bot_ai.trade_bot import OfferEvaluation
    import services.trading.engine as eng

    monkeypatch.setattr(eng, "evaluate_offer", lambda *a, **k: OfferEvaluation(accept, 0.0, 0, "forçado no teste"))


def ok(m):
    """Elencos e saldos íntegros e dinheiro conservado (o dinheiro só muda de mãos)."""
    assert integrity_problems(m.engine, 50_000_000 * len(m.clubs)) == []


@pytest.fixture
def m():
    return make_market(4, model_with(SILENT))  # bots não propõem e só responderiam no fim do prazo


def propose(m, money=0, frm=None, to=None, give=0, take=0, op="op-1"):
    frm = frm or m.user
    to = to or m.clubs[1]
    return m.engine.propose(frm, to, m.roster(frm)[give], m.roster(to)[take], money, op)


# ------------------------------------------------------------------ propostas
def test_valid_proposal(m):
    p = propose(m, money=1_000_000)
    assert p.status == "pending" and p.money == 1_000_000
    assert p.expires_at - p.created_at == 10
    assert m.engine.clubs[m.user].budget == 50_000_000  # nada é pago antes da conclusão
    ok(m)


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(to=None, money=-1), "INVALID_AMOUNT"),
        (dict(money=50_000_001), "INSUFFICIENT_FUNDS"),
    ],
)
def test_invalid_money(m, kwargs, code):
    with pytest.raises(TradingError) as e:
        propose(m, **{k: v for k, v in kwargs.items() if v is not None})
    assert e.value.code == code
    assert not m.engine.proposals


def test_invalid_players_and_clubs(m):
    e = m.engine
    a, b = m.roster(m.user), m.roster(m.clubs[1])
    cases = [
        ((m.user, m.user, a[0], a[1], 0), "SAME_CLUB"),
        ((m.user, m.clubs[1], b[0], b[1], 0), "PLAYER_NOT_OWNED"),  # oferece jogador que não é seu
        ((m.user, m.clubs[1], a[0], a[1], 0), "PLAYER_NOT_OWNED"),  # pede jogador que o destinatário não tem
        ((m.user, 999, a[0], b[0], 0), "CLUB_NOT_IN_MARKET"),
    ]
    for i, (args, code) in enumerate(cases):
        with pytest.raises(TradingError) as err:
            e.propose(*args, f"bad-{i}")
        assert err.value.code == code
    assert not e.proposals


def test_only_one_pending_proposal_per_proponent(m):
    propose(m)
    with pytest.raises(TradingError) as e:
        propose(m, to=m.clubs[2], op="op-2")
    assert e.value.code == "PENDING_PROPOSAL_EXISTS"


def test_a_club_may_receive_several_proposals(m):
    propose(m, frm=m.clubs[1], to=m.user, op="a")
    propose(m, frm=m.clubs[2], to=m.user, op="b")
    assert Counter(p.recipient for p in m.engine.proposals.values())[m.user] == 2


def test_proposal_idempotency(m):
    a = propose(m, op="same")
    b = propose(m, op="same")
    assert a is b and len(m.engine.proposals) == 1
    with pytest.raises(TradingError) as e:
        propose(m, money=100_000, op="same")
    assert e.value.code == "OPERATION_ID_REUSED"


# ------------------------------------------------------------------ decisões
def test_accept_executes_atomic_swap_and_money():
    m = make_market(4, model_with(SILENT))
    bot = m.clubs[1]
    give, take = m.roster(bot)[0], m.roster(m.user)[3]
    p = m.engine.propose(bot, m.user, give, take, 2_000_000, "bot-op")
    m.engine.respond(m.user, p.id, True, "accept-1")
    assert p.status == "accepted"
    assert take in m.roster(bot) and give in m.roster(m.user)
    assert give not in m.roster(bot) and take not in m.roster(m.user)
    assert m.engine.clubs[bot].budget == 48_000_000 and m.engine.clubs[m.user].budget == 52_000_000
    assert m.engine.clubs[bot].completed == m.engine.clubs[m.user].completed == 1
    assert len(m.roster(bot)) == len(m.roster(m.user)) == 18
    assert m.engine.history[-1].proposal_id == p.id
    ok(m)


def test_reject_changes_nothing(m):
    before = {c: (m.roster(c), m.engine.clubs[c].budget) for c in m.clubs}
    p = propose(m, frm=m.clubs[1], to=m.user)
    m.engine.respond(m.user, p.id, False, "rej")
    assert p.status == "rejected"
    assert {c: (m.roster(c), m.engine.clubs[c].budget) for c in m.clubs} == before


def test_double_acceptance_executes_one_trade(m):
    p = propose(m, frm=m.clubs[1], to=m.user, money=1_000_000)
    m.engine.respond(m.user, p.id, True, "acc-1")
    replay = m.engine.respond(m.user, p.id, True, "acc-1")  # mesmo comando reenviado
    assert replay.status == "accepted"
    with pytest.raises(TradingError) as e:
        m.engine.respond(m.user, p.id, True, "acc-2")  # novo comando de aceitação
    assert e.value.code == "PROPOSAL_NOT_PENDING"
    assert len(m.engine.history) == 1 and m.engine.clubs[m.user].completed == 1
    ok(m)


def test_only_recipient_answers_and_only_proponent_cancels(m):
    p = propose(m)
    with pytest.raises(TradingError) as e:
        m.engine.respond(m.user, p.id, True, "x")
    assert e.value.code == "NOT_RECIPIENT"
    with pytest.raises(TradingError) as e:
        m.engine.cancel(m.clubs[1], p.id, "y")
    assert e.value.code == "NOT_PROPONENT"


def test_cancel_while_pending(m):
    p = propose(m)
    m.engine.cancel(m.user, p.id, "c1")
    assert p.status == "cancelled"
    assert m.engine.cancel(m.user, p.id, "c1").status == "cancelled"  # repetido: idempotente
    with pytest.raises(TradingError) as e:
        m.engine.cancel(m.user, p.id, "c2")
    assert e.value.code == "PROPOSAL_NOT_PENDING"
    propose(m, op="again")  # pode propor de novo após cancelar


def test_bot_accepts_or_rejects_by_its_own_evaluation(monkeypatch):
    force_bots(monkeypatch, True)
    acc = make_market(4, model_with(ALWAYS_ACCEPT))
    p = propose(acc)
    acc.clock.advance(1.0)
    acc.engine.tick()
    assert p.status == "accepted"
    ok(acc)
    force_bots(monkeypatch, False)
    rej = make_market(4, model_with(ALWAYS_REJECT))
    q = propose(rej)
    rej.clock.advance(1.0)
    rej.engine.tick()
    assert q.status == "rejected" and not rej.engine.history


# ------------------------------------------------------------------ prazos e encerramento
def test_expiration_at_exactly_ten_seconds(m):
    p = propose(m, frm=m.clubs[1], to=m.user)  # o usuário não responde
    m.clock.advance(9.999)
    m.engine.tick()
    assert p.status == "pending"
    m.clock.advance(0.001)
    m.engine.tick()
    assert p.status == "expired" and p.decided_at == p.expires_at


def test_accept_after_expiry_is_refused(m):
    p = propose(m, frm=m.clubs[1], to=m.user)
    m.clock.advance(10)
    with pytest.raises(TradingError) as e:
        m.engine.respond(m.user, p.id, True, "late")
    assert e.value.code == "PROPOSAL_NOT_PENDING" and p.status == "expired"
    assert not m.engine.history


def test_deadline_limited_by_market_end_and_market_closes(m):
    m.clock.advance(175)
    p = propose(m)
    assert p.expires_at == m.engine.ends_at
    m.clock.advance(5)
    m.engine.tick()
    assert m.engine.phase == "finished" and p.status == "expired"
    with pytest.raises(TradingError) as e:
        propose(m, op="after")
    assert e.value.code == "MARKET_NOT_RUNNING"
    assert m.engine.ends_at - m.engine.started_at == rules.MARKET_SECONDS == 180


def test_market_does_not_pause_without_requests(m):
    m.clock.advance(500)  # "desconectado": nenhum comando por 500 s
    m.engine.tick()
    assert m.engine.phase == "finished"


# ------------------------------------------------------------------ limite de três
def test_three_trade_limit_for_proponent_and_recipient(monkeypatch):
    force_bots(monkeypatch, True)
    m = make_market(5, model_with(ALWAYS_ACCEPT))
    for i in range(3):
        p = propose(m, to=m.clubs[1 + i], give=i, op=f"t{i}")
        m.clock.advance(1.0)
        m.engine.tick()
        assert p.status == "accepted"
    assert m.engine.clubs[m.user].completed == 3
    with pytest.raises(TradingError) as e:
        propose(m, to=m.clubs[4], op="t4")
    assert e.value.code == "TRADE_LIMIT_REACHED"
    with pytest.raises(TradingError) as e:  # usuário como destinatário também conta
        m.engine.propose(m.clubs[4], m.user, m.roster(m.clubs[4])[0], m.roster(m.user)[0], 0, "to-user")
    assert e.value.code == "TRADE_LIMIT_REACHED"
    ok(m)


def test_pending_proposals_are_invalidated_when_limit_or_players_change():
    m = make_market(4, model_with(SILENT))
    e = m.engine
    a = e.propose(m.clubs[1], m.user, m.roster(m.clubs[1])[0], m.roster(m.user)[0], 0, "a")
    b = e.propose(m.clubs[2], m.user, m.roster(m.clubs[2])[0], m.roster(m.user)[0], 0, "b")  # mesmo jogador do usuário
    e.respond(m.user, a.id, True, "acc")
    assert b.status == "invalidated" and "mudou de clube" in b.reason
    ok(m)


# ------------------------------------------------------------------ falha na confirmação
def test_failure_during_confirmation_changes_nothing(m, monkeypatch):
    p = propose(m, frm=m.clubs[1], to=m.user, money=3_000_000)
    before = {c: (m.roster(c), m.engine.clubs[c].budget, m.engine.clubs[c].completed) for c in m.clubs}
    original = m.engine._validate_commit

    def boom(changes):
        raise TradingError("TRADE_FAILED", "falha simulada no meio da confirmação", status=500, retryable=True)

    monkeypatch.setattr(m.engine, "_validate_commit", boom)
    with pytest.raises(TradingError) as e:
        m.engine.respond(m.user, p.id, True, "boom")
    assert e.value.retryable
    assert {c: (m.roster(c), m.engine.clubs[c].budget, m.engine.clubs[c].completed) for c in m.clubs} == before
    assert p.status == "pending" and not m.engine.history
    monkeypatch.setattr(m.engine, "_validate_commit", original)
    assert m.engine.respond(m.user, p.id, True, "boom").status == "accepted"  # repetir após a falha funciona
    ok(m)


# ------------------------------------------------------------------ concorrência
def test_concurrent_accept_cancel_and_expiry_yield_one_decision():
    for trial in range(20):
        m = make_market(4, model_with(SILENT), seed=trial)
        e = m.engine
        p = e.propose(m.clubs[1], m.user, m.roster(m.clubs[1])[0], m.roster(m.user)[0], 500_000, "p")
        m.clock.advance(9.99)
        results = []
        barrier = threading.Barrier(5)

        def accept(i):
            barrier.wait()
            try:
                results.append(("accept", e.respond(m.user, p.id, True, f"a{i}").status))
            except TradingError as exc:
                results.append(("accept", exc.code))

        def cancel():
            barrier.wait()
            try:
                results.append(("cancel", e.cancel(m.clubs[1], p.id, "c").status))
            except TradingError as exc:
                results.append(("cancel", exc.code))

        def expire():
            barrier.wait()
            with e.lock:
                m.clock.advance(0.01)
            e.tick()

        threads = [threading.Thread(target=accept, args=(i,)) for i in range(3)] + [
            threading.Thread(target=cancel), threading.Thread(target=expire)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        winners = [r for r in results if r[1] in ("accepted", "cancelled")]
        assert p.status in ("accepted", "cancelled", "expired")
        assert len(winners) <= 1
        assert len(e.history) == (1 if p.status == "accepted" else 0)
        ok(m)


def test_simultaneous_proposals_from_same_club_only_one_survives(m):
    barrier = threading.Barrier(8)
    out = []

    def go(i):
        barrier.wait()
        try:
            out.append(propose(m, to=m.clubs[1 + i % 3], op=f"sim-{i}").id)
        except TradingError as exc:
            out.append(exc.code)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for x in out if x.startswith("T-")) == 1
    assert out.count("PENDING_PROPOSAL_EXISTS") == 7


# ------------------------------------------------------------------ IA
def test_bot_to_bot_negotiation_keeps_integrity():
    m = make_market(12, FakeAuctionModel(), seed=5)
    while m.engine.phase == "running":
        m.clock.advance(0.5)
        m.engine.tick()
    trades = m.engine.history
    assert trades and all(m.user not in (t.proponent, t.recipient) for t in trades)
    assert all(c.completed <= 3 for c in m.engine.clubs.values())
    ok(m)


def test_bots_cannot_be_systematically_exploited():
    model = FakeAuctionModel()
    m = make_market(2, model)
    bot = m.clubs[1]
    squad = [m.engine.players[pid] for pid in m.roster(bot)]
    star = max(squad, key=model.market_value)
    junk = min((m.engine.players[pid] for pid in m.roster(m.user)), key=model.market_value)
    for name in ("aggressive", "conservative", "balanced", "opportunist"):
        prof = model.trade_profile(name)
        ev = evaluate_offer(squad, star, junk, 100_000, model, prof)
        assert not ev.accept, (name, ev)
        # pagando a diferença de valor e a perda esportiva, a troca passa a ser aceitável
        fair = model.market_value(star) - model.market_value(junk) + int(max(0, -ev.sport_gain) * prof.money_per_quality) + 1
        ev2 = evaluate_offer(squad, star, junk, fair, model, prof)
        assert ev2.value_balance >= 0
        if -ev2.sport_gain <= prof.max_sport_loss:
            assert ev2.accept


def test_small_sporting_loss_needs_economic_justification():
    model = FakeAuctionModel()
    m = make_market(2, model)
    squad = [m.engine.players[pid] for pid in m.roster(m.clubs[1])]
    prof = model.trade_profile("balanced")
    for give in squad:
        for recv_id in m.roster(m.user):
            recv = m.engine.players[recv_id]
            ev = evaluate_offer(squad, give, recv, 0, model, prof)
            if -prof.max_sport_loss <= ev.sport_gain < 0:
                assert not ev.accept or ev.value_balance >= 0
                needed = int(-ev.sport_gain * prof.money_per_quality) + max(0, -ev.value_balance) + 1
                assert evaluate_offer(squad, give, recv, needed, model, prof).accept
                return
    pytest.skip("nenhum par com pequena perda nesta base sintética")
