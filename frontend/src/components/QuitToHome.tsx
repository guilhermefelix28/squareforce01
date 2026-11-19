/** Encerra a competição atual (com confirmação, GDD §23) e volta à tela inicial. */
import { useState } from "react";
import { ApiError } from "../api/client";
import { closeSession, getSession } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { ConfirmDialog } from "./ConfirmDialog";
import { Notice } from "./Notice";

export function QuitToHome({ navigate, label = "Encerrar e voltar ao início" }: { navigate: (h: string) => void; label?: string }) {
  const { session, setSession } = useSession();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!session || session.status !== "active") return null;
  const what = session.config.format === "cup" ? "copa" : "liga";

  async function quit() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await closeSession(session.id, session.version));
      setOpen(false);
      navigate("#/home");
    } catch (e) {
      if (e instanceof ApiError && e.code === "VERSION_CONFLICT") {
        setSession(await getSession(session.id));
        setError(`O estado da ${what} mudou. Confirme novamente.`);
      } else setError(e instanceof ApiError ? e.message : `Não foi possível encerrar a ${what}.`);
      setOpen(false);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="btn btn--ghost" onClick={() => setOpen(true)} disabled={busy}>⏏ {label}</button>
      {error && <Notice kind="error">{error}</Notice>}
      <ConfirmDialog
        open={open}
        title={`Encerrar esta ${what}?`}
        message={`O progresso não é salvo: a ${what} será encerrada e você volta à tela inicial.`}
        confirmLabel={`Encerrar ${what}`}
        danger
        busy={busy}
        onConfirm={() => void quit()}
        onCancel={() => setOpen(false)}
      />
    </>
  );
}
