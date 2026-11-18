"""Motor do mercado de negociações (GDD §8) — relógio autoritativo e decisões atômicas.

Garantias (sob uma única trava):
- Troca de exatamente um jogador por outro, dinheiro opcional pago SOMENTE pelo proponente.
- Uma proposta pendente por proponente; até 3 negociações concluídas por clube.
- Prazo de 10 s (limitado ao fim do mercado); sem contraproposta; cancelamento pelo proponente.
- Cada proposta recebe UMA decisão final: aceita, rejeitada, cancelada, expirada ou invalidada.
  Aceitar, cancelar e expirar ao mesmo tempo resultam em uma única decisão válida.
- Conclusão atômica por cópia-e-confirmação: os novos elencos e saldos são montados e validados
  (18 jogadores, sem duplicação, saldo >= 0) antes de substituir o estado. Falha => nada muda.
- Identificador de operação por clube: comando repetido devolve o mesmo resultado, sem nova troca.
- Linha do tempo determinística: expirações, respostas dos bots, novas propostas e o fim do mercado
  são processados em ordem de tempo do servidor até o instante do relógio.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from services.auction.engine import Contract
from services.auction.model import PERSONALITIES, AuctionModel, AuctionModelError
from services.bot_ai.trade_bot import choose_proposal, evaluate_offer
from squadforce_shared.domain.players import PlayerProfile

from . import rules

Clock = Callable[[], float]
FINAL = {"accepted", "rejected", "cancelled", "expired", "invalidated"}


class TradingError(Exception):
    def __init__(self, code: str, message: str, *, status: int = 409, retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        self.details = details or {}


@dataclass
class Proposal:
    id: str
    proponent: int
    recipient: int
    offered_player_id: int
    requested_player_id: int
    money: int
    created_at: float
    expires_at: float
    seq: int
    status: str = "pending"
    decided_at: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TradeRecord:
    proposal_id: str
    proponent: int
    recipient: int
    offered_player_id: int
    requested_player_id: int
    money: int
    completed_at: float


@dataclass
class TradeClub:
    club_uid: int
    is_bot: bool
    personality: str | None
    budget: int
    contracts: list[Contract]
    completed: int = 0


class TradingEngine:
    def __init__(
        self,
        *,
        clubs: Mapping[int, tuple[int, Sequence[Contract], str | None]],  # club -> (saldo, contratos, personalidade)
        user_club_uid: int,
        players: Mapping[int, PlayerProfile],
        model: AuctionModel,
        rng: random.Random,
        clock: Clock,
    ):
        self.model, self.rng, self.clock = model, rng, clock
        self.user_club_uid = user_club_uid
        self.players = dict(players)
        self.clubs: dict[int, TradeClub] = {}
        for uid, (budget, contracts, personality) in clubs.items():
            if len(contracts) != rules.SQUAD_SIZE or budget < 0:
                raise ValueError(f"Clube {uid} não pode entrar no mercado: precisa de 18 contratados e saldo >= 0.")
            is_bot = uid != user_club_uid
            if is_bot and personality not in PERSONALITIES:
                raise ValueError(f"Clube {uid} sem personalidade válida.")
            self.clubs[uid] = TradeClub(uid, is_bot, personality if is_bot else None, budget, list(contracts))
        if user_club_uid not in self.clubs:
            raise ValueError("Clube do usuário ausente do mercado.")
        self._check_integrity()
        for name in PERSONALITIES:
            prof = model.trade_profile(name)
            if not 0 <= prof.response_delay[0] <= prof.response_delay[1] < rules.PROPOSAL_SECONDS:
                raise AuctionModelError(f"Tempo de resposta do perfil {name} deve ficar dentro dos 10 s da proposta.")
            if not 0 < prof.proposal_interval[0] <= prof.proposal_interval[1]:
                raise AuctionModelError(f"Intervalo de propostas do perfil {name} inválido.")
        self.phase = "pending"  # pending -> running -> finished
        self.started_at: float | None = None
        self.ends_at: float | None = None
        self.proposals: dict[str, Proposal] = {}
        self.history: list[TradeRecord] = []
        self._seq = 0
        self._ops: dict[tuple[int, str], tuple[tuple, Any]] = {}
        self._bot_next: dict[int, float] = {}
        self._bot_responses: dict[str, float] = {}
        self._events: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # ================================================================ ciclo de vida
    def start(self) -> None:
        with self._lock:
            if self.phase != "pending":
                raise TradingError("MARKET_ALREADY_STARTED", "O mercado já foi iniciado.")
            now = self.clock()
            self.phase, self.started_at, self.ends_at = "running", now, now + rules.MARKET_SECONDS
            for uid, c in sorted(self.clubs.items()):
                if c.is_bot:
                    self._bot_next[uid] = now + self.rng.uniform(*self.model.trade_profile(c.personality).proposal_interval)
            self._events.append({"type": "trading.started"})

    def tick(self) -> list[dict[str, Any]]:
        with self._lock:
            self._advance(self.clock())
            events, self._events = self._events, []
            return events

    def _next_event(self) -> tuple[float, int, str, Any] | None:
        """Próximo acontecimento da linha do tempo: (instante, prioridade, tipo, alvo)."""
        cands: list[tuple[float, int, str, Any]] = []
        for p in self.proposals.values():
            if p.status == "pending":
                cands.append((p.expires_at, 0, "expire", p.id))
        for pid, due in self._bot_responses.items():
            cands.append((due, 1, "respond", pid))
        for uid, due in self._bot_next.items():
            if due < self.ends_at:
                cands.append((due, 2, "propose", uid))
        cands.append((self.ends_at, 3, "close", None))
        return min(cands) if cands else None

    def _advance(self, now: float) -> None:
        while self.phase == "running":
            ev = self._next_event()
            if ev is None or ev[0] > now:
                return
            at, _, kind, target = ev
            if kind == "expire":
                self._decide(self.proposals[target], "expired", at, "prazo de 10 s esgotado")
            elif kind == "respond":
                del self._bot_responses[target]
                self._bot_respond(self.proposals[target], at)
            elif kind == "propose":
                self._bot_propose(target, at)
            else:
                for p in self.proposals.values():
                    if p.status == "pending":
                        self._decide(p, "expired", at, "mercado encerrado")
                self.phase = "finished"
                self._bot_next.clear()
                self._bot_responses.clear()
                self._events.append({"type": "trading.finished"})

    # ================================================================ comandos
    def _replay(self, club: int, op_id: str, fp: tuple):
        key = (club, op_id)
        if key in self._ops:
            prev_fp, result = self._ops[key]
            if prev_fp != fp:
                raise TradingError("OPERATION_ID_REUSED", "Este identificador de operação já foi usado com outro comando.")
            if isinstance(result, TradingError):
                raise result  # comando repetido: mesmo erro definitivo, nada é reexecutado
            return True, result
        return False, None

    def propose(self, proponent: int, recipient: int, offered: int, requested: int, money: int, op_id: str) -> Proposal:
        with self._lock:
            now = self.clock()
            self._advance(now)
            fp = ("propose", recipient, offered, requested, money)
            seen, result = self._replay(proponent, op_id, fp)
            if seen:
                return result
            p = self._create(proponent, recipient, offered, requested, money, now)
            self._ops[(proponent, op_id)] = (fp, p)
            return p

    def respond(self, club: int, proposal_id: str, accept: bool, op_id: str) -> Proposal:
        with self._lock:
            now = self.clock()
            self._advance(now)
            fp = ("respond", proposal_id, accept)
            seen, result = self._replay(club, op_id, fp)
            if seen:
                return result
            p = self._get(proposal_id)
            if p.recipient != club:
                raise TradingError("NOT_RECIPIENT", "Somente o clube que recebeu a proposta pode respondê-la.", status=403)
            try:
                self._require_pending(p)
                if accept:
                    self._accept(p, now)
                else:
                    self._decide(p, "rejected", now, "rejeitada pelo destinatário")
            except TradingError as exc:
                if not exc.retryable:
                    self._ops[(club, op_id)] = (fp, exc)
                raise
            snapshot = replace(p)
            self._ops[(club, op_id)] = (fp, snapshot)
            return snapshot

    def cancel(self, club: int, proposal_id: str, op_id: str) -> Proposal:
        with self._lock:
            now = self.clock()
            self._advance(now)
            fp = ("cancel", proposal_id)
            seen, result = self._replay(club, op_id, fp)
            if seen:
                return result
            p = self._get(proposal_id)
            if p.proponent != club:
                raise TradingError("NOT_PROPONENT", "Somente o proponente pode cancelar a proposta.", status=403)
            try:
                self._require_pending(p)
            except TradingError as exc:
                self._ops[(club, op_id)] = (fp, exc)
                raise
            self._decide(p, "cancelled", now, "cancelada pelo proponente")
            snapshot = replace(p)
            self._ops[(club, op_id)] = (fp, snapshot)
            return snapshot

    # ================================================================ regras
    def _get(self, proposal_id: str) -> Proposal:
        p = self.proposals.get(proposal_id)
        if p is None:
            raise TradingError("PROPOSAL_NOT_FOUND", "Proposta não encontrada.", status=404)
        return p

    def _require_pending(self, p: Proposal) -> None:
        if p.status != "pending":
            raise TradingError("PROPOSAL_NOT_PENDING", f"A proposta já foi decidida ({p.status}).",
                               details={"status": p.status, "reason": p.reason})

    def _owner(self, player_id: int) -> int | None:
        for uid, c in self.clubs.items():
            if any(k.player_id == player_id for k in c.contracts):
                return uid
        return None

    def _create(self, proponent: int, recipient: int, offered: int, requested: int, money: int, now: float) -> Proposal:
        if self.phase != "running" or now >= self.ends_at:
            raise TradingError("MARKET_NOT_RUNNING", "O mercado de negociações não está aberto.")
        a, b = self.clubs.get(proponent), self.clubs.get(recipient)
        if a is None or b is None:
            raise TradingError("CLUB_NOT_IN_MARKET", "Clube fora do mercado.", status=422)
        if proponent == recipient:
            raise TradingError("SAME_CLUB", "Não é possível negociar com o próprio clube.", status=422)
        if any(p.status == "pending" and p.proponent == proponent for p in self.proposals.values()):
            raise TradingError("PENDING_PROPOSAL_EXISTS", "Você já tem uma proposta pendente. Aguarde ou cancele-a.")
        for c in (a, b):
            if c.completed >= rules.MAX_COMPLETED_TRADES:
                raise TradingError("TRADE_LIMIT_REACHED", f"O clube {c.club_uid} já concluiu 3 negociações.",
                                   status=422, details={"club_uid": c.club_uid})
        if self._owner(offered) != proponent:
            raise TradingError("PLAYER_NOT_OWNED", "O jogador oferecido não pertence ao seu elenco.", status=422)
        if self._owner(requested) != recipient:
            raise TradingError("PLAYER_NOT_OWNED", "O jogador desejado não pertence ao clube destinatário.", status=422)
        if isinstance(money, bool) or not isinstance(money, int) or money < 0:
            raise TradingError("INVALID_AMOUNT", "Dinheiro adicional deve ser um inteiro >= 0.", status=422)
        if money > a.budget:
            raise TradingError("INSUFFICIENT_FUNDS", "Saldo insuficiente para o dinheiro adicional.", status=422,
                               details={"budget": a.budget})
        self._seq += 1
        p = Proposal(
            id=f"T-{self._seq:04d}", proponent=proponent, recipient=recipient, offered_player_id=offered,
            requested_player_id=requested, money=money, created_at=now,
            expires_at=min(now + rules.PROPOSAL_SECONDS, self.ends_at), seq=self._seq,
        )
        self.proposals[p.id] = p
        if b.is_bot:
            due = now + self.rng.uniform(*self.model.trade_profile(b.personality).response_delay)
            if due < p.expires_at:
                self._bot_responses[p.id] = due
        self._events.append({"type": "trading.proposal_created", "involves_user": self.user_club_uid in (proponent, recipient)})
        return p

    def _decide(self, p: Proposal, status: str, at: float, reason: str) -> None:
        assert p.status == "pending" and status in FINAL
        p.status, p.decided_at, p.reason = status, at, reason
        self._bot_responses.pop(p.id, None)
        self._events.append({"type": "trading.proposal_decided", "status": status,
                             "involves_user": self.user_club_uid in (p.proponent, p.recipient)})

    def _accept(self, p: Proposal, at: float) -> None:
        a, b = self.clubs[p.proponent], self.clubs[p.recipient]
        problem = None
        if at >= p.expires_at:
            problem = "prazo esgotado"
        elif self._owner(p.offered_player_id) != a.club_uid or self._owner(p.requested_player_id) != b.club_uid:
            problem = "um dos jogadores já mudou de clube"
        elif a.completed >= rules.MAX_COMPLETED_TRADES or b.completed >= rules.MAX_COMPLETED_TRADES:
            problem = "limite de 3 negociações atingido"
        elif p.money > a.budget:
            problem = "saldo do proponente insuficiente"
        if problem:
            self._decide(p, "invalidated", at, problem)
            raise TradingError("PROPOSAL_INVALIDATED", f"A troca não pode ser concluída: {problem}.",
                               details={"reason": problem})

        # cópia-e-confirmação: monta o novo estado e valida antes de substituir
        give = next(k for k in a.contracts if k.player_id == p.offered_player_id)
        take = next(k for k in b.contracts if k.player_id == p.requested_player_id)
        new_a = [k for k in a.contracts if k is not give] + [Contract(take.player_id, take.price, "trade")]
        new_b = [k for k in b.contracts if k is not take] + [Contract(give.player_id, give.price, "trade")]
        new_budget_a, new_budget_b = a.budget - p.money, b.budget + p.money
        self._validate_commit({a.club_uid: (new_a, new_budget_a), b.club_uid: (new_b, new_budget_b)})

        a.contracts, a.budget, a.completed = new_a, new_budget_a, a.completed + 1
        b.contracts, b.budget, b.completed = new_b, new_budget_b, b.completed + 1
        self._decide(p, "accepted", at, "troca concluída")
        self.history.append(TradeRecord(p.id, a.club_uid, b.club_uid, p.offered_player_id, p.requested_player_id, p.money, at))
        self._events.append({"type": "trading.trade_completed"})
        # propostas pendentes que ficaram impossíveis são invalidadas imediatamente
        moved = {p.offered_player_id, p.requested_player_id}
        for other in self.proposals.values():
            if other.status != "pending":
                continue
            if moved & {other.offered_player_id, other.requested_player_id}:
                self._decide(other, "invalidated", at, "um dos jogadores já mudou de clube")
            elif any(self.clubs[c].completed >= rules.MAX_COMPLETED_TRADES for c in (other.proponent, other.recipient)):
                self._decide(other, "invalidated", at, "limite de 3 negociações atingido")

    def _validate_commit(self, changes: Mapping[int, tuple[list[Contract], int]]) -> None:
        """Valida o estado resultante ANTES de aplicá-lo (ponto de falha testável)."""
        owners: dict[int, int] = {}
        for uid, c in self.clubs.items():
            contracts, budget = changes.get(uid, (c.contracts, c.budget))
            if len(contracts) != rules.SQUAD_SIZE or budget < 0:
                raise TradingError("TRADE_FAILED", "Troca recusada: violaria 18 jogadores ou saldo >= 0.",
                                   status=500, retryable=True)
            for k in contracts:
                if k.player_id in owners:
                    raise TradingError("TRADE_FAILED", "Troca recusada: jogador duplicado.", status=500, retryable=True)
                owners[k.player_id] = uid

    def _check_integrity(self) -> None:
        self._validate_commit({})

    # ================================================================ bots
    def _squad(self, club: int) -> list[PlayerProfile]:
        return [self.players[k.player_id] for k in self.clubs[club].contracts]

    def _bot_respond(self, p: Proposal, at: float) -> None:
        if p.status != "pending":
            return
        club = self.clubs[p.recipient]
        ev = evaluate_offer(
            self._squad(p.recipient), self.players[p.requested_player_id], self.players[p.offered_player_id],
            p.money, self.model, self.model.trade_profile(club.personality),
        )
        if ev.accept:
            try:
                self._accept(p, at)
            except TradingError:
                pass  # invalidada (estado mudou) ou falha: decisão já registrada ou proposta continua até expirar
        else:
            self._decide(p, "rejected", at, "rejeitada pelo destinatário")

    def _bot_propose(self, uid: int, at: float) -> None:
        club = self.clubs[uid]
        prof = self.model.trade_profile(club.personality)
        self._bot_next[uid] = at + self.rng.uniform(*prof.proposal_interval)
        if club.completed >= rules.MAX_COMPLETED_TRADES:
            self._bot_next.pop(uid, None)
            return
        if any(p.status == "pending" and p.proponent == uid for p in self.proposals.values()):
            return
        blocked = {x for p in self.proposals.values() if p.status == "pending"
                   for x in (p.offered_player_id, p.requested_player_id)}
        rivals = {
            c: self._squad(c) for c, info in self.clubs.items()
            if c != uid and info.completed < rules.MAX_COMPLETED_TRADES
        }
        intent = choose_proposal(self._squad(uid), club.budget, rivals, blocked, self.model, prof, self.rng)
        if intent is None:
            return
        try:
            self._create(uid, intent.recipient, intent.offered_player_id, intent.requested_player_id, intent.money, at)
        except TradingError:
            return


def integrity_problems(engine: TradingEngine, initial_total_money: int | None = None) -> list[str]:
    """Invariantes do mercado; lista vazia = íntegro."""
    problems = []
    try:
        engine._validate_commit({})
    except TradingError as exc:
        problems.append(exc.message)
    for c in engine.clubs.values():
        if c.completed > rules.MAX_COMPLETED_TRADES:
            problems.append(f"Clube {c.club_uid} com {c.completed} negociações.")
    if initial_total_money is not None:
        total = sum(c.budget for c in engine.clubs.values())
        if total != initial_total_money:
            problems.append(f"Dinheiro criado/destruído: {total} != {initial_total_money}.")
    trades = {}
    for r in engine.history:
        for c in (r.proponent, r.recipient):
            trades[c] = trades.get(c, 0) + 1
    for uid, n in trades.items():
        if n != engine.clubs[uid].completed:
            problems.append(f"Contador de negociações do clube {uid} diverge do histórico.")
    pending = [p for p in engine.proposals.values() if p.status == "pending"]
    by_proponent = {}
    for p in pending:
        by_proponent[p.proponent] = by_proponent.get(p.proponent, 0) + 1
    if any(n > rules.MAX_PENDING_PER_PROPONENT for n in by_proponent.values()):
        problems.append("Clube com mais de uma proposta pendente.")
    return problems


__all__ = ["Proposal", "TradeRecord", "TradingEngine", "TradingError", "integrity_problems"]
