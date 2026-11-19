/** Nova partida (assistente) ou detalhes da competição ativa (participantes, calendário, encerrar). */
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getCompetition, getCompetitionOptions, listClubs } from "../api/endpoints";
import { phaseHome } from "../app/phase";
import { useSession } from "../app/SessionContext";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { CompetitionView } from "../features/competition/CompetitionView";
import { SessionForm } from "../features/session/SessionForm";
import { SessionPanel } from "../features/session/SessionPanel";
import type { Club, CompetitionOptions, CompetitionOut } from "../types/api";

export function SessionPage({ onSessionChanged, navigate }: { onSessionChanged: () => void; navigate: (h: string) => void }) {
  const { session, setSession, lostMessage, live, restoring } = useSession();
  const [options, setOptions] = useState<CompetitionOptions | null>(null);
  const [clubs, setClubs] = useState<Club[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [competition, setCompetition] = useState<CompetitionOut | null>(null);

  const sessionId = session?.id;
  useEffect(() => {
    setCompetition(null);
    if (!sessionId) return;
    getCompetition(sessionId)
      .then(setCompetition)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar a competição."));
  }, [sessionId]);

  useEffect(() => {
    Promise.all([getCompetitionOptions(), listClubs()])
      .then(([o, c]) => {
        setOptions(o);
        setClubs(c.items);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Erro ao carregar opções."));
  }, [session?.status]);

  if (restoring) return <p className="muted">Reconectando…</p>;

  const active = session?.status === "active";
  return (
    <div className="stack">
      <PhaseBanner kicker={active ? "Detalhes" : "Nova partida"} title={active ? "Sua competição" : "Monte sua competição"}>
        {active ? "Participantes, calendário e encerramento." : "Escolha o formato e o clube que você vai comandar."}
      </PhaseBanner>
      {lostMessage && <Notice kind="warning" title="Sessão anterior indisponível">{lostMessage}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {success && <Notice kind="success" onDismiss={() => setSuccess(null)}>{success}</Notice>}
      {session && (
        <SessionPanel
          session={session}
          clubs={clubs}
          live={live}
          onChange={(s) => {
            setSession(s);
            onSessionChanged();
            if (s.status === "closed") setSuccess("Competição encerrada. Você já pode começar uma nova partida.");
          }}
        />
      )}
      {!active && options && (
        options.catalog_ready ? (
          <SessionForm
            options={options}
            clubs={clubs}
            onCreated={(s) => {
              setSession(s);
              onSessionChanged();
              navigate("#/tatica");
            }}
          />
        ) : (
          <Notice kind="warning" title="Bases não carregadas">
            As bases de clubes e jogadores ainda não foram importadas pelo administrador.
          </Notice>
        )
      )}
      {active && competition && <CompetitionView competition={competition} clubs={clubs} />}
      {active && session && (
        <ActionBar>
          <button type="button" className="btn btn--cta" onClick={() => navigate(phaseHome(session))}>Voltar ao jogo ▶</button>
        </ActionBar>
      )}
    </div>
  );
}
