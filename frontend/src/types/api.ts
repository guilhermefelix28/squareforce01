/**
 * Tipos da API derivados do contrato OpenAPI gerado pelo backend.
 * Não edite openapi.d.ts manualmente: rode `npm run gen:api` após `python scripts/export_openapi.py`.
 */
import type { components } from "./openapi";

type S = components["schemas"];

export type Health = S["HealthResponse"];
export type Club = S["ClubOut"];
export type Player = S["PlayerOut"];
export type ClubPage = S["ClubPage"];
export type PlayerPage = S["PlayerPage"];
export type ImportReport = S["ImportReport"];
export type ImportIssue = S["ImportIssue"];
export type Session = S["SessionOut"];
export type SessionCreate = S["SessionCreateRequest"];
export type CompetitionConfig = S["CompetitionConfig"];
export type CompetitionOptions = S["CompetitionOptions"];
export type ErrorBody = S["ErrorBody"];
export type Position = S["Position"];
export type CompetitionFormat = S["CompetitionFormat"];
export type LeagueRounds = S["LeagueRounds"];

export type ImportBase = "clubs" | "players";

/** Mensagens recebidas no canal /ws/sessions/{id}. */
export interface WsMessage {
  type: "session.snapshot" | "session.closed" | "pong" | "error" | string;
  session_id?: string | null;
  version?: number | null;
  data: Record<string, unknown>;
}
