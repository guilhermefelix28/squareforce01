import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { formatClock, formatMoneyShort, parseMoney } from "../../domain/money";
import { CLUBS, SESSION, apiError, fakeApi, json } from "../../test/fakeApi";
import type { AuctionState, Club } from "../../types/api";
import { AuctionBoard } from "./AuctionBoard";

const player = (id: number, name: string, min: number) => ({
  unique_id: id, name, age: 24, club_short_name: "Origem", position: "STC" as const, minimum_bid: min, has_photo: false,
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

function renderBoard(state = STATE, onChanged = vi.fn()) {
  render(
    <AuctionBoard sessionId={SESSION.id} state={state} clubs={CLUBS as Club[]} roundRemainingMs={8_000} globalRemainingMs={540_000} onChanged={onChanged} />,
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
    expect(screen.getByText(/Rodada 7 · ATA/)).toBeInTheDocument();
    expect(screen.getByText("0:08")).toBeInTheDocument();
    expect(screen.getByText("9:00")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { pressed: false })).toHaveLength(5);
    const panel = screen.getByRole("form", { name: "Fazer lance" });
    expect(within(panel).getByText("R$ 120 mi")).toBeInTheDocument();
    expect(within(panel).getByText("R$ 111,5 mi")).toBeInTheDocument();
    const results = screen.getByRole("complementary", { name: "Resultados" });
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
    await user.click(screen.getByRole("button", { name: "+500 mil" }));
    await user.click(screen.getByRole("button", { name: "+1 mi" }));
    expect(input).toHaveValue("4000000");
    await user.click(screen.getByRole("button", { name: "Lance mínimo" }));
    await user.click(screen.getByRole("button", { name: "+100 mil" }));
    await user.click(screen.getByRole("button", { name: "Confirmar lance" }));
    expect(await screen.findByText(/Lance de R\$\s2\.600\.000 em Atacante Dois confirmado/)).toBeInTheDocument();
    const call = calls.find((c) => c.method === "POST")!;
    expect(JSON.parse(String(call.init.body))).toEqual({ player_id: 2, amount: 2_600_000, round_number: 7 });
    expect((call.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
    expect(onChanged).toHaveBeenCalled();
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

  it("destaca a oferta ativa do usuário e sugere aumento no mesmo atleta", async () => {
    const user = userEvent.setup();
    fakeApi({});
    renderBoard({ ...STATE, active_bid: { round: 7, player_id: 3, amount: 900_000, seq: 4 } });
    expect(screen.getByText("seu lance: R$ 900 mil")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Três/ }));
    expect(screen.getByLabelText(/Valor para Três/)).toHaveValue("1000000");
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
      [`POST /api/sessions/${SESSION.id}/auction/start`]: () =>
        apiError(409, "AUCTION_MODEL_NOT_CONFIGURED", "O leilão está desligado neste servidor."),
    });
    window.location.hash = "#/auction";
    const { App } = await import("../../app/App");
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Iniciar leilão" }));
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Iniciar" }));
    expect(await screen.findByText("Leilão desligado neste servidor")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Iniciar leilão" })).toBeEnabled());
  });
});
