"""Visões da interface (Entrega 8): elenco, escalação, adversário, partida ao vivo, estatísticas e calendário."""

from __future__ import annotations

import math

from services.match_engine.engine import LINE
from services.match_engine.calibration import SAMPLE_FORMATIONS
from services.match_engine.types import MatchPlayer, TeamSheet
from squadforce_shared.contracts import (
    CalendarOut, CalendarRoundOut, ClubSeasonStatsOut, FormationOut, LineupOut, LineupPlayerOut, LineupSlotOut,
    LivePlayerOut, LiveStateOut, MatchEventOut, OpponentPreviewOut, PlayerSeasonStatsOut, SeasonFixtureOut,
    SeasonStatsOut, SquadPlayerOut, TeamLineupOut,
)

from .live import LiveMatch
from .season import MAIN_EVENTS, Season, SeasonError, UserLineup

# Lista oficial de formações PENDENTE (PM-01): usa-se a lista de amostra do motor, marcada como provisória.
PROVISIONAL_FORMATIONS = SAMPLE_FORMATIONS

FIT_THRESHOLDS = ((90, "natural"), (70, "boa"), (40, "regular"))  # familiaridade 1–100 (apresentação, PI-02)


def fit_level(player: MatchPlayer, slot) -> str:
    fam = int(player.familiarity.get(slot, 1))
    return next((label for limit, label in FIT_THRESHOLDS if fam >= limit), "improvisada")


def formation_name(formation) -> str:
    counts = {"def": 0, "mid": 0, "att": 0}
    for pos in formation:
        if LINE[pos] in counts:
            counts[LINE[pos]] += 1
    base = f"{counts['def']}-{counts['mid']}-{counts['att']}"
    dm = sum(1 for pos in formation if pos.value == "DM")
    return base if dm in (0, 1) else f"{base} ({dm} volantes)"


def _formations() -> list[FormationOut]:
    return [FormationOut(id=formation_name(f), positions=[p.value for p in f]) for f in PROVISIONAL_FORMATIONS]


def formation_by_name(name: str):
    return next((f for f in PROVISIONAL_FORMATIONS if formation_name(f) == name), None)


STAT_KEYS = ("shots", "shots_on_target", "xg", "big_chances", "big_chances_missed", "possession_pct", "corners",
             "fouls", "yellow_cards", "red_cards", "saves_made", "tackles", "interceptions", "progressions",
             "blocks_made", "woodwork", "penalties", "injuries", "substitutions")


class SeasonViewsMixin:
    """Métodos de visão usados pelo SeasonService (requer _campaign, _award, _fixture, _lock, _live, _ages)."""

    def _team_lineup(self, sheet: TeamSheet) -> TeamLineupOut:
        return TeamLineupOut(
            club_uid=sheet.club_uid, formation=formation_name(sheet.formation),
            starters=[LineupPlayerOut(player=p.unique_id, name=p.name, slot=slot.value)
                      for p, slot in zip(sheet.starters, sheet.formation)],
            bench=[LineupPlayerOut(player=p.unique_id, name=p.name, slot=p.natural_position.value) for p in sheet.bench],
            initial_posture=sheet.posture,
        )

    def formations(self) -> list[FormationOut]:
        return _formations()

    def squad(self, session_id: str, s: Season) -> list[SquadPlayerOut]:
        led, comp = s.state.ledger, s.competition_id
        ages = self._ages.get(session_id, {})
        team_matches = s.state.club_matches.get(s.user_club, 0)
        out = []
        for p in s.squads[s.user_club]:
            st = s.state.players[p.unique_id]
            out.append(SquadPlayerOut(
                player=p.unique_id, name=p.name, age=ages.get(p.unique_id), position=p.natural_position.value,
                available=led.is_available(p.unique_id, comp), unavailable_reason=led.unavailable_reason(p.unique_id, comp),
                fit={pos.value: fit_level(p, pos) for pos in LINE},
                appearances=st.appearances, goals=st.goals, assists=st.assists,
                average_rating=round(st.average_rating, 2) if st.ratings else None, motm=st.motm,
                yellow_cards=st.yellow, red_cards=st.red,
            ))
        return out

    def live(self, session_id: str, s: Season) -> LiveMatch | None:
        with self._lock:
            entry = self._live.get(session_id)
        if entry is None or s.snapshot is None or entry[0] != s.snapshot.snapshot_id:
            return None
        return entry[1]

    def start_live(self, session_id: str, s: Season, speed: str, clock) -> LiveMatch:
        task = s.user_task()
        live = LiveMatch.start(task, s.user_club, speed, clock)
        with self._lock:
            self._live[session_id] = (s.snapshot.snapshot_id, live)
        return live

    def clear_live(self, session_id: str) -> None:
        with self._lock:
            self._live.pop(session_id, None)

    def opponent_preview(self, s: Season, club: int) -> OpponentPreviewOut:
        table_pos = {r.club_uid: r.position for r in s.standings()} if s.kind == "league" else {}
        previous = []
        for pm in s.state.history:
            for sheet in (pm.home_sheet, pm.away_sheet):
                if sheet is not None and sheet.club_uid == club:
                    previous.append(formation_name(sheet.formation))
        pool = [p for p in s.state.players.values() if p.club == club]
        top = sorted(pool, key=lambda p: (-p.goals, -p.average_rating, p.player))[:3]
        return OpponentPreviewOut(
            club_uid=club, campaign=self._campaign(s, club, table_pos), previous_formations=previous,
            top_players=self._award([p for p in top if p.appearances > 0], lambda p: p.goals),
        )

    def lineup(self, session_id: str, s: Season) -> LineupOut:
        task = s.user_task() if s.phase != "finished" else None
        if task is None:
            return LineupOut(has_match=False, locked=True, formations=_formations())
        side = 0 if task.home_club == s.user_club else 1
        sheet = task.home if side == 0 else task.away
        opp = task.away_club if side == 0 else task.home_club
        locked = s.phase != "ready" or self.live(session_id, s) is not None
        return LineupOut(
            has_match=True, match_id=task.match_id, opponent=self.opponent_preview(s, opp),
            is_home=None if s.kind == "cup" else side == 0, formation=formation_name(sheet.formation),
            starters=[LineupSlotOut(index=i, position=slot.value, player=p.unique_id, name=p.name, fit=fit_level(p, slot))
                      for i, (p, slot) in enumerate(zip(sheet.starters, sheet.formation))],
            bench=[LineupPlayerOut(player=p.unique_id, name=p.name, slot=p.natural_position.value) for p in sheet.bench],
            posture=sheet.posture, source="user" if s.user_lineup is not None and s.lineup_note is None else "auto",
            note=s.lineup_note, locked=locked, formations=_formations(),
        )

    def set_lineup(self, s: Season, formation: str, starters, bench, posture: str) -> None:
        f = formation_by_name(formation)
        if f is None:
            raise SeasonError("INVALID_LINEUP", f"Formação desconhecida: {formation}.")
        s.set_user_lineup(UserLineup(tuple(f), tuple(starters), tuple(bench), posture))

    def live_state(self, session_id: str, s: Season, live: LiveMatch) -> LiveStateOut:
        v = live.view()
        task = live.task
        clubs = (task.home_club, task.away_club)
        players = s.state.players

        def name(pid):
            if pid in players:
                return players[pid].name
            for sh in (task.home, task.away):
                for p in (*sh.starters, *sh.bench):
                    if p.unique_id == pid:
                        return p.name
            return None

        events = [MatchEventOut(seq=e.seq, minute=e.minute, second=e.second, period=e.period, type=e.type, side=e.side,
                                club_uid=clubs[e.side] if e.side in (0, 1) else None, player=e.player,
                                player_name=name(e.player), other=e.other, other_name=name(e.other), data=dict(e.data))
                  for e in v["events"] if e.type in MAIN_EVENTS]
        second = v["game_second"]
        return LiveStateOut(
            session_id=session_id, match_id=task.match_id, home_club_uid=task.home_club, away_club_uid=task.away_club,
            user_side=live.user_side, speed=v["speed"], minute=min(int(second // 60) + (0 if second == 0 else 1), 999),
            game_second=round(second, 1), finished=v["finished"], score=v["score"], shootout=v["shootout"],
            events=events, stats={k: dict(x) for k, x in v["stats"].items()}, postures=v["postures"],
            own_players=[LivePlayerOut(**p) for p in v["own_players"]],
            own_bench=[LineupPlayerOut(player=p["player"], name=p["name"], slot="BENCH") for p in v["own_bench"]],
            substitutions_used=v["substitutions_used"],
        )

    def stats(self, session_id: str, s: Season) -> SeasonStatsOut:
        players = []
        for p in s.state.players.values():
            team_matches = s.state.club_matches.get(p.club, 0)
            players.append(PlayerSeasonStatsOut(
                player=p.player, name=p.name, club_uid=p.club, appearances=p.appearances, goals=p.goals,
                assists=p.assists, average_rating=round(p.average_rating, 2) if p.ratings else None,
                rating_eligible=team_matches > 0 and p.appearances >= math.ceil(team_matches / 2),
                motm=p.motm, yellow_cards=p.yellow, red_cards=p.red,
            ))
        clubs = []
        for c in s.participants:
            rec = s.state.records[c]
            mine = {k: 0.0 for k in STAT_KEYS}
            theirs = {k: 0.0 for k in STAT_KEYS}
            for pm in s.state.history:
                if c not in (pm.home, pm.away):
                    continue
                own, opp = ("home", "away") if pm.home == c else ("away", "home")
                for k in STAT_KEYS:
                    mine[k] += float(pm.result.stats[own].get(k, 0))
                    theirs[k] += float(pm.result.stats[opp].get(k, 0))
            if rec.played:
                mine["possession_pct"] = round(mine["possession_pct"] / rec.played, 1)
                theirs["possession_pct"] = round(theirs["possession_pct"] / rec.played, 1)
            clubs.append(ClubSeasonStatsOut(
                club_uid=c, played=rec.played, wins=rec.wins, draws=rec.draws, losses=rec.losses,
                goals_for=rec.goals_for, goals_against=rec.goals_against,
                totals={k: round(v, 3) for k, v in mine.items()}, against={k: round(v, 3) for k, v in theirs.items()},
            ))
        return SeasonStatsOut(session_id=session_id, matches_played=len(s.state.history), players=players, clubs=clubs)

    def calendar(self, session_id: str, s: Season) -> CalendarOut:
        played = {pm.match_id: pm for pm in s.state.history}
        rounds = []

        def fixture(match_id, number, home, away):
            if match_id in played:
                return self._fixture(s, played[match_id])
            return SeasonFixtureOut(match_id=match_id, round=number, home_club_uid=home, away_club_uid=away,
                                    is_user_match=s.user_club in (home, away), played=False)

        if s.schedule is not None:
            for r in s.schedule.rounds:
                label = f"Rodada {r.number}" + (" (returno)" if r.turn == 2 else "")
                rounds.append(CalendarRoundOut(
                    number=r.number, label=label, byes=[r.bye_club_uid] if r.bye_club_uid is not None else [],
                    fixtures=[fixture(m.id, r.number, m.home_club_uid, m.away_club_uid) for m in r.matches]))
        else:
            for r in s.state.bracket.rounds:
                fx = []
                for m in r.matches:
                    if m.club_a_uid is not None and m.club_b_uid is not None:
                        fx.append(fixture(m.id, r.number, m.club_a_uid, m.club_b_uid))
                rounds.append(CalendarRoundOut(number=r.number, label=r.name, byes=[], fixtures=fx))
        current = s.total_rounds if s.phase == "finished" else s.round_index + 1
        return CalendarOut(session_id=session_id, kind=s.kind, current_round=current, rounds=rounds)
