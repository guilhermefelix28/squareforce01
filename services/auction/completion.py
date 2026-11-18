"""Complementação automática dos elencos após o leilão (GDD §7).

- Reservas básica e complementar construídas pelo modelo (PE-04) a partir dos NÃO vendidos e validadas:
  disjuntas, sem atletas vendidos, básica suficiente para todas as vagas e com preço <= R$ 500 mil.
- Limite de melhorias por clube = min(18 − C, piso(C/4)), C = contratações efetivas no leilão.
- No máximo 1 destaque (overall calibrado >= percentil 85 da base completa) por clube.
- Melhoria custa a média entre valor de mercado e lance mínimo; só se o saldo preservar
  R$ 500 mil por vaga que restar.
- Distribuição justa: escolhas em turnos, um atleta por clube por turno, ordem sorteada a cada turno
  (sem prioridade fixa entre clubes). Sem compensação por mau desempenho no leilão.
- Resultado: exatamente 18 por clube, sem duplicações e sem saldo negativo (verificado ao final).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from services.bot_ai.evaluation import marginal_gain, squad_quality
from services.auction.model import AuctionModelError, PlayerProfile

from . import rules

if TYPE_CHECKING:  # pragma: no cover
    from .engine import AuctionEngine


@dataclass(frozen=True)
class CompletionPick:
    club_uid: int
    player_id: int
    price: int
    kind: str  # "improvement" | "basic"
    highlight: bool
    turn: int


@dataclass(frozen=True)
class CompletionResult:
    picks: tuple[CompletionPick, ...]
    improvement_limits: dict[int, int]
    auction_signings: dict[int, int]
    basic_reserve_size: int
    complementary_reserve_size: int


def improvement_price(engine: "AuctionEngine", pid: int) -> int:
    """§7: preço médio entre valor de mercado e lance mínimo."""
    return (engine.market_value[pid] + engine.minimum_bid[pid]) // 2


def complete_squads(engine: "AuctionEngine", unsold: Sequence[PlayerProfile]) -> CompletionResult:
    from .engine import Contract  # evita import circular

    model, rng = engine.model, engine.rng
    clubs = engine.clubs
    unsold_ids = {p.unique_id for p in unsold}
    to_fill = sum(c.open_slots for c in clubs.values())

    reserves = model.build_reserves(list(unsold), to_fill, len(clubs))
    basic, comp = list(dict.fromkeys(reserves.basic)), list(dict.fromkeys(reserves.complementary))
    if set(basic) & set(comp):
        raise AuctionModelError("Reservas básica e complementar devem ser distintas.")
    if not (set(basic) | set(comp)) <= unsold_ids:
        raise AuctionModelError("Reservas só podem conter atletas não vendidos.")
    if len(basic) < to_fill:
        raise AuctionModelError(f"Reserva básica insuficiente: {len(basic)} para {to_fill} vagas.")
    basic_price = {pid: int(model.basic_price(engine.players[pid])) for pid in basic}
    if any(not 0 < v <= rules.BASIC_RESERVE_MAX_PRICE for v in basic_price.values()):
        raise AuctionModelError("Preço da reserva básica deve estar em (0, R$ 500 mil].")

    signings = {u: len(c.contracts) for u, c in clubs.items()}
    limits = {u: rules.improvement_limit(n) for u, n in signings.items()}
    used_improvements = {u: 0 for u in clubs}
    has_highlight = {u: False for u in clubs}
    taken: set[int] = set()
    picks: list[CompletionPick] = []

    turn = 0
    while any(c.open_slots for c in clubs.values()):
        turn += 1
        order = sorted(u for u, c in clubs.items() if c.open_slots)
        rng.shuffle(order)  # ordem sorteada a cada turno: nenhuma prioridade fixa
        for uid in order:
            club = clubs[uid]
            squad = [engine.players[k.player_id] for k in club.contracts]
            before = squad_quality(squad, model)
            choice: tuple[float, int, str, int] | None = None  # (ganho, pid, tipo, preço)

            if used_improvements[uid] < limits[uid]:
                reserve_after = rules.MIN_RESERVE_PER_SLOT * (club.open_slots - 1)
                eligible_comp = [
                    pid for pid in comp
                    if pid not in taken
                    and not (engine.is_highlight(pid) and has_highlight[uid])
                    and club.budget - improvement_price(engine, pid) >= reserve_after
                ]
                for pid in _shortlist(eligible_comp, engine, taken):
                    hl = engine.is_highlight(pid)
                    if hl and has_highlight[uid]:
                        continue
                    price = improvement_price(engine, pid)
                    if club.budget - price < reserve_after:
                        continue
                    gain = _gain(squad, before, engine.players[pid], model)
                    if gain > 0 and (choice is None or gain > choice[0]):
                        choice = (gain, pid, "improvement", price)

            if choice is None:
                for pid in _shortlist(basic, engine, taken):
                    gain = _gain(squad, before, engine.players[pid], model)
                    if choice is None or gain > choice[0]:
                        choice = (gain, pid, "basic", basic_price[pid])

            if choice is None:  # impossível se a reserva básica tem tamanho suficiente
                raise AuctionModelError(f"Sem atletas para completar o clube {uid}.")
            _, pid, kind, price = choice
            hl = kind == "improvement" and engine.is_highlight(pid)
            club.budget -= price
            club.contracts.append(Contract(pid, price, kind))
            engine.sold[pid] = uid
            taken.add(pid)
            if kind == "improvement":
                used_improvements[uid] += 1
                has_highlight[uid] = has_highlight[uid] or hl
            picks.append(CompletionPick(uid, pid, price, kind, hl, turn))

    for c in clubs.values():
        if len(c.contracts) != rules.SQUAD_SIZE or c.budget < 0:
            raise RuntimeError(f"Complementação inválida para o clube {c.club_uid}.")
    return CompletionResult(tuple(picks), limits, signings, len(basic), len(comp))


SHORTLIST_PER_POSITION = 3


def _shortlist(pids, engine, taken: set[int]) -> list[int]:
    """Melhores candidatos de cada posição principal (pela própria qualidade na posição): o maior
    ganho marginal está entre eles, e o custo da avaliação fica limitado."""
    by_pos: dict = {}
    for pid in pids:
        if pid in taken:
            continue
        p = engine.players[pid]
        by_pos.setdefault(p.main_position, []).append((engine.model.player_quality(p, p.main_position), pid))
    out: list[int] = []
    for items in by_pos.values():
        items.sort(key=lambda t: (-t[0], t[1]))
        out += [pid for _, pid in items[:SHORTLIST_PER_POSITION]]
    return out


def _gain(squad, before, candidate, model) -> float:
    return marginal_gain(squad, candidate, model, before)


__all__ = ["CompletionPick", "CompletionResult", "complete_squads", "improvement_price", "marginal_gain"]
