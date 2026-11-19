"""Parâmetros do motor esportivo — TODOS PROVISÓRIOS, PENDENTES DE CALIBRAÇÃO E APROVAÇÃO (PM-02).

O Game Design v5.2 define as REGRAS (eventos encadeados, xG contextual sem dupla contagem, penalidade
posicional de até 35%, lesões de 0 a 3 jogos, até 5 substituições, < 7 jogadores = encerramento, notas
0–10 etc.), mas não define NENHUM peso numérico. Os valores abaixo foram escolhidos apenas para produzir
partidas estruturalmente coerentes e foram ajustados em lotes exploratórios (ver
docs/architecture/motor-calibracao-exploratoria.md). NÃO estão calibrados com referências oficiais.

Regra de uso: nenhum número do motor fica fora deste módulo. Trocar os parâmetros = nova `version`.
O resultado de uma partida é função de (estado inicial, ENGINE_VERSION, parâmetros, semente, decisões).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

ENGINE_VERSION = "0.1.0"

# Atributos REAIS da base (Dados/jogadores.xlsx), agrupados para leitura. Nenhum atributo é inventado.
TECHNICAL = ("attributes_crossing", "attributes_dribbling", "attributes_finishing", "attributes_heading",
             "attributes_long_shots", "attributes_marking", "attributes_passing", "attributes_penalty_taking",
             "attributes_tackling", "attributes_first_touch", "attributes_technique", "attributes_corners",
             "attributes_free_kick_taking", "attributes_long_throws")
MENTAL = ("attributes_anticipation", "attributes_decisions", "attributes_positioning", "attributes_vision",
          "attributes_flair", "attributes_teamwork", "attributes_work_rate", "attributes_leadership",
          "attributes_bravery", "attributes_aggression", "attributes_composure", "attributes_concentration",
          "attributes_determination", "attributes_off_the_ball", "attributes_consistency",
          "attributes_important_matches", "attributes_dirtiness")
PHYSICAL = ("attributes_acceleration", "attributes_pace", "attributes_strength", "attributes_stamina",
            "attributes_jumping_reach", "attributes_balance", "attributes_agility", "attributes_natural_fitness",
            "attributes_injury_proneness")
GOALKEEPING = ("attributes_handling", "attributes_aerial_reach", "attributes_command_of_area",
               "attributes_communication", "attributes_kicking", "attributes_throwing", "attributes_one_on_ones",
               "attributes_reflexes", "attributes_rushing_out", "attributes_punching", "attributes_eccentricity")


def _a(*names: str) -> tuple[str, ...]:
    return tuple(f"attributes_{n}" for n in names)


# Composições de atributos por AÇÃO (pesos iguais dentro de cada composição — provisório).
SKILLS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "buildup": _a("passing", "decisions", "composure", "technique", "first_touch", "teamwork"),
    "progression": _a("passing", "vision", "dribbling", "first_touch", "technique", "decisions", "off_the_ball"),
    "creation": _a("vision", "passing", "dribbling", "flair", "technique", "off_the_ball", "crossing"),
    "pressing": _a("work_rate", "aggression", "anticipation", "acceleration", "stamina", "teamwork"),
    "midfield_defense": _a("tackling", "positioning", "anticipation", "work_rate", "marking", "decisions"),
    "box_defense": _a("marking", "tackling", "positioning", "heading", "strength", "anticipation", "concentration", "pace"),
    "finishing": _a("finishing", "composure", "technique", "first_touch"),
    "long_shot": _a("long_shots", "technique", "composure"),
    "heading": _a("heading", "jumping_reach", "strength", "bravery"),
    "penalty": _a("penalty_taking", "composure"),
    "free_kick": _a("free_kick_taking", "technique"),
    "accuracy": _a("technique", "composure", "decisions"),
    "goalkeeping": _a("reflexes", "handling", "one_on_ones", "positioning", "aerial_reach", "command_of_area"),
    "gk_penalty": _a("reflexes", "one_on_ones", "anticipation"),
    "block": _a("bravery", "positioning", "anticipation", "concentration"),
    "foul_risk": _a("aggression", "dirtiness"),
    "attack_movement": _a("off_the_ball", "acceleration", "pace", "anticipation"),
})

# Atributos afetados pelo cansaço (físicos + concentração/decisões).
FATIGUE_SENSITIVE = frozenset(PHYSICAL) | frozenset(_a("concentration", "decisions", "work_rate", "composure"))

POSTURES = ("retranca", "defensiva", "equilibrada", "ofensiva", "ataque_total")


@dataclass(frozen=True)
class PostureEffect:
    """Efeitos MODERADOS de uma postura (GDD §11). Somados às probabilidades base."""

    progression: float  # chance de avançar de zona
    creation: float  # chance de finalizar no terço final
    cover: float  # redução da progressão/criação do adversário (exposição defensiva)
    pressing: float  # intensidade sem bola (afeta faltas e roubadas)
    fatigue: float  # multiplicador do desgaste


@dataclass(frozen=True)
class MatchParams:
    version: str = "provisorio-0.6"
    status: str = "PROVISÓRIO — pendente de calibração estatística e aprovação (PM-02)"

    # ---------------------------------------------------------------- tempo
    half_seconds: int = 45 * 60
    stoppage_first: tuple[int, int] = (30, 240)
    stoppage_second: tuple[int, int] = (90, 360)
    step_seconds: tuple[float, float] = (10.0, 22.0)  # duração de cada ação de uma posse
    restart_seconds: tuple[float, float] = (5.0, 25.0)  # bola parada / reinício

    # ---------------------------------------------------------------- progressão (equilíbrio = probabilidade base)
    base_progress_def: float = 0.48  # sair do próprio terço
    base_progress_mid: float = 0.30  # entrar no terço final
    base_shot_in_final: float = 0.20  # finalizar após chegar ao terço final
    skill_slope: float = 0.007  # efeito por ponto (1–100) da diferença de composições (ajustado: favorito extremo ~79%)
    out_of_play_share: float = 0.28  # das perdas de bola, fração que vira lateral/escanteio
    corner_share_final: float = 0.38  # bolas para fora no terço final que viram escanteio
    corner_shot_prob: float = 0.30

    # ---------------------------------------------------------------- finalizações
    chance_types: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "through_ball": 0.16, "cutback": 0.10, "cross_header": 0.16, "cross_foot": 0.12,
        "individual": 0.14, "long_shot": 0.32,
    }))
    distance: Mapping[str, tuple[float, float]] = field(default_factory=lambda: MappingProxyType({
        "through_ball": (12.0, 3.5), "cutback": (9.0, 2.0), "cross_header": (8.5, 2.0), "cross_foot": (10.0, 2.5),
        "individual": (15.0, 4.0), "long_shot": (24.0, 4.0), "corner_header": (8.0, 2.0), "free_kick": (23.0, 3.0),
        "rebound": (8.0, 2.5),
    }))
    xg_intercept: float = 0.88  # Entrega 9: calibrado para gols/xG da faixa de referência (criterios.md); era 0.75
    xg_distance: float = -0.155
    xg_angle: float = 1.05  # bônus para ângulo central (0 = linha de fundo, 1 = frontal)
    xg_header: float = -0.85
    xg_pressure: float = -1.25
    xg_type_bonus: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "through_ball": 0.55, "cutback": 0.45, "individual": 0.0, "rebound": 0.35, "free_kick": -0.65,
    }))
    xg_penalty: float = 0.76
    big_chance_xg: float = 0.30  # limiar de grande chance (com pressão baixa)
    big_chance_max_pressure: float = 0.55
    shooter_effect: float = 0.55  # multiplicador de chances por desvio da habilidade (separado do xG)
    keeper_effect: float = 0.50  # idem para o goleiro (separado do finalizador)
    shooter_reference: float = 60.0  # média medida na base real (lote exploratório) — provisório
    keeper_reference: float = 65.0  # média medida na base real (lote exploratório) — provisório
    block_base: float = 0.22
    on_target_base: float = 0.27  # P(no alvo | não é gol, não bloqueado) para habilidade média
    on_target_slope: float = 0.012
    save_corner_prob: float = 0.22
    rebound_prob: float = 0.10
    woodwork_prob: float = 0.04  # das finalizações para fora, fração que acerta a trave

    # ---------------------------------------------------------------- faltas, cartões, lesões
    foul_base: float = 0.11  # das disputas perdidas pelo atacante, fração que é falta
    foul_risk_slope: float = 0.010
    penalty_box_share: float = 0.09  # faltas no terço final que ocorrem na área
    free_kick_shot_prob: float = 0.30  # faltas perigosas viram finalização direta
    yellow_prob: float = 0.12
    yellow_risk_slope: float = 0.006
    direct_red_prob: float = 0.002
    second_yellow_is_red: bool = True
    booked_caution: float = 0.35  # atleta com amarelo comete menos faltas/arrisca menos (× risco)
    injury_per_contact: float = 0.0025
    injury_proneness_slope: float = 0.012
    injury_matches_weights: tuple[float, float, float, float] = (0.45, 0.30, 0.17, 0.08)  # 0, 1, 2, 3 jogos
    red_card_suspension_matches: int = 1  # PENDENTE: GDD não define a duração (registrado em pendências)
    yellow_accumulation_threshold: int | None = None  # PENDENTE: GDD não define suspensão por acúmulo

    # ---------------------------------------------------------------- desgaste
    fatigue_per_minute: float = 0.42  # pontos de condição por minuto com stamina 50
    stamina_slope: float = 0.008
    fatigue_floor: float = 25.0
    fatigue_effect: float = 0.30  # condição 0 => atributos sensíveis × (1 − 0,30)
    action_fatigue: float = 0.35  # custo extra por disputa
    form_sd: float = 0.04  # variação de forma do dia, reduzida pela consistência

    # ---------------------------------------------------------------- posição
    max_positional_penalty: float = 0.35  # GDD §3 (aprovado): penalidade máxima de 35%
    # forma da curva entre familiaridade 1 e 100: PENDENTE (linear provisória)

    # ---------------------------------------------------------------- substituições
    max_substitutions: int = 5  # GDD §13 (aprovado)
    sub_min_minute: int = 55
    sub_condition_threshold: float = 55.0
    sub_rating_threshold: float = 5.4
    min_players: int = 7  # GDD §13 (aprovado)

    # ---------------------------------------------------------------- emergenciais
    emergency_attribute: int = 30  # "baixa qualidade" (GDD §9) — valor provisório
    emergency_age: int = 21

    # ---------------------------------------------------------------- mando
    home_advantage: float = 0.0  # PC-03 pendente: sem efeito até decisão

    # ---------------------------------------------------------------- notas
    rating_base: float = 6.0
    rating_deltas: Mapping[str, float] = field(default_factory=lambda: MappingProxyType({
        "goal": 1.0, "assist": 0.6, "key_pass": 0.15, "shot_on_target": 0.12, "shot_off_target": -0.06,
        "big_chance_missed": -0.30, "progression": 0.03, "tackle_won": 0.10, "interception": 0.08,
        "block": 0.12, "possession_lost": -0.05, "foul": -0.06, "yellow": -0.30, "red": -1.5,
        "save": 0.25, "goal_conceded_gk": -0.35, "goal_conceded_def": -0.15, "penalty_saved": 0.9,
        "penalty_conceded": -0.5, "own_half_error": -0.12,
    }))
    rating_result: float = 0.35  # vitória +, derrota −, ponderado pelo tempo em campo
    rating_clean_sheet: float = 0.45  # goleiro/defensores, ponderado pelo tempo em campo

    postures: Mapping[str, PostureEffect] = field(default_factory=lambda: MappingProxyType({
        "retranca": PostureEffect(-0.065, -0.055, 0.05, -0.03, 0.92),
        "defensiva": PostureEffect(-0.03, -0.025, 0.025, -0.015, 0.96),
        "equilibrada": PostureEffect(0.0, 0.0, 0.0, 0.0, 1.0),
        "ofensiva": PostureEffect(0.03, 0.025, -0.025, 0.02, 1.05),
        "ataque_total": PostureEffect(0.065, 0.055, -0.05, 0.04, 1.10),
    }))


DEFAULT_PARAMS = MatchParams()
