/**
 * Desenho tático no campo a partir do NOME da formação oficial (ex.: "4-2-3-1" = linhas 4, 2, 3, 1 após o goleiro).
 * As vagas da formação (ordem oficial do servidor) são distribuídas pelas linhas nessa ordem. Dentro de cada linha,
 * o lateral esquerdo fica à esquerda e o direito à direita; as vagas ficam igualmente espaçadas na largura,
 * então nunca se sobrepõem (cartas com largura <= 100 / maior linha).
 */
import type { Position } from "../../types/api";

export interface FormationDef {
  id: string;
  positions: string[];
}

export const rowsOf = (id: string): number[] => id.split("-").map((n) => Number(n));

/** Índices das vagas (na ordem do servidor) agrupados por linha: [goleiro], [defesa], ..., [ataque]. */
export function slotRows(f: FormationDef): number[][] {
  const counts = rowsOf(f.id);
  const rows: number[][] = [[0]];
  let k = 1;
  for (const n of counts) {
    rows.push(Array.from({ length: n }, (_, i) => k + i));
    k += n;
  }
  const side = (p: string) => (p === "DL" ? 0 : p === "DR" ? 2 : 1);
  return rows.map((r) => [...r].sort((a, b) => side(f.positions[a]) - side(f.positions[b]) || a - b));
}

/** Coordenadas (%) de cada vaga: goleiro embaixo (y alto), ataque em cima. */
export function slotLayout(f: FormationDef): { x: number; y: number; row: number }[] {
  const rows = slotRows(f);
  const out: { x: number; y: number; row: number }[] = new Array(f.positions.length);
  const last = rows.length - 1;
  rows.forEach((idx, row) => {
    const y = row === 0 ? 92.5 : 74 - ((row - 1) * (74 - 13)) / Math.max(1, last - 1);
    idx.forEach((slot, k) => {
      out[slot] = { x: ((k + 0.5) / idx.length) * 100, y, row };
    });
  });
  return out;
}

/** Maior número de vagas numa linha (define a largura máxima de carta sem sobreposição). */
export const widestRow = (f: FormationDef): number => Math.max(...slotRows(f).map((r) => r.length));

/** Formação oficial com estas contagens por linha (após o goleiro), ou null se não for oficial. */
export function detectFormation(counts: number[], formations: FormationDef[]): FormationDef | null {
  const id = counts.join("-");
  return formations.find((f) => f.id === id) ?? null;
}

/**
 * Move o titular da vaga `from` para a linha `toRow` (inserido em `at` dentro da linha). Se o novo desenho for
 * uma formação oficial, devolve a nova formação e os titulares reordenados nas vagas dela; senão, null.
 */
export function moveToRow(
  f: FormationDef,
  starters: (number | null)[],
  from: number,
  toRow: number,
  at: number,
  formations: FormationDef[],
): { formation: FormationDef; starters: (number | null)[] } | null {
  const rows = slotRows(f).map((r) => r.map((slot) => starters[slot]));
  const fromRow = slotRows(f).findIndex((r) => r.includes(from));
  if (fromRow < 0 || fromRow === toRow || toRow <= 0 || fromRow === 0) return null; // goleiro fica no gol
  const pos = slotRows(f)[fromRow].indexOf(from);
  const [player] = rows[fromRow].splice(pos, 1);
  rows[toRow].splice(Math.max(0, Math.min(at, rows[toRow].length)), 0, player);
  const target = detectFormation(rows.slice(1).map((r) => r.length), formations);
  if (!target) return null;
  const next: (number | null)[] = new Array(target.positions.length).fill(null);
  slotRows(target).forEach((slots, r) => slots.forEach((slot, k) => (next[slot] = rows[r][k] ?? null)));
  return { formation: target, starters: next };
}

export type { Position };
