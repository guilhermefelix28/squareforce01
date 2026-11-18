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
  catalog_ready: true,
  imports_blocked: false,
};

export const CLUBS = [
  { club_uid: 322, name: "Clube de Regatas do Flamengo", short_name: "Flamengo", nation_id: 189, player_count: 40 },
  { club_uid: 329, name: "Sociedade Esportiva Palmeiras", short_name: "Palmeiras", nation_id: 189, player_count: 40 },
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
  participants: null,
};
