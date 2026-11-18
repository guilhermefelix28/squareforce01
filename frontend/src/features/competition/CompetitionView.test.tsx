import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { CLUBS, CUP_COMPETITION, LEAGUE_COMPETITION, fakeApi } from "../../test/fakeApi";
import type { Club, CompetitionOut } from "../../types/api";
import { CompetitionView } from "./CompetitionView";

const clubs = [...CLUBS, { club_uid: 316, name: "Botafogo", short_name: "Botafogo", nation_id: 189, player_count: 40, division: "A" }] as Club[];

describe("CompetitionView — Liga", () => {
  it("mostra resumo, rodada atual e folga", async () => {
    fakeApi({});
    const user = userEvent.setup();
    render(<CompetitionView competition={LEAGUE_COMPETITION as CompetitionOut} clubs={clubs} />);
    expect(screen.getByText("Calendário da Liga")).toBeInTheDocument();
    expect(screen.getByText("Turno único")).toBeInTheDocument();
    const round1 = screen.getByRole("list", { name: "Rodada 1" });
    expect(within(round1).getByText("Flamengo")).toBeInTheDocument();
    expect(within(round1).getByText("Palmeiras")).toBeInTheDocument();
    expect(screen.getByText(/Folga:/)).toHaveTextContent("Goiás");
    expect(screen.getByText(/não conta como partida/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Próxima rodada" }));
    expect(screen.getByText(/Folga:/)).toHaveTextContent("Flamengo");
  });

  it("filtra os jogos do clube do usuário", async () => {
    fakeApi({});
    const user = userEvent.setup();
    render(<CompetitionView competition={LEAGUE_COMPETITION as CompetitionOut} clubs={clubs} />);
    await user.click(screen.getByLabelText("Somente jogos do meu clube"));
    const items = screen.getAllByText(/^R\d$/);
    expect(items.map((e) => e.textContent)).toEqual(["R1", "R3"]);
  });
});

describe("CompetitionView — Copa", () => {
  it("mostra fases, regras e vagas aguardando vencedores", () => {
    fakeApi({});
    render(<CompetitionView competition={CUP_COMPETITION as CompetitionOut} clubs={clubs} />);
    expect(screen.getByText("Chaveamento da Copa")).toBeInTheDocument();
    expect(screen.getByText(/sem prorrogação/)).toBeInTheDocument();
    expect(screen.getByText(/pênaltis/)).toBeInTheDocument();
    const final = screen.getByRole("listitem", { name: "Final" });
    expect(within(final).getByText("Vencedor de 1ª fase, jogo 1")).toBeInTheDocument();
    expect(within(final).getByText("Vencedor de 1ª fase, jogo 2")).toBeInTheDocument();
    const semi = screen.getByRole("listitem", { name: "Semifinal" });
    expect(within(semi).getByText("você")).toBeInTheDocument();
  });
});
