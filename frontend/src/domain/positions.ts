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

export const POSITION_ORDER: Position[] = ["GK", "DR", "DL", "DC", "DM", "MC", "STC"];

export const displayPosition = (p: Position): string => POSITION_DISPLAY[p] ?? p;
