/**
 * Desenho tático no campo por FAIXAS DE FUNÇÃO (DR-08): GOL, DEF (LD/ZAG/LE), VOL, ME e ATA. Volante e meia têm
 * faixas próprias, então o campo mostra a diferença entre eles e o usuário pode arrastar um titular de uma faixa
 * para outra. Dentro de cada faixa as vagas ficam igualmente espaçadas (LE à esquerda, LD à direita), então as
 * cartas nunca se sobrepõem (largura <= 100 / maior faixa). Faixas vazias continuam existindo como destino.
 */
import type { Position } from "../../types/api";

export interface FormationDef {
  id: string;
  positions: string[];
}

export const BAND_LABELS = ["GOL", "DEF", "VOL", "ME", "ATA"] as const;
/** Altura (%) de cada faixa: goleiro embaixo, ataque em cima. */
export const BAND_Y = [92.5, 74, 53.5, 33, 13];
/** Posição atribuída a um atleta que entra numa faixa (DEF depende do lado; ver `bandPositions`). */
const BAND_OF: Record<string, number> = { GK: 0, DR: 1, DC: 1, DL: 1, DM: 2, MC: 3, STC: 4 };

export const bandOf = (p: string): number => BAND_OF[p] ?? 3;
export const rowsOf = (id: string): number[] => id.split("-").map((n) => Number(n));

/** Índices das vagas (na ordem do servidor) por faixa: [goleiro], [defesa], [volantes], [meias], [ataque]. */
export function slotRows(f: FormationDef): number[][] {
  const rows: number[][] = [[], [], [], [], []];
  f.positions.forEach((p, i) => rows[bandOf(p)].push(i));
  const side = (p: string) => (p === "DL" ? 0 : p === "DR" ? 2 : 1);
  return rows.map((r) => [...r].sort((a, b) => side(f.positions[a]) - side(f.positions[b]) || a - b));
}

/** Coordenadas (%) de cada vaga. */
export function slotLayout(f: FormationDef): { x: number; y: number; row: number }[] {
  const out: { x: number; y: number; row: number }[] = new Array(f.positions.length);
  slotRows(f).forEach((idx, row) => {
    idx.forEach((slot, k) => {
      out[slot] = { x: ((k + 0.5) / idx.length) * 100, y: BAND_Y[row], row };
    });
  });
  return out;
}

/** Maior número de vagas numa faixa (define a largura máxima de carta sem sobreposição). */
export const widestRow = (f: FormationDef): number => Math.max(...slotRows(f).map((r) => r.length));

/** Quantidade de vagas por faixa de linha (DEF, VOL, ME, ATA). */
export const bandCounts = (f: FormationDef): number[] => slotRows(f).slice(1).map((r) => r.length);

/**
 * Formação oficial com estas contagens por faixa [DEF, VOL, ME, ATA], ou null. Quando duas oficiais têm a mesma
 * composição (ex.: 3-5-2 e 5-3-2), prefere a de `prefer`, depois a cujo nome descreve as faixas.
 */
export function detectFormation(counts: number[], formations: FormationDef[], prefer?: string): FormationDef | null {
  const same = formations.filter((f) => bandCounts(f).join() === counts.join());
  if (same.length === 0) return null;
  const preferred = same.find((f) => f.id === prefer);
  if (preferred) return preferred;
  const [d, v, m, a] = counts;
  const names = [[d, v, m, a], [d, v + m, a]].map((r) => r.filter((n) => n > 0).join("-"));
  return same.find((f) => names.includes(f.id)) ?? same[0];
}

/**
 * Move o titular da vaga `from` para a faixa `toRow` (inserido em `at` dentro da faixa). Se o novo desenho for uma
 * formação oficial, devolve a nova formação e os titulares reordenados nas vagas dela; senão, null.
 */
export function moveToRow(
  f: FormationDef,
  starters: (number | null)[],
  from: number,
  toRow: number,
  at: number,
  formations: FormationDef[],
): { formation: FormationDef; starters: (number | null)[] } | null {
  const slots = slotRows(f);
  const rows = slots.map((r) => r.map((slot) => starters[slot]));
  const fromRow = slots.findIndex((r) => r.includes(from));
  if (fromRow < 0 || fromRow === toRow || toRow <= 0 || toRow >= slots.length || fromRow === 0) return null; // goleiro fica no gol
  const [player] = rows[fromRow].splice(slots[fromRow].indexOf(from), 1);
  rows[toRow].splice(Math.max(0, Math.min(at, rows[toRow].length)), 0, player);
  const target = detectFormation(rows.slice(1).map((r) => r.length), formations);
  if (!target) return null;
  const next: (number | null)[] = new Array(target.positions.length).fill(null);
  slotRows(target).forEach((s, r) => s.forEach((slot, k) => (next[slot] = rows[r][k] ?? null)));
  return { formation: target, starters: next };
}

export type { Position };
