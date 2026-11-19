import type { FitLevel, Posture, Speed } from "../../types/api";

export const POSTURES: { id: Posture; label: string }[] = [
  { id: "retranca", label: "Retranca" },
  { id: "defensiva", label: "Defensiva" },
  { id: "equilibrada", label: "Equilibrada" },
  { id: "ofensiva", label: "Ofensiva" },
  { id: "ataque_total", label: "Ataque Total" },
];
export const postureLabel = (p: string) => POSTURES.find((x) => x.id === p)?.label ?? p;

export const SPEEDS: { id: Speed; label: string }[] = [
  { id: "15s", label: "15 s" },
  { id: "30s", label: "30 s" },
  { id: "60s", label: "60 s" },
  { id: "instant", label: "Instantâneo" },
];

export const FIT_LABEL: Record<FitLevel, string> = {
  natural: "Posição natural",
  boa: "Boa adequação",
  regular: "Adequação regular",
  improvisada: "Improvisado",
};

const EVENT_LABEL: Record<string, string> = {
  goal: "Gol",
  yellow_card: "Cartão amarelo",
  red_card: "Cartão vermelho",
  injury: "Lesão",
  substitution: "Substituição",
  penalty_awarded: "Pênalti!",
  save: "Defesa",
  shootout_kick: "Cobrança de pênalti",
  shootout_end: "Fim da disputa de pênaltis",
  abandoned: "Partida encerrada",
  posture_change: "Mudança de postura",
  half_time: "Intervalo",
  full_time: "Fim de jogo",
};
export const eventLabel = (t: string) => EVENT_LABEL[t] ?? t;
export const EVENT_ICON: Record<string, string> = {
  goal: "⚽",
  yellow_card: "🟨",
  red_card: "🟥",
  injury: "✚",
  substitution: "⇄",
  posture_change: "⚙",
  save: "🧤",
  penalty_awarded: "◎",
  shootout_kick: "◎",
};

export const STAT_LABELS: { key: string; label: string; pct?: boolean; dec?: boolean }[] = [
  { key: "possession_pct", label: "Posse de bola", pct: true },
  { key: "shots", label: "Finalizações" },
  { key: "shots_on_target", label: "No alvo" },
  { key: "xg", label: "xG", dec: true },
  { key: "big_chances", label: "Grandes chances" },
  { key: "corners", label: "Escanteios" },
  { key: "fouls", label: "Faltas" },
  { key: "yellow_cards", label: "Amarelos" },
  { key: "red_cards", label: "Vermelhos" },
  { key: "saves_made", label: "Defesas" },
];

export function formatStat(v: unknown, s: { pct?: boolean; dec?: boolean }): string {
  const n = Number(v ?? 0);
  if (s.pct) return `${n.toFixed(0)}%`;
  if (s.dec) return n.toFixed(2);
  return String(Math.round(n));
}

/** Descrição curta de um evento para feeds (sem inventar dados: só o que o evento traz). */
export function describeEvent(e: { type: string; player_name?: string | null; other_name?: string | null; data?: Record<string, unknown> }): string {
  const who = e.player_name ?? "";
  switch (e.type) {
    case "goal":
      return `${who}${e.other_name ? ` (assist. ${e.other_name})` : ""}`;
    case "substitution":
      return `Entra ${e.player_name ?? "?"}, sai ${e.other_name ?? "?"}`;
    case "injury":
      return `${who} lesionado`;
    case "penalty_awarded":
      // o motor registra quem sofreu (player) e quem cometeu (other); hoje não há pênalti por toque de mão (DR-06)
      return e.other_name ? `Falta de ${e.other_name} em ${who}` : `${who} sofre a falta`;
    case "posture_change":
      return `Nova postura: ${postureLabel(String(e.data?.posture ?? ""))}`;
    case "shootout_kick":
      return `${who}: ${e.data?.scored ? "converteu" : "perdeu"}`;
    default:
      return who;
  }
}
