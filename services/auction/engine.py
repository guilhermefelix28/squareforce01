"""Motor do leilão (GDD §5–§7) — máquina de estados com relógio autoritativo do servidor.

Garantias (todas sob uma única trava, testadas com concorrência):
- Rodadas de 10 s, contíguas, com 5 atletas da mesma posição principal; o resultado de uma rodada é
  publicado enquanto a seguinte já corre (o relógio global nunca para).
- Ofertas fechadas: um lance ativo por clube; aumentar ou trocar de alvo é atômico (se a troca falhar,
  o lance anterior permanece); aumentar ou reduzir o lance no mesmo atleta é permitido (decisão do responsável).
- Lance <= saldo − R$ 500 mil × vagas que restarão após a contratação.
- Vencedor: maior lance; empate → menor timestamp do servidor em que o valor final foi atingido →
  menor número de sequência de aceitação.
- Identificador de operação (op_id) impede lances duplicados.
- Encerramento: fim do relógio global ou todos os elencos com 18; então complementação automática.
- O tempo é sempre lido do `clock` injetado; avançar o relógio processa tudo de forma determinística.
"""

from __future__ import annotations

import math
import random
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from services.bot_ai.auction_bot import BotAuctionView, decide_bid
from squadforce_shared.domain.competition import CompetitionFormat
from squadforce_shared.domain.positions import POSITION_ORDER, Position

from . import rules
from .completion import CompletionResult, complete_squads
from .model import PERSONALITIES, AuctionModel, AuctionModelError, PlayerProfile

Clock = Callable[[], float]


class AuctionError(Exception):
    """Comando recusado. `code` estável; `retryable` indica se repetir pode funcionar."""

    def __init__(self, code: str, message: str, *, retryable: bool = False, status: int = 409, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.retryable, self.status = code, message, retryable, status
        self.details = details or {}


@dataclass(frozen=True)
class Contract:
    player_id: int
    price: int
    source: str  # "auction" | "improvement" | "basic"
    round: int | None = None


@dataclass
class ClubBook:
    club_uid: int
    is_bot: bool
    personality: str | None  # oculta (§2/§6); nunca exposta pela API
    budget: int = rules.INITIAL_BUDGET
    contracts: list[Contract] = field(default_factory=list)

    @property
    def open_slots(self) -> int:
        return rules.SQUAD_SIZE - len(self.contracts)


@dataclass
class Bid:
    club_uid: int
    player_id: int
    amount: int
    accepted_at: float
    seq: int
    op_id: str


@dataclass
class AuctionRound:
    number: int
    position: Position
    player_ids: tuple[int, ...]
    minimum_bids: dict[int, int]
    starts_at: float
    ends_at: float
    bids: dict[int, Bid] = field(default_factory=dict)  # club_uid -> lance ativo (SIGILOSO)
    forced_by_window: bool = False


@dataclass(frozen=True)
class RoundResult:
    number: int
    position: Position
    sales: tuple[tuple[int, int, int], ...]  # (player_id, club_uid, preço)
    unsold: tuple[int, ...]
    closed_at: float


@dataclass(frozen=True)
class BidAck:
    round: int
    player_id: int
    amount: int
    accepted_at: float
    seq: int
    replaced_player_id: int | None
    replayed: bool = False


class AuctionEngine:
    def __init__(
        self,
        *,
        participants: Sequence[int],
        user_club_uid: int,
        fmt: CompetitionFormat,
        num_clubs: int,
        pool: Sequence[PlayerProfile],
        model: AuctionModel,
        rng: random.Random,
        clock: Clock,
    ):
        if len(set(participants)) != len(participants) or user_club_uid not in participants:
            raise ValueError("Participantes inválidos para o leilão.")
        bind = getattr(model, "for_pool", None)
        self.model = bind(list(pool)) if callable(bind) else model  # calibrado para a base atual
        self.rng = rng
        self.clock = clock
        self.fmt, self.num_clubs = fmt, num_clubs
        self.user_club_uid = user_club_uid
        self.duration = rules.auction_duration_seconds(fmt, num_clubs)
        self.players: dict[int, PlayerProfile] = {p.unique_id: p for p in pool}
        if len(self.players) != len(pool):
            raise ValueError("Base de atletas com IDs duplicados.")
        self.clubs: dict[int, ClubBook] = {
            uid: ClubBook(uid, uid != user_club_uid, None if uid == user_club_uid else rng.choice(PERSONALITIES))
            for uid in participants
        }
        self.sold: dict[int, int] = {}
        self.unsold_counts: Counter[int] = Counter()
        self.position_log: list[Position] = []  # posição de cada rodada CONCLUÍDA, em ordem
        self.results: list[RoundResult] = []
        self.round: AuctionRound | None = None
        self.phase = "pending"  # pending -> running -> completed
        self.started_at: float | None = None
        self.ends_at: float | None = None
        self.finished_at: float | None = None
        self.finish_reason: str | None = None
        self.completion: CompletionResult | None = None
        self._seq = 0
        self._ops: dict[tuple[int, str], tuple[tuple, BidAck]] = {}
        self._bot_actions: list[tuple[float, int, int]] = []  # (instante, clube, ordem)
        self._lock = threading.RLock()
        self._pending_events: list[dict[str, Any]] = []
        self._validate_model_outputs()

    # ================================================================ validação do modelo
    def _validate_model_outputs(self) -> None:
        self.overall = {pid: float(self.model.overall(p)) for pid, p in self.players.items()}
        ranked = sorted(self.overall.values())
        # percentil 85 pelo método do posto mais próximo (nearest-rank) sobre a base completa (§7)
        rank = max(1, math.ceil(rules.HIGHLIGHT_PERCENTILE / 100 * len(ranked)))
        self.highlight_threshold = ranked[rank - 1] if ranked else math.inf
        self.minimum_bid: dict[int, int] = {}
        self.market_value: dict[int, int] = {}
        for pid, p in self.players.items():
            mb, mv = int(self.model.minimum_bid(p)), int(self.model.market_value(p))
            if not 0 < mb <= rules.MAX_MINIMUM_BID:
                raise AuctionModelError(f"Lance mínimo de {pid} fora de (0, R$ 30 mi]: {mb}")
            if not 0 < mv <= rules.MAX_REFERENCE_VALUE:
                raise AuctionModelError(f"Valor de mercado de {pid} fora de (0, R$ 50 mi]: {mv}")
            self.minimum_bid[pid], self.market_value[pid] = mb, mv
        for name in PERSONALITIES:
            prof = self.model.bot_profile(name)
            lo, hi = prof.decision_delay
            if not 0 <= lo <= hi < rules.ROUND_SECONDS or not 0 <= prof.reevaluation_lead < rules.ROUND_SECONDS:
                raise AuctionModelError(f"Tempos do perfil {name} fora da rodada de 10 s.")
        if not self.model.formations():
            raise AuctionModelError("O modelo não forneceu formações.")

    def is_highlight(self, player_id: int) -> bool:
        return self.overall[player_id] >= self.highlight_threshold

    # ================================================================ ciclo de vida
    def start(self) -> None:
        with self._lock:
            if self.phase != "pending":
                raise AuctionError("AUCTION_ALREADY_STARTED", "O leilão já foi iniciado.")
            now = self.clock()
            self.phase = "running"
            self.started_at, self.ends_at = now, now + self.duration
            self._open_round(now)

    def tick(self) -> list[dict[str, Any]]:
        """Avança o estado até o instante atual do relógio. Retorna eventos públicos novos."""
        with self._lock:
            self._advance(self.clock())
            events, self._pending_events = self._pending_events, []
            return events

    def _advance(self, now: float) -> None:
        while self.phase == "running" and self.round is not None:
            r = self.round
            self._run_bot_actions(min(now, r.ends_at))
            if now < r.ends_at:
                return
            self._close_round(r)
            if self._all_full():
                self._finish(r.ends_at, "all_squads_complete")
            elif r.ends_at >= self.ends_at:
                self._finish(r.ends_at, "time_up")
            else:
                self._open_round(r.ends_at)
                if self.round is None:
                    self._finish(r.ends_at, "no_eligible_players")

    def _all_full(self) -> bool:
        return all(c.open_slots == 0 for c in self.clubs.values())

    # ================================================================ rodadas
    def _available_by_position(self) -> dict[Position, list[PlayerProfile]]:
        out: dict[Position, list[PlayerProfile]] = {p: [] for p in POSITION_ORDER}
        for pid, p in self.players.items():
            if pid not in self.sold:
                out[p.main_position].append(p)
        return out

    def _collective_needs(self) -> dict[Position, float]:
        """Necessidade coletiva pública: vagas da formação mais exigente ainda sem atleta, somadas
        entre os clubes com vagas abertas."""
        demand = {p: 0 for p in POSITION_ORDER}
        for f in self.model.formations():
            for pos, n in Counter(f.slots).items():
                demand[pos] = max(demand[pos], n)
        needs = {p: 0.0 for p in POSITION_ORDER}
        for c in self.clubs.values():
            if c.open_slots == 0:
                continue
            have = Counter(self.players[k.player_id].main_position for k in c.contracts)
            for pos in POSITION_ORDER:
                needs[pos] += max(0, demand[pos] - have[pos])
        return needs

    def _choose_position(self, eligible: list[Position]) -> tuple[Position, bool]:
        """Regra das 14 rodadas (§5) por prazo mais próximo; senão sorteio ponderado do modelo."""
        current = len(self.position_log)  # índice desta rodada (0-based)
        last = {p: -1 for p in eligible}
        for i, p in enumerate(self.position_log):
            if p in last:
                last[p] = i
        slack = sorted((last[p] + rules.POSITION_WINDOW - current, POSITION_ORDER.index(p), p) for p in eligible)
        # slack + 1 = rodadas disponíveis (incluindo esta) até o prazo da posição. Se as k posições
        # mais urgentes não cabem nas rodadas restantes, a mais urgente é obrigatória agora (EDF).
        for k, (s, _, _) in enumerate(slack, start=1):
            if s + 1 <= k:
                return slack[0][2], True
        avail = self._available_by_position()
        weights = self.model.position_weights(
            eligible, self._collective_needs(), tuple(self.position_log[-rules.POSITION_WINDOW:]),
            {p: len(avail[p]) for p in eligible},
        )
        w = [float(weights.get(p, 0.0)) for p in eligible]
        if any(x < 0 or math.isnan(x) for x in w) or sum(w) <= 0:
            raise AuctionModelError("Pesos de posição inválidos.")
        return self.rng.choices(eligible, weights=w, k=1)[0], False

    def _open_round(self, at: float) -> None:
        self.round = None
        if at >= self.ends_at:
            return
        avail = self._available_by_position()
        eligible = [p for p in POSITION_ORDER if len(avail[p]) >= rules.MIN_PLAYERS_FOR_ELIGIBLE_POSITION]
        if not eligible:
            return
        position, forced = self._choose_position(eligible)
        candidates = avail[position]
        picked = list(self.model.pick_round_players(candidates, dict(self.unsold_counts), self.rng, rules.PLAYERS_PER_ROUND))
        valid = {p.unique_id for p in candidates}
        if len(picked) != rules.PLAYERS_PER_ROUND or len(set(picked)) != len(picked) or not set(picked) <= valid:
            raise AuctionModelError("pick_round_players deve devolver 5 atletas distintos, disponíveis e da posição.")
        number = len(self.results) + 1
        self.round = AuctionRound(
            number=number,
            position=position,
            player_ids=tuple(picked),
            minimum_bids={pid: self.minimum_bid[pid] for pid in picked},
            starts_at=at,
            ends_at=min(at + rules.ROUND_SECONDS, self.ends_at),
            forced_by_window=forced,
        )
        self._schedule_bots(self.round)
        self._pending_events.append({"type": "auction.round_started", "round": number})

    def _close_round(self, r: AuctionRound) -> None:
        by_player: dict[int, list[Bid]] = {}
        for b in r.bids.values():
            by_player.setdefault(b.player_id, []).append(b)
        sales = []
        for pid in r.player_ids:
            bids = by_player.get(pid)
            if not bids:
                continue
            win = min(bids, key=lambda b: (-b.amount, b.accepted_at, b.seq))
            club = self.clubs[win.club_uid]
            # invariantes revalidadas no fechamento (defesa em profundidade)
            if pid in self.sold or club.open_slots == 0 or win.amount > rules.max_affordable_bid(club.budget, len(club.contracts)):
                raise RuntimeError(f"Invariante violada ao vender {pid}")
            club.budget -= win.amount
            club.contracts.append(Contract(pid, win.amount, "auction", r.number))
            self.sold[pid] = club.club_uid
            sales.append((pid, club.club_uid, win.amount))
        unsold = tuple(pid for pid in r.player_ids if pid not in self.sold)
        for pid in unsold:
            self.unsold_counts[pid] += 1
        self.position_log.append(r.position)
        self.results.append(RoundResult(r.number, r.position, tuple(sales), unsold, r.ends_at))
        self._bot_actions.clear()
        self._pending_events.append({"type": "auction.round_closed", "round": r.number})

    def _finish(self, at: float, reason: str) -> None:
        self.round = None
        self.finished_at, self.finish_reason = at, reason
        unsold = [p for pid, p in self.players.items() if pid not in self.sold]
        self.completion = complete_squads(self, unsold)
        self.phase = "completed"
        self._pending_events.append({"type": "auction.finished", "reason": reason})

    # ================================================================ lances
    def place_bid(self, club_uid: int, player_id: int, amount: int, op_id: str, round_number: int | None = None) -> BidAck:
        with self._lock:
            now = self.clock()
            self._advance(now)
            key = (club_uid, op_id)
            fp = (player_id, amount, round_number)
            if key in self._ops:
                prev_fp, ack = self._ops[key]
                if prev_fp != fp:
                    raise AuctionError("OPERATION_ID_REUSED", "Este identificador de operação já foi usado com outro lance.")
                return BidAck(**{**ack.__dict__, "replayed": True})
            ack = self._accept(club_uid, player_id, amount, op_id, round_number, now)
            self._ops[key] = (fp, ack)
            return ack

    def _accept(self, club_uid: int, player_id: int, amount: int, op_id: str, round_number: int | None, at: float) -> BidAck:
        if self.phase != "running" or self.round is None:
            raise AuctionError("AUCTION_NOT_RUNNING", "O leilão não está em andamento.")
        r = self.round
        if at >= r.ends_at:
            raise AuctionError("ROUND_CLOSED", "A rodada já foi encerrada.")
        if round_number is not None and round_number != r.number:
            raise AuctionError("STALE_ROUND", f"A rodada {round_number} não está mais aberta (atual: {r.number}).",
                               details={"current_round": r.number})
        club = self.clubs.get(club_uid)
        if club is None:
            raise AuctionError("CLUB_NOT_IN_AUCTION", "Clube não participa do leilão.", status=422)
        if player_id not in r.minimum_bids:
            raise AuctionError("PLAYER_NOT_IN_ROUND", "O atleta não está nesta rodada.", status=422)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise AuctionError("INVALID_AMOUNT", "Valor inválido.", status=422)
        if club.open_slots == 0:
            raise AuctionError("SQUAD_FULL", "O elenco já tem 18 jogadores.", status=422)
        if amount < r.minimum_bids[player_id]:
            raise AuctionError("BELOW_MINIMUM_BID", "Lance abaixo do mínimo.", status=422,
                               details={"minimum_bid": r.minimum_bids[player_id]})
        limit = rules.max_affordable_bid(club.budget, len(club.contracts))
        if amount > limit:
            raise AuctionError("INSUFFICIENT_FUNDS",
                               "Lance acima do disponível (é preciso preservar R$ 500 mil por vaga restante).",
                               status=422, details={"max_bid": max(0, limit)})
        current = r.bids.get(club_uid)
        if current and current.player_id == player_id and amount == current.amount:
            # Redução permitida: decisão do responsável (2026-11-19), sobrepõe GDD §5. Repetir o valor não tem efeito.
            raise AuctionError("BID_UNCHANGED", "O lance já está neste valor.",
                               status=422, details={"current_amount": current.amount})
        self._seq += 1
        r.bids[club_uid] = Bid(club_uid, player_id, amount, at, self._seq, op_id)  # troca atômica do alvo
        return BidAck(r.number, player_id, amount, at, self._seq,
                      current.player_id if current and current.player_id != player_id else None)

    # ================================================================ bots
    def _schedule_bots(self, r: AuctionRound) -> None:
        for uid, club in sorted(self.clubs.items()):
            if not club.is_bot or club.open_slots == 0:
                continue
            prof = self.model.bot_profile(club.personality)
            first = r.starts_at + self.rng.uniform(*prof.decision_delay)
            self._bot_actions.append((first, uid, 0))
            again = r.ends_at - prof.reevaluation_lead
            if prof.reevaluation_lead > 0 and again > first:
                self._bot_actions.append((again, uid, 1))
        self._bot_actions.sort()

    def bot_view(self, club_uid: int, at: float) -> BotAuctionView:
        """Somente informação pública + o próprio lance. Nunca as ofertas de outros clubes."""
        r = self.round
        club = self.clubs[club_uid]
        own = r.bids.get(club_uid) if r else None
        return BotAuctionView(
            club_uid=club_uid,
            budget=club.budget,
            squad=tuple(self.players[c.player_id] for c in club.contracts),
            round_players=tuple(self.players[pid] for pid in r.player_ids) if r else (),
            minimum_bids=dict(r.minimum_bids) if r else {},
            global_progress=(at - self.started_at) / self.duration if self.started_at is not None else 0.0,
            own_bid=(own.player_id, own.amount) if own else None,
            rivals_open_slots={u: c.open_slots for u, c in self.clubs.items() if u != club_uid},
            rivals_budgets={u: c.budget for u, c in self.clubs.items() if u != club_uid},
        )

    def _run_bot_actions(self, until: float) -> None:
        while self._bot_actions and self._bot_actions[0][0] <= until and self.round is not None:
            at, uid, _ = self._bot_actions.pop(0)
            if at >= self.round.ends_at:
                continue
            club = self.clubs[uid]
            intent = decide_bid(self.bot_view(uid, at), self.model, self.model.bot_profile(club.personality))
            if intent is None:
                continue
            current = self.round.bids.get(uid)
            if current and current.player_id == intent.player_id and intent.amount <= current.amount:
                continue  # nada a melhorar
            try:
                self._accept(uid, intent.player_id, intent.amount, f"bot-{self.round.number}-{uid}-{at:.3f}", None, at)
            except AuctionError:
                continue  # decisão inválida: mantém o lance anterior (§5)

    # ================================================================ consultas
    @property
    def lock(self) -> threading.RLock:
        return self._lock


def summary_ok(engine: AuctionEngine) -> list[str]:
    """Verifica invariantes finais; lista vazia = tudo certo (usado em testes e no gateway)."""
    problems: list[str] = []
    owners: dict[int, int] = {}
    for c in engine.clubs.values():
        if len(c.contracts) != rules.SQUAD_SIZE:
            problems.append(f"Clube {c.club_uid} com {len(c.contracts)} jogadores.")
        if c.budget < 0:
            problems.append(f"Clube {c.club_uid} com saldo negativo.")
        spent = sum(k.price for k in c.contracts)
        if spent + c.budget != rules.INITIAL_BUDGET:
            problems.append(f"Clube {c.club_uid}: gastos e saldo não fecham.")
        for k in c.contracts:
            if k.player_id in owners:
                problems.append(f"Jogador {k.player_id} em dois clubes.")
            owners[k.player_id] = c.club_uid
    return problems
