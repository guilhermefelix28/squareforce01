/** Pós-partida (GDD §21): placar, acontecimentos, estatísticas, avaliações, Craque e tabela atualizada. */
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { advanceRound, getMatchReport } from "../api/endpoints";
import { Notice } from "../components/Notice";
import { MatchReportView, StandingsTable } from "../features/season/SeasonParts";
import { useCommand } from "../features/season/useCommand";
import { useClubNames, useSeason } from "../features/season/useSeason";
import type { MatchReport } from "../types/api";

export function PostMatchPage({ matchId, navigate }: { matchId: string; navigate: (h: string) => void }) {
  const { sid, state, setState } = useSeason();
  const names = useClubNames();
  const [report, setReport] = useState<MatchReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cmd = useCommand();

  useEffect(() => {
    if (!sid) return;
    setReport(null);
    getMatchReport(sid, matchId)
      .then(setReport)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Falha ao carregar a partida."));
  }, [sid, matchId]);

  if (!sid || !state) return <p className="muted" role="status">Carregando…</p>;
  const advance = () =>
    void cmd.run(async (k) => {
      const s = await advanceRound(sid, k);
      setState(s);
      navigate(s.phase === "finished" ? "#/encerramento" : "#/temporada/central");
    });
  const canAdvance = state.phase === "awaiting_advance" && state.fixtures.some((f) => f.match_id === matchId);

  return (
    <div className="stack">
      <div className="season-head">
        <h2>Pós-partida</h2>
        <button type="button" className="btn btn--ghost btn--small" onClick={() => navigate("#/temporada/resultados")}>← Resultados</button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!report && !error && <p className="muted" role="status">Carregando partida…</p>}
      {report && <MatchReportView report={report} names={names} user={state.user_club_uid} />}
      {canAdvance && (
        <section className="card">
          <h3>Rodada concluída</h3>
          {state.kind === "league" && <StandingsTable rows={state.standings} names={names} user={state.user_club_uid} compact />}
          {state.kind === "cup" && (
            <p className="muted">{state.user_eliminated ? "Seu clube foi eliminado; a Copa segue até a final." : "Chaveamento atualizado."}{" "}
              <a href="#/temporada/classificacao">Ver chaveamento</a></p>
          )}
          {cmd.error && <Notice kind="error">{cmd.error.message}</Notice>}
          <button type="button" className="btn btn--primary" onClick={advance} disabled={cmd.busy}>
            {state.round_number >= state.total_rounds ? "Encerrar competição" : "Próximo confronto"}
          </button>
        </section>
      )}
    </div>
  );
}
