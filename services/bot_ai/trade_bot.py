"""Decisões dos bots no mercado de negociações (GDD §8).

Mesma capacidade de avaliação de todos os bots (qualidade 0,8 titulares / 0,2 reservas sobre a melhor
formação, o que já considera posições necessárias, adequação às formações e composição do elenco).
Os números de cada personalidade vêm de `TradeProfile` (pendentes, PB-02).

Aceitação (bot que RECEBE a proposta — recebe `offered` + dinheiro, cede `requested`):
1. Ganho esportivo >= 0 e saldo de valor >= −value_tolerance × valor cedido  → aceita;
2. Pequena perda (0 < perda <= max_sport_loss) com dinheiro >= perda × money_per_quality
   e saldo de valor >= 0 (justificativa econômica)                         → aceita;
3. Caso contrário                                                         → rejeita.
O saldo de valor (valor recebido + dinheiro − valor cedido) impede a exploração financeira
sistemática: ninguém leva um atleta valioso por um fraco sem pagar a diferença.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Mapping, Sequence

from services.auction.model import AuctionModel, TradeProfile
from squadforce_shared.domain.players import PlayerProfile

from .evaluation import SquadQuality, squad_quality
from services.auction.rules import RESERVES_WEIGHT, STARTERS_WEIGHT

MONEY_STEP = 100_000
CANDIDATES_PER_DECISION = 24  # limite de pares avaliados por tentativa (custo do algoritmo húngaro)


def _score(q: SquadQuality) -> float:
    return STARTERS_WEIGHT * q.starters + RESERVES_WEIGHT * q.reserves


def swap_gain(squad: Sequence[PlayerProfile], give: PlayerProfile, receive: PlayerProfile, model: AuctionModel,
              before: SquadQuality | None = None) -> float:
    """Variação 0,8/0,2 da qualidade do elenco ao trocar `give` por `receive`."""
    before = before or squad_quality(squad, model)
    after = squad_quality([p for p in squad if p.unique_id != give.unique_id] + [receive], model)
    return _score(after) - _score(before)


@dataclass(frozen=True)
class OfferEvaluation:
    accept: bool
    sport_gain: float
    value_balance: int
    reason: str


def evaluate_offer(
    squad: Sequence[PlayerProfile],
    give: PlayerProfile,
    receive: PlayerProfile,
    money: int,
    model: AuctionModel,
    profile: TradeProfile,
) -> OfferEvaluation:
    gain = swap_gain(squad, give, receive, model)
    v_give, v_receive = model.market_value(give), model.market_value(receive)
    balance = v_receive + money - v_give
    if gain >= 0 and balance >= -profile.value_tolerance * v_give:
        return OfferEvaluation(True, gain, balance, "ganho esportivo sem perda financeira relevante")
    loss = -gain
    if 0 < loss <= profile.max_sport_loss and money >= loss * profile.money_per_quality and balance >= 0:
        return OfferEvaluation(True, gain, balance, "pequena perda esportiva compensada financeiramente")
    if gain >= 0:
        return OfferEvaluation(False, gain, balance, "perda financeira excessiva")
    return OfferEvaluation(False, gain, balance, "perda esportiva não compensada")


@dataclass(frozen=True)
class ProposalIntent:
    recipient: int
    offered_player_id: int
    requested_player_id: int
    money: int


def choose_proposal(
    own_squad: Sequence[PlayerProfile],
    budget: int,
    rivals: Mapping[int, Sequence[PlayerProfile]],  # elencos públicos dos clubes elegíveis para negociar
    blocked_players: set[int],
    model: AuctionModel,
    profile: TradeProfile,
    rng: random.Random,
) -> ProposalIntent | None:
    """Procura uma troca que melhore o próprio elenco e que o rival provavelmente aceite.

    A aceitação do rival é ESTIMADA com o próprio perfil (personalidades alheias são ocultas) e
    apenas com informação pública (elencos e valores de referência do modelo).
    """
    before = squad_quality(own_squad, model)
    targets = [(club, p) for club, squad in rivals.items() for p in squad if p.unique_id not in blocked_players]
    if not targets:
        return None
    rng.shuffle(targets)
    lineup = set(before.lineup)
    # cede preferencialmente quem está fora dos titulares, da mesma posição do alvo
    bench = [p for p in own_squad if p.unique_id not in lineup and p.unique_id not in blocked_players]
    best: tuple[float, ProposalIntent] | None = None
    evaluated = 0
    for club, target in targets:
        if evaluated >= CANDIDATES_PER_DECISION:
            break
        options = [p for p in bench if p.main_position == target.main_position] or bench[:2]
        for give in options[:2]:
            evaluated += 1
            gain = swap_gain(own_squad, give, target, model, before)
            if gain < profile.min_gain_to_propose:
                continue
            their_squad = rivals[club]
            their_gain = swap_gain(their_squad, target, give, model)
            v_gap = model.market_value(target) - model.market_value(give)
            needed = max(0.0, v_gap, (-their_gain) * profile.money_per_quality if their_gain < 0 else 0.0)
            money = int(math.ceil(needed / MONEY_STEP) * MONEY_STEP)
            if money > budget * profile.max_money_share or money > budget:
                continue
            if their_gain < 0 and -their_gain > profile.max_sport_loss:
                continue  # o rival provavelmente recusaria: não insiste em proposta ruim para ele
            score = gain - money / max(1, profile.money_per_quality)
            if best is None or score > best[0]:
                best = (score, ProposalIntent(club, give.unique_id, target.unique_id, money))
    return best[1] if best else None
