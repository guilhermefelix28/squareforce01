import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("abre sobre a página inteira, fora de barras fixas que o conteriam (regressão: diálogo cortado no rodapé)", () => {
    render(
      <div className="action-bar" data-testid="bar">
        <ConfirmDialog open title="Encerrar esta copa?" message="m" confirmLabel="Encerrar" onConfirm={() => {}} onCancel={() => {}} />
      </div>,
    );
    const dialog = screen.getByRole("alertdialog", { name: "Encerrar esta copa?" });
    expect(screen.getByTestId("bar").contains(dialog)).toBe(false);
    expect(dialog.closest(".dialog-backdrop")?.parentElement).toBe(document.body);
  });
});
