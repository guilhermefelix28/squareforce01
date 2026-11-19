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
  SeasonState,
  SeasonSummary,
  MatchReport,
  Calendar,
  Formation,
  Lineup,
  LineupIn,
  LiveState,
  Posture,
  SeasonStats,
  Speed,
  SquadPlayer,
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

/* Área oculta de dados (DR-04): a senha é verificada no servidor; o token vale até o servidor reiniciar. */
const ADMIN_KEY = "squadforce.admin";
let adminToken: string | null = null;

export function getAdminToken(): string | null {
  if (adminToken) return adminToken;
  try {
    adminToken = sessionStorage.getItem(ADMIN_KEY);
  } catch {
    /* sem armazenamento: só nesta aba */
  }
  return adminToken;
}

export function clearAdminToken() {
  adminToken = null;
  try {
    sessionStorage.removeItem(ADMIN_KEY);
  } catch {
    /* ignora */
  }
}

export async function adminLogin(password: string, idempotencyKey = newIdempotencyKey()) {
  const out = await apiRequest<{ token: string }>("/api/admin/login", { method: "POST", json: { password }, idempotencyKey });
  adminToken = out.token;
  try {
    sessionStorage.setItem(ADMIN_KEY, out.token);
  } catch {
    /* ignora */
  }
  return out.token;
}

export function importBase(base: ImportBase, file: File, idempotencyKey = newIdempotencyKey()) {
  const form = new FormData();
  form.append("file", file, file.name);
  const token = getAdminToken();
  return apiRequest<ImportReport>(`/api/imports/${base}`, {
    method: "POST",
    form,
    idempotencyKey,
    headers: token ? { "X-Admin-Token": token } : undefined,
  });
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

// ---------------------------------------------------------------- temporada (Entrega 7)
export const startSeason = (id: string, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<SeasonState>(`${sid(id)}/season/start`, { method: "POST", json: {}, idempotencyKey });

export const getSeason = (id: string) => apiRequest<SeasonState>(`${sid(id)}/season`, { retries: 1 });

/** Processa a rodada atual (paralelo, consolidação atômica). Erro ROUND_FAILED: chamar de novo repete só as falhas. */
export const playRound = (id: string, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<SeasonState>(`${sid(id)}/season/play`, { method: "POST", json: {}, idempotencyKey, retries: 1 });

/** Avanço manual para a próxima rodada/fase. */
export const advanceRound = (id: string, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<SeasonState>(`${sid(id)}/season/advance`, { method: "POST", json: {}, idempotencyKey, retries: 1 });

export const getMatchReport = (id: string, matchId: string) =>
  apiRequest<MatchReport>(`${sid(id)}/season/matches/${encodeURIComponent(matchId)}`);

export const getSeasonSummary = (id: string) => apiRequest<SeasonSummary>(`${sid(id)}/season/summary`);

// ---------------------------------------------------------------- interface (Entrega 8)
export const getFormations = (id: string) => apiRequest<Formation[]>(`${sid(id)}/season/formations`);
export const getSquad = (id: string) => apiRequest<SquadPlayer[]>(`${sid(id)}/season/squad`);
export const getLineup = (id: string) => apiRequest<Lineup>(`${sid(id)}/season/lineup`, { retries: 1 });
export const saveLineup = (id: string, body: LineupIn, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<Lineup>(`${sid(id)}/season/lineup`, { method: "POST", json: body, idempotencyKey, retries: 1 });
export const startLive = (id: string, speed: Speed, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<LiveState>(`${sid(id)}/season/live/start`, { method: "POST", json: { speed }, idempotencyKey, retries: 1 });
export const getLive = (id: string) => apiRequest<LiveState>(`${sid(id)}/season/live`, { retries: 0 });
export const changePosture = (id: string, posture: Posture, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<LiveState>(`${sid(id)}/season/live/posture`, { method: "POST", json: { posture }, idempotencyKey, retries: 1 });
export const changeSpeed = (id: string, speed: Speed, idempotencyKey = newIdempotencyKey()) =>
  apiRequest<LiveState>(`${sid(id)}/season/live/speed`, { method: "POST", json: { speed }, idempotencyKey, retries: 1 });
export const getSeasonStats = (id: string) => apiRequest<SeasonStats>(`${sid(id)}/season/stats`);
export const getCalendar = (id: string) => apiRequest<Calendar>(`${sid(id)}/season/calendar`);

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
