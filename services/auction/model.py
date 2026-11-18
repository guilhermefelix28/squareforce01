"""Ponto de extensão das regras PENDENTES de calibração (PE-01 a PE-05, PM-01).

Por decisão do responsável (2026-11-18), nenhuma fórmula econômica é inventada: o leilão só roda
quando um `AuctionModel` aprovado for fornecido. Enquanto isso, `load_auction_model()` retorna None e
o início do leilão é recusado com AUCTION_MODEL_NOT_CONFIGURED.

Um modelo é carregado pela variável de ambiente SQUADFORCE_AUCTION_MODEL="pacote.modulo:objeto".
Os testes usam um modelo FALSO em tests/support/fake_auction_model.py (nunca em produção).

Todas as saídas do modelo são VALIDADAS pelo motor contra as regras aprovadas (limites do GDD).
"""

from __future__ import annotations

import importlib
import os
import random
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from squadforce_shared.domain.players import PlayerProfile
from squadforce_shared.domain.positions import Position


@dataclass(frozen=True)
class Formation:
    """Formação: nome e exatamente 11 posições (com repetição, ex.: dois DC)."""

    name: str
    slots: tuple[Position, ...]


@dataclass(frozen=True)
class BotProfile:
    """Parâmetros de uma personalidade (Agressivo, Conservador, Equilibrado, Oportunista).

    Os VALORES são pendentes (fornecidos pelo AuctionModel). O significado de cada campo:
    - value_multiplier: quanto, sobre o valor de mercado, aceita pagar por ganho esportivo (tolerância ao risco).
    - overbid_fraction: fração entre o lance mínimo e o limite usada no lance inicial (0..1).
    - min_gain: ganho marginal mínimo para disputar um atleta.
    - price_sensitivity: peso do preço na escolha do alvo (oportunismo: maior = busca barganhas).
    - spend_ratio: fração do orçamento disponível por vaga que aceita comprometer num único atleta.
    - urgency_weight: aumento gradual do limite conforme o relógio global se esgota (sem desespero).
    - decision_delay: (mín, máx) segundos após o início da rodada para o primeiro lance.
    - reevaluation_lead: segundos antes do fim da rodada em que o bot reavalia o lance.
    """

    value_multiplier: float
    overbid_fraction: float
    min_gain: float
    price_sensitivity: float
    spend_ratio: float
    urgency_weight: float
    decision_delay: tuple[float, float]
    reevaluation_lead: float


@dataclass(frozen=True)
class Reserves:
    """§7: reserva básica (completa todos os elencos, até R$ 500 mil) e complementar (intermediários e destaques)."""

    basic: tuple[int, ...]
    complementary: tuple[int, ...]


PERSONALITIES = ("aggressive", "conservative", "balanced", "opportunist")


class AuctionModel(Protocol):
    """Fórmulas e calibrações pendentes. Implementação aprovada a ser fornecida pelo responsável."""

    version: str

    def overall(self, player: PlayerProfile) -> float:
        """PE-01: overall calibrado (mediana-alvo 70; > 90 raro)."""

    def player_quality(self, player: PlayerProfile, position: Position) -> float:
        """PE-01/PE-03: rendimento esperado na posição (ponderações + familiaridade; penalidade máx. 35%)."""

    def market_value(self, player: PlayerProfile) -> int:
        """PE-02: valor de mercado em R$ (overall calibrado + idade; referência máx. R$ 50 mi)."""

    def minimum_bid(self, player: PlayerProfile) -> int:
        """PE-02: lance mínimo em R$ (até R$ 30 mi)."""

    def basic_price(self, player: PlayerProfile) -> int:
        """PE-04: preço de um atleta da reserva básica (até R$ 500 mil)."""

    def formations(self) -> Sequence[Formation]:
        """PM-01: formações disponíveis."""

    def position_weights(
        self,
        eligible: Sequence[Position],
        needs: Mapping[Position, float],
        recent: Sequence[Position],
        available: Mapping[Position, int],
    ) -> Mapping[Position, float]:
        """PE-05: pesos do sorteio da posição da rodada (necessidade, disponibilidade, histórico)."""

    def pick_round_players(
        self,
        candidates: Sequence[PlayerProfile],
        unsold_counts: Mapping[int, int],
        rng: random.Random,
        k: int,
    ) -> Sequence[int]:
        """§5: escolhe k atletas variados em qualidade, evitando repetição excessiva de não vendidos."""

    def build_reserves(self, unsold: Sequence[PlayerProfile], slots_to_fill: int, num_clubs: int) -> Reserves:
        """PE-04: reservas básica e complementar a partir dos atletas não vendidos."""

    def bot_profile(self, personality: str) -> BotProfile:
        """Parâmetros de cada personalidade (pendentes)."""


class AuctionModelError(ValueError):
    """Saída do modelo viola uma regra aprovada do GDD."""


def load_auction_model() -> AuctionModel | None:
    spec = os.environ.get("SQUADFORCE_AUCTION_MODEL", "").strip()
    if not spec:
        return None
    module, _, attr = spec.partition(":")
    obj = getattr(importlib.import_module(module), attr or "MODEL")
    return obj() if isinstance(obj, type) else obj
