import { useState } from "react";
import { ApiError } from "../../api/client";
import { closeSession, getSession } from "../../api/endpoints";
import { ClubCrest } from "../../components/ClubCrest";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { Notice } from "../../components/Notice";
import type { Club, Session } from "../../types/api";

const fmtDate = (iso: string) => new Date(iso).toLocaleString("pt-BR");

export function SessionPanel({
  session,
  clubs,
  live,
  onChange,
}: {
  session: Session;
  clubs: Club[];
  live: boolean;
  onChange: (s: Session) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const club = clubs.find((c) => c.club_uid === session.config.user_club_uid);
  const active = session.status === "active";
  const cfg = session.config;

  async function doClose() {
    setBusy(true);
    setError(null);
    try {
      onChange(await closeSession(session.id, session.version));
      setConfirming(false);
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
        onChange(await getSession(session.id));
        setError("O estado da sessão mudou. Os dados foram atualizados; confirme novamente.");
      } else setError(e instanceof ApiError ? e.message : "Não foi possível encerrar a sessão.");
      setConfirming(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card session-panel" aria-labelledby="session-title">
      <header className="session-panel__head">
        <h3 id="session-title">{active ? "Competição ativa" : "Sessão encerrada"}</h3>
        <span className={`pill ${active ? "pill--ok" : "pill--muted"}`}>
          {active ? (live ? "ativa · ao vivo" : "ativa") : "encerrada"}
        </span>
      </header>
      <div className="session-club">
        {club && <ClubCrest clubUid={club.club_uid} name={club.short_name} size={48} />}
        <div>
          <div className="muted small">Seu clube</div>
          <strong>{club?.short_name ?? `#${cfg.user_club_uid}`}</strong>
        </div>
      </div>
      <dl className="stats">
        <div><dt>Formato</dt><dd>{cfg.format === "league" ? "Liga" : "Copa"}</dd></div>
        <div><dt>Clubes</dt><dd>{cfg.num_clubs}</dd></div>
        {cfg.format === "league" && (
          <div><dt>Turnos</dt><dd>{cfg.league_rounds === "double" ? "Turno e returno" : "Turno único"}</dd></div>
        )}
        <div><dt>Fase</dt><dd>{session.phase === "setup" ? "Configuração" : session.phase}</dd></div>
        <div><dt>Versão</dt><dd>{session.version}</dd></div>
      </dl>
      <p className="muted small">
        Sessão <code>{session.id.slice(0, 8)}</code> · criada em {fmtDate(session.created_at)}
        {session.closed_at && ` · encerrada em ${fmtDate(session.closed_at)}`}
      </p>
      {active && (
        <Notice kind="info">
          O progresso existe apenas na memória do servidor. Não há salvamento: se o servidor for reiniciado, a competição
          não poderá ser restaurada. Importações ficam bloqueadas enquanto a sessão estiver ativa.
        </Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {active && (
        <button type="button" className="btn btn--danger" onClick={() => setConfirming(true)}>
          Encerrar sessão
        </button>
      )}
      <ConfirmDialog
        open={confirming}
        title="Encerrar a competição?"
        message="Todo o progresso desta competição será perdido e não poderá ser recuperado."
        confirmLabel="Encerrar"
        danger
        busy={busy}
        onConfirm={() => void doClose()}
        onCancel={() => setConfirming(false)}
      />
    </section>
  );
}
