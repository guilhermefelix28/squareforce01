import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getCompetitionOptions, listClubs } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { Notice } from "../components/Notice";
import { SessionForm } from "../features/session/SessionForm";
import { SessionPanel } from "../features/session/SessionPanel";
import type { Club, CompetitionOptions } from "../types/api";

export function SessionPage({ onSessionChanged }: { onSessionChanged: () => void }) {
  const { session, setSession, lostMessage, live, restoring } = useSession();
  const [options, setOptions] = useState<CompetitionOptions | null>(null);
  const [clubs, setClubs] = useState<Club[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
      <h2>Competição</h2>
      {lostMessage && <Notice kind="warning" title="Sessão anterior indisponível">{lostMessage}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {success && <Notice kind="success" onDismiss={() => setSuccess(null)}>{success}</Notice>}
      <div className="grid-2 grid-2--wide">
        {session && (
          <SessionPanel
            session={session}
            clubs={clubs}
            live={live}
            onChange={(s) => {
              setSession(s);
              onSessionChanged();
              if (s.status === "closed") setSuccess("Sessão encerrada. As importações foram liberadas.");
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
                setSuccess("Sessão iniciada. Leilão e partidas serão habilitados nas próximas entregas.");
              }}
            />
          ) : (
            <Notice kind="warning" title="Bases não importadas">
              Importe clubes e jogadores na área de Dados antes de iniciar uma competição.
            </Notice>
          )
        )}
      </div>
    </div>
  );
}
