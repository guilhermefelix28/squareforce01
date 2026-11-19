"""Execução de Liga e Copa (GDD §17–§21): snapshot por rodada, partidas paralelas e consolidação atômica.

Ciclo (avanço SEMPRE manual):
  ready (rodada preparada com snapshot imutável)
    → play(): partidas em paralelo, cada uma com estado, semente e evolução próprios; resultados ficam em
      um buffer (a classificação oficial NÃO muda durante a rodada)
    → consolidação atômica: valida tudo e aplica uma única vez (classificação/chave, lesões e suspensões,
      estatísticas, histórico); qualquer falha crítica => nada é aplicado e as partidas falhas podem ser
      repetidas com a MESMA tarefa (estado inicial, semente e decisões preservados)
  awaiting_advance (pós-partida disponível) → advance() → próxima rodada ou finished.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import math
from concurrent.futures import Executor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from services.bot_ai.tactics import (
    CompetitionSituation,
    OpponentHistory,
    PreMatchContext,
    choose_lineup,
    league_situation,
)
from services.competition.planner import register_cup_winner
from services.match_engine.availability import AvailabilityLedger
from services.match_engine.params import DEFAULT_PARAMS, POSTURES
from services.match_engine.types import MatchPlayer, MatchResult, PostureChange, TeamSheet
from squadforce_shared.contracts import CupBracket, LeagueSchedule
from squadforce_shared.domain.positions import Position

from .standings import ClubRecord, MatchScore, PointsSystem, StandingRow, apply_result, standings
from .worker import FixtureOutcome, FixtureTask, play_fixture

RECENT_RATINGS = 3
MAIN_EVENTS = {"goal", "yellow_card", "red_card", "injury", "substitution", "penalty_awarded", "save",
               "shootout_kick", "shootout_end", "abandoned", "posture_change", "half_time", "full_time"}


class SeasonError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}


@dataclass(frozen=True)
class RoundSnapshot:
    """Estado competitivo IMUTÁVEL do início da rodada/fase: o mesmo ponto de referência para todos os jogos."""

    snapshot_id: str
    round_no: int
    label: str
    standings: tuple[StandingRow, ...]  # classificação oficial no início da rodada (Liga)
    fixtures: tuple[tuple[str, int, int], ...]  # (match_id, mandante/clube A, visitante/clube B)
    byes: tuple[int, ...]
    injuries: tuple[tuple[int, int], ...]
    suspensions: tuple[tuple[str, int, int], ...]
    tasks: tuple[FixtureTask, ...]


@dataclass(frozen=True)
class PlayedMatch:
    match_id: str
    round_no: int
    home: int
    away: int
    result: MatchResult
    home_sheet: TeamSheet | None = None  # escalações (histórico completo, GDD §20)
    away_sheet: TeamSheet | None = None


@dataclass(frozen=True)
class UserLineup:
    """Escalação escolhida pelo usuário (GDD §9): formação, titulares na ordem das vagas, reservas e postura."""

    formation: tuple[Position, ...]
    starters: tuple[int, ...]
    bench: tuple[int, ...]
    posture: str


def events_digest(result: MatchResult) -> tuple:
    return tuple((e.seq, round(e.second, 6), e.type, e.side, e.player, e.other) for e in result.events)


@dataclass
class PlayerStats:
    player: int
    club: int
    name: str
    appearances: int = 0
    goals: int = 0
    assists: int = 0
    motm: int = 0
    yellow: int = 0
    red: int = 0
    ratings: list[float] = field(default_factory=list)

    @property
    def average_rating(self) -> float:
        return sum(self.ratings) / len(self.ratings) if self.ratings else 0.0


@dataclass
class _State:
    """Tudo o que muda na consolidação (copiado e trocado de uma vez)."""

    records: dict[int, ClubRecord]
    bracket: CupBracket | None
    ledger: AvailabilityLedger
    players: dict[int, PlayerStats]
    history: list[PlayedMatch]
    club_matches: dict[int, int]

    def copy(self) -> "_State":
        """Cópia do estado MUTÁVEL (resultados de partidas são imutáveis e compartilhados)."""
        led = self.ledger
        return _State(
            records={c: dataclasses.replace(r, form=list(r.form)) for c, r in self.records.items()},
            bracket=self.bracket.model_copy(deep=True) if self.bracket is not None else None,
            ledger=AvailabilityLedger(led.params, dict(led.injuries), dict(led.suspensions), dict(led.yellows),
                                      list(led.history)),
            players={k: dataclasses.replace(v, ratings=list(v.ratings)) for k, v in self.players.items()},
            history=list(self.history),
            club_matches=dict(self.club_matches),
        )


def match_seed(base_seed: int, competition_id: str, match_id: str) -> int:
    """Semente própria de cada partida, independente da ordem de processamento."""
    digest = hashlib.sha256(f"{base_seed}:{competition_id}:{match_id}".encode()).hexdigest()
    return int(digest[:15], 16)


class Season:
    def __init__(
        self,
        *,
        competition_id: str,
        structure: LeagueSchedule | CupBracket,
        squads: Mapping[int, Sequence[MatchPlayer]],
        names: Mapping[int, str],
        user_club: int,
        personalities: Mapping[int, str],
        formations: Sequence[Sequence[Position]],
        seed: int,
        points: PointsSystem = PointsSystem(),
        tiebreakers: Sequence[str] = (),
        runner: Callable[[FixtureTask], FixtureOutcome] = play_fixture,
        round_timeout: float = 600.0,
    ):
        if not formations:
            raise SeasonError("NO_FORMATIONS", "Nenhuma formação disponível (lista oficial pendente — PM-01).")
        self.competition_id = competition_id
        self.kind = structure.kind
        self.schedule = structure if structure.kind == "league" else None
        participants = list(structure.participants)
        for c in participants:
            if c not in squads:
                raise SeasonError("MISSING_SQUAD", f"Elenco do clube {c} ausente.")
            if c != user_club and personalities.get(c) is None:
                raise SeasonError("MISSING_PERSONALITY", f"Personalidade do clube-bot {c} ausente.")
        self.participants = participants
        self.squads = {c: tuple(squads[c]) for c in participants}
        self.names = dict(names)
        self.user_club = user_club
        self.personalities = dict(personalities)
        self.formations = [tuple(f) for f in formations]
        self.seed = seed
        self.points = points
        self.tiebreakers = tuple(tiebreakers)
        self.runner = runner
        self.round_timeout = round_timeout
        player_names = {p.unique_id: (c, p.name) for c, sq in self.squads.items() for p in sq}
        self.state = _State(
            records={c: ClubRecord(c) for c in participants},
            bracket=copy.deepcopy(structure) if structure.kind == "cup" else None,
            ledger=AvailabilityLedger(DEFAULT_PARAMS),
            players={pid: PlayerStats(pid, c, n) for pid, (c, n) in player_names.items()},
            history=[],
            club_matches={c: 0 for c in participants},
        )
        self.round_index = 0  # índice da rodada/fase atual (0-based)
        self.phase = "ready"  # ready | awaiting_advance | finished
        self.snapshot: RoundSnapshot | None = None
        self.pending: dict[str, FixtureOutcome] = {}  # resultados válidos aguardando consolidação (buffer)
        self.errors: dict[str, str] = {}  # partidas falhas -> motivo
        self.failed: list[str] = []
        self.consolidated_snapshots: set[str] = set()
        self.last_round: list[PlayedMatch] = []
        self.user_decisions: dict[str, tuple[PostureChange, ...]] = {}
        self.user_lineup: UserLineup | None = None
        self.lineup_note: str | None = None  # por que a escalação do usuário não pôde ser usada
        self.expected: dict[str, tuple] = {}  # partidas já apresentadas ao vivo: resultado deve ser idêntico
        self._prepare()

    # ================================================================ rodadas
    @property
    def total_rounds(self) -> int:
        return len(self.schedule.rounds) if self.schedule else len(self.state.bracket.rounds)

    def _round_fixtures(self) -> tuple[list[tuple[str, int, int]], list[int], str]:
        if self.schedule:
            r = self.schedule.rounds[self.round_index]
            byes = [r.bye_club_uid] if r.bye_club_uid is not None else []
            label = f"Rodada {r.number}" + (" (returno)" if r.turn == 2 else "")
            return [(m.id, m.home_club_uid, m.away_club_uid) for m in r.matches], byes, label
        rnd = self.state.bracket.rounds[self.round_index]
        fixtures = []
        for m in rnd.matches:
            if m.club_a_uid is None or m.club_b_uid is None:
                raise SeasonError("BRACKET_INCOMPLETE", f"Confronto {m.id} sem os dois clubes definidos.")
            fixtures.append((m.id, m.club_a_uid, m.club_b_uid))
        return fixtures, [], rnd.name

    def _public_history(self, club: int) -> OpponentHistory:
        """Histórico PÚBLICO consolidado do clube (antes desta rodada)."""
        played = gf = ga = 0
        for pm in self.state.history:
            if club in (pm.home, pm.away):
                h = pm.home == club
                played += 1
                gf += pm.result.score[0 if h else 1]
                ga += pm.result.score[1 if h else 0]
        return OpponentHistory(matches=played, goals_for=float(gf), goals_against=float(ga))

    def _recent_ratings(self, club: int) -> dict[int, float]:
        out = {}
        for p in self.squads[club]:
            r = self.state.players[p.unique_id].ratings[-RECENT_RATINGS:]
            if r:
                out[p.unique_id] = sum(r) / len(r)
        return out

    def _situation(self, club: int, table: Sequence[StandingRow]) -> CompetitionSituation:
        if self.kind == "cup":
            return CompetitionSituation.cup()
        leader = max(row.points for row in table) if table else 0
        mine = next(row.points for row in table if row.club_uid == club)
        remaining = self.total_rounds - self.round_index
        return league_situation(mine, leader, None, remaining)

    def standings(self) -> list[StandingRow]:
        results = [MatchScore(pm.home, pm.away, *pm.result.official_score) for pm in self.state.history]
        return standings(self.state.records, self.names, self.tiebreakers, results, self.points)

    def _prepare(self) -> None:
        fixtures, byes, label = self._round_fixtures()
        self.lineup_note = None
        table = tuple(self.standings()) if self.kind == "league" else ()
        led = self.state.ledger
        snapshot_id = f"{self.competition_id}:{self.round_index + 1}"
        tasks = []
        comp = self.competition_id
        for match_id, home, away in fixtures:
            sheets: list[TeamSheet] = []
            contexts: list[PreMatchContext | None] = []
            for club, opp in ((home, away), (away, home)):
                ctx = PreMatchContext(self._situation(club, table), self.personalities.get(club, "balanced"),
                                      self._public_history(opp))
                sheet = None
                if club == self.user_club and self.user_lineup is not None:
                    sheet, self.lineup_note = self._user_sheet(self.user_lineup)
                if sheet is None:
                    choice = choose_lineup(club, list(self.squads[club]), self.formations, ctx, led, comp,
                                           recent_ratings=self._recent_ratings(club))
                    sheet = choice.sheet
                    if club == self.user_club:  # sem escalação válida do usuário: sugestão automática, equilibrada
                        sheet = TeamSheet(sheet.club_uid, sheet.formation, sheet.starters, sheet.bench, "equilibrada")
                if club == self.user_club:  # o usuário decide a postura: sem controlador automático
                    contexts.append(None)
                else:
                    contexts.append(ctx)
                sheets.append(sheet)
            eligible = [frozenset(p.unique_id for p in self.squads[c] if led.is_available(p.unique_id, comp))
                        for c in (home, away)]
            tasks.append(FixtureTask(
                snapshot_id=snapshot_id, match_id=match_id, round_no=self.round_index + 1, competition=comp,
                home_club=home, away_club=away, home=sheets[0], away=sheets[1],
                seed=match_seed(self.seed, comp, match_id), knockout=self.kind == "cup",
                neutral_venue=self.kind == "cup", home_context=contexts[0], away_context=contexts[1],
                user_decisions=self.user_decisions.get(match_id, ()),
                eligible_home=eligible[0], eligible_away=eligible[1],
            ))
        self.snapshot = RoundSnapshot(
            snapshot_id=snapshot_id, round_no=self.round_index + 1, label=label, standings=table,
            fixtures=tuple(fixtures), byes=tuple(byes),
            injuries=tuple(sorted(led.injuries.items())),
            suspensions=tuple(sorted((c, p, n) for (c, p), n in led.suspensions.items())),
            tasks=tuple(tasks),
        )
        self.pending, self.errors, self.failed = {}, {}, []
        self.phase = "ready"

    # ================================================================ escalação do usuário
    def _user_sheet(self, lu: UserLineup) -> tuple[TeamSheet | None, str | None]:
        """Valida a escalação do usuário contra o estado OFICIAL atual; inválida => (None, motivo)."""
        led, comp = self.state.ledger, self.competition_id
        squad = {p.unique_id: p for p in self.squads[self.user_club]}
        if tuple(lu.formation) not in self.formations:
            return None, "Formação indisponível."
        ids = list(lu.starters) + list(lu.bench)
        if len(lu.starters) != 11 or len(lu.bench) > 7 or len(set(ids)) != len(ids):
            return None, "A escalação exige 11 titulares distintos e até 7 reservas."
        unknown = [i for i in ids if i not in squad]
        if unknown:
            return None, f"Jogadores fora do elenco: {unknown}."
        out = [i for i in ids if not led.is_available(i, comp)]
        if out:
            names = ", ".join(f"{squad[i].name} ({led.unavailable_reason(i, comp)})" for i in out)
            return None, f"Indisponíveis: {names}."
        if lu.posture not in POSTURES:
            return None, "Postura inválida."
        try:
            sheet = TeamSheet(self.user_club, tuple(lu.formation), tuple(squad[i] for i in lu.starters),
                              tuple(squad[i] for i in lu.bench), lu.posture)
        except ValueError as exc:
            return None, str(exc)
        return sheet, None

    def set_user_lineup(self, lineup: UserLineup) -> None:
        """Escalação do usuário para a rodada pronta (vale também para as próximas enquanto continuar válida)."""
        if self.phase != "ready":
            raise SeasonError("INVALID_STATE", "A escalação só pode ser alterada antes de a rodada ser jogada.")
        sheet, problem = self._user_sheet(lineup)
        if sheet is None:
            raise SeasonError("INVALID_LINEUP", problem or "Escalação inválida.")
        self.user_lineup = lineup
        self._prepare()

    def user_task(self) -> FixtureTask | None:
        if self.snapshot is None:
            return None
        return next((t for t in self.snapshot.tasks if self.user_club in (t.home_club, t.away_club)), None)

    def expect_result(self, match_id: str, digest: tuple) -> None:
        """Partida do usuário já apresentada ao vivo: a execução da rodada deve reproduzi-la exatamente."""
        self.expected[match_id] = digest

    # ================================================================ execução paralela
    def play(self, executor: Executor) -> list[PlayedMatch]:
        """Executa a rodada em paralelo e consolida atomicamente. Falha => nada é aplicado."""
        if self.phase != "ready":
            raise SeasonError("INVALID_STATE", f"Rodada não está pronta para jogar (estado: {self.phase}).")
        todo = [t for t in self.snapshot.tasks if t.match_id not in self.pending]
        self._run(executor, todo)
        return self._try_consolidate()

    def retry_failed(self, executor: Executor) -> list[PlayedMatch]:
        """Repete SOMENTE as partidas que falharam, com a mesma tarefa (estado inicial, semente, decisões)."""
        if self.phase != "ready" or not self.failed:
            raise SeasonError("NOTHING_TO_RETRY", "Não há partidas falhas a repetir.")
        tasks = [t for t in self.snapshot.tasks if t.match_id in self.failed]
        self._run(executor, tasks)
        return self._try_consolidate()

    def _run(self, executor: Executor, tasks: Sequence[FixtureTask]) -> None:
        futures = {t.match_id: executor.submit(self.runner, t) for t in tasks}
        for match_id, fut in futures.items():
            try:
                out = fut.result(timeout=self.round_timeout)
            except FutureTimeout:
                out = FixtureOutcome(self.snapshot.snapshot_id, match_id, None, "Tempo limite excedido.")
            except Exception as exc:
                out = FixtureOutcome(self.snapshot.snapshot_id, match_id, None, f"{type(exc).__name__}: {exc}")
            if out.ok:
                self.pending[match_id] = out
                self.errors.pop(match_id, None)
            else:
                self.pending.pop(match_id, None)
                self.errors[match_id] = out.error or "; ".join(out.problems)
        self.failed = sorted(m for m, _, _ in self.snapshot.fixtures if m not in self.pending)

    # ================================================================ consolidação atômica
    def _try_consolidate(self) -> list[PlayedMatch]:
        if self.failed:
            details = {m: self.errors.get(m, "não executada") for m in self.failed}
            raise SeasonError("ROUND_FAILED", f"{len(self.failed)} partida(s) falharam; nada foi consolidado.",
                              {"failed": self.failed, "errors": details})
        return self._consolidate()

    def _consolidate(self) -> list[PlayedMatch]:
        snap = self.snapshot
        if snap.snapshot_id in self.consolidated_snapshots:
            raise SeasonError("ALREADY_CONSOLIDATED", "Rodada já consolidada.")
        outcomes = dict(self.pending)
        expected = {m for m, _, _ in snap.fixtures}
        # 1–5: verificação de resultados, integridade, identidade e duplicação
        if set(outcomes) != expected:
            raise SeasonError("CONSOLIDATION_MISMATCH", "Resultados não correspondem aos confrontos da rodada.",
                              {"expected": sorted(expected), "got": sorted(outcomes)})
        tasks = {t.match_id: t for t in snap.tasks}
        seen_ids: set[str] = set()
        for m, o in outcomes.items():
            res = o.result
            if o.snapshot_id != snap.snapshot_id or res.match_id != m or m in seen_ids:
                raise SeasonError("CONSOLIDATION_IDENTITY", f"Identidade inválida na partida {m}.")
            seen_ids.add(m)
            if res.seed != tasks[m].seed or res.competition != self.competition_id:
                raise SeasonError("CONSOLIDATION_IDENTITY", f"Semente/competição divergentes na partida {m}.")
            if o.problems:
                raise SeasonError("CONSOLIDATION_INVALID", f"Partida {m} inválida.", {"problems": list(o.problems)})
            if res.stats["home"]["goals"] != res.score[0] or res.stats["away"]["goals"] != res.score[1]:
                raise SeasonError("CONSOLIDATION_INVALID", f"Estatísticas e placar divergentes na partida {m}.")
            if m in self.expected and events_digest(res) != self.expected[m]:
                raise SeasonError("CONSOLIDATION_INVALID",
                                  f"Partida {m} diverge da apresentação ao vivo (determinismo violado).")
            if self.kind == "cup" and res.winner_side is None:
                raise SeasonError("CONSOLIDATION_INVALID", f"Confronto eliminatório {m} sem vencedor.")
        # 6–9: aplica em CÓPIAS e troca de uma vez (nenhuma consolidação parcial)
        new = self.state.copy()
        played: list[PlayedMatch] = []
        for m, home, away in snap.fixtures:  # ordem fixa pelo calendário
            res = outcomes[m].result
            task = tasks[m]
            pm = PlayedMatch(m, snap.round_no, home, away, res, task.home, task.away)
            played.append(pm)
            new.history.append(pm)
            new.club_matches[home] += 1
            new.club_matches[away] += 1
            if self.kind == "league":
                apply_result(new.records, MatchScore(home, away, *res.official_score), self.points)
            else:
                winner = home if res.winner_side == 0 else away
                decided_by = "penalties" if res.shootout else "regular_time"
                new.bracket = register_cup_winner(new.bracket, m, winner, decided_by)
                apply_result(new.records, MatchScore(home, away, *res.official_score), self.points)
            squads = ({p.unique_id for p in self.squads[home]}, {p.unique_id for p in self.squads[away]})
            new.ledger.record_match(res, (task.home, task.away), squads)
            self._accumulate(new, res, task)
        self.state = new
        self.consolidated_snapshots.add(snap.snapshot_id)
        self.last_round = played
        self.pending = {}
        # 10: libera o avanço manual
        self.phase = "awaiting_advance"
        return played

    def _accumulate(self, st: _State, res: MatchResult, task: FixtureTask) -> None:
        for e in res.events:
            if e.type == "goal" and e.player in st.players:  # gols da partida (pênaltis da disputa não contam)
                st.players[e.player].goals += 1
                if e.other in st.players:
                    st.players[e.other].assists += 1
            elif e.type == "yellow_card" and e.player in st.players:
                st.players[e.player].yellow += 1
            elif e.type == "red_card" and e.player in st.players:
                st.players[e.player].red += 1
        for r in res.ratings:
            if r.player in st.players and r.minutes > 0:
                st.players[r.player].appearances += 1
                st.players[r.player].ratings.append(r.rating)
        if res.man_of_the_match in st.players:
            st.players[res.man_of_the_match].motm += 1

    # ================================================================ avanço manual
    def advance(self) -> None:
        if self.phase != "awaiting_advance":
            raise SeasonError("INVALID_STATE", f"Avanço indisponível no estado {self.phase}.")
        self.expected = {}
        if self.round_index + 1 >= self.total_rounds:
            self.phase = "finished"
            self.snapshot = None
            return
        self.round_index += 1
        self._prepare()

    def set_user_decisions(self, match_id: str, decisions: Sequence[PostureChange]) -> None:
        """Decisões táticas do usuário para a próxima partida (antes de jogá-la)."""
        if self.phase != "ready" or match_id not in {m for m, _, _ in self.snapshot.fixtures}:
            raise SeasonError("INVALID_STATE", "Decisões só podem ser registradas para a rodada pronta.")
        self.user_decisions[match_id] = tuple(decisions)
        self._prepare()

    # ================================================================ consultas e premiações
    def champion(self) -> tuple[int | None, tuple[int, ...]]:
        """(campeão, clubes empatados no topo sem critério de desempate)."""
        if self.phase != "finished":
            return None, ()
        if self.kind == "cup":
            return self.state.bracket.champion_club_uid, ()
        table = self.standings()
        top = table[0]
        if top.tied_with:
            return None, tuple(sorted((top.club_uid, *top.tied_with)))
        return top.club_uid, ()

    def awards(self) -> dict:
        players = list(self.state.players.values())

        def leaders(metric: Callable[[PlayerStats], float], pool: Sequence[PlayerStats]) -> list[PlayerStats]:
            if not pool:
                return []
            best = max(metric(p) for p in pool)
            return sorted((p for p in pool if metric(p) == best and best > 0), key=lambda p: p.player)

        def eligible_for_rating(p: PlayerStats) -> bool:
            team_matches = self.state.club_matches.get(p.club, 0)
            return team_matches > 0 and p.appearances >= math.ceil(team_matches / 2)

        rated = [p for p in players if eligible_for_rating(p)]
        return {
            "top_scorers": leaders(lambda p: p.goals, players),
            "top_assists": leaders(lambda p: p.assists, players),
            "best_average": leaders(lambda p: round(p.average_rating, 6), rated),
            "most_motm": leaders(lambda p: p.motm, players),
        }

    def campaign(self, club: int) -> list[dict]:
        out = []
        for pm in self.state.history:
            if club not in (pm.home, pm.away):
                continue
            home = pm.home == club
            gf, ga = pm.result.official_score if home else pm.result.official_score[::-1]
            so = pm.result.shootout
            if so and not home:
                so = so[::-1]
            won = (pm.result.winner_side == (0 if home else 1)) if pm.result.winner_side is not None else None
            out.append({"match_id": pm.match_id, "round": pm.round_no, "opponent": pm.away if home else pm.home,
                        "home": home, "goals_for": gf, "goals_against": ga, "shootout": so,
                        "outcome": "V" if won else ("E" if won is None else "D")})
        return out

    def eliminated(self, club: int) -> bool:
        if self.kind != "cup":
            return False
        return any(club in (pm.home, pm.away) and pm.result.winner_side is not None
                   and (pm.home if pm.result.winner_side == 1 else pm.away) == club for pm in self.state.history)
