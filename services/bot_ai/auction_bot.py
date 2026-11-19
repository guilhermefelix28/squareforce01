"""Decisão de lances dos bots no leilão (GDD §6).

O bot recebe SOMENTE `BotAuctionView` — informação pública (atletas da rodada, lances mínimos,
próprio orçamento e elenco, tamanhos de elenco e saldos públicos dos demais) — nunca as ofertas
sigilosas dos outros clubes. A estrutura da decisão é fixa; os números de cada personalidade vêm
de `BotProfile` (pendentes, fornecidos pelo AuctionModel).
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from services.auction.model import AuctionModel, BotProfile, PlayerProfile
from services.auction.rules import MIN_RESERVE_PER_SLOT, SQUAD_SIZE, max_affordable_bid

from .evaluation import marginal_gain, squad_quality

BID_STEP = 100_000  # lances em múltiplos de R$ 100 mil (menor botão rápido do GDD)
# Concorrência (§6, só informação pública): rivais com vaga e saldo para o lance mínimo se distribuem entre os
# atletas da rodada na proporção dos lances mínimos (os melhores atraem mais). Chance estimada de vencer =
# 1 / (1 + rivais esperados × lance mínimo / próprio lance): lances mais altos enfrentam menos concorrência.
# Parâmetro de IA (provisório, como os de tactics_params), não regra de jogo.
COMPETITION_WEIGHT = 0.5
# Escolha mista: o alvo é sorteado com probabilidade proporcional a score^SAMPLING_POWER, por um sorteio
# determinístico por (clube, atletas da rodada). Bots que pensam igual deixam de colidir no mesmo atleta.
SAMPLING_POWER = 2.0


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


def expected_rivals(view: BotAuctionView) -> dict[int, float]:
    """Rivais esperados em cada atleta da rodada, estimados SÓ com informação pública."""
    mbs = {p.unique_id: view.minimum_bids[p.unique_id] for p in view.round_players}
    total = sum(mbs.values())
    out: dict[int, float] = {}
    for pid, mb in mbs.items():
        able = sum(
            1 for uid, slots in view.rivals_open_slots.items()
            if slots > 0 and max_affordable_bid(view.rivals_budgets.get(uid, 0), SQUAD_SIZE - slots) >= mb
        )
        out[pid] = able * (mb / total if total else 0.0)
    return out


def decide_bid(view: BotAuctionView, model: AuctionModel, profile: BotProfile) -> BidIntent | None:
    """Escolhe o atleta e o valor; None = não disputar a rodada.

    Score = ganho marginal × chance estimada de vencer × (1 − price_sensitivity × preço/limite): o oportunista
    privilegia barganhas, o agressivo aceita pagar perto do limite, e todos evitam os alvos mais disputados
    quando há alternativa. Nunca reduz o próprio lance ativo.
    """
    if len(view.squad) >= SQUAD_SIZE:
        return None
    options: list[tuple[float, BidIntent]] = []
    before = squad_quality(view.squad, model)
    rivals = expected_rivals(view)
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
        win = 1.0 / (1.0 + COMPETITION_WEIGHT * rivals[p.unique_id] * min_bid / amount)
        score = gain * win * (1.0 - profile.price_sensitivity * (amount / cap if cap else 1.0))
        options.append((score, BidIntent(p.unique_id, amount)))
    return _mixed_choice(view, options)


def _mixed_choice(view: BotAuctionView, options: list[tuple[float, BidIntent]]) -> BidIntent | None:
    if not options:
        return None
    if view.own_bid is not None:  # já tem lance: mantém o alvo (só revisa o valor), sem trocar ao acaso
        same = next((o for o in options if o[1].player_id == view.own_bid[0]), None)
        if same is not None:
            return same[1]
    weights = [max(0.0, sc) ** SAMPLING_POWER for sc, _ in options]
    total = sum(weights)
    if total <= 0:
        return max(options, key=lambda o: o[0])[1]
    key = f"{view.club_uid}:" + ",".join(str(p.unique_id) for p in view.round_players)
    u = int(hashlib.sha256(key.encode()).hexdigest()[:12], 16) / 16**12
    acc = 0.0
    for w, (_, intent) in zip(weights, options):
        acc += w / total
        if u < acc:
            return intent
    return options[-1][1]


def summarize_view(view: BotAuctionView) -> Sequence[str]:
    """Campos expostos ao bot (usado no teste de vazamento de informação)."""
    return tuple(view.__dataclass_fields__)
