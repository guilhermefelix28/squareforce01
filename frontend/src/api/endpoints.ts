import type {
  ClubPage,
  CompetitionOut,
  CompetitionOptions,
  Health,
  ImportBase,
  ImportReport,
  PlayerPage,
  Session,
  SessionCreate,
} from "../types/api";
import { apiRequest, apiUrl, newIdempotencyKey } from "./client";

export const getHealth = () => apiRequest<Health>("/api/health", { retries: 0 });

export const getCompetitionOptions = () => apiRequest<CompetitionOptions>("/api/competitions/options");

export const listClubs = (params: { search?: string; limit?: number; offset?: number } = {}) =>
  apiRequest<ClubPage>("/api/catalog/clubs", { query: { limit: 200, ...params } });

export const listPlayers = (params: {
  club_uid?: number;
  position?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) => apiRequest<PlayerPage>("/api/catalog/players", { query: params });

export function importBase(base: ImportBase, file: File, idempotencyKey = newIdempotencyKey()) {
  const form = new FormData();
  form.append("file", file, file.name);
  return apiRequest<ImportReport>(`/api/imports/${base}`, { method: "POST", form, idempotencyKey });
}

export const createSession = (body: SessionCreate, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<Session>("/api/sessions", { method: "POST", json: body, idempotencyKey });

export const getSession = (id: string) => apiRequest<Session>(`/api/sessions/${encodeURIComponent(id)}`);

export const getCompetition = (id: string) =>
  apiRequest<CompetitionOut>(`/api/sessions/${encodeURIComponent(id)}/competition`);

export const closeSession = (id: string, expectedVersion?: number, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<Session>(`/api/sessions/${encodeURIComponent(id)}/close`, {
    method: "POST",
    json: expectedVersion === undefined ? {} : { expected_version: expectedVersion },
    idempotencyKey,
  });

export const clubLogoUrl = (clubUid: number) => apiUrl(`/api/assets/clubs/${clubUid}`);
export const playerPhotoUrl = (uniqueId: number) => apiUrl(`/api/assets/players/${uniqueId}`);

export function sessionSocketUrl(id: string): string {
  const base = apiUrl("") || window.location.origin;
  return base.replace(/^http/, "ws") + `/ws/sessions/${encodeURIComponent(id)}`;
}
