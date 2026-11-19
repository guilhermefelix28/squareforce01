"""SeasonService: uma temporada (Liga ou Copa) por sessão, somente em memória, e visões públicas tipadas.

O executor de partidas é compartilhado e tem limite de trabalhadores (processos por padrão): as partidas de
uma rodada correm em paralelo, isoladas umas das outras (GDD §19).
"""

from __future__ import annotations

import threading
from concurrent.futures import Executor
from typing import Callable, Mapping

from services.match_engine.lineup import to_match_player
from services.trading.engine import TradingEngine
from squadforce_shared.contracts import (
    AwardEntryOut,
    ClubCampaignOut,
    MatchEventOut,
    MatchReportOut,
    PlayerRatingOut,
    PointsSystemOut,
    SeasonFixtureOut,
    SeasonStateOut,
    SeasonSummaryOut,
    StandingRowOut,
)

from .live import LiveMatch
from .season import MAIN_EVENTS, PlayedMatch, PlayerStats, Season
from .views import SEASON_FORMATIONS, SeasonViewsMixin



class SeasonService(SeasonViewsMixin):
    def __init__(self, executor_factory: Callable[[], Executor]):
        self._executor_factory = executor_factory
        self._executor: Executor | None = None
        self._seasons: dict[str, Season] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._ages: dict[str, dict[int, int]] = {}
        self._live: dict[str, tuple[str, LiveMatch]] = {}  # sessão -> (snapshot, partida ao vivo)
        self._lock = threading.Lock()

    # -------------------------------------------------------------- ciclo de vida
    def executor(self) -> Executor:
        with self._lock:
            if self._executor is None:
                self._executor = self._executor_factory()
            return self._executor

    def shutdown(self) -> None:
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

    def create(self, session_id: str, *, competition_id: str, structure, market: TradingEngine,
               names: Mapping[int, str], seed: int) -> Season:
        with market.lock:
            squads = {u: [to_match_player(market.players[k.player_id]) for k in c.contracts]
                      for u, c in market.clubs.items()}
            personalities = {u: c.personality for u, c in market.clubs.items() if c.is_bot}
            user = market.user_club_uid
            ages = {pid: p.age for pid, p in market.players.items()}
        season = Season(competition_id=competition_id, structure=structure,
                        squads={c: squads[c] for c in structure.participants}, names=names, user_club=user,
                        personalities=personalities, formations=SEASON_FORMATIONS, seed=seed)
        with self._lock:
            self._seasons[session_id] = season
            self._locks[session_id] = threading.Lock()
            self._ages[session_id] = ages
        return season

    def get(self, session_id: str) -> Season | None:
        with self._lock:
            return self._seasons.get(session_id)

    def lock(self, session_id: str) -> threading.Lock:
        with self._lock:
            return self._locks[session_id]

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._seasons.pop(session_id, None)
            self._locks.pop(session_id, None)
            self._ages.pop(session_id, None)
            self._live.pop(session_id, None)

    # -------------------------------------------------------------- visões
    @staticmethod
    def _fixture(s: Season, pm: PlayedMatch) -> SeasonFixtureOut:
        r = pm.result
        winner = None if r.winner_side is None else (pm.home if r.winner_side == 0 else pm.away)
        return SeasonFixtureOut(match_id=pm.match_id, round=pm.round_no, home_club_uid=pm.home, away_club_uid=pm.away,
                                is_user_match=s.user_club in (pm.home, pm.away), played=True, score=r.score,
                                official_score=r.official_score, shootout=r.shootout, winner_club_uid=winner)

    def state(self, session_id: str, s: Season) -> SeasonStateOut:
        champion, tied = s.champion()
        if s.phase == "finished":
            fixtures, byes, label = [], [], None
            number = s.total_rounds
        else:
            played = {pm.match_id: pm for pm in s.last_round} if s.phase == "awaiting_advance" else {}
            fixtures = [
                self._fixture(s, played[m]) if m in played else SeasonFixtureOut(
                    match_id=m, round=s.round_index + 1, home_club_uid=h, away_club_uid=a,
                    is_user_match=s.user_club in (h, a), played=False)
                for m, h, a in s.snapshot.fixtures
            ]
            byes, label, number = list(s.snapshot.byes), s.snapshot.label, s.round_index + 1
        return SeasonStateOut(
            session_id=session_id, kind=s.kind, phase=s.phase, round_number=number, total_rounds=s.total_rounds,
            round_label=label, fixtures=fixtures, byes=byes, failed_matches=list(s.failed),
            standings=[StandingRowOut(**{**r.__dict__, "form": list(r.form), "tied_with": list(r.tied_with)})
                       for r in s.standings()] if s.kind == "league" else [],
            bracket=s.state.bracket,
            points_system=PointsSystemOut(win=s.points.win, draw=s.points.draw, loss=s.points.loss,
                                          status=s.points.status) if s.kind == "league" else None,
            tiebreakers=list(s.tiebreakers), user_club_uid=s.user_club, user_eliminated=s.eliminated(s.user_club),
            champion_club_uid=champion, tied_champions=list(tied),
        )

    def report(self, s: Season, match_id: str) -> MatchReportOut | None:
        pm = next((x for x in s.state.history if x.match_id == match_id), None)
        if pm is None:
            return None
        r = pm.result
        players = s.state.players
        clubs = (pm.home, pm.away)

        def name(pid):
            return players[pid].name if pid in players else None

        def rating(x) -> PlayerRatingOut:
            return PlayerRatingOut(player=x.player, name=name(x.player) or str(x.player), club_uid=clubs[x.side],
                                   rating=x.display, minutes=x.minutes)

        ratings = [rating(x) for x in r.ratings if x.minutes > 0]
        motm = next((x for x in ratings if x.player == r.man_of_the_match), None)
        return MatchReportOut(
            match_id=pm.match_id, round=pm.round_no, home_club_uid=pm.home, away_club_uid=pm.away, status=r.status,
            score=r.score, official_score=r.official_score, shootout=r.shootout,
            winner_club_uid=None if r.winner_side is None else clubs[r.winner_side],
            events=[MatchEventOut(seq=e.seq, minute=e.minute, second=e.second, period=e.period, type=e.type,
                                  side=e.side, club_uid=clubs[e.side] if e.side in (0, 1) else None,
                                  player=e.player, player_name=name(e.player), other=e.other,
                                  other_name=name(e.other), data=dict(e.data))
                    for e in r.events if e.type in MAIN_EVENTS],
            stats={k: dict(v) for k, v in r.stats.items()},
            ratings=sorted(ratings, key=lambda x: (-x.rating, x.player)), man_of_the_match=motm,
            final_postures=r.final_postures, engine_version=r.engine_version, params_version=r.params_version,
            lineups=[self._team_lineup(sh) for sh in (pm.home_sheet, pm.away_sheet) if sh is not None],
        )

    @staticmethod
    def _award(entries: list[PlayerStats], value: Callable[[PlayerStats], float]) -> list[AwardEntryOut]:
        return [AwardEntryOut(player=p.player, name=p.name, club_uid=p.club, value=round(value(p), 2),
                              appearances=p.appearances) for p in entries]

    def _campaign(self, s: Season, club: int, table_pos: dict[int, int]) -> ClubCampaignOut:
        matches = [self._fixture(s, pm) for pm in s.state.history if club in (pm.home, pm.away)]
        rec = s.state.records[club]
        so_won = sum(1 for m in matches if m.shootout and m.winner_club_uid == club)
        so_lost = sum(1 for m in matches if m.shootout and m.winner_club_uid not in (club, None))
        if s.kind == "league":
            result = f"{table_pos[club]}º lugar"
        else:
            lost = next((m for m in matches if m.winner_club_uid not in (club, None)), None)
            if lost is not None:
                rnd = s.state.bracket.rounds[lost.round - 1]
                result = f"Eliminado: {rnd.name}"
            elif s.state.bracket.champion_club_uid == club:
                result = "Campeão"
            else:
                result = "Em disputa"
        return ClubCampaignOut(club_uid=club, played=rec.played, wins=rec.wins, draws=rec.draws, losses=rec.losses,
                               goals_for=rec.goals_for, goals_against=rec.goals_against, shootouts_won=so_won,
                               shootouts_lost=so_lost, result=result, matches=matches)

    def summary(self, session_id: str, s: Season) -> SeasonSummaryOut:
        champion, tied = s.champion()
        aw = s.awards()
        table_pos = {r.club_uid: r.position for r in s.standings()} if s.kind == "league" else {}
        campaigns = [self._campaign(s, c, table_pos) for c in s.participants]
        return SeasonSummaryOut(
            session_id=session_id, finished=s.phase == "finished", champion_club_uid=champion,
            tied_champions=list(tied),
            top_scorers=self._award(aw["top_scorers"], lambda p: p.goals),
            top_assists=self._award(aw["top_assists"], lambda p: p.assists),
            best_average_rating=self._award(aw["best_average"], lambda p: p.average_rating),
            most_man_of_the_match=self._award(aw["most_motm"], lambda p: p.motm),
            campaigns=campaigns,
            user_campaign=next(c for c in campaigns if c.club_uid == s.user_club),
            history=[self._fixture(s, pm) for pm in s.state.history],
        )
