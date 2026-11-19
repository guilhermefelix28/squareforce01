import { describe, expect, it } from "vitest";
import { FORMATIONS } from "../../test/fakeApi";
import { BAND_Y, detectFormation, moveToRow, slotLayout, slotRows, widestRow, type FormationDef } from "./layout";

/** As 20 formações oficiais (DR-11), na mesma ordem de vagas do servidor. */
export const OFFICIAL: FormationDef[] = FORMATIONS;
const byId = (id: string) => OFFICIAL.find((f) => f.id === id)!;

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
  it("lateral esquerdo à esquerda, direito à direita, goleiro embaixo; VOL e ME em faixas diferentes", () => {
    const f = OFFICIAL[0];
    const pts = slotLayout(f);
    expect(pts[4].x).toBeLessThan(pts[1].x); // DL < DR
    expect(pts[0].y).toBeGreaterThan(pts[1].y);
    expect(pts[5].y).toBe(BAND_Y[2]); // VOL
    expect(pts[7].y).toBe(BAND_Y[3]); // ME
    expect(pts[5].y).toBeGreaterThan(pts[7].y); // volante atrás do meia
    expect(pts[9].y).toBeLessThan(pts[7].y);
    expect(slotRows(byId("4-2-2-2"))[1]).toEqual([4, 2, 3, 1]); // LE ... LD na faixa de defesa
    expect(slotRows(byId("3-1-3-3"))[1]).toEqual([1, 2, 3]); // linha de 3: três zagueiros
    expect(slotRows(byId("5-4-1"))[2]).toEqual([]); // 5-4-1: faixa de volantes vazia (mas existe como destino)
  });
});

describe("reconhece a formação ao mudar o desenho", () => {
  it("contagens por faixa [DEF, VOL, ME, ATA]", () => {
    expect(detectFormation([4, 1, 2, 3], OFFICIAL)?.id).toBe("4-1-2-3");
    expect(detectFormation([4, 2, 2, 2], OFFICIAL)?.id).toBe("4-2-2-2");
    expect(detectFormation([4, 2, 3, 1], OFFICIAL)?.id).toBe("4-2-3-1");
    expect(detectFormation([5, 1, 2, 2], OFFICIAL)?.id).toBe("5-1-2-2");
    expect(detectFormation([5, 0, 3, 2], OFFICIAL)?.id).toBe("5-3-2");
    expect(detectFormation([3, 2, 3, 2], OFFICIAL)?.id).toBe("3-2-3-2");
    // toda formação oficial é reconhecida pelas próprias faixas
    for (const f of OFFICIAL) expect(detectFormation(slotRows(f).slice(1).map((r) => r.length), OFFICIAL)?.id).toBe(f.id);
    expect(detectFormation([2, 4, 4, 0], OFFICIAL)).toBeNull();
  });
  it("volante levado à faixa de meias: 4-2-2-2 vira 4-1-3-2 com os mesmos atletas", () => {
    const starters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const r = moveToRow(OFFICIAL[0], starters, 5, 3, 0, OFFICIAL)!;
    expect(r.formation.id).toBe("4-1-3-2");
    expect([...r.starters].sort((a, b) => a! - b!)).toEqual(starters);
    expect(r.starters[0]).toBe(1); // goleiro intacto
    const rows = slotRows(r.formation).map((s) => s.map((i) => r.starters[i]));
    expect(rows[3]).toContain(6);
    expect(rows[2]).toEqual([7]);
  });
  it("atacante recuado: 4-1-2-3 vira 4-2-2-2 (faixa VOL) ou 4-1-3-2 (faixa ME); desenho não oficial ou goleiro => null", () => {
    const starters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    expect(moveToRow(OFFICIAL[1], starters, 9, 2, 0, OFFICIAL)?.formation.id).toBe("4-2-2-2");
    expect(moveToRow(OFFICIAL[1], starters, 9, 3, 0, OFFICIAL)?.formation.id).toBe("4-1-3-2");
    expect(moveToRow(byId("4-1-4-1"), starters, 5, 1, 0, OFFICIAL)?.formation.id).toBe("5-4-1"); // volante na defesa
    expect(moveToRow(byId("4-1-4-1"), starters, 10, 1, 0, OFFICIAL)).toBeNull(); // 5-1-4-0: sem atacante
    expect(moveToRow(OFFICIAL[0], starters, 0, 1, 0, OFFICIAL)).toBeNull();
  });
  it("faixa vazia também recebe: meia do 5-4-1 levado à faixa VOL vira 5-1-3-1", () => {
    const starters = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
    const r = moveToRow(byId("5-4-1"), starters, 7, 2, 0, OFFICIAL)!;
    expect(r.formation.id).toBe("5-1-3-1");
    expect(r.starters[r.formation.positions.indexOf("DM")]).toBe(8);
  });
});
