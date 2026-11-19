import { describe, expect, it } from "vitest";
import { detectFormation, moveToRow, slotLayout, slotRows, widestRow, type FormationDef } from "./layout";

/** As 11 formações oficiais (mesma ordem de vagas do servidor). */
export const OFFICIAL: FormationDef[] = [
  ["4-4-2", "GK DR DC DC DL MC MC MC MC STC STC"],
  ["4-3-3", "GK DR DC DC DL DM MC MC STC STC STC"],
  ["4-2-3-1", "GK DR DC DC DL DM DM MC MC MC STC"],
  ["3-5-2", "GK DC DC DC DR DL DM MC MC STC STC"],
  ["3-4-3", "GK DC DC DC DR DL DM MC STC STC STC"],
  ["5-3-2", "GK DR DC DC DC DL DM MC MC STC STC"],
  ["4-1-4-1", "GK DR DC DC DL DM MC MC MC MC STC"],
  ["4-5-1", "GK DR DC DC DL MC MC MC MC MC STC"],
  ["4-3-2-1", "GK DR DC DC DL DM MC DM MC MC STC"],
  ["4-3-1-2", "GK DR DC DC DL DM MC MC MC STC STC"],
  ["5-4-1", "GK DR DC DC DC DL DM MC MC MC STC"],
].map(([id, p]) => ({ id, positions: p.split(" ") }));

describe("desenho tático sem sobreposição", () => {
  it.each(OFFICIAL.map((f) => [f.id, f] as const))("%s: vagas distintas e espaçadas em 360 px", (_, f) => {
    const pts = slotLayout(f);
    expect(pts).toHaveLength(11);
    const pitchW = 360 - 32; // celular com margens
    const pitchH = (pitchW * 90) / 68;
    const cardW = pitchW / widestRow(f); // a carta nunca é mais larga que a fatia da linha
    for (let i = 0; i < 11; i++)
      for (let j = i + 1; j < 11; j++) {
        const dx = (Math.abs(pts[i].x - pts[j].x) / 100) * pitchW;
        const dy = (Math.abs(pts[i].y - pts[j].y) / 100) * pitchH;
        expect(dx >= cardW - 0.01 || dy >= 56).toBe(true); // 56 px = altura da carta compacta
      }
  });
  it("lateral esquerdo à esquerda, direito à direita, goleiro embaixo", () => {
    const f = OFFICIAL[0];
    const pts = slotLayout(f);
    expect(pts[4].x).toBeLessThan(pts[1].x); // DL < DR
    expect(pts[0].y).toBeGreaterThan(pts[1].y);
    expect(pts[9].y).toBeLessThan(pts[5].y);
    expect(slotRows(OFFICIAL[3])[2]).toEqual([5, 6, 7, 8, 4]); // 3-5-2: LE ... LD na linha de 5
  });
});

describe("reconhece a formação ao mudar o desenho", () => {
  it("contagens oficiais e não oficiais", () => {
    expect(detectFormation([4, 3, 3], OFFICIAL)?.id).toBe("4-3-3");
    expect(detectFormation([2, 4, 4], OFFICIAL)).toBeNull();
  });
  it("zagueiro arrastado para o meio: 4-4-2 vira 3-5-2 com os mesmos atletas", () => {
    const starters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const r = moveToRow(OFFICIAL[0], starters, 2, 2, 2, OFFICIAL)!;
    expect(r.formation.id).toBe("3-5-2");
    expect([...r.starters].sort((a, b) => a! - b!)).toEqual(starters);
    expect(r.starters[0]).toBe(1); // goleiro intacto
    const rows = slotRows(r.formation).map((s) => s.map((i) => r.starters[i]));
    expect(rows[2]).toContain(3);
  });
  it("atacante recuado: 4-3-3 vira 4-4-2; desenho não oficial ou goleiro movido => null", () => {
    const starters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    expect(moveToRow(OFFICIAL[1], starters, 9, 2, 0, OFFICIAL)?.formation.id).toBe("4-4-2");
    expect(moveToRow(OFFICIAL[0], starters, 9, 1, 0, OFFICIAL)?.formation.id).toBe("5-4-1");
    expect(moveToRow(OFFICIAL[6], starters, 5, 1, 0, OFFICIAL)).toBeNull(); // 4-1-4-1 sem volante: "5-0-4-1"
    expect(moveToRow(OFFICIAL[0], starters, 0, 1, 0, OFFICIAL)).toBeNull();
  });
});
