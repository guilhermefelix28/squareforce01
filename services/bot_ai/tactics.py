"""IA tática dos bots (GDD §15) — formação, escalação, postura inicial e posturas durante o jogo.

Modelo decisório (leve, sem Monte Carlo): para cada postura, os gols que ainda podem sair são aproximados
por duas Poisson independentes, com taxas que combinam:
  - a expectativa anterior (média do motor, qualidade efetiva do PRÓPRIO time, histórico público do adversário);
  - o xG OBSERVADO nesta partida (atualização gama-Poisson);
  - os multiplicadores das posturas MEDIDOS no motor (próprios e da postura observável do adversário);
  - a desvantagem numérica observada.
Isso gera P(vitória), P(empate), P(derrota). A utilidade esperada = Σ P × valor do resultado na situação da
competição (ex.: Liga 3/1/0; precisa vencer; evitar derrota; Copa com pênaltis), ajustada moderadamente pela
personalidade e pelo custo de desgaste. A troca só ocorre com ganho mínimo, histerese e intervalo de
estabilidade — exceto após acontecimentos decisivos (gol, expulsão, jogador perdido).

Informação permitida: só `TacticalObservation` (própria equipe + acontecimentos desta partida) e o contexto
pré-jogo PÚBLICO (`PreMatchContext`). Nenhum RNG: decisões determinísticas e reproduzíveis. Nenhum bônus de
atributo: a IA só escolhe posturas, formações, escalações e substituições permitidas a qualquer clube.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from services.match_engine.availability import AvailabilityLedger
from services.match_engine.lineup import build_team_sheet, slot_value
from services.match_engine.params import DEFAULT_PARAMS, POSTURES, MatchParams
from services.match_engine.types import MatchPlayer, TacticalObservation, TeamSheet
from squadforce_shared.domain.assignment import hungarian_max
from squadforce_shared.domain.positions import Position

from .tactics_params import DEFAULT_TACTICS, TacticsParams

DEFENSIVE = {Position.GK, Position.DR, Position.DL, Position.DC, Position.DM}
ATTACKING = {Position.STC, Position.MC}


# ====================================================================== situação e contexto (públicos)
@dataclass(frozen=True)
class CompetitionSituation:
    """Valor de cada resultado para o clube nesta partida (estado PÚBLICO no início da rodada)."""

    win: float
    draw: float
    loss: float
    label: str

    @staticmethod
    def league() -> "CompetitionSituation":
        return CompetitionSituation(3.0, 1.0, 0.0, "liga")

    @staticmethod
    def must_win() -> "CompetitionSituation":
        """Precisa vencer (ex.: disputar o título): o empate vale pouco mais que a derrota."""
        return CompetitionSituation(3.0, 0.4, 0.0, "precisa_vencer")

    @staticmethod
    def avoid_defeat() -> "CompetitionSituation":
        """Precisa evitar a derrota (ex.: garantir posição): o empate vale quase uma vitória."""
        return CompetitionSituation(3.0, 2.4, -1.0, "evitar_derrota")

    @staticmethod
    def cup(penalty_win_prob: float = 0.5) -> "CompetitionSituation":
        """Mata-mata: vencer = avançar (1); empate = pênaltis; perder = eliminação (0)."""
        return CompetitionSituation(1.0, penalty_win_prob, 0.0, "copa")


def league_situation(points: int, leader_points: int, safety_points: int | None, remaining_rounds: int) -> CompetitionSituation:
    """Regra PROVISÓRIA (PB-03) a partir da classificação pública no início da rodada.

    - Ainda alcança o líder, mas só se vencer (distância > 0 e ≤ 3 × rodadas restantes, com poucas rodadas): precisa vencer.
    - Está a até 2 pontos acima da zona de perigo informada, com poucas rodadas: evitar derrota.
    - Caso contrário: Liga padrão.
    """
    gap = leader_points - points
    if remaining_rounds <= 3 and 0 < gap <= 3 * remaining_rounds:
        return CompetitionSituation.must_win()
    if safety_points is not None and remaining_rounds <= 3 and 0 <= points - safety_points <= 2:
        return CompetitionSituation.avoid_defeat()
    return CompetitionSituation.league()


@dataclass(frozen=True)
class OpponentHistory:
    """Histórico PÚBLICO do adversário (resultados anteriores)."""

    matches: int = 0
    goals_for: float = 0.0
    goals_against: float = 0.0
    recent_formations: tuple[tuple[Position, ...], ...] = ()


@dataclass(frozen=True)
class PreMatchContext:
    situation: CompetitionSituation
    personality: str  # oculta: só o próprio bot conhece
    opponent: OpponentHistory = field(default_factory=OpponentHistory)


# ====================================================================== probabilidades
def _poisson(mu: float, n: int) -> list[float]:
    probs = [math.exp(-mu)]
    for k in range(1, n + 1):
        probs.append(probs[-1] * mu / k)
    tail = max(0.0, 1.0 - sum(probs))
    probs[-1] += tail
    return probs


def outcome_probabilities(diff: int, mu_for: float, mu_against: float, max_goals: int = 10) -> tuple[float, float, float]:
    """P(vitória, empate, derrota) dado o saldo atual e as médias de gols restantes."""
    pf, pa = _poisson(max(0.0, mu_for), max_goals), _poisson(max(0.0, mu_against), max_goals)
    win = draw = loss = 0.0
    for i, a in enumerate(pf):
        for j, b in enumerate(pa):
            d = diff + i - j
            if d > 0:
                win += a * b
            elif d == 0:
                draw += a * b
            else:
                loss += a * b
    s = win + draw + loss
    return win / s, draw / s, loss / s


# ====================================================================== controlador ao vivo
class TacticalBot:
    """Controlador de um lado da partida. Uma instância por partida (guarda o histórico de decisões)."""

    def __init__(self, context: PreMatchContext, params: TacticsParams = DEFAULT_TACTICS,
                 match_params: MatchParams = DEFAULT_PARAMS):
        if context.personality not in params.personalities:
            raise ValueError(f"Personalidade desconhecida: {context.personality}")
        self.ctx, self.tp, self.mp = context, params, match_params
        self.eval_interval = params.eval_interval
        self.last_change: float | None = None
        self.previous: str | None = None
        self.decisions: list[tuple[float, str, str, float]] = []  # (segundo, de, para, ganho) — auditoria

    # ------------------------------------------------------------------ taxas
    def _own_quality(self, obs: TacticalObservation) -> float:
        vals = [slot_value(p.player, p.slot, self.mp) for p in obs.own_players]
        return sum(vals) / len(vals) if vals else self.tp.quality_reference

    def prior_rates(self, own_quality: float) -> tuple[float, float]:
        tp, opp = self.tp, self.ctx.opponent
        base = tp.base_goals_per_team
        q = math.exp(tp.quality_slope * (own_quality - tp.quality_reference))
        if opp.matches:
            opp_concedes = (opp.goals_against / opp.matches + base) / (2 * base)  # suavizado com a média
            opp_scores = (opp.goals_for / opp.matches + base) / (2 * base)
        else:
            opp_concedes = opp_scores = 1.0
        return base * q * opp_concedes, base / q * opp_scores

    def rates(self, obs: TacticalObservation, posture: str) -> tuple[float, float]:
        tp = self.tp
        prior_for, prior_against = self.prior_rates(self._own_quality(obs))
        elapsed = 1.0 - obs.remaining_fraction
        rate_for = (prior_for * tp.prior_weight + float(obs.stats_for.get("xg", 0.0))) / (tp.prior_weight + elapsed)
        rate_against = (prior_against * tp.prior_weight + float(obs.stats_against.get("xg", 0.0))) / (tp.prior_weight + elapsed)
        missing = obs.players_against - obs.players_for  # > 0: estamos com menos
        if missing > 0:
            rate_for *= tp.missing_player_attack ** missing
            rate_against *= tp.missing_player_defense ** missing
        elif missing < 0:
            rate_for *= tp.missing_player_defense ** (-missing)
            rate_against *= tp.missing_player_attack ** (-missing)
        opp_post = obs.opponent_posture if obs.opponent_posture in POSTURES else "equilibrada"
        mu_for = rate_for * tp.posture_attack[posture] * tp.posture_defense[opp_post] * obs.remaining_fraction
        mu_against = rate_against * tp.posture_defense[posture] * tp.posture_attack[opp_post] * obs.remaining_fraction
        return mu_for, mu_against

    # ------------------------------------------------------------------ utilidade
    def utility(self, obs: TacticalObservation, posture: str) -> float:
        tp = self.tp
        mu_for, mu_against = self.rates(obs, posture)
        w, d, l = outcome_probabilities(obs.goals_for - obs.goals_against, mu_for, mu_against, tp.max_goals)
        s = self.ctx.situation
        pers = tp.personalities[self.ctx.personality]
        win_value = s.win * (1 + pers.win_bonus)
        if obs.players_against < obs.players_for:
            win_value += s.win * pers.opportunism
        loss_value = s.loss - s.win * pers.loss_penalty
        mean = w * win_value + d * s.draw + l * loss_value
        # aversão à PERDA (personalidade): queda esperada em relação ao resultado vigente. Perdendo, não há o que
        # perder (nenhuma penalidade); empatando, arrisca-se o ponto; vencendo, arrisca-se a vitória.
        diff = obs.goals_for - obs.goals_against
        current = win_value if diff > 0 else s.draw if diff == 0 else loss_value
        downside = (w * max(0.0, current - win_value) + d * max(0.0, current - s.draw)
                    + l * max(0.0, current - loss_value))
        u = mean - pers.risk_aversion * downside
        # moderação: custo convexo da intensidade (degraus²), proporcional ao tempo restante
        step = POSTURES.index(posture) - POSTURES.index("equilibrada")
        u -= tp.intensity_cost * step * step * obs.remaining_fraction * s.win
        # desgaste extra projetado: posturas intensas consomem condição no tempo que resta (afeta atributos)
        u -= tp.projected_fatigue_cost * max(0.0, tp.posture_fatigue[posture] - 1.0) * obs.remaining_fraction * s.win
        # custo adicional quando o time JÁ está cansado
        cond = [p.condition for p in obs.own_players]
        avg = sum(cond) / len(cond) if cond else 100.0
        if avg < tp.fatigue_threshold:
            deficit = (tp.fatigue_threshold - avg) / tp.fatigue_threshold
            u -= tp.fatigue_cost * max(0.0, tp.posture_fatigue[posture] - 1.0) * deficit * s.win * obs.remaining_fraction
        return u

    def utilities(self, obs: TacticalObservation) -> dict[str, float]:
        return {p: self.utility(obs, p) for p in POSTURES}

    # ------------------------------------------------------------------ decisão
    def decide(self, obs: TacticalObservation) -> str | None:
        tp = self.tp
        u = self.utilities(obs)
        current = obs.own_posture
        best = max(POSTURES, key=lambda p: (round(u[p], 12), p == current, -POSTURES.index(p)))
        if best == current:
            return None
        gain = u[best] - u[current]
        decisive = any(t in tp.decisive_triggers for t in obs.triggers)
        if not decisive and self.last_change is not None and obs.second - self.last_change < tp.stability_seconds:
            return None
        threshold = tp.min_benefit * (tp.late_scale_floor + obs.remaining_fraction)
        if (best == self.previous and self.last_change is not None
                and obs.second - self.last_change < tp.revert_window):
            threshold += tp.hysteresis * (tp.late_scale_floor + obs.remaining_fraction)
        if gain < threshold:
            return None
        self.decisions.append((obs.second, current, best, gain))
        self.previous, self.last_change = current, obs.second
        return best

    def substitution_bias(self, obs: TacticalObservation) -> str | None:
        diff = obs.goals_for - obs.goals_against
        if diff < 0 and obs.own_posture in ("ofensiva", "ataque_total"):
            return "attack"
        if diff > 0 and obs.own_posture in ("retranca", "defensiva") and obs.remaining_fraction < 0.35:
            return "defend"
        return None

    def initial_posture(self, own_players: Sequence[tuple[MatchPlayer, Position]]) -> str:
        """Postura inicial pelo mesmo modelo, com 0 × 0 e todo o jogo pela frente."""
        from services.match_engine.types import OwnPlayerState

        obs = TacticalObservation(
            side=0, second=0.0, period=1, remaining_fraction=1.0, goals_for=0, goals_against=0, players_for=11,
            players_against=11, own_posture="equilibrada", opponent_posture="equilibrada",
            own_players=tuple(OwnPlayerState(p.unique_id, s, 100.0, 0, p) for p, s in own_players), bench=(),
            substitutions_left=5, stats_for={}, stats_against={}, triggers=(), knockout=False,
        )
        u = self.utilities(obs)
        best = max(POSTURES, key=lambda p: (round(u[p], 12), p == "equilibrada", -POSTURES.index(p)))
        return best if u[best] - u["equilibrada"] >= self.tp.min_benefit else "equilibrada"


# ====================================================================== formação e escalação (pré-jogo)
@dataclass(frozen=True)
class LineupChoice:
    sheet: TeamSheet
    formation_scores: Mapping[tuple[Position, ...], float]


def _performance_factor(pid: int, ratings: Mapping[int, float], tp: TacticsParams) -> float:
    r = ratings.get(pid)
    return 1.0 if r is None else max(0.85, min(1.15, 1 + tp.performance_weight * (r - 6.5)))


def _best_eleven(available: Sequence[MatchPlayer], formation: Sequence[Position], ratings: Mapping[int, float],
                 tp: TacticsParams, mp: MatchParams) -> tuple[float, list[MatchPlayer]]:
    weights = [[slot_value(p, s, mp) * _performance_factor(p.unique_id, ratings, tp) for p in available]
               for s in formation]
    total, assign = hungarian_max(weights)
    return total / len(formation), [available[a] for a in assign]


def _bench(available: Sequence[MatchPlayer], starters: Sequence[MatchPlayer], formation: Sequence[Position],
           mp: MatchParams) -> list[MatchPlayer]:
    """Reservas equilibrados: goleiro reserva (se houver), depois o melhor de cada setor, depois os melhores."""
    chosen = {p.unique_id for p in starters}
    pool = [p for p in available if p.unique_id not in chosen]
    bench: list[MatchPlayer] = []

    def best_for(slots: set[Position]) -> MatchPlayer | None:
        cands = [p for p in pool if p not in bench and p.natural_position in slots]
        return max(cands, key=lambda p: (max(slot_value(p, s, mp) for s in slots), -p.unique_id)) if cands else None

    for group in ({Position.GK}, {Position.DC, Position.DR, Position.DL}, {Position.DM, Position.MC}, {Position.STC}):
        b = best_for(group)
        if b is not None:
            bench.append(b)
    rest = sorted((p for p in pool if p not in bench),
                  key=lambda p: (-max(slot_value(p, s, mp) for s in set(formation)), p.unique_id))
    return (bench + rest)[:7]


def choose_lineup(
    club_uid: int,
    squad: Sequence[MatchPlayer],
    formations: Sequence[Sequence[Position]],
    context: PreMatchContext,
    ledger: AvailabilityLedger | None = None,
    competition: str = "",
    reference_formation: Sequence[Position] | None = None,
    recent_ratings: Mapping[int, float] | None = None,
    params: TacticsParams = DEFAULT_TACTICS,
    match_params: MatchParams = DEFAULT_PARAMS,
) -> LineupChoice:
    """Escolhe formação e escalação antes da partida (a formação fica fixa durante o jogo).

    Considera: atletas disponíveis (lesões/suspensões), qualidade efetiva na vaga (atributos + familiaridade;
    não o overall), notas recentes do próprio elenco, equilíbrio entre setores e banco, a formação de
    referência escolhida antes do leilão e o histórico público do adversário. Condição física: todos começam
    com 100% (GDD §13). Emergenciais só com menos de 11 aptos (delegado a `build_team_sheet`).
    """
    if not formations:
        raise ValueError("Nenhuma formação candidata informada (lista oficial pendente — PM-01).")
    ratings = recent_ratings or {}
    available = [p for p in squad if ledger is None or ledger.is_available(p.unique_id, competition)]
    opp = context.opponent
    base = params.base_goals_per_team
    opp_attack = (opp.goals_for / opp.matches - base) if opp.matches else 0.0
    opp_defense_leak = (opp.goals_against / opp.matches - base) if opp.matches else 0.0

    scores: dict[tuple[Position, ...], float] = {}
    best: tuple[float, tuple[Position, ...], list[MatchPlayer]] | None = None
    for f in formations:
        f = tuple(f)
        if len(available) < 11:
            starters_val, starters = 0.0, []
        else:
            starters_val, starters = _best_eleven(available, f, ratings, params, match_params)
        bench = _bench(available, starters, f, match_params) if starters else []
        bench_val = sum(max(slot_value(p, s, match_params) for s in set(f)) for p in bench) / 7 if bench else 0.0
        defensive_slots = sum(1 for s in f if s in DEFENSIVE)
        attacking_slots = sum(1 for s in f if s in ATTACKING)
        score = (starters_val + params.bench_weight * bench_val
                 + (params.reference_formation_bonus if reference_formation and f == tuple(reference_formation) else 0.0)
                 + params.opponent_adjust * (opp_attack * defensive_slots + opp_defense_leak * attacking_slots))
        scores[f] = score
        if best is None or score > best[0] + 1e-12:
            best = (score, f, starters)
    assert best is not None
    _, formation, starters = best
    if len(available) < 11:
        sheet = build_team_sheet(club_uid, available, formation, params=match_params)  # emergenciais
    else:
        bench = _bench(available, starters, formation, match_params)
        sheet = TeamSheet(club_uid, formation, tuple(starters), tuple(bench), "equilibrada")
    bot = TacticalBot(context, params, match_params)
    posture = bot.initial_posture(list(zip(sheet.starters, sheet.formation)))
    sheet = TeamSheet(sheet.club_uid, sheet.formation, sheet.starters, sheet.bench, posture)
    return LineupChoice(sheet, scores)
