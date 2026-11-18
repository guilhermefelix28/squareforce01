import type { CompetitionOptions, SessionCreate } from "../../types/api";

/** Validação no cliente (espelha o backend, que continua sendo a autoridade). */
export function validateSessionConfig(cfg: SessionCreate, opts: CompetitionOptions): string | null {
  if (!Number.isInteger(cfg.num_clubs)) return "Informe uma quantidade inteira de clubes.";
  if (cfg.format === "league") {
    if (cfg.num_clubs < opts.league.min_clubs || cfg.num_clubs > opts.league.max_clubs)
      return `A Liga aceita de ${opts.league.min_clubs} a ${opts.league.max_clubs} clubes.`;
    if (!cfg.league_rounds) return "Escolha turno único ou turno e returno.";
  } else {
    if (!opts.cup.allowed_sizes.includes(cfg.num_clubs))
      return `A Copa aceita ${opts.cup.allowed_sizes.join(", ")} participantes.`;
  }
  if (cfg.num_clubs > opts.eligible_clubs)
    return `Há apenas ${opts.eligible_clubs} clubes elegíveis (com Série A/B).`;
  if (!cfg.user_club_uid) return "Escolha o seu clube.";
  return null;
}
