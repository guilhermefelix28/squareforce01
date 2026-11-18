import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { apiError, fakeApi, json } from "../../test/fakeApi";
import { ImportCard } from "./ImportCard";

const REJECTED = {
  base: "players", status: "rejected", file_name: "jogadores.xlsx", sheet: "Jogadores",
  rows_read: 2, rows_imported: 0, rows_skipped: 0, previous_count: 0,
  critical_errors: [{ row: 3, column: "unique_id", code: "DUPLICATE_ID", message: "unique_id 5 repetido" }],
  critical_error_count: 1, warnings: [], warning_count: 0,
};

const file = () => new File(["PK\u0003\u0004"], "jogadores.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

describe("ImportCard", () => {
  it("envia o arquivo selecionado e mostra o resultado", async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();
    const { calls } = fakeApi({
      "POST /api/imports/players": () =>
        json(200, { ...REJECTED, status: "imported", rows_imported: 1574, rows_skipped: 11, critical_errors: [], critical_error_count: 0, warning_count: 11 }),
    });
    render(<ImportCard base="players" blocked={false} onImported={onImported} />);
    await user.upload(screen.getByLabelText(/Selecionar arquivo/), file());
    await user.click(screen.getByRole("button", { name: "Importar" }));
    expect(await screen.findByText("Importação concluída")).toBeInTheDocument();
    expect(screen.getByText("1574")).toBeInTheDocument();
    expect(onImported).toHaveBeenCalledOnce();
    expect(calls[0].init.body).toBeInstanceOf(FormData);
  });

  it("mostra erros críticos e informa que a base foi preservada", async () => {
    const user = userEvent.setup();
    fakeApi({
      "POST /api/imports/players": () =>
        apiError(422, "IMPORT_VALIDATION_FAILED", "Importação rejeitada: 1 erro(s) crítico(s). A base anterior foi preservada.", false, { report: REJECTED }),
    });
    render(<ImportCard base="players" blocked={false} onImported={vi.fn()} />);
    await user.upload(screen.getByLabelText(/Selecionar arquivo/), file());
    await user.click(screen.getByRole("button", { name: "Importar" }));
    expect(await screen.findByText("Importação rejeitada")).toBeInTheDocument();
    expect(screen.getByText(/base anterior foi preservada/)).toBeInTheDocument();
    expect(screen.getByText(/unique_id 5 repetido/)).toBeInTheDocument();
  });

  it("desabilita a importação durante competição ativa", () => {
    fakeApi({});
    render(<ImportCard base="clubs" blocked onImported={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Importar" })).toBeDisabled();
    expect(screen.getByText("Importação bloqueada")).toBeInTheDocument();
  });
});
