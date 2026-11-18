import type {
  AuctionBidAck,
  AuctionBidRequest,
  AuctionState,
  AuctionSummary,
  ClubPage,
  Proposal,
  ProposalCreate,
  TradingSquad,
  TradingState,
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

const sid = (id: string) => `/api/sessions/${encodeURIComponent(id)}`;

export const startAuction = (id: string, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<AuctionState>(`${sid(id)}/auction/start`, { method: "POST", json: {}, idempotencyKey });

export const getAuction = (id: string) => apiRequest<AuctionState>(`${sid(id)}/auction`, { retries: 1 });

export const placeBid = (id: string, body: AuctionBidRequest, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<AuctionBidAck>(`${sid(id)}/auction/bids`, { method: "POST", json: body, idempotencyKey, retries: 1 });

export const getAuctionSummary = (id: string) => apiRequest<AuctionSummary>(`${sid(id)}/auction/summary`);

export const startTrading = (id: string, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<TradingState>(`${sid(id)}/trading/start`, { method: "POST", json: {}, idempotencyKey });

export const getTrading = (id: string) => apiRequest<TradingState>(`${sid(id)}/trading`, { retries: 1 });

export const getTradingSquads = (id: string, params: { search?: string; club_uid?: number; position?: string } = {}) =>
  apiRequest<TradingSquad[]>(`${sid(id)}/trading/squads`, { query: params });

export const createProposal = (id: string, body: ProposalCreate, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<Proposal>(`${sid(id)}/trading/proposals`, { method: "POST", json: body, idempotencyKey, retries: 1 });

export const actOnProposal = (id: string, proposalId: string, action: "accept" | "reject" | "cancel", idempotencyKey = newIdempotencyKey()) =>
  apiRequest<Proposal>(`${sid(id)}/trading/proposals/${encodeURIComponent(proposalId)}/${action}`, { method: "POST", json: {}, idempotencyKey, retries: 1 });

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
