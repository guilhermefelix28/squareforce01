import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CLUBS, SESSION, apiError, fakeApi, json } from "../../test/fakeApi";
import type { Club, TradingSquad, TradingState } from "../../types/api";
import { TradingBoard } from "./TradingBoard";

const pl = (id: number, name: string, position: "GK" | "MC" | "STC", club: number) => ({ unique_id: id, name, age: 25, position, club_uid: club });
const SQUADS: TradingSquad[] = [
  { club_uid: 322, is_user: true, budget: 40_000_000, completed_trades: 0, players: [pl(1, "Meu Goleiro", "GK", 322), pl(2, "Meu Meia", "MC", 322)] },
  { club_uid: 329, is_user: false, budget: 30_000_000, completed_trades: 1, players: [pl(10, "Craque Alviverde", "STC", 329), pl(11, "Goleiro Verde", "GK", 329)] },
  { club_uid: 102496, is_user: false, budget: 10_000_000, completed_trades: 3, players: [pl(20, "Meia Goiano", "MC", 102496)] },
];
const proposal = (over = {}) => ({
  id: "T-0007", direction: "incoming" as const, proponent_club_uid: 329, recipient_club_uid: 322,
  offered: pl(11, "Goleiro Verde", "GK", 329), requested: pl(1, "Meu Goleiro", "GK", 322), money: 1_500_000,
  status: "pending" as const, reason: null, remaining_ms: 6_000, ...over,
});
const STATE: TradingState = {
  session_id: SESSION.id, phase: "running", remaining_ms: 150_000, duration_ms: 180_000, user_club_uid: 322,
  budget: 40_000_000, completed_trades: 0, max_trades: 3, outgoing: null, incoming: [proposal()],
  recent_decisions: [], history: [{ proposal_id: "T-0001", proponent_club_uid: 329, recipient_club_uid: 102496,
    offered: pl(30, "Fulano", "MC", 102496), requested: pl(31, "Beltrano", "MC", 329), money: 0, elapsed_ms: 12_000 }],
  clubs: SQUADS.map(({ players: _p, ...c }) => c),
};

function renderBoard(state = STATE) {
  render(<TradingBoard sessionId={SESSION.id} state={state} squads={SQUADS} clubs={CLUBS as Club[]} remainingMs={state.remaining_ms}
    left={(ms) => ms} onChanged={() => undefined} />);
}

describe("TradingBoard", () => {
  it("mostra relógio, saldo, limite, propostas recebidas e histórico", () => {
    fakeApi({});
    renderBoard();
    expect(screen.getByText("2:30")).toBeInTheDocument();
    expect(screen.getByText("0/3")).toBeInTheDocument();
    const incoming = screen.getByRole("region", { name: "Propostas recebidas" });
    expect(within(incoming).getByText("0:06")).toBeInTheDocument();
    expect(within(incoming).getByText(/R\$\s1\.500\.000 para você/)).toBeInTheDocument();
    expect(screen.getByText(/Fulano ⇄ Beltrano/)).toBeInTheDocument();
  });

  it("filtra jogadores adversários por nome, clube e posição", async () => {
    const user = userEvent.setup();
    fakeApi({});
    renderBoard();
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(4); // cabeçalho + 3 adversários (sem o próprio elenco)
    await user.type(screen.getByLabelText("Buscar jogador"), "craque");
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    await user.clear(screen.getByLabelText("Buscar jogador"));
    await user.selectOptions(screen.getByLabelText("Posição"), "GK");
    expect(within(table).getByText("Goleiro Verde")).toBeInTheDocument();
    expect(within(table).queryByText("Craque Alviverde")).toBeNull();
    await user.selectOptions(screen.getByLabelText("Posição"), "");
    await user.selectOptions(screen.getByLabelText("Clube"), "102496");
    expect(within(table).getByRole("button", { name: "Quero Meia Goiano" })).toBeDisabled(); // clube já fez 3 trocas
  });

  it("monta, confirma e envia a proposta com chave de idempotência", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      [`POST /api/sessions/${SESSION.id}/trading/proposals`]: () => json(200, proposal({ direction: "outgoing", id: "T-0009" })),
    });
    renderBoard({ ...STATE, incoming: [] });
    await user.click(screen.getByRole("button", { name: "Quero Craque Alviverde" }));
    await user.selectOptions(screen.getByLabelText(/Jogador oferecido/), "2");
    await user.type(screen.getByLabelText(/Dinheiro adicional/), "2,5 mi");
    await user.click(screen.getByRole("button", { name: "Revisar e enviar proposta" }));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent(/Você entrega Meu Meia e recebe Craque Alviverde .*pagando R\$\s2\.500\.000/);
    expect(calls.some((c) => c.method === "POST")).toBe(false); // nada enviado antes de confirmar
    await user.click(within(dialog).getByRole("button", { name: "Enviar proposta" }));
    expect(await screen.findByText(/Proposta enviada/)).toBeInTheDocument();
    const call = calls.find((c) => c.method === "POST")!;
    expect(JSON.parse(String(call.init.body))).toEqual({ recipient_club_uid: 329, offered_player_id: 2, requested_player_id: 10, money: 2_500_000 });
    expect((call.init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^sf-/);
  });

  it("impede dinheiro acima do saldo", async () => {
    const user = userEvent.setup();
    fakeApi({});
    renderBoard({ ...STATE, incoming: [] });
    await user.click(screen.getByRole("button", { name: "Quero Craque Alviverde" }));
    await user.selectOptions(screen.getByLabelText(/Jogador oferecido/), "1");
    await user.type(screen.getByLabelText(/Dinheiro adicional/), "41 mi");
    expect(screen.getByText(/acima do seu saldo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revisar e enviar proposta" })).toBeDisabled();
  });

  it("aceita proposta recebida e explica decisões já tomadas", async () => {
    const user = userEvent.setup();
    let n = 0;
    fakeApi({
      [`POST /api/sessions/${SESSION.id}/trading/proposals/T-0007/accept`]: () =>
        n++ === 0 ? json(200, proposal({ status: "accepted" })) : apiError(409, "PROPOSAL_NOT_PENDING", "x"),
    });
    renderBoard();
    await user.click(screen.getByRole("button", { name: "Aceitar" }));
    expect(await screen.findByText(/Proposta aceita\. Troca concluída\./)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aceitar" }));
    expect(await screen.findByText("Esta proposta já foi decidida.")).toBeInTheDocument();
  });

  it("permite cancelar a própria proposta pendente e bloqueia nova proposta", async () => {
    const user = userEvent.setup();
    const { calls } = fakeApi({
      [`POST /api/sessions/${SESSION.id}/trading/proposals/T-0008/cancel`]: () => json(200, proposal({ id: "T-0008", status: "cancelled", direction: "outgoing" })),
    });
    renderBoard({ ...STATE, incoming: [], outgoing: proposal({ id: "T-0008", direction: "outgoing", proponent_club_uid: 322, recipient_club_uid: 329 }) });
    expect(screen.getByRole("button", { name: "Aguardando resposta da proposta atual" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Cancelar proposta" }));
    expect(await screen.findByText("Proposta cancelada.")).toBeInTheDocument();
    expect(calls.at(-1)!.path).toBe(`/api/sessions/${SESSION.id}/trading/proposals/T-0008/cancel`);
  });

  it("informa o limite de 3 negociações", () => {
    fakeApi({});
    renderBoard({ ...STATE, completed_trades: 3 });
    expect(screen.getByText("Você já concluiu as 3 negociações permitidas.")).toBeInTheDocument();
  });
});
