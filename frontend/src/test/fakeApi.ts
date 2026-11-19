import { vi } from "vitest";
import { configureApi } from "../api/client";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

export const apiError = (status: number, code: string, message = code, retryable = false, details = {}) =>
  json(status, { error: { code, message, retryable, details } });

/** Instala um fetch falso roteado por "MÉTODO caminho" (sem query string). */
export function fakeApi(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; init: RequestInit }[] = [];
  const impl = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const method = init.method ?? "GET";
    calls.push({ method, path, init });
    const handler = routes[`${method} ${path}`];
    if (!handler) return apiError(404, "NOT_FOUND");
    return handler(url, init);
  });
  configureApi({ fetchImpl: impl as unknown as typeof fetch, baseUrl: "" });
  return { calls, impl };
}

export const OPTIONS = {
  league: { min_clubs: 2, max_clubs: 20, rounds: ["single", "double"] },
  cup: { allowed_sizes: [2, 4, 8, 16, 32] },
  available_clubs: 40,
  eligible_clubs: 40,
  division_counts: { A: 20, B: 20 },
  catalog_ready: true,
  imports_blocked: false,
};

export const CLUBS = [
  { club_uid: 322, name: "Clube de Regatas do Flamengo", short_name: "Flamengo", nation_id: 189, player_count: 40, division: "A" },
  { club_uid: 329, name: "Sociedade Esportiva Palmeiras", short_name: "Palmeiras", nation_id: 189, player_count: 40, division: "A" },
  { club_uid: 102496, name: "Goiás Esporte Clube", short_name: "Goiás", nation_id: 189, player_count: 40, division: "B" },
];

export const SESSION = {
  id: "11111111-2222-3333-4444-555555555555",
  version: 1,
  status: "active",
  phase: "setup",
  config: { format: "league", num_clubs: 20, user_club_uid: 322, league_rounds: "double" },
  created_at: "2026-11-18T12:00:00Z",
  updated_at: "2026-11-18T12:00:00Z",
  closed_at: null,
  participants: [322, 329, 102496],
};

const cupMatch = (id: string, round: number, slot: number, a: number | null, b: number | null, sa: string | null, sb: string | null, next: string | null) => ({
  id, round, slot, club_a_uid: a, club_b_uid: b, source_a: sa, source_b: sb, next_match_id: next, winner_club_uid: null, decided_by: null,
});

export const LEAGUE_COMPETITION = {
  session_id: SESSION.id,
  version: 1,
  format: "league",
  user_club_uid: 322,
  structure: {
    kind: "league",
    rounds_mode: "single",
    participants: [322, 329, 102496],
    total_rounds: 3,
    total_matches: 3,
    matches_per_club: 2,
    rounds: [
      { number: 1, turn: 1, bye_club_uid: 102496, matches: [{ id: "L-R01-M01", round: 1, turn: 1, home_club_uid: 322, away_club_uid: 329 }] },
      { number: 2, turn: 1, bye_club_uid: 322, matches: [{ id: "L-R02-M01", round: 2, turn: 1, home_club_uid: 329, away_club_uid: 102496 }] },
      { number: 3, turn: 1, bye_club_uid: 329, matches: [{ id: "L-R03-M01", round: 3, turn: 1, home_club_uid: 102496, away_club_uid: 322 }] },
    ],
  },
};

export const CUP_COMPETITION = {
  session_id: SESSION.id,
  version: 1,
  format: "cup",
  user_club_uid: 322,
  structure: {
    kind: "cup",
    participants: [322, 329, 102496, 316],
    rules: { single_match: true, neutral_venue: true, regulation_minutes: 90, extra_time: false, draw_decided_by: "penalties", penalties_count_as_goals: false },
    total_rounds: 2,
    total_matches: 3,
    champion_club_uid: null,
    rounds: [
      { number: 1, name: "Semifinal", matches: [
        cupMatch("C-R1-M01", 1, 1, 322, 316, null, null, "C-R2-M01"),
        cupMatch("C-R1-M02", 1, 2, 329, 102496, null, null, "C-R2-M01"),
      ] },
      { number: 2, name: "Final", matches: [cupMatch("C-R2-M01", 2, 1, null, null, "C-R1-M01", "C-R1-M02", null)] },
    ],
  },
};

/** As 11 formações oficiais (mesmas vagas do servidor). */
export const FORMATIONS = [
  ["4-4-2", "GK DR DC DC DL MC MC MC MC STC STC"],
  ["4-3-3", "GK DR DC DC DL DM MC MC STC STC STC"],
  ["4-2-3-1", "GK DR DC DC DL DM DM MC MC MC STC"],
  ["3-5-2", "GK DC DC DC DR DL DM MC MC STC STC"],
  ["3-4-3", "GK DC DC DC DR DL DM MC STC STC STC"],
  ["5-3-2", "GK DR DC DC DC DL DM MC MC STC STC"],
  ["4-1-4-1", "GK DR DC DC DL DM MC MC MC MC STC"],
  ["4-5-1", "GK DR DC DC DL MC MC MC MC MC STC"],
  ["4-3-2-1", "GK DR DC DC DL DM MC DM MC MC STC"],
  ["4-3-1-2", "GK DR DC DC DL DM MC MC MC STC STC"],
  ["5-4-1", "GK DR DC DC DC DL DM MC MC MC STC"],
].map(([id, p]) => ({ id, positions: p.split(" ") }));
