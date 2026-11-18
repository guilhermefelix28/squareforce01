import { describe, expect, it } from "vitest";
import { POSITION_DISPLAY, POSITION_ORDER, displayPosition } from "./positions";

describe("posições (GDD seção 3)", () => {
  it("usa exatamente a tabela oficial", () => {
    expect(POSITION_DISPLAY).toEqual({ GK: "GOL", DR: "LD", DL: "LE", DC: "ZAG", DM: "VOL", MC: "ME", STC: "ATA" });
  });
  it("ordena do goleiro ao ataque", () => {
    expect(POSITION_ORDER.map(displayPosition)).toEqual(["GOL", "LD", "LE", "ZAG", "VOL", "ME", "ATA"]);
  });
});
