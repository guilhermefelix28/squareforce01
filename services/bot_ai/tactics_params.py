"""Parâmetros da IA tática dos bots (Entrega 6) — PROVISÓRIOS, pendentes de aprovação (PB-03).

O GDD §15 define O QUE os bots consideram (placar, tempo, força efetiva, estatísticas e eventos observados,
condição física, desvantagem numérica, situação na competição, personalidade moderada e oculta; modelo
probabilístico leve; reavaliações periódicas e por eventos; ganho mínimo; intervalo de estabilidade;
exceções para acontecimentos decisivos), mas não define números.

Os multiplicadores de gols por postura NÃO são opinião: foram MEDIDOS no próprio motor (parâmetros
`provisorio-0.5`, times equivalentes, 2500 partidas por postura) e SUAVIZADOS por um ajuste linear por
degrau (os efeitos das posturas no motor são lineares: "ofensiva" = metade de "ataque total"), o que remove o
ruído de amostragem (~±2%). Medido: ataque 0,785/0,897/1/1,103/1,199; sofridos 0,810/0,900/1/1,141/1,199.
Inclinação ajustada: +10,3% de gols marcados e +10,2% de sofridos por degrau. Se o motor mudar, medir de novo.
Entrega 9 (motor `provisorio-0.6`): re-medido no lote B da homologação (5.000 partidas) — marcados 0,78/0,89/1/1,11/1,20 e
sofridos 0,83/0,90/1/1,10/1,16 relativos à Equilibrada; diferenças ≤ 4% dos valores abaixo, mantidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PersonalityTactics:
    """Ajustes MODERADOS no valor dos resultados (apetite ao risco). Nunca altera atributos."""

    win_bonus: float  # fração extra do valor da vitória
    loss_penalty: float  # fração do valor da vitória descontada na derrota (aversão ao risco)
    opportunism: float  # bônus à vitória quando o adversário está com menos jogadores ou o jogo está aberto
    risk_aversion: float  # aversão à perda: peso da queda esperada em relação ao resultado vigente


@dataclass(frozen=True)
class TacticsParams:
    version: str = "provisorio-0.7"
    status: str = "PROVISÓRIO — pendente de aprovação (PB-03)"

    # ---------------------------------------------------------------- reavaliação e estabilidade
    eval_interval: float = 300.0  # reavaliação periódica a cada 5 min de jogo
    stability_seconds: float = 600.0  # intervalo mínimo entre mudanças (exceto acontecimentos decisivos)
    min_benefit: float = 0.030  # ganho mínimo de utilidade (em "pontos esperados") no início do jogo
    hysteresis: float = 0.025  # margem extra para voltar a uma postura abandonada há pouco
    revert_window: float = 900.0
    late_scale_floor: float = 0.15  # limiar = min_benefit × (piso + fração restante): decisões finais exigem menos
    decisive_triggers: frozenset = frozenset({"goal_for", "goal_against", "red_own", "red_opp",
                                              "player_off_own", "player_off_opp"})

    # ---------------------------------------------------------------- modelo de gols (Poisson)
    base_goals_per_team: float = 1.15  # média observada nos lotes exploratórios do motor (2,30 por partida)
    prior_weight: float = 1.0  # peso (em partidas) da expectativa anterior frente ao xG observado no jogo
    quality_reference: float = 60.0  # qualidade efetiva média dos titulares na base real (lote exploratório)
    quality_slope: float = 0.035  # efeito da qualidade própria na taxa de gols (log)
    missing_player_attack: float = 0.85  # por jogador a menos: ataque × 0,85
    missing_player_defense: float = 1.18  # por jogador a menos: gols sofridos × 1,18
    max_goals: int = 10

    # medidos no motor (ver docstring): marcados/sofridos relativos à postura equilibrada
    posture_attack: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "retranca": 0.793, "defensiva": 0.897, "equilibrada": 1.0, "ofensiva": 1.103, "ataque_total": 1.207,
    }))
    posture_defense: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "retranca": 0.796, "defensiva": 0.898, "equilibrada": 1.0, "ofensiva": 1.102, "ataque_total": 1.204,
    }))
    posture_fatigue: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "retranca": 0.92, "defensiva": 0.96, "equilibrada": 1.0, "ofensiva": 1.05, "ataque_total": 1.10,
    }))
    fatigue_threshold: float = 70.0  # condição média abaixo disso torna posturas intensas mais caras
    fatigue_cost: float = 0.6  # custo por (excesso de desgaste da postura) × (déficit de condição relativo)
    intensity_cost: float = 0.0  # custo convexo (degraus²); testado e DESCARTADO (anulava reações coerentes) — mantido 0
    projected_fatigue_cost: float = 0.15  # custo do desgaste extra projetado (∝ tempo restante; ajustado em lote)

    # ---------------------------------------------------------------- escalação e formação
    performance_weight: float = 0.04  # ± por ponto de nota média recente acima/abaixo de 6,5
    reference_formation_bonus: float = 0.6  # preferência pela formação de referência (antes do leilão)
    opponent_adjust: float = 0.25  # ajuste por vaga defensiva/ofensiva conforme histórico público do adversário
    bench_weight: float = 0.08

    # ---------------------------------------------------------------- personalidades (moderadas)
    personalities: Mapping[str, PersonalityTactics] = field(default_factory=lambda: MappingProxyType({
        # Moderação: em situações claras (perdendo/vencendo) todas concordam; a personalidade só desloca a
        # fronteira de decisão nos empates (varredura documentada em docs/architecture/ia-tatica-lotes.md).
        "aggressive": PersonalityTactics(0.04, 0.0, 0.0, 0.55),
        "conservative": PersonalityTactics(0.0, 0.0, 0.0, 1.00),
        "balanced": PersonalityTactics(0.0, 0.0, 0.0, 0.85),
        "opportunist": PersonalityTactics(0.0, 0.0, 0.12, 0.70),
    }))


DEFAULT_TACTICS = TacticsParams()
