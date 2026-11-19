import type { Position } from "../types/api";

/** GDD v5.2 seção 3 — exibição na interface × código interno. */
export const POSITION_DISPLAY: Record<Position, string> = {
  GK: "GOL",
  DR: "LD",
  DL: "LE",
  DC: "ZAG",
  DM: "VOL",
  MC: "ME",
  STC: "ATA",
};

/** Ordem de exibição definida pelo responsável (DR-05): GOL · LD · ZAG · LE · VOL · ME · ATA. */
export const POSITION_ORDER: Position[] = ["GK", "DR", "DC", "DL", "DM", "MC", "STC"];

export const displayPosition = (p: Position | string): string => POSITION_DISPLAY[p as Position] ?? p;

export type Sector = "gol" | "def" | "mei" | "ata";
/** Setor do campo (cor do selo de posição). */
export function sector(p: Position | string): Sector {
  if (p === "GK") return "gol";
  if (p === "DR" || p === "DL" || p === "DC") return "def";
  if (p === "DM" || p === "MC") return "mei";
  return "ata";
}

/** Índice de ordenação de uma posição (desconhecidas vão para o fim). */
export const positionRank = (p: Position | string): number => {
  const i = POSITION_ORDER.indexOf(p as Position);
  return i < 0 ? POSITION_ORDER.length : i;
};

/** Ordena uma lista pela posição na ordem oficial de exibição (estável para o mesmo setor). */
export function byPosition<T>(items: readonly T[], pos: (x: T) => Position | string): T[] {
  return items
    .map((x, i) => [x, i] as const)
    .sort((a, b) => positionRank(pos(a[0])) - positionRank(pos(b[0])) || a[1] - b[1])
    .map(([x]) => x);
}
