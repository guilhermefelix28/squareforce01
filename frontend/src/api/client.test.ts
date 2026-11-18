import { describe, expect, it } from "vitest";
import { apiError, fakeApi, json } from "../test/fakeApi";
import { ApiError, apiRequest, NETWORK_ERROR } from "./client";
import { createSession, importBase } from "./endpoints";

describe("apiRequest", () => {
  it("converte o erro padronizado do backend em ApiError", async () => {
    fakeApi({ "GET /api/sessions/x": () => apiError(404, "SESSION_NOT_FOUND", "Sessão não encontrada.") });
    const err = await apiRequest("/api/sessions/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 404, code: "SESSION_NOT_FOUND", retryable: false });
  });

  it("repete após falha de rede recuperável e conclui", async () => {
    let n = 0;
    const { impl } = fakeApi({});
    impl.mockImplementation(async () => {
      if (n++ === 0) throw new TypeError("Failed to fetch");
      return json(200, { status: "ok" });
    });
    await expect(apiRequest("/api/health")).resolves.toEqual({ status: "ok" });
    expect(impl).toHaveBeenCalledTimes(2);
  });

  it("reenvia comandos com a MESMA Idempotency-Key", async () => {
    const keys: string[] = [];
    let n = 0;
    const { impl } = fakeApi({});
    impl.mockImplementation(async (_url: unknown, init: RequestInit = {}) => {
      keys.push((init.headers as Record<string, string>)["Idempotency-Key"]);
      if (n++ < 2) return apiError(503, "INTERNAL_ERROR", "indisponível", true);
      return json(201, { id: "s1" });
    });
    await createSession(
      { format: "cup", num_clubs: 8, user_club_uid: 322, league_rounds: null, confirm_replace: false },
      "sf-chave-fixa",
    );
    expect(keys).toEqual(["sf-chave-fixa", "sf-chave-fixa", "sf-chave-fixa"]);
  });

  it("não repete erros definitivos", async () => {
    const { impl } = fakeApi({ "POST /api/sessions": () => apiError(422, "INVALID_COMPETITION_CONFIG") });
    await expect(
      createSession({ format: "league", num_clubs: 1, user_club_uid: 1, league_rounds: "single", confirm_replace: false }),
    ).rejects.toMatchObject({ code: "INVALID_COMPETITION_CONFIG" });
    expect(impl).toHaveBeenCalledTimes(1);
  });

  it("repete erros marcados como retryable pelo backend", async () => {
    let n = 0;
    const { impl } = fakeApi({});
    impl.mockImplementation(async () =>
      n++ === 0 ? apiError(409, "IMPORT_IN_PROGRESS", "ocupado", true) : json(200, { status: "imported" }),
    );
    const file = new File(["PK"], "jogadores.xlsx");
    await expect(importBase("players", file)).resolves.toEqual({ status: "imported" });
    expect(impl).toHaveBeenCalledTimes(2);
  });

  it("após esgotar tentativas devolve NETWORK_ERROR recuperável", async () => {
    const { impl } = fakeApi({});
    impl.mockRejectedValue(new TypeError("offline"));
    const err = await apiRequest("/api/health", { retries: 2 }).catch((e) => e);
    expect(err).toMatchObject({ code: NETWORK_ERROR, retryable: true, status: 0 });
    expect(impl).toHaveBeenCalledTimes(3);
  });

  it("exige chave de idempotência em comandos", async () => {
    await expect(apiRequest("/api/sessions", { method: "POST", json: {} })).rejects.toThrow(/idempotencyKey/);
  });

  it("monta a query string ignorando vazios", async () => {
    const { impl } = fakeApi({ "GET /api/catalog/players": () => json(200, { items: [] }) });
    await apiRequest("/api/catalog/players", { query: { position: "GOL", search: "", club_uid: undefined, limit: 5 } });
    expect(String(impl.mock.calls[0][0])).toBe("/api/catalog/players?position=GOL&limit=5");
  });
});
