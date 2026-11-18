/**
 * Cliente HTTP do SquadForce.
 * - Erros padronizados do backend viram ApiError (code, message, retryable, details).
 * - Falhas de comunicação recuperáveis são repetidas com backoff.
 * - Comandos (POST) só são repetidos com a MESMA Idempotency-Key, o que torna a repetição segura:
 *   o backend devolve a resposta original em vez de executar duas vezes.
 */
import type { ErrorBody } from "../types/api";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly details: Record<string, unknown>;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.retryable = body.retryable;
    this.details = (body.details ?? {}) as Record<string, unknown>;
  }
}

export const NETWORK_ERROR = "NETWORK_ERROR";

interface ApiConfig {
  baseUrl: string;
  retryDelayMs: number;
  timeoutMs: number;
  fetchImpl: typeof fetch;
}

const config: ApiConfig = {
  baseUrl: "",
  retryDelayMs: 400,
  timeoutMs: 30_000,
  fetchImpl: (...args) => fetch(...args),
};

export function configureApi(partial: Partial<ApiConfig>): void {
  Object.assign(config, partial);
}

export function apiUrl(path: string): string {
  return `${config.baseUrl}${path}`;
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `sf-${crypto.randomUUID()}`;
  return `sf-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export interface RequestOptions {
  method?: "GET" | "POST";
  json?: unknown;
  form?: FormData;
  idempotencyKey?: string;
  /** Quantidade de repetições após a primeira tentativa. */
  retries?: number;
  query?: Record<string, string | number | undefined | null>;
}

const RETRYABLE_STATUS = new Set([502, 503, 504]);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function isErrorBody(x: unknown): x is { error: ErrorBody } {
  return !!x && typeof x === "object" && "error" in x && typeof (x as { error: { code?: unknown } }).error?.code === "string";
}

export async function apiRequest<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? "GET";
  if (method !== "GET" && !opts.idempotencyKey) {
    throw new Error("Comandos exigem idempotencyKey");
  }
  const retries = opts.retries ?? 2;
  const qs = opts.query
    ? "?" +
      Object.entries(opts.query)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const url = apiUrl(path) + (qs === "?" ? "" : qs);

  let lastError: ApiError | null = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    if (attempt > 0) await sleep(config.retryDelayMs * 2 ** (attempt - 1));
    const headers: Record<string, string> = { Accept: "application/json" };
    if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
    let body: BodyInit | undefined;
    if (opts.form) body = opts.form;
    else if (opts.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), config.timeoutMs);
    let res: Response;
    try {
      res = await config.fetchImpl(url, { method, headers, body, signal: controller.signal });
    } catch {
      lastError = new ApiError(0, {
        code: NETWORK_ERROR,
        message: "Não foi possível comunicar com o servidor. Verifique se o backend está em execução.",
        retryable: true,
        details: {},
      });
      continue;
    } finally {
      clearTimeout(timer);
    }

    let payload: unknown = null;
    const text = await res.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }
    if (res.ok) return payload as T;

    const err = isErrorBody(payload)
      ? new ApiError(res.status, payload.error)
      : new ApiError(res.status, {
          code: res.status >= 500 ? "INTERNAL_ERROR" : "HTTP_ERROR",
          message: `O servidor respondeu com erro ${res.status}.`,
          retryable: RETRYABLE_STATUS.has(res.status),
          details: {},
        });
    if (err.retryable || RETRYABLE_STATUS.has(res.status)) {
      lastError = err;
      continue;
    }
    throw err;
  }
  throw lastError!;
}
