import { FORMATIONS as OFFICIAL_FORMATIONS } from "./fakeApi";
/** Respostas de exemplo da API de temporada (formato idêntico ao contrato OpenAPI). */
import { CLUBS, SESSION, json } from "./fakeApi";

export const SID = SESSION.id;
export const USER = 322;
export const OPP = 329;
export const SESSION_COMP = { ...SESSION, phase: "competition", config: { ...SESSION.config, num_clubs: 4, league_rounds: "single" } };

const fixture = (id: string, h: number, a: number, played = false, score: [number, number] | null = null) => ({
  match_id: id, round: 1, home_club_uid: h, away_club_uid: a, is_user_match: h === USER || a === USER, played,
  score, official_score: score, shootout: null, winner_club_uid: null,
});

const row = (pos: number, club: number, pts = 0) => ({
  position: pos, club_uid: club, played: pts ? 1 : 0, wins: pts === 3 ? 1 : 0, draws: pts === 1 ? 1 : 0, losses: 0,
  goals_for: 0, goals_against: 0, goal_difference: 0, points: pts, form: [], tied_with: [],
});

export const SEASON_READY = {
  session_id: SID, kind: "league", phase: "ready", round_number: 1, total_rounds: 3, round_label: "Rodada 1",
  fixtures: [fixture("L-R01-M01", USER, OPP), fixture("L-R01-M02", 102496, 999)], byes: [], failed_matches: [],
  standings: [row(1, USER), row(1, OPP), row(1, 102496), row(1, 999)], bracket: null,
  points_system: { win: 3, draw: 1, loss: 0, status: "confirmada" }, tiebreakers: ["wins", "goal_difference", "goals_for", "head_to_head_two_clubs", "fewer_red_cards", "fewer_yellow_cards", "draw"], user_club_uid: USER,
  user_eliminated: false, champion_club_uid: null, tied_champions: [],
};

export const SEASON_PLAYED = {
  ...SEASON_READY, phase: "awaiting_advance",
  fixtures: [fixture("L-R01-M01", USER, OPP, true, [2, 1]), fixture("L-R01-M02", 102496, 999, true, [0, 0])],
  standings: [row(1, USER, 3), row(2, 102496, 1), row(2, 999, 1), row(4, OPP, 0)],
};

export const SEASON_FINISHED = { ...SEASON_PLAYED, phase: "finished", champion_club_uid: USER, round_number: 3 };

const POS = ["GK", "DR", "DC", "DC", "DL", "DM", "MC", "MC", "STC", "STC", "STC"];
export const FORMATIONS = OFFICIAL_FORMATIONS; // as 11 oficiais (4-3-3 = POS)
const fitAll = (natural: string) =>
  Object.fromEntries(["GK", "DR", "DL", "DC", "DM", "MC", "STC"].map((p) => [p, p === natural ? "natural" : "improvisada"]));

export const SQUAD = [...POS, "GK", "DC", "MC", "STC", "DM", "DR", "MC"].map((pos, i) => ({
  player: 1000 + i, name: `Atleta ${i + 1}`, age: 25, position: pos, available: i !== 17,
  unavailable_reason: i === 17 ? "lesionado (2 jogo(s))" : null, fit: fitAll(pos), appearances: 0, goals: 0, assists: 0,
  average_rating: null, motm: 0, yellow_cards: 0, red_cards: 0,
}));

export const LINEUP = {
  has_match: true, match_id: "L-R01-M01", is_home: true, formation: "4-3-3", posture: "equilibrada", source: "auto",
  note: null, locked: false, formations: FORMATIONS,
  starters: POS.map((p, i) => ({ index: i, position: p, player: 1000 + i, name: `Atleta ${i + 1}`, fit: "natural" })),
  bench: [11, 12, 13].map((i) => ({ player: 1000 + i, name: `Atleta ${i + 1}`, slot: SQUAD[i].position })),
  opponent: {
    club_uid: OPP, previous_formations: ["4-4-2"], top_players: [],
    campaign: { club_uid: OPP, played: 0, wins: 0, draws: 0, losses: 0, goals_for: 0, goals_against: 0, shootouts_won: 0, shootouts_lost: 0, result: "1º lugar", matches: [] },
  },
};

const ev = (seq: number, minute: number, type: string, extra: object = {}) => ({
  seq, minute, second: minute * 60 - 30, period: minute > 45 ? 2 : 1, type, side: 0, club_uid: USER, player: 1008,
  player_name: "Atleta 9", other: null, other_name: null, data: {}, ...extra,
});
const stats = { possession_pct: 55, shots: 7, shots_on_target: 3, xg: 1.2, big_chances: 2, corners: 4, fouls: 9, yellow_cards: 1, red_cards: 0, saves_made: 2 };

export const LIVE = {
  session_id: SID, match_id: "L-R01-M01", home_club_uid: USER, away_club_uid: OPP, user_side: 0, speed: "30s",
  minute: 34, game_second: 2010, finished: false, score: [1, 0], shootout: null,
  events: [ev(10, 12, "goal"), ev(20, 30, "yellow_card", { side: 1, club_uid: OPP, player_name: "Rival" }),
    ev(25, 31, "penalty_awarded", { player_name: "Atleta 9", other_name: "Rival 4", other: 2003 })],
  stats: { home: stats, away: { ...stats, possession_pct: 45 } }, postures: ["equilibrada", "defensiva"],
  own_players: POS.map((p, i) => ({ player: 1000 + i, name: `Atleta ${i + 1}`, slot: p, condition: 90 - i * 3, on_field: true, yellow_cards: 0 })),
  own_bench: [], substitutions_used: 0, max_substitutions: 5,
  opponent_players: POS.map((p, i) => ({ player: 2000 + i, name: `Rival ${i + 1}`, slot: p, on_field: true, yellow_cards: 0 })),
  other_matches: [{ match_id: "L-R01-M02", home_club_uid: 102496, away_club_uid: 333, score: [0, 2], finished: false }],
};

export const REPORT = {
  match_id: "L-R01-M01", round: 1, home_club_uid: USER, away_club_uid: OPP, status: "completed", score: [2, 1], official_score: [2, 1],
  shootout: null, winner_club_uid: USER, events: [ev(10, 12, "goal"), ev(30, 88, "goal", { player_name: "Atleta 10" })],
  stats: { home: stats, away: stats }, final_postures: ["retranca", "ataque_total"], engine_version: "e", params_version: "p",
  ratings: [{ player: 1008, name: "Atleta 9", club_uid: USER, rating: 8.4, minutes: 90 }, { player: 2000, name: "Rival", club_uid: OPP, rating: 6.1, minutes: 90 }],
  man_of_the_match: { player: 1008, name: "Atleta 9", club_uid: USER, rating: 8.4, minutes: 90 },
  lineups: [],
};

export const STATS = {
  session_id: SID, matches_played: 2,
  players: [
    { player: 1008, name: "Atleta 9", club_uid: USER, appearances: 1, goals: 2, assists: 0, average_rating: 8.4, rating_eligible: true, motm: 1, yellow_cards: 0, red_cards: 0 },
    { player: 2000, name: "Rival", club_uid: OPP, appearances: 1, goals: 1, assists: 1, average_rating: 6.1, rating_eligible: true, motm: 0, yellow_cards: 1, red_cards: 0 },
  ],
  clubs: [USER, OPP].map((c) => ({
    club_uid: c, played: 1, wins: c === USER ? 1 : 0, draws: 0, losses: c === USER ? 0 : 1, goals_for: c === USER ? 2 : 1, goals_against: c === USER ? 1 : 2,
    totals: { ...stats, tackles: 10, interceptions: 5, progressions: 30, blocks_made: 1, woodwork: 0, penalties: 0, injuries: 0, substitutions: 3, big_chances_missed: 1 },
    against: { ...stats, tackles: 10, interceptions: 5, progressions: 30, blocks_made: 1, woodwork: 0, penalties: 0, injuries: 0, substitutions: 3, big_chances_missed: 1 },
  })),
};

export const CALENDAR = {
  session_id: SID, kind: "league", current_round: 1,
  rounds: [{ number: 1, label: "Rodada 1", byes: [], fixtures: SEASON_PLAYED.fixtures }, { number: 2, label: "Rodada 2", byes: [], fixtures: [fixture("L-R02-M01", OPP, USER)] }],
};

export const SUMMARY = {
  session_id: SID, finished: true, champion_club_uid: USER, tied_champions: [],
  top_scorers: [{ player: 1008, name: "Atleta 9", club_uid: USER, value: 2, appearances: 1 }],
  top_assists: [], best_average_rating: [{ player: 1008, name: "Atleta 9", club_uid: USER, value: 8.4, appearances: 1 }],
  most_man_of_the_match: [{ player: 1008, name: "Atleta 9", club_uid: USER, value: 1, appearances: 1 }],
  campaigns: [{ ...LINEUP.opponent.campaign, club_uid: USER, played: 3, wins: 3, result: "1º lugar", matches: SEASON_PLAYED.fixtures }],
  user_campaign: { ...LINEUP.opponent.campaign, club_uid: USER, played: 3, wins: 3, result: "1º lugar", matches: SEASON_PLAYED.fixtures },
  history: SEASON_PLAYED.fixtures,
};

const CLUB_PAGE = {
  items: [...CLUBS, { club_uid: 999, name: "Quarto Clube", short_name: "Quarto", nation_id: 1, player_count: 18, division: "B" }],
  total: 4, limit: 200, offset: 0,
};

/** Rotas base: sessão em competição, catálogo e health. */
export function baseRoutes(session: object = SESSION_COMP) {
  return {
    "GET /api/health": () => json(200, {
      status: "ok", service: "g", version: "0.1.0", time: "2026-11-18T12:00:00Z",
      database: { status: "ok", schema_version: 2, clubs: 40, players: 1574 }, active_session: true, services: {},
    }),
    [`GET /api/sessions/${SID}`]: () => json(200, session),
    "GET /api/catalog/clubs": () => json(200, CLUB_PAGE),
  };
}
