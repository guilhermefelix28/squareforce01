import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { CLUBS, LEAGUE_COMPETITION, OPTIONS, SESSION, apiError, fakeApi, json } from "../test/fakeApi";
import { App } from "./App";

const HEALTH = {
  status: "ok",
  service: "squadforce-gateway",
  version: "0.1.0",
  time: "2026-11-18T12:00:00Z",
  database: { status: "ok", schema_version: 1, clubs: 40, players: 1574 },
  active_session: false,
  services: { gateway: "ready", session: "ready", data: "ready", auction: "planned" },
};

beforeEach(() => {
  window.location.hash = "";
});

describe("App", () => {
  it("mostra servidor online e contagens do banco", async () => {
    fakeApi({ "GET /api/health": () => json(200, HEALTH) });
    render(<App />);
    expect(await screen.findByText("Servidor online")).toBeInTheDocument();
    expect(screen.getByText("1574")).toBeInTheDocument();
    // navegação contextual: sem competição ativa não há aba de leilão; Dados fica disponível
    expect(screen.getByRole("link", { name: "Dados" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Leilão" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Leilão")).toHaveLength(1); // somente na lista de serviços
  });

  it("informa claramente quando o backend está inacessível", async () => {
    const { impl } = fakeApi({});
    impl.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);
    expect(await screen.findByText("Servidor offline")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/Sem comunicação com o servidor/);
  });

  it("cria uma sessão válida e encerra após confirmação", async () => {
    const user = userEvent.setup();
    let closed = false;
    const { calls } = fakeApi({
      "GET /api/health": () => json(200, HEALTH),
      "GET /api/competitions/options": () => json(200, OPTIONS),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 2, limit: 200, offset: 0 }),
      "POST /api/sessions": () => json(201, SESSION),
      "GET /api/sessions/11111111-2222-3333-4444-555555555555/competition": () => json(200, LEAGUE_COMPETITION),
      "POST /api/sessions/11111111-2222-3333-4444-555555555555/close": () => {
        closed = true;
        return json(200, { ...SESSION, status: "closed", version: 2, closed_at: "2026-11-18T12:05:00Z" });
      },
    });
    window.location.hash = "#/session";
    render(<App />);

    await user.selectOptions(await screen.findByLabelText("Seu clube"), "322");
    await user.click(screen.getByRole("button", { name: "Iniciar sessão" }));
    expect(await screen.findByText("Competição ativa")).toBeInTheDocument();
    expect(await screen.findByText("Calendário da Liga")).toBeInTheDocument();
    const create = calls.find((c) => c.method === "POST" && c.path === "/api/sessions")!;
    expect(JSON.parse(String(create.init.body))).toMatchObject({ format: "league", user_club_uid: 322, league_rounds: "double" });
    expect((create.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
    expect(localStorage.getItem("squadforce.sessionId")).toBe(SESSION.id);

    await user.click(screen.getByRole("button", { name: "Encerrar sessão" }));
    const dialog = screen.getByRole("alertdialog");
    expect(closed).toBe(false); // nada acontece sem confirmação
    await user.click(within(dialog).getByRole("button", { name: "Encerrar" }));
    await waitFor(() => expect(closed).toBe(true));
    expect(await screen.findByText("Sessão encerrada")).toBeInTheDocument();
    const close = calls.find((c) => c.path.endsWith("/close"))!;
    expect(JSON.parse(String(close.init.body))).toEqual({ expected_version: 1 });
  });

  it("bloqueia configuração inválida no cliente sem chamar a API", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      "GET /api/health": () => json(200, HEALTH),
      "GET /api/competitions/options": () => json(200, OPTIONS),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 2, limit: 200, offset: 0 }),
    });
    window.location.hash = "#/session";
    render(<App />);
    const input = await screen.findByLabelText(/Clubes \(2–20\)/);
    await user.clear(input);
    await user.type(input, "25");
    await user.selectOptions(screen.getByLabelText("Seu clube"), "322");
    await user.click(screen.getByRole("button", { name: "Iniciar sessão" }));
    expect(await screen.findByText(/A Liga aceita de 2 a 20 clubes/)).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("pede confirmação para substituir competição ativa", async () => {
    const user = userEvent.setup();
    const bodies: unknown[] = [];
    fakeApi({
      "GET /api/health": () => json(200, HEALTH),
      "GET /api/competitions/options": () => json(200, OPTIONS),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 2, limit: 200, offset: 0 }),
      "POST /api/sessions": (_u, init) => {
        const b = JSON.parse(String(init.body));
        bodies.push(b);
        return b.confirm_replace
          ? json(201, SESSION)
          : apiError(409, "SESSION_ALREADY_ACTIVE", "Já existe uma competição ativa.", false, { active_session_id: "x" });
      },
    });
    window.location.hash = "#/session";
    render(<App />);
    await user.selectOptions(await screen.findByLabelText("Seu clube"), "329");
    await user.click(screen.getByRole("button", { name: "Iniciar sessão" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Encerrar e iniciar nova" }));
    expect(await screen.findByText("Competição ativa")).toBeInTheDocument();
    expect(bodies.map((b) => (b as { confirm_replace: boolean }).confirm_replace)).toEqual([false, true]);
  });

  it("avisa quando a sessão salva no navegador foi perdida pelo servidor", async () => {
    localStorage.setItem("squadforce.sessionId", "perdida");
    fakeApi({
      "GET /api/health": () => json(200, HEALTH),
      "GET /api/competitions/options": () => json(200, OPTIONS),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 2, limit: 200, offset: 0 }),
      "GET /api/sessions/perdida": () =>
        apiError(404, "SESSION_NOT_FOUND", "Sessão não encontrada. Se o servidor foi reiniciado, a competição não pode ser restaurada."),
    });
    window.location.hash = "#/session";
    render(<App />);
    expect(await screen.findByText(/não pode ser restaurada/)).toBeInTheDocument();
    expect(localStorage.getItem("squadforce.sessionId")).toBeNull();
  });
});
