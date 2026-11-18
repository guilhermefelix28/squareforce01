"""Regras APROVADAS do leilão (GDD v5.2 §4, §5 e §7). Somente valores escritos no Game Design.

Tudo o que depende de calibração (overall, valor de mercado, lance mínimo, reservas, pesos,
formações, perfis dos bots) NÃO está aqui: vem do AuctionModel (ver model.py), pendente.
"""

from __future__ import annotations

from squadforce_shared.domain.competition import CompetitionFormat

INITIAL_BUDGET = 120_000_000  # §4: cada clube começa com R$ 120 milhões
SQUAD_SIZE = 18  # §7: exatamente 18 contratados
STARTERS = 11  # §7: 11 titulares
RESERVES = 7  # §7: sete reservas
ROUND_SECONDS = 10.0  # §5: rodadas de dez segundos
PLAYERS_PER_ROUND = 5  # §5: cinco jogadores da mesma posição principal
MIN_RESERVE_PER_SLOT = 500_000  # §5: preservar ao menos R$ 500 mil por vaga restante
POSITION_WINDOW = 14  # §5: posição elegível aparece ao menos 1x em 14 rodadas concluídas
MIN_PLAYERS_FOR_ELIGIBLE_POSITION = 5  # §5: "desde que existam pelo menos cinco jogadores elegíveis distintos"
MAX_REFERENCE_VALUE = 50_000_000  # §4: valor máximo de referência por jogador
MAX_MINIMUM_BID = 30_000_000  # §4: lance mínimo pode atingir até R$ 30 milhões
BASIC_RESERVE_MAX_PRICE = 500_000  # §7: reserva básica com preços de até R$ 500 mil por vaga
HIGHLIGHT_PERCENTILE = 85  # §7: destaque = overall calibrado no percentil 85 ou superior da base completa
MAX_HIGHLIGHTS_PER_CLUB = 1  # §7: no máximo um destaque entre as melhorias complementares
STARTERS_WEIGHT = 0.8  # §6: 80% da mudança na qualidade dos 11 titulares
RESERVES_WEIGHT = 0.2  # §6: 20% da mudança na qualidade dos sete reservas
BID_INCREMENTS = (100_000, 500_000, 1_000_000)  # §5: botões rápidos


def auction_duration_seconds(fmt: CompetitionFormat, num_clubs: int) -> int:
    """Duração global do leilão (§5)."""
    if fmt is CompetitionFormat.LEAGUE:
        if 2 <= num_clubs <= 10:
            return 10 * 60
        if 11 <= num_clubs <= 20:
            return 15 * 60
    else:
        if num_clubs in (2, 4, 8):
            return 10 * 60
        if num_clubs == 16:
            return 15 * 60
        if num_clubs == 32:
            return 20 * 60
    raise ValueError(f"Configuração sem duração definida: {fmt.value} com {num_clubs} clubes.")


def improvement_limit(auction_signings: int) -> int:
    """§7: limite de melhorias complementares = mínimo(18 − C, piso(C / 4))."""
    c = auction_signings
    return max(0, min(SQUAD_SIZE - c, c // 4))


def max_affordable_bid(budget: int, squad_count: int) -> int:
    """Maior lance possível preservando R$ 500 mil por vaga que restará APÓS esta contratação."""
    remaining_after = SQUAD_SIZE - squad_count - 1
    return budget - MIN_RESERVE_PER_SLOT * max(0, remaining_after)
