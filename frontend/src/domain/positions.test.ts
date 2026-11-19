import { describe, expect, it } from "vitest";
import { POSITION_DISPLAY, POSITION_ORDER, byPosition, displayPosition, sector } from "./positions";

describe("posições (GDD seção 3; ordem DR-05)", () => {
  it("usa exatamente a tabela oficial", () => {
    expect(POSITION_DISPLAY).toEqual({ GK: "GOL", DR: "LD", DL: "LE", DC: "ZAG", DM: "VOL", MC: "ME", STC: "ATA" });
  });
  it("ordena GOL-LD-ZAG-LE-VOL-ME-ATA", () => {
    expect(POSITION_ORDER.map(displayPosition)).toEqual(["GOL", "LD", "ZAG", "LE", "VOL", "ME", "ATA"]);
  });
  it("agrupa listas pela ordem oficial e mantém a ordem dentro da posição", () => {
    const xs = [{ n: "a", p: "STC" }, { n: "b", p: "DL" }, { n: "c", p: "GK" }, { n: "d", p: "DC" }, { n: "e", p: "DC" }, { n: "f", p: "DR" }];
    expect(byPosition(xs, (x) => x.p).map((x) => x.n)).toEqual(["c", "f", "d", "e", "b", "a"]);
  });
  it("classifica setores", () => {
    expect(["GK", "DR", "DC", "DM", "MC", "STC"].map(sector)).toEqual(["gol", "def", "def", "mei", "mei", "ata"]);
  });
});
