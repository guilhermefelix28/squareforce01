import type { Session } from "../types/api";

/** Tela principal da fase atual (botão "Continuar" e transições de fase). */
export function phaseHome(session: Session | null): string {
  if (session?.status !== "active") return "#/session";
  switch (session.phase) {
    case "setup":
      return session.user_formation ? "#/auction" : "#/tatica";
    case "auction":
      return "#/auction";
    case "squad_completion":
    case "trading":
      return "#/trading";
    case "competition":
      return "#/temporada/central";
    case "finished":
      return "#/encerramento";
    default:
      return "#/session";
  }
}
