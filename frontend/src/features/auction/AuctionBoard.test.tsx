import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { formatClock, formatMoneyShort, parseMoney } from "../../domain/money";
import { CLUBS, FORMATIONS, SESSION, apiError, fakeApi, json } from "../../test/fakeApi";
import type { AuctionState, Club } from "../../types/api";
import { AuctionBoard } from "./AuctionBoard";

const player = (id: number, name: string, min: number) => ({
  unique_id: id, name, age: 24, club_short_name: "Origem", club_uid: 900, position: "STC" as const, minimum_bid: min, has_photo: false,
});

const STATE: AuctionState = {
  session_id: SESSION.id,
  phase: "running",
  global_remaining_ms: 540_000,
  global_duration_ms: 600_000,
  round: {
    number: 7, position: "STC", duration_ms: 10_000, remaining_ms: 8_000,
    players: [player(1, "Atacante Um", 1_000_000), player(2, "Atacante Dois", 2_500_000), player(3, "Três", 300_000),
      player(4, "Quatro", 400_000), player(5, "Cinco", 500_000)],
  },
  user_club_uid: 322,
  budget: 120_000_000,
  max_bid: 111_500_000,
  open_slots: 18,
  active_bid: null,
  squad: [],
  clubs: [
    { club_uid: 322, is_user: true, squad_count: 0, budget: 120_000_000 },
    { club_uid: 329, is_user: false, squad_count: 2, budget: 110_000_000 },
  ],
  recent_results: [{ number: 6, position: "GK", sales: [{ player_id: 99, player_name: "Goleiro X", club_uid: 329, price: 3_200_000 }], unsold_player_ids: [7, 8] }],
  rounds_completed: 6,
  finish_reason: null,
  bid_increments: [100_000, 500_000, 1_000_000],
};

function renderBoard(state = STATE, onChanged = vi.fn(), formation: (typeof FORMATIONS)[number] | null = null) {
  render(
    <AuctionBoard sessionId={SESSION.id} state={state} clubs={CLUBS as Club[]} formation={formation} roundRemainingMs={8_000} globalRemainingMs={540_000} onChanged={onChanged} />,
  );
  return onChanged;
}

describe("dinheiro e relógio", () => {
  it("formata e interpreta valores", () => {
    expect(formatMoneyShort(2_500_000)).toBe("R$ 2,5 mi");
    expect(formatMoneyShort(500_000)).toBe("R$ 500 mil");
    expect(parseMoney("2,5 mi")).toBe(2_500_000);
    expect(parseMoney("1.500.000")).toBe(1_500_000);
    expect(parseMoney("800 mil")).toBe(800_000);
    expect(parseMoney("abc")).toBeNaN();
    expect(formatClock(65_001)).toBe("1:06");
  });
});

describe("AuctionBoard", () => {
  it("mostra rodada, temporizadores, saldo e resultados sem dados ocultos", () => {
    fakeApi({});
    renderBoard();
    expect(screen.getByText("Rodada 7")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /ATA em disputa/ })).toBeInTheDocument();
    expect(screen.getByRole("timer", { name: "Tempo da rodada: 8 segundos" })).toHaveTextContent("8");
    expect(screen.getByText("9:00")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { pressed: false })).toHaveLength(5);
    expect(screen.getAllByText("R$ 120 mi").length).toBeGreaterThan(0);
    expect(screen.getByText("R$ 111,5 mi")).toBeInTheDocument();
    const results = screen.getByRole("complementary", { name: "Seu elenco e resultados" });
    expect(within(results).getByText("Goleiro X")).toBeInTheDocument();
    expect(within(results).getByText("2 sem lance vencedor")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/overall|atributo/i);
  });

  it("usa lance mínimo e incrementos e confirma com chave de idempotência", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      [`POST /api/sessions/${SESSION.id}/auction/bids`]: (_u, init) => {
        const b = JSON.parse(String(init.body));
        return json(200, { round: 7, player_id: b.player_id, amount: b.amount, seq: 12, replaced_player_id: null, replayed: false });
      },
    });
    const onChanged = renderBoard();
    await user.click(screen.getByRole("button", { name: /Atacante Dois/ }));
    const input = screen.getByLabelText(/Valor para Atacante Dois/);
    expect(input).toHaveValue("2500000");
    // atalhos do negativo para o positivo; sem "Mínimo" nem ±100 mil (o − e o + já andam de 100 em 100 mil)
    const shortcuts = within(screen.getByRole("group", { name: "Atalhos de valor" })).getAllByRole("button");
    expect(shortcuts.map((b) => b.textContent)).toEqual(["−1 mi", "−500 mil", "+500 mil", "+1 mi"]);
    expect(screen.queryByRole("button", { name: "Mínimo" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "+500 mil" }));
    await user.click(screen.getByRole("button", { name: "+1 mi" }));
    expect(input).toHaveValue("4000000");
    await user.click(screen.getByRole("button", { name: "Aumentar lance" }));
    expect(input).toHaveValue("4100000");
    await user.click(screen.getByRole("button", { name: "Reduzir R$ 1 mi" }));
    await user.click(screen.getByRole("button", { name: "Diminuir lance" }));
    expect(input).toHaveValue("3000000");
    await user.click(screen.getByRole("button", { name: "Confirmar lance" }));
    expect(await screen.findByText(/Lance de R\$\s3\.000\.000 em Atacante Dois confirmado/)).toBeInTheDocument();
    const call = calls.find((c) => c.method === "POST")!;
    expect(JSON.parse(String(call.init.body))).toEqual({ player_id: 2, amount: 3_000_000, round_number: 7 });
    expect((call.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
    expect(onChanged).toHaveBeenCalled();
  });

  it("a mensagem do lance some quando a rodada muda (regressão: 'Lance de R$…' de rodada anterior)", async () => {
    const user = userEvent.setup();
    fakeApi({
      [`POST /api/sessions/${SESSION.id}/auction/bids`]: (_u, init) => {
        const b = JSON.parse(String(init.body));
        return json(200, { round: 7, player_id: b.player_id, amount: b.amount, seq: 12, replaced_player_id: null, replayed: false });
      },
    });
    const view = render(
      <AuctionBoard sessionId={SESSION.id} state={STATE} clubs={CLUBS as Club[]} formation={null} roundRemainingMs={8_000} globalRemainingMs={540_000} onChanged={vi.fn()} />,
    );
    await user.click(screen.getByRole("button", { name: /Atacante Dois/ }));
    await user.click(screen.getByRole("button", { name: "Confirmar lance" }));
    expect(await screen.findByText(/Lance de R\$\s2\.500\.000 em Atacante Dois confirmado/)).toBeInTheDocument();
    const next = { ...STATE, round: { ...STATE.round!, number: 8 } };
    view.rerender(
      <AuctionBoard sessionId={SESSION.id} state={next} clubs={CLUBS as Club[]} formation={null} roundRemainingMs={8_000} globalRemainingMs={540_000} onChanged={vi.fn()} />,
    );
    expect(screen.queryByText(/Lance de R\$/)).toBeNull();
  });

  it("aceita digitação manual e explica recusas do servidor", async () => {
    const user = userEvent.setup();
    fakeApi({
      [`POST /api/sessions/${SESSION.id}/auction/bids`]: () =>
        apiError(422, "INSUFFICIENT_FUNDS", "x", false, { max_bid: 111_500_000 }),
    });
    renderBoard();
    await user.click(screen.getByRole("button", { name: /Atacante Um/ }));
    const input = screen.getByLabelText(/Valor para Atacante Um/);
    await user.clear(input);
    await user.type(input, "200 mi");
    expect(screen.getByText(/Você está oferecendo R\$\s200\.000\.000/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar lance" }));
    expect(await screen.findByText(/preservar R\$ 500 mil por vaga restante/)).toBeInTheDocument();
  });

  it("destaca a oferta ativa e permite REDUZIR o lance no mesmo atleta (DR-01)", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      [`POST /api/sessions/${SESSION.id}/auction/bids`]: (_u, init) => {
        const b = JSON.parse(String(init.body));
        return json(200, { round: 7, player_id: b.player_id, amount: b.amount, seq: 13, replaced_player_id: null, replayed: false });
      },
    });
    renderBoard({ ...STATE, active_bid: { round: 7, player_id: 3, amount: 900_000, seq: 4 } });
    expect(screen.getByText("seu lance: R$ 900 mil")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Três/ }));
    const input = screen.getByLabelText(/Valor para Três/);
    expect(input).toHaveValue("900000"); // parte do lance atual
    await user.click(screen.getByRole("button", { name: "Reduzir R$ 500 mil" }));
    expect(input).toHaveValue("400000");
    await user.click(screen.getByRole("button", { name: "Reduzir R$ 500 mil" }));
    expect(input).toHaveValue("300000"); // nunca abaixo do mínimo
    expect(screen.getByRole("button", { name: "Diminuir lance" })).toBeDisabled();
    expect(screen.getByText(/Você está reduzindo seu lance/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirmar novo valor" }));
    await screen.findByText(/confirmado/);
    expect(JSON.parse(String(calls.find((c) => c.method === "POST")!.init.body))).toMatchObject({ player_id: 3, amount: 300_000 });
  });

  it("cancela o próprio lance durante a rodada (DR-07)", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      [`POST /api/sessions/${SESSION.id}/auction/bids/cancel`]: () => json(200, { round: 7, player_id: 3, amount: 900_000, replayed: false }),
    });
    const onChanged = renderBoard({ ...STATE, active_bid: { round: 7, player_id: 3, amount: 900_000, seq: 4 } });
    await user.click(screen.getByRole("button", { name: /Cancelar meu lance/ }));
    expect(await screen.findByText(/Lance em Três cancelado/)).toBeInTheDocument();
    const call = calls.find((c) => c.method === "POST")!;
    expect(JSON.parse(String(call.init.body))).toEqual({ round_number: 7 });
    expect((call.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
    expect(onChanged).toHaveBeenCalled();
  });

  it("sem lance ativo não há botão de cancelar; a carta destaca o clube de origem", () => {
    fakeApi({});
    renderBoard();
    expect(screen.queryByRole("button", { name: /Cancelar meu lance/ })).toBeNull();
    expect(screen.getAllByTitle("Clube de origem: Origem")).toHaveLength(5);
    expect(screen.getAllByTestId("player-silhouette")).toHaveLength(5); // sem foto: silhueta genérica
  });

  it("mostra o elenco agrupado GOL-LD-ZAG-LE-VOL-ME-ATA e as vagas da formação", () => {
    fakeApi({});
    const k = (id: number, name: string, position: string) => ({ player_id: id, name, position, price: 1_000_000, source: "auction" });
    renderBoard({ ...STATE, squad: [k(1, "Ata", "STC"), k(2, "Lat Esq", "DL"), k(3, "Gol", "GK"), k(4, "Zag", "DC"), k(5, "Lat Dir", "DR")] as never }, vi.fn(), FORMATIONS[0]);
    const side = screen.getByRole("complementary", { name: "Seu elenco e resultados" });
    const names = [...side.querySelectorAll(".pos-group .chip > span:first-child")].map((e) => e.textContent);
    expect(names).toEqual(["Gol", "Lat Dir", "Zag", "Lat Esq", "Ata"]);
    const vac = within(side).getByLabelText("Vagas da formação 4-2-2-2");
    expect(vac).toHaveTextContent("ZAG 1/2");
    expect(vac).toHaveTextContent("GOL 1/1");
  });

  it("bloqueia lances com elenco completo", () => {
    fakeApi({});
    renderBoard({ ...STATE, open_slots: 0 });
    for (const b of screen.getAllByRole("button", { pressed: false })) expect(b).toBeDisabled();
    expect(screen.getByText("Seu elenco está completo.")).toBeInTheDocument();
  });
});

describe("AuctionPage", () => {
  it("explica que o leilão aguarda as fórmulas aprovadas", async () => {
    const user = userEvent.setup();
    localStorage.setItem("squadforce.sessionId", SESSION.id);
    fakeApi({
      "GET /api/health": () => json(200, { status: "ok", service: "g", version: "0", time: "2026-11-18T12:00:00Z",
        database: { status: "ok", schema_version: 2, clubs: 40, players: 1583 }, active_session: true, services: {} }),
      [`GET /api/sessions/${SESSION.id}`]: () => json(200, SESSION),
      "GET /api/catalog/clubs": () => json(200, { items: CLUBS, total: 3, limit: 200, offset: 0 }),
      "GET /api/formations": () => json(200, FORMATIONS),
      [`POST /api/sessions/${SESSION.id}/auction/start`]: () =>
        apiError(409, "AUCTION_MODEL_NOT_CONFIGURED", "O leilão está desligado neste servidor."),
    });
    window.location.hash = "#/auction";
    const { App } = await import("../../app/App");
    render(<App />);
    await user.click(await screen.findByRole("button", { name: /Começar leilão/ }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Começar" }));
    expect(await screen.findByText("Leilão desligado neste servidor")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /Começar leilão/ })).toBeEnabled());
  });
});
