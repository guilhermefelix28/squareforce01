"""Decisão de lances dos bots no leilão (GDD §6).

O bot recebe SOMENTE `BotAuctionView` — informação pública (atletas da rodada, lances mínimos,
próprio orçamento e elenco, tamanhos de elenco e saldos públicos dos demais) — nunca as ofertas
sigilosas dos outros clubes. A estrutura da decisão é fixa; os números de cada personalidade vêm
de `BotProfile` (pendentes, fornecidos pelo AuctionModel).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from services.auction.model import AuctionModel, BotProfile, PlayerProfile
from services.auction.rules import MIN_RESERVE_PER_SLOT, SQUAD_SIZE, max_affordable_bid

from .evaluation import marginal_gain, squad_quality

BID_STEP = 100_000  # lances em múltiplos de R$ 100 mil (menor botão rápido do GDD)


@dataclass(frozen=True)
class BotAuctionView:
    """Visão pública para o bot. Não contém lances de nenhum clube além do próprio."""

    club_uid: int
    budget: int
    squad: tuple[PlayerProfile, ...]
    round_players: tuple[PlayerProfile, ...]
    minimum_bids: Mapping[int, int]
    global_progress: float  # 0 = início do leilão, 1 = fim do relógio global
    own_bid: tuple[int, int] | None  # (player_id, valor) do próprio lance ativo
    rivals_open_slots: Mapping[int, int]  # público: vagas restantes de cada rival
    rivals_budgets: Mapping[int, int]  # público: saldo de cada rival (derivado dos resultados)


@dataclass(frozen=True)
class BidIntent:
    player_id: int
    amount: int


def _round_down(v: float) -> int:
    return int(math.floor(v / BID_STEP) * BID_STEP)


def price_cap(view: BotAuctionView, profile: BotProfile, market_value: int, gain: float) -> int:
    """Limite estratégico dinâmico para um atleta (nunca acima do permitido pela reserva por vaga)."""
    open_slots = SQUAD_SIZE - len(view.squad)
    affordable = max_affordable_bid(view.budget, len(view.squad))
    per_slot = (view.budget - MIN_RESERVE_PER_SLOT * max(0, open_slots - 1)) / max(1, open_slots)
    urgency = 1.0 + profile.urgency_weight * max(0.0, min(1.0, view.global_progress))
    by_value = market_value * profile.value_multiplier * urgency
    by_budget = per_slot * profile.spend_ratio * urgency  # spend_ratio > 1 = aceita gastar acima da média por vaga
    cap = min(by_value, by_budget, affordable) if gain > 0 else 0
    return _round_down(cap)


def decide_bid(view: BotAuctionView, model: AuctionModel, profile: BotProfile) -> BidIntent | None:
    """Escolhe o atleta e o valor; None = não disputar a rodada.

    Score = ganho marginal × (1 − price_sensitivity × preço/limite): o oportunista privilegia
    barganhas, o agressivo aceita pagar perto do limite. Nunca reduz o próprio lance ativo.
    """
    if len(view.squad) >= SQUAD_SIZE:
        return None
    best: tuple[float, BidIntent] | None = None
    before = squad_quality(view.squad, model)
    for p in view.round_players:
        min_bid = view.minimum_bids[p.unique_id]
        gain = marginal_gain(view.squad, p, model, before)
        if gain < profile.min_gain:
            continue
        cap = price_cap(view, profile, model.market_value(p), gain)
        if cap < min_bid:
            continue
        amount = _round_down(min_bid + profile.overbid_fraction * (cap - min_bid))
        amount = max(amount, min_bid)
        if view.own_bid and view.own_bid[0] == p.unique_id:
            amount = max(amount, view.own_bid[1])  # proibido reduzir o lance no mesmo atleta
        score = gain * (1.0 - profile.price_sensitivity * (amount / cap if cap else 1.0))
        if best is None or score > best[0]:
            best = (score, BidIntent(p.unique_id, amount))
    return best[1] if best else None


def summarize_view(view: BotAuctionView) -> Sequence[str]:
    """Campos expostos ao bot (usado no teste de vazamento de informação)."""
    return tuple(view.__dataclass_fields__)
