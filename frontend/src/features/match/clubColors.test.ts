import { describe, expect, it } from "vitest";
import { dominantColors, inkFor, kitColors, type Rgb } from "./clubColors";

/** Pixels RGBA: `n` pixels de cada cor (alpha 255), mais transparentes que devem ser ignorados. */
function pixels(parts: [Rgb, number][], transparent = 50): number[] {
  const out: number[] = [];
  for (const [c, n] of parts) for (let i = 0; i < n; i++) out.push(c[0], c[1], c[2], 255);
  for (let i = 0; i < transparent; i++) out.push(0, 0, 0, 0);
  return out;
}

describe("cores do clube a partir do escudo", () => {
  it("primária = tom mais frequente; secundária = tom bem diferente; transparência ignorada", () => {
    const c = dominantColors(pixels([[[200, 20, 30], 60], [[205, 25, 28], 10], [[250, 250, 250], 30], [[10, 10, 10], 5]], 400))!;
    expect(c.primary[0]).toBeGreaterThan(190);
    expect(c.primary[1]).toBeLessThan(40);
    expect(c.secondary).toEqual([250, 250, 250]);
    expect(dominantColors(pixels([], 10))).toBeNull();
  });

  it("mandante com a primária; visitante com a secundária só quando as primárias se confundem", () => {
    const red = { primary: [200, 20, 30] as Rgb, secondary: [255, 255, 255] as Rgb };
    const darkRed = { primary: [180, 30, 40] as Rgb, secondary: [20, 20, 20] as Rgb };
    const green = { primary: [0, 120, 60] as Rgb, secondary: [255, 255, 255] as Rgb };
    expect(kitColors(red, green)).toEqual([red.primary, green.primary]);
    expect(kitColors(red, darkRed)).toEqual([red.primary, darkRed.secondary]);
  });

  it("texto legível sobre a cor do uniforme", () => {
    expect(inkFor([250, 250, 250])).toBe("#0b0f0a");
    expect(inkFor([10, 30, 120])).toBe("#ffffff");
  });
});
