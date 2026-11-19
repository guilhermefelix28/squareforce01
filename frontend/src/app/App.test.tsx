import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { CLUBS, FORMATIONS, LEAGUE_COMPETITION, OPTIONS, SESSION, apiError, fakeApi, json } from "../test/fakeApi";
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
  it("abre com a apresentação do jogo e o botão de nova partida, sem abas", async () => {
    const user = userEvent.setup();
    fakeApi({ "GET /api/health": () => json(200, HEALTH) });
    render(<App />);
    expect(await screen.findByText("Servidor online")).toBeInTheDocument();
    expect(screen.getByText(/40 clubes · 1574 jogadores/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Nova partida/ })).toBeEnabled();
    // sem abas de navegação; a área de dados é oculta (sem link em lugar nenhum)
    expect(screen.queryByRole("navigation", { name: "Navegação principal" })).not.toBeInTheDocument();
    expect(screen.queryByText("IA dos bots")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Menu/ }));
    const menu = screen.getByRole("navigation", { name: "Menu do jogo" });
    expect(within(menu).queryByText(/Dados/)).not.toBeInTheDocument();
    expect(document.querySelector('a[href="#/admin"]')).toBeNull();
  });

  it("tema escuro é o padrão mesmo com o sistema em modo claro", async () => {
    localStorage.removeItem("squadforce.theme");
    window.matchMedia = ((q: string) => ({ matches: q.includes("light"), media: q, addEventListener() {}, removeEventListener() {} })) as never;
    fakeApi({ "GET /api/health": () => json(200, HEALTH) });
    render(<App />);
    await screen.findByText("Servidor online");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("button", { name: "Alternar para tema claro" })).toBeInTheDocument();
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
      "GET /api/formations": () => json(200, FORMATIONS),
      "GET /api/sessions/11111111-2222-3333-4444-555555555555/competition": () => json(200, LEAGUE_COMPETITION),
      "POST /api/sessions/11111111-2222-3333-4444-555555555555/close": () => {
        closed = true;
        return json(200, { ...SESSION, status: "closed", version: 2, closed_at: "2026-11-18T12:05:00Z" });
      },
    });
    window.location.hash = "#/session";
    render(<App />);

    await user.click(await screen.findByRole("radio", { name: "Flamengo" }));
    await user.click(screen.getByRole("button", { name: /Começar partida/ }));
    // após criar, o jogo conduz à escolha da tática
    expect(await screen.findByText("Escolha sua tática")).toBeInTheDocument();
    expect(window.location.hash).toBe("#/tatica");
    window.location.hash = "#/session";
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
    await user.click(screen.getByRole("radio", { name: "Flamengo" }));
    await user.click(screen.getByRole("button", { name: /Começar partida/ }));
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
      "GET /api/formations": () => json(200, FORMATIONS),
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
    await user.click(await screen.findByRole("radio", { name: "Palmeiras" }));
    await user.click(screen.getByRole("button", { name: /Começar partida/ }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Encerrar e iniciar nova" }));
    expect(await screen.findByText("Escolha sua tática")).toBeInTheDocument();
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

describe("tática antes do leilão (DR-02)", () => {
  it("escolhe a formação, salva com idempotência e segue para o leilão", async () => {
    const user = userEvent.setup();
    localStorage.setItem("squadforce.sessionId", SESSION.id);
    const { calls } = fakeApi({
      "GET /api/health": () => json(200, { ...HEALTH, active_session: true }),
      [`GET /api/sessions/${SESSION.id}`]: () => json(200, SESSION),
      "GET /api/formations": () => json(200, FORMATIONS),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 3, limit: 200, offset: 0 }),
      [`POST /api/sessions/${SESSION.id}/formation`]: (_u, init) =>
        json(200, { ...SESSION, version: 2, user_formation: JSON.parse(String(init.body)).formation }),
    });
    window.location.hash = "#/tatica";
    render(<App />);
    const tiles = await screen.findAllByRole("radio");
    expect(tiles).toHaveLength(11);
    await user.click(screen.getByRole("radio", { name: "3-5-2" }));
    expect(screen.getByRole("radio", { name: "3-5-2" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("button", { name: /Confirmar tática/ }));
    await waitFor(() => expect(window.location.hash).toBe("#/auction"));
    const post = calls.find((c) => c.method === "POST")!;
    expect(JSON.parse(String(post.init.body))).toEqual({ formation: "3-5-2" });
    expect((post.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
    expect(await screen.findByText("Sua tática: 3-5-2")).toBeInTheDocument();
    localStorage.removeItem("squadforce.sessionId");
  });
});

describe("área oculta de dados (DR-04)", () => {
  it("pede senha, verificada no servidor, antes de mostrar as importações", async () => {
    const user = userEvent.setup();
    sessionStorage.clear();
    fakeApi({
      "GET /api/health": () => json(200, HEALTH),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 3, limit: 200, offset: 0 }),
      "GET /api/catalog/players": () => json(200, { items: [], total: 0, limit: 25, offset: 0 }),
      "POST /api/admin/login": (_u, init) =>
        JSON.parse(String(init.body)).password === "9153" ? json(200, { token: "t".repeat(40) }) : apiError(401, "ADMIN_AUTH_FAILED", "Senha incorreta."),
    });
    window.location.hash = "#/admin";
    render(<App />);
    expect(await screen.findByText("Área restrita")).toBeInTheDocument();
    expect(screen.queryByText("Importação de bases")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Senha"), "1111");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Senha incorreta.")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Senha"));
    await user.type(screen.getByLabelText("Senha"), "9153");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Importação de bases")).toBeInTheDocument();
    expect(sessionStorage.getItem("squadforce.admin")).toBe("t".repeat(40));
  });
});
