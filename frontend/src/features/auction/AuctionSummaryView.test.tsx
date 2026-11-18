import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CLUBS, fakeApi } from "../../test/fakeApi";
import type { AuctionSummary, Club } from "../../types/api";
import { AuctionSummaryView } from "./AuctionSummaryView";

const contracts = (n: number, base: number) =>
  Array.from({ length: n }, (_, i) => ({
    player_id: base + i, name: `Jogador ${base + i}`, position: (i === 0 ? "GK" : "MC") as "GK" | "MC", age: 25,
    price: i < 3 ? 2_000_000 : 400_000, source: (i < 3 ? "auction" : i < 4 ? "improvement" : "basic") as "auction" | "improvement" | "basic",
    round: i < 3 ? i + 1 : null,
  }));

const SUMMARY: AuctionSummary = {
  session_id: "s",
  finish_reason: "time_up",
  rounds_completed: 60,
  squads: [
    { club_uid: 329, is_user: false, budget: 100_000_000, spent: 20_000_000, auction_signings: 10, improvement_limit: 2, contracts: contracts(18, 100) },
    { club_uid: 322, is_user: true, budget: 110_000_000, spent: 10_000_000, auction_signings: 3, improvement_limit: 0, contracts: contracts(18, 200) },
  ],
};

describe("AuctionSummaryView", () => {
  it("mostra os 18 de cada clube, saldos e o clube do usuário primeiro", () => {
    fakeApi({});
    render(<AuctionSummaryView summary={SUMMARY} clubs={CLUBS as Club[]} />);
    expect(screen.getByText(/O relógio global chegou ao fim\. 60 rodadas/)).toBeInTheDocument();
    const squads = document.querySelectorAll("details.squad");
    expect(squads).toHaveLength(2);
    expect(squads[0]).toHaveTextContent("Flamengo");
    expect(squads[0]).toHaveAttribute("open");
    expect(within(squads[0] as HTMLElement).getByText(/18\/18 · gasto R\$ 10 mi · saldo R\$ 110 mi/)).toBeInTheDocument();
    expect(within(squads[0] as HTMLElement).getAllByRole("row")).toHaveLength(19);
    expect(within(squads[0] as HTMLElement).getByText("melhoria")).toBeInTheDocument();
  });
});
