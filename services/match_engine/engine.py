"""Motor esportivo (GDD §10–§13, §16) — simulação progressiva por acontecimentos encadeados.

Fluxo de cada posse: início (reinício) → construção/progressão por zonas (defesa → meio → terço final)
com disputas contra a oposição → criação de oportunidade → finalização → bloqueio/defesa do goleiro/
gol/fora → reinício. Perdas de bola geram desarmes, interceptações, faltas (cartões, lesões, pênaltis,
faltas perigosas) ou bola fora (escanteio/lateral).

Determinismo: um único `random.Random(seed)`; formas do dia e acréscimos são sorteados no início em ordem
fixa. Decisões de postura valem a partir da primeira posse que começa em `second` ou depois, então
simular de uma vez ou em etapas (apresentação 15/30/60 s/instantânea) produz os mesmos eventos.
O placar nunca é predeterminado: só eventos de gol alteram o placar.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Protocol, Sequence

from squadforce_shared.domain.positions import Position

from .attributes import skill
from .params import DEFAULT_PARAMS, ENGINE_VERSION, POSTURES, MatchParams
from .ratings import event_deltas, live_rating
from .types import (
    Card,
    Event,
    Injury,
    MatchInput,
    MatchPlayer,
    MatchResult,
    OwnPlayerState,
    PostureChange,
    TacticalObservation,
    TeamSheet,
)


class TacticalController(Protocol):
    """Controlador tático de um lado (bots — Entrega 6). Deve ser determinístico e não usar o RNG do motor."""

    eval_interval: float  # segundos de jogo entre reavaliações periódicas

    def decide(self, obs: TacticalObservation) -> str | None: ...

    def substitution_bias(self, obs: TacticalObservation) -> str | None: ...  # "attack" | "defend" | None


TRIGGER_EVENTS = {"goal": ("goal_for", "goal_against"), "red_card": ("red_own", "red_opp"),
                  "player_off": ("player_off_own", "player_off_opp")}

DEF, MID, FINAL = 0, 1, 2
LINE = {Position.GK: "gk", Position.DR: "def", Position.DL: "def", Position.DC: "def",
        Position.DM: "mid", Position.MC: "mid", Position.STC: "att"}
SHOOTER_WEIGHT = {"att": 3.0, "mid": 1.4, "def": 0.45, "gk": 0.0}
CREATOR_WEIGHT = {"att": 1.0, "mid": 2.0, "def": 0.9, "gk": 0.05}
ASSISTED = {"through_ball", "cutback", "cross_header", "cross_foot", "corner_header"}


def _logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def contextual_xg(p: MatchParams, kind: str, distance: float, angle: float, pressure: float) -> float:
    """xG CONTEXTUAL (GDD §12): distância, ângulo, tipo de oportunidade, cabeceio e pressão defensiva.
    Não recebe atributos de finalizador nem de goleiro — eles atuam depois, separadamente."""
    if kind == "penalty":
        return p.xg_penalty
    header = kind in ("cross_header", "corner_header")
    return _logistic(p.xg_intercept + p.xg_distance * distance + p.xg_angle * angle + (p.xg_header if header else 0.0)
                     + p.xg_pressure * pressure + p.xg_type_bonus.get(kind, 0.0) - 1.6)


def is_big_chance(p: MatchParams, xg: float, pressure: float) -> bool:
    return xg >= p.big_chance_xg and pressure <= p.big_chance_max_pressure


@dataclass
class OnField:
    player: MatchPlayer
    slot: Position
    form: float
    condition: float = 100.0
    yellow: int = 0
    active: bool = True  # em campo

    @property
    def line(self) -> str:
        return LINE[self.slot]


@dataclass
class TeamState:
    side: int
    sheet: TeamSheet
    posture: str
    players: list[OnField] = field(default_factory=list)  # todos que já estiveram em campo
    bench: list[MatchPlayer] = field(default_factory=list)
    forms: dict[int, float] = field(default_factory=dict)
    subs_used: int = 0
    goals: int = 0

    def on_field(self) -> list[OnField]:
        return [p for p in self.players if p.active]

    def by_line(self, *lines: str) -> list[OnField]:
        return [p for p in self.players if p.active and p.line in lines]

    def keeper(self) -> OnField | None:
        gk = [p for p in self.players if p.active and p.slot is Position.GK]
        if gk:
            return gk[0]
        others = self.on_field()
        return min(others, key=lambda p: p.player.unique_id) if others else None


class MatchSimulation:
    def __init__(self, match: MatchInput, params: MatchParams = DEFAULT_PARAMS, decisions: Iterable[PostureChange] = (),
                 controllers: Mapping[int, TacticalController] | None = None):
        for s in (match.home, match.away):
            if s.posture not in POSTURES:
                raise ValueError(f"Postura desconhecida: {s.posture}")
        self.match, self.p = match, params
        self.rng = random.Random(match.seed)
        self.teams = [self._team(0, match.home), self._team(1, match.away)]
        s1 = self.rng.randint(*params.stoppage_first)
        s2 = self.rng.randint(*params.stoppage_second)
        self.period = 1
        self.period_end = [params.half_seconds + s1, 0.0]
        self.second_half_stoppage = s2
        self.t = 0.0
        self.period_start = 0.0
        self.events: list[Event] = []
        self.decisions: list[PostureChange] = sorted(decisions, key=lambda d: (d.second, d.side))
        for d in self.decisions:
            if d.posture not in POSTURES:
                raise ValueError(f"Postura desconhecida: {d.posture}")
        self.ball = 0  # mandante começa
        self.restart = "kickoff"
        self.zone = MID
        self.finished = False
        self.status = "completed"
        self.abandoned_side: int | None = None
        self.injuries: list[Injury] = []
        self.cards: list[Card] = []
        self.live: dict[int, float] = {}  # nota parcial incremental por jogador
        # IA tática (Entrega 6): só age se houver controlador; sem ele o caminho é idêntico ao da Entrega 5
        self.controllers: dict[int, TacticalController] = dict(controllers or {})
        self._triggers: dict[int, list[str]] = {0: [], 1: []}
        self._next_eval: dict[int, float] = {0: 0.0, 1: 0.0}
        self._sub_bias: dict[int, str | None] = {0: None, 1: None}
        self.shootout: tuple[int, int] | None = None
        self._emit("lineups", data={
            "home": [(p.player.unique_id, p.slot.value) for p in self.teams[0].players],
            "away": [(p.player.unique_id, p.slot.value) for p in self.teams[1].players],
            "home_bench": [b.unique_id for b in self.teams[0].bench],
            "away_bench": [b.unique_id for b in self.teams[1].bench],
            "emergency": [p.unique_id for s in (match.home, match.away) for p in s.starters if p.is_emergency],
            "postures": [match.home.posture, match.away.posture],
        })
        self._emit("kickoff", side=0)

    # ================================================================ preparação
    def _team(self, side: int, sheet: TeamSheet) -> TeamState:
        team = TeamState(side, sheet, sheet.posture, bench=list(sheet.bench))
        for pl in (*sheet.starters, *sheet.bench):  # forma do dia em ordem fixa (determinismo)
            consistency = pl.attributes.get("attributes_consistency", 50)
            sd = self.p.form_sd * (1.5 - consistency / 100)
            team.forms[pl.unique_id] = _clamp(self.rng.gauss(1.0, sd), 0.85, 1.15)
        for pl, slot in zip(sheet.starters, sheet.formation):
            team.players.append(OnField(pl, slot, team.forms[pl.unique_id]))
        return team

    # ================================================================ eventos
    def _clock(self) -> str:
        if self.period == 1:
            m = self.t / 60
            return f"{int(m) + 1}'" if self.t < self.p.half_seconds else f"45+{int((self.t - self.p.half_seconds) // 60) + 1}'"
        elapsed = self.t - self.period_start
        if elapsed < self.p.half_seconds:
            return f"{46 + int(elapsed // 60)}'"
        return f"90+{int((elapsed - self.p.half_seconds) // 60) + 1}'"

    def _emit(self, type_: str, side: int | None = None, player: int | None = None, other: int | None = None,
              data: dict[str, Any] | None = None) -> Event:
        ev = Event(len(self.events) + 1, round(self.t, 3), self.period, type_, side, player, other,
                   {**(data or {}), "clock": self._clock()})
        self.events.append(ev)
        for pid, delta, _ in event_deltas(ev, self.p):
            self.live[pid] = self.live.get(pid, 0.0) + delta
        if self.controllers and type_ in TRIGGER_EVENTS and side is not None:
            mine, theirs = TRIGGER_EVENTS[type_]
            self._triggers[side].append(mine)
            self._triggers[1 - side].append(theirs)
        return ev

    # ================================================================ habilidades
    def _skill(self, of: OnField, name: str) -> float:
        return skill(of.player, name, of.slot, of.condition, of.form, self.p)

    def _team_skill(self, team: TeamState, name: str, lines: Sequence[str], nominal: int) -> float:
        """Média por vaga NOMINAL: jogadores a menos (expulsões/lesões) reduzem a força."""
        group = team.by_line(*lines)
        if not group:
            return 15.0
        return sum(self._skill(p, name) for p in group) / max(nominal, len(group))

    def _nominal(self, team: TeamState, *lines: str) -> int:
        return max(1, sum(1 for s in team.sheet.formation if LINE[s] in lines))

    def _posture(self, side: int):
        return self.p.postures[self.teams[side].posture]

    def _pick(self, candidates: list[OnField], weights: list[float]) -> OnField | None:
        if not candidates:
            return None
        if sum(weights) <= 0:
            weights = [1.0] * len(candidates)
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    # ================================================================ tempo e desgaste
    def _tick(self, dt: float) -> None:
        self.t += dt
        for team in self.teams:
            mult = self.p.postures[team.posture].fatigue
            for pl in team.on_field():
                a = pl.player.attributes
                stamina = a.get("attributes_stamina", 50)
                fitness = a.get("attributes_natural_fitness", 50)
                work = a.get("attributes_work_rate", 50)
                drain = (self.p.fatigue_per_minute * dt / 60 * mult
                         * (1 - self.p.stamina_slope * ((stamina + fitness) / 2 - 50))
                         * (0.8 + 0.4 * work / 100))
                if pl.slot is Position.GK:
                    drain *= self.p.gk_fatigue_multiplier
                pl.condition = max(self.p.fatigue_floor, pl.condition - max(0.0, drain))

    def _exert(self, *players: OnField | None) -> None:
        for pl in players:
            if pl is not None:
                cost = self.p.action_fatigue * (self.p.gk_fatigue_multiplier if pl.slot is Position.GK else 1.0)
                pl.condition = max(self.p.fatigue_floor, pl.condition - cost)

    # ================================================================ laço principal
    def set_posture(self, side: int, posture: str) -> None:
        """Decisão ao vivo: vale para as posses que começarem a partir de agora."""
        if posture not in POSTURES:
            raise ValueError(f"Postura desconhecida: {posture}")
        self.decisions.append(PostureChange(self.t, side, posture))
        self.decisions.sort(key=lambda d: (d.second, d.side))

    def _apply_decisions(self) -> None:
        while self.decisions and self.decisions[0].second <= self.t:
            d = self.decisions.pop(0)
            if self.teams[d.side].posture != d.posture:
                self.teams[d.side].posture = d.posture
                self._emit("posture_change", side=d.side, data={"posture": d.posture})

    def advance_to(self, second: float) -> list[Event]:
        """Simula as posses que começam antes de `second`. Retorna os eventos novos."""
        start = len(self.events)
        while not self.finished and self.t < second:
            self._step()
        return self.events[start:]

    def run(self) -> MatchResult:
        self.advance_to(math.inf)
        return self.result()

    def _step(self) -> None:
        end = self.period_end[self.period - 1]
        if self.t >= end:
            if self.period == 1:
                self._emit("half_time")
                self.period = 2
                self.period_start = self.t
                self.period_end[1] = self.t + self.p.half_seconds + self.second_half_stoppage
                self.ball, self.restart, self.zone = 1, "kickoff", MID
                self._emit("kickoff", side=1)
            else:
                self._emit("full_time")
                if self.match.knockout and self.teams[0].goals == self.teams[1].goals:
                    self._shootout()
                self.finished = True
            return
        if self.controllers:
            self._consult_controllers()
        self._apply_decisions()
        for team in self.teams:
            self._consider_substitution(team)
        if not self.finished:
            self._possession()

    # ================================================================ posse
    def _possession(self) -> None:
        side, restart = self.ball, self.restart
        att, opp = self.teams[side], self.teams[1 - side]
        self._emit("possession", side=side, data={"zone": self.zone, "restart": restart})
        self.restart = "open_play"
        if restart in ("kickoff", "goal_kick", "throw_in", "free_kick", "keeper"):
            self._tick(self.rng.uniform(*self.p.restart_seconds))
        if restart == "corner":
            self._corner(att, opp)
            return
        if restart == "penalty":
            self._penalty(att, opp)
            return
        if restart == "free_kick_danger":
            self._shot(att, opp, "free_kick")
            return
        zone = self.zone
        pa, po = self._posture(att.side), self._posture(opp.side)
        home = self.p.home_advantage * (1 if att.side == 0 else -1) * (0 if self.match.neutral_venue else 1)
        while True:
            self._tick(self.rng.uniform(*self.p.step_seconds))
            if self.t >= self.period_end[self.period - 1]:
                return  # fim do tempo durante a posse
            if zone < FINAL:
                if zone == DEF:
                    a = self._team_skill(att, "buildup", ("def", "mid"), self._nominal(att, "def", "mid"))
                    d = self._team_skill(opp, "pressing", ("att", "mid"), self._nominal(opp, "att", "mid"))
                    base = self.p.base_progress_def
                else:
                    a = self._team_skill(att, "progression", ("mid", "att"), self._nominal(att, "mid", "att"))
                    d = self._team_skill(opp, "midfield_defense", ("mid", "def"), self._nominal(opp, "mid", "def"))
                    base = self.p.base_progress_mid
                prob = _clamp(base + self.p.skill_slope * (a - d) + pa.progression - po.cover - po.pressing / 2 + home,
                              0.05, 0.95)
                if self.rng.random() < prob:
                    pool = att.by_line("def", "mid") if zone == DEF else att.by_line("mid", "att")
                    carrier = self._pick(pool, [1.0] * len(pool))
                    zone += 1
                    self._emit("progression", side=att.side, player=carrier.player.unique_id if carrier else None,
                               data={"to_zone": zone})
                    continue
                self._lose_ball(att, opp, zone)
                return
            creation = self._team_skill(att, "creation", ("mid", "att"), self._nominal(att, "mid", "att"))
            box = self._team_skill(opp, "box_defense", ("def", "mid"), self._nominal(opp, "def", "mid"))
            prob = _clamp(self.p.base_shot_in_final + self.p.skill_slope * (creation - box) + pa.creation - po.cover + home,
                          0.05, 0.9)
            if self.rng.random() < prob:
                self._shot(att, opp, None)
            else:
                self._lose_ball(att, opp, zone)
            return

    # ================================================================ perda de bola, faltas
    def _lose_ball(self, att: TeamState, opp: TeamState, zone: int) -> None:
        carrier_pool = att.by_line(*(("def", "mid") if zone == DEF else ("mid", "att") if zone == MID else ("att", "mid")))
        defender_pool = opp.by_line(*(("att", "mid") if zone == DEF else ("mid", "def") if zone == MID else ("def", "mid")))
        carrier = self._pick(carrier_pool, [1.0] * len(carrier_pool)) or self._pick(att.on_field(), [1.0] * len(att.on_field()))
        defender = self._pick(defender_pool, [1.0] * len(defender_pool)) or self._pick(opp.on_field(), [1.0] * len(opp.on_field()))
        if carrier is None or defender is None:
            self._turnover(opp, zone)
            return
        self._exert(carrier, defender)
        risk = self._skill(defender, "foul_risk")
        p_foul = _clamp(self.p.foul_base + self.p.foul_risk_slope * (risk - 50) + self._posture(opp.side).pressing, 0.02, 0.6)
        if defender.yellow:
            p_foul *= self.p.booked_caution
        if self.rng.random() < p_foul:
            self._foul(att, opp, carrier, defender, zone)
            return
        self._contact_injury(att, carrier)
        if self.finished:
            return
        if self.rng.random() < self.p.out_of_play_share:
            if zone == FINAL and self.rng.random() < self.p.corner_share_final:
                self._emit("out_of_play", side=att.side, data={"restart": "corner"})
                self._set_restart(att.side, "corner", FINAL)
            else:
                self._emit("out_of_play", side=att.side, data={"restart": "throw_in"})
                self._set_restart(opp.side, "throw_in", 2 - zone)
            return
        kind = "tackle" if self.rng.random() < 0.5 else "interception"
        self._emit(kind, side=opp.side, player=defender.player.unique_id, other=carrier.player.unique_id,
                   data={"zone": zone, "own_third_error": zone == DEF})
        self._turnover(opp, zone)

    def _turnover(self, new_owner: TeamState, zone_of_loser: int) -> None:
        self._set_restart(new_owner.side, "open_play", 2 - zone_of_loser)

    def _set_restart(self, side: int, restart: str, zone: int) -> None:
        self.ball, self.restart, self.zone = side, restart, zone

    def _foul(self, att: TeamState, opp: TeamState, victim: OnField, offender: OnField, zone: int) -> None:
        in_box = zone == FINAL and self.rng.random() < self.p.penalty_box_share
        self._emit("foul", side=opp.side, player=offender.player.unique_id, other=victim.player.unique_id,
                   data={"zone": zone, "penalty": in_box})
        risk = self._skill(offender, "foul_risk")
        if self.rng.random() < self.p.direct_red_prob:
            self._card(opp, offender, "red")
        elif self.rng.random() < _clamp((self.p.yellow_prob + self.p.yellow_risk_slope * (risk - 50) + (0.2 if in_box else 0.0))
                                        * (self.p.booked_caution if offender.yellow else 1.0), 0.01, 0.9):
            self._card(opp, offender, "yellow")
        if self.finished:
            return
        self._contact_injury(att, victim, foul=True)
        if self.finished:
            return
        if in_box:
            self._emit("penalty_awarded", side=att.side, player=victim.player.unique_id, other=offender.player.unique_id)
            self._set_restart(att.side, "penalty", FINAL)
        elif zone == FINAL and self.rng.random() < self.p.free_kick_shot_prob:
            self._set_restart(att.side, "free_kick_danger", FINAL)
        else:
            self._set_restart(att.side, "free_kick", zone)

    def _card(self, team: TeamState, pl: OnField, color: str) -> None:
        if not pl.active:
            return
        if color == "yellow":
            pl.yellow += 1
            self._emit("yellow_card", side=team.side, player=pl.player.unique_id)
            self.cards.append(Card(pl.player.unique_id, team.side, "yellow", self.t))
            if pl.yellow == 2 and self.p.second_yellow_is_red:
                self._send_off(team, pl, second_yellow=True)
        else:
            self._send_off(team, pl, second_yellow=False)

    def _send_off(self, team: TeamState, pl: OnField, second_yellow: bool) -> None:
        pl.active = False
        self._emit("red_card", side=team.side, player=pl.player.unique_id, data={"second_yellow": second_yellow})
        self.cards.append(Card(pl.player.unique_id, team.side, "red", self.t, second_yellow))
        self._check_minimum(team)  # expulso não é substituído (GDD §13)

    def _contact_injury(self, team: TeamState, pl: OnField, foul: bool = False) -> None:
        if not pl.active:
            return
        prone = pl.player.attributes.get("attributes_injury_proneness", 50)
        p = (self.p.injury_per_contact * (1.6 if foul else 1.0)
             * (1 + self.p.injury_proneness_slope * (prone - 50)) * (1 + (100 - pl.condition) / 100))
        if self.rng.random() >= max(0.0, p):
            return
        matches = self.rng.choices([0, 1, 2, 3], weights=self.p.injury_matches_weights, k=1)[0]
        self._emit("injury", side=team.side, player=pl.player.unique_id, data={"matches": matches})
        self.injuries.append(Injury(pl.player.unique_id, team.side, matches, self.t))
        replacement = self._best_replacement(team, pl.slot)
        if replacement is not None and team.subs_used < self.p.max_substitutions:
            self._substitute(team, pl, replacement, reason="injury")
        else:
            pl.active = False
            self._emit("player_off", side=team.side, player=pl.player.unique_id, data={"reason": "injury_no_sub"})
            self._check_minimum(team)

    def _check_minimum(self, team: TeamState) -> None:
        if len(team.on_field()) < self.p.min_players and not self.finished:
            self.status, self.abandoned_side, self.finished = "abandoned", team.side, True
            self._emit("abandoned", side=team.side, data={"players": len(team.on_field())})

    # ================================================================ substituições
    def _best_replacement(self, team: TeamState, slot: Position) -> MatchPlayer | None:
        if not team.bench:
            return None

        def value(mp: MatchPlayer) -> tuple[float, int]:
            of = OnField(mp, slot, team.forms[mp.unique_id])
            main = "goalkeeping" if slot is Position.GK else {"def": "box_defense", "mid": "progression", "att": "finishing"}[LINE[slot]]
            return (self._skill(of, main), -mp.unique_id)

        return max(team.bench, key=value)

    def _substitute(self, team: TeamState, off: OnField, on: MatchPlayer, reason: str) -> None:
        off.active = False
        team.bench.remove(on)
        team.subs_used += 1
        team.players.append(OnField(on, off.slot, team.forms[on.unique_id]))
        self._emit("substitution", side=team.side, player=on.unique_id, other=off.player.unique_id,
                   data={"reason": reason, "slot": off.slot.value, "number": team.subs_used})

    # ================================================================ IA tática (gancho)
    def observation(self, side: int) -> TacticalObservation:
        from .stats import compute_stats

        team, opp = self.teams[side], self.teams[1 - side]
        stats = compute_stats(self.events)
        keys = ("home", "away")
        first_len = self.period_end[0]
        total = first_len + self.p.half_seconds + self.second_half_stoppage
        elapsed = self.t if self.period == 1 else first_len + (self.t - self.period_start)
        return TacticalObservation(
            side=side, second=self.t, period=self.period,
            remaining_fraction=_clamp(1 - elapsed / total, 0.0, 1.0),
            goals_for=team.goals, goals_against=opp.goals,
            players_for=len(team.on_field()), players_against=len(opp.on_field()),
            own_posture=team.posture, opponent_posture=opp.posture,
            own_players=tuple(OwnPlayerState(p.player.unique_id, p.slot, p.condition, p.yellow, p.player)
                              for p in team.on_field()),
            bench=tuple(team.bench), substitutions_left=self.p.max_substitutions - team.subs_used,
            stats_for=stats[keys[side]], stats_against=stats[keys[1 - side]],
            triggers=tuple(self._triggers[side]), knockout=self.match.knockout,
        )

    def _consult_controllers(self) -> None:
        for side in (0, 1):
            ctrl = self.controllers.get(side)
            if ctrl is None or self.finished:
                continue
            if self.t < self._next_eval[side] and not self._triggers[side]:
                continue
            obs = self.observation(side)
            choice = ctrl.decide(obs)
            self._sub_bias[side] = ctrl.substitution_bias(obs)
            self._triggers[side] = []
            self._next_eval[side] = self.t + ctrl.eval_interval
            if choice is not None and choice in POSTURES and choice != self.teams[side].posture:
                self.decisions.append(PostureChange(self.t, side, choice))
                self.decisions.sort(key=lambda d: (d.second, d.side))

    def _tactical_substitution(self, team: TeamState) -> bool:
        """Substituição por contexto tático pedida pelo controlador (somente com controlador presente)."""
        bias = self._sub_bias.get(team.side)
        if bias is None or self.t < 60 * 60:
            return False
        if bias == "attack":
            out_lines, in_pos = ("def", "mid"), (Position.STC, Position.MC)
        else:
            out_lines, in_pos = ("att", "mid"), (Position.DC, Position.DM)
        tired = [p for p in team.on_field() if p.line in out_lines and p.condition < 80 and p.slot is not Position.GK]
        bench = [b for b in team.bench if b.natural_position in in_pos]
        if not tired or not bench:
            return False
        off = min(tired, key=lambda p: (p.condition, p.player.unique_id))
        on = max(bench, key=lambda b: (b.familiarity.get(off.slot, 1), -b.unique_id))
        self._substitute(team, off, on, "tactical")
        return True

    def _consider_substitution(self, team: TeamState) -> None:
        if (team.subs_used >= self.p.max_substitutions or not team.bench
                or self.t < self.p.sub_min_minute * 60 or self.finished):
            return
        if team.side in self.controllers and not self._urgent_need(team) and self._tactical_substitution(team):
            return
        losing = team.goals < self.teams[1 - team.side].goals
        worst: tuple[float, OnField, str] | None = None
        for pl in team.on_field():
            if pl.slot is Position.GK and not any(b.natural_position is Position.GK for b in team.bench):
                continue
            score = 0.0
            reason = ""
            if pl.condition < self.p.sub_condition_threshold:
                score, reason = self.p.sub_condition_threshold - pl.condition, "fatigue"
            r = live_rating(self.live, pl.player.unique_id, self.p)
            if r < self.p.sub_rating_threshold and self.t >= 60 * 60:
                s = (self.p.sub_rating_threshold - r) * 10
                if s > score:
                    score, reason = s, "performance"
            if losing and self.t >= 70 * 60 and pl.line == "def" and pl.condition < 75 and score == 0:
                score, reason = 1.0, "tactical"
            if score > 0 and (worst is None or score > worst[0]):
                worst = (score, pl, reason)
        if worst is None:
            return
        _, pl, reason = worst
        slot = pl.slot
        if reason == "tactical":
            attackers = [b for b in team.bench if b.natural_position is Position.STC]
            if attackers:
                replacement = max(attackers, key=lambda b: (b.familiarity.get(slot, 1), -b.unique_id))
            else:
                replacement = self._best_replacement(team, slot)
        else:
            replacement = self._best_replacement(team, slot)
        if replacement is not None:
            self._substitute(team, pl, replacement, reason)

    def _urgent_need(self, team: TeamState) -> bool:
        """Há atleta exausto (abaixo do limiar de condição)? Então a troca por desgaste tem prioridade."""
        return any(p.condition < self.p.sub_condition_threshold for p in team.on_field())

    # ================================================================ oportunidades
    def _corner(self, att: TeamState, opp: TeamState) -> None:
        taker = self._pick(att.on_field(), [p.player.attributes.get("attributes_corners", 1) for p in att.on_field()])
        self._emit("corner", side=att.side, player=taker.player.unique_id if taker else None)
        self._tick(self.rng.uniform(*self.p.restart_seconds))
        if self.rng.random() < self.p.corner_shot_prob:
            self._shot(att, opp, "corner_header", creator=taker)
        else:
            self._set_restart(opp.side, "open_play", DEF)

    def _penalty(self, att: TeamState, opp: TeamState) -> None:
        taker = max(att.on_field(), key=lambda p: (self._skill(p, "penalty"), -p.player.unique_id))
        gk = opp.keeper()
        self._tick(30.0)
        xg = self.p.xg_penalty
        p_goal = _clamp(xg * math.exp(self.p.shooter_effect * (self._skill(taker, "penalty") - 50) / 50)
                        * math.exp(-self.p.keeper_effect * ((self._skill(gk, "gk_penalty") if gk else 10) - 50) / 50), 0.3, 0.95)
        self._emit("shot", side=att.side, player=taker.player.unique_id,
                   data={"type": "penalty", "xg": round(xg, 4), "distance": 11.0, "big_chance": True, "pressure": 0.0})
        if self.rng.random() < p_goal:
            self._goal(att, opp, taker, None, xg, "penalty")
        elif gk is not None and self.rng.random() < 0.75:
            self._emit("save", side=opp.side, player=gk.player.unique_id, other=taker.player.unique_id,
                       data={"xg": round(xg, 4), "penalty": True})
            self._set_restart(opp.side, "keeper", DEF)
        else:
            self._emit("miss", side=att.side, player=taker.player.unique_id, data={"xg": round(xg, 4), "woodwork": False})
            self._set_restart(opp.side, "goal_kick", DEF)

    def _shot(self, att: TeamState, opp: TeamState, forced: str | None, creator: OnField | None = None) -> None:
        p = self.p
        kind = forced or self.rng.choices(list(p.chance_types), weights=list(p.chance_types.values()), k=1)[0]
        field_players = att.on_field()
        if kind in ASSISTED and creator is None and kind != "corner_header":
            creator = self._pick(field_players, [CREATOR_WEIGHT[x.line] * self._skill(x, "creation") for x in field_players])
        pool = [x for x in field_players if x is not creator and x.slot is not Position.GK] or field_players
        skill_name = {"cross_header": "heading", "corner_header": "heading", "long_shot": "long_shot",
                      "free_kick": "free_kick"}.get(kind, "finishing")
        if kind == "free_kick":
            shooter = max(pool, key=lambda x: (self._skill(x, "free_kick"), -x.player.unique_id))
        else:
            shooter = self._pick(pool, [SHOOTER_WEIGHT[x.line] * max(1.0, self._skill(x, "attack_movement"))
                                        * (self._skill(x, "heading") / 50 if skill_name == "heading" else 1.0) for x in pool])
        if shooter is None:
            self._set_restart(opp.side, "goal_kick", DEF)
            return
        mu, sd = p.distance[kind]
        distance = _clamp(self.rng.gauss(mu, sd), 5.0, 35.0)
        angle = _clamp(self.rng.uniform(0.15, 1.0) if kind not in ("cutback", "through_ball") else self.rng.uniform(0.45, 1.0), 0, 1)
        markers = opp.by_line("def", "mid") or opp.on_field()
        marker = self._pick(markers, [1.0] * len(markers))
        mark = self._skill(marker, "box_defense") if marker else 20.0
        pressure = _clamp(0.5 + (mark - self._skill(shooter, "attack_movement")) / 100 + self.rng.uniform(-0.25, 0.25), 0, 1)
        if kind == "free_kick":
            pressure = 0.0
        header = kind in ("cross_header", "corner_header")
        xg = contextual_xg(p, kind, distance, angle, pressure)  # só o contexto do lance
        big = is_big_chance(p, xg, pressure)
        self._tick(self.rng.uniform(2.0, 6.0))
        self._emit("shot", side=att.side, player=shooter.player.unique_id,
                   other=creator.player.unique_id if creator else None,
                   data={"type": kind, "xg": round(xg, 4), "distance": round(distance, 1), "angle": round(angle, 2),
                         "pressure": round(pressure, 2), "big_chance": big, "header": header})
        self._exert(shooter)
        # bloqueio
        blockers = [x for x in opp.by_line("def", "mid")] or opp.on_field()
        blocker = self._pick(blockers, [self._skill(x, "block") for x in blockers])
        p_block = _clamp(p.block_base * (0.5 + pressure) * (1.4 if kind == "long_shot" else 0.8 if header else 1.0)
                         * ((self._skill(blocker, "block") if blocker else 30) / 50), 0, 0.7)
        if kind != "free_kick" and blocker is not None and self.rng.random() < p_block:
            self._emit("block", side=opp.side, player=blocker.player.unique_id, other=shooter.player.unique_id,
                       data={"xg": round(xg, 4)})
            if self.rng.random() < 0.35:
                self._set_restart(att.side, "corner", FINAL)
            else:
                self._set_restart(opp.side, "open_play", DEF)
            return
        # finalizador e goleiro modificam SEPARADAMENTE a probabilidade de gol (sem dupla contagem)
        gk = opp.keeper()
        shooter_skill = self._skill(shooter, skill_name)
        keeper_skill = self._skill(gk, "goalkeeping") if gk else 5.0
        # condicionado a não ter havido bloqueio: E[gols] = xG × multiplicadores (≈ xG para atletas de referência)
        no_block = 1.0 - (p_block if kind != "free_kick" and blocker is not None else 0.0)
        p_goal = _clamp(xg / max(0.3, no_block)
                        * math.exp(p.shooter_effect * (shooter_skill - p.shooter_reference) / 50)
                        * math.exp(-p.keeper_effect * (keeper_skill - p.keeper_reference) / 50), 0.002, 0.97)
        if self.rng.random() < p_goal:
            self._goal(att, opp, shooter, creator if kind in ASSISTED else None, xg, kind)
            return
        accuracy = self._skill(shooter, "accuracy")
        p_on = _clamp(p.on_target_base + p.on_target_slope * (accuracy - 50) + 0.15 * xg, 0.1, 0.85)
        if gk is not None and self.rng.random() < p_on:
            self._emit("save", side=opp.side, player=gk.player.unique_id, other=shooter.player.unique_id,
                       data={"xg": round(xg, 4), "penalty": False})
            self._exert(gk)
            r = self.rng.random()
            if r < p.rebound_prob:
                self._tick(self.rng.uniform(1.0, 3.0))
                self._shot(att, opp, "rebound")
            elif r < p.rebound_prob + p.save_corner_prob:
                self._set_restart(att.side, "corner", FINAL)
            else:
                self._set_restart(opp.side, "keeper", DEF)
            return
        self._emit("miss", side=att.side, player=shooter.player.unique_id,
                   data={"xg": round(xg, 4), "woodwork": self.rng.random() < p.woodwork_prob, "big_chance": big})
        self._set_restart(opp.side, "goal_kick", DEF)

    def _goal(self, att: TeamState, opp: TeamState, scorer: OnField, assist: OnField | None, xg: float, kind: str) -> None:
        att.goals += 1
        self._emit("goal", side=att.side, player=scorer.player.unique_id,
                   other=assist.player.unique_id if assist and assist is not scorer else None,
                   data={"xg": round(xg, 4), "type": kind, "score": [self.teams[0].goals, self.teams[1].goals]})
        self._set_restart(opp.side, "kickoff", MID)
        self._tick(self.rng.uniform(40.0, 70.0))  # comemoração e reinício

    # ================================================================ pênaltis (Copa)
    def _shootout(self) -> None:
        """Disputa de pênaltis sem prorrogação (GDD §18). Não altera o placar nem a artilharia."""
        takers = []
        for team in self.teams:
            field = sorted(team.on_field(), key=lambda p: (p.slot is Position.GK, -self._skill(p, "penalty"), p.player.unique_id))
            takers.append(field or team.players[:1])
        score = [0, 0]
        kicks = [0, 0]

        def kick(side: int) -> None:
            team, opp = self.teams[side], self.teams[1 - side]
            taker = takers[side][kicks[side] % len(takers[side])]
            gk = opp.keeper()
            p = _clamp(self.p.xg_penalty * math.exp(self.p.shooter_effect * (self._skill(taker, "penalty") - self.p.shooter_reference) / 50)
                       * math.exp(-self.p.keeper_effect * ((self._skill(gk, "gk_penalty") if gk else 10) - self.p.keeper_reference) / 50), 0.3, 0.95)
            scored = self.rng.random() < p
            kicks[side] += 1
            score[side] += scored
            self._emit("shootout_kick", side=side, player=taker.player.unique_id,
                       other=gk.player.unique_id if gk else None, data={"scored": scored, "shootout": list(score)})

        self._emit("shootout_start")
        for _ in range(5):
            for side in (0, 1):
                kick(side)
                remaining = [5 - kicks[0], 5 - kicks[1]]
                if score[0] + remaining[0] < score[1] or score[1] + remaining[1] < score[0]:
                    break
            else:
                continue
            break
        while score[0] == score[1]:
            kick(0)
            kick(1)
        self.shootout = (score[0], score[1])
        self._emit("shootout_end", side=0 if score[0] > score[1] else 1, data={"shootout": list(score)})

    # ================================================================ resultado
    def result(self) -> MatchResult:
        if not self.finished:
            raise RuntimeError("A partida ainda não terminou.")
        from .ratings import compute_ratings, man_of_the_match
        from .stats import compute_stats

        score = (self.teams[0].goals, self.teams[1].goals)
        official = score
        if self.status == "abandoned":
            loser = self.abandoned_side
            winner = 1 - loser
            margin = score[winner] - score[loser]
            # 3 × 0 ou placar real se for mais favorável ao adversário (GDD §13)
            if not (margin > 3 or (margin == 3 and score[winner] >= 3)):
                official = (3, 0) if winner == 0 else (0, 3)
        stats = compute_stats(self.events)
        ratings = compute_ratings(self.events, self.match, self.p, score)
        return MatchResult(
            match_id=self.match.match_id, competition=self.match.competition,
            engine_version=ENGINE_VERSION,
            params_version=self.p.version, seed=self.match.seed, events=tuple(self.events), score=score,
            official_score=official, status=self.status, abandoned_side=self.abandoned_side, stats=stats,
            ratings=tuple(ratings), man_of_the_match=man_of_the_match(ratings), injuries=tuple(self.injuries),
            cards=tuple(self.cards), final_postures=(self.teams[0].posture, self.teams[1].posture),
            shootout=self.shootout, winner_side=self._winner(official),
        )

    def _winner(self, official: tuple[int, int]) -> int | None:
        if official[0] != official[1]:
            return 0 if official[0] > official[1] else 1
        if self.shootout:
            return 0 if self.shootout[0] > self.shootout[1] else 1
        return None


def simulate(match: MatchInput, params: MatchParams = DEFAULT_PARAMS, decisions: Iterable[PostureChange] = (),
             controllers: Mapping[int, TacticalController] | None = None) -> MatchResult:
    return MatchSimulation(match, params, decisions, controllers).run()
