import { useEffect, useRef, useState } from "react";
import { ApiError, newIdempotencyKey } from "../api/client";
import { getAuctionSummary, getSession, listClubs, startAuction } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Notice } from "../components/Notice";
import { AuctionBoard } from "../features/auction/AuctionBoard";
import { AuctionSummaryView } from "../features/auction/AuctionSummaryView";
import { useAuction } from "../features/auction/useAuction";
import type { AuctionSummary, Club } from "../types/api";

export function AuctionPage({ go }: { go: (page: "session") => void }) {
  const { session, setSession } = useSession();
  const [clubs, setClubs] = useState<Club[]>([]);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<AuctionSummary | null>(null);
  const keyRef = useRef(newIdempotencyKey());

  const sid = session?.status === "active" ? session.id : null;
  const phase = session?.phase;
  const live = phase === "auction";
  const { state, error: pollError, refresh, roundRemainingMs, globalRemainingMs } = useAuction(sid, live);

  useEffect(() => {
    listClubs().then((p) => setClubs(p.items)).catch(() => undefined);
  }, []);

  // leilão terminou: atualiza a sessão (fase) e carrega o resumo
  useEffect(() => {
    if (!sid) return;
    if (state?.phase === "completed" || phase === "squad_completion") {
      getSession(sid).then(setSession).catch(() => undefined);
      getAuctionSummary(sid).then(setSummary).catch(() => undefined);
    }
  }, [sid, state?.phase, phase, setSession]);

  async function begin() {
    if (!sid) return;
    setBusy(true);
    setError(null);
    try {
      await startAuction(sid, keyRef.current);
      setSession(await getSession(sid));
      setConfirm(false);
      void refresh();
    } catch (e) {
      setError(e instanceof ApiError ? { code: e.code, message: e.message } : { code: "", message: "Falha ao iniciar o leilão." });
      setConfirm(false);
    } finally {
      keyRef.current = newIdempotencyKey();
      setBusy(false);
    }
  }

  if (!sid) {
    return (
      <div className="stack">
        <h2>Leilão</h2>
        <Notice kind="info" title="Nenhuma competição ativa">
          Crie uma competição antes de participar do leilão.{" "}
          <button type="button" className="btn btn--small btn--ghost" onClick={() => go("session")}>Ir para Competição</button>
        </Notice>
      </div>
    );
  }

  return (
    <div className="stack">
      <h2>Leilão</h2>
      {error && (
        <Notice kind={error.code === "AUCTION_MODEL_NOT_CONFIGURED" ? "warning" : "error"}
          title={error.code === "AUCTION_MODEL_NOT_CONFIGURED" ? "Leilão aguardando fórmulas aprovadas" : "Não foi possível iniciar"}>
          {error.message}
        </Notice>
      )}
      {pollError && live && <Notice kind="warning">{pollError} Tentando novamente…</Notice>}

      {phase === "setup" && (
        <section className="card">
          <h3>Pronto para o leilão</h3>
          <p className="muted">
            Rodadas de 10 segundos com 5 jogadores da mesma posição. Cada clube começa com R$ 120 milhões e precisa
            terminar com 18 jogadores. O relógio é global e não pausa.
          </p>
          <button type="button" className="btn btn--primary" onClick={() => setConfirm(true)} disabled={busy}>
            Iniciar leilão
          </button>
        </section>
      )}

      {live && state && state.phase === "running" && (
        <AuctionBoard
          sessionId={sid}
          state={state}
          clubs={clubs}
          roundRemainingMs={roundRemainingMs}
          globalRemainingMs={globalRemainingMs}
          onChanged={refresh}
        />
      )}
      {live && !state && <p className="muted">Conectando ao leilão…</p>}
      {(phase === "squad_completion" || state?.phase === "completed") && !summary && <p className="muted">Completando elencos…</p>}
      {summary && <AuctionSummaryView summary={summary} clubs={clubs} />}

      <ConfirmDialog
        open={confirm}
        title="Iniciar o leilão?"
        message="O relógio global começa imediatamente e não pode ser pausado."
        confirmLabel="Iniciar"
        busy={busy}
        onConfirm={() => void begin()}
        onCancel={() => setConfirm(false)}
      />
    </div>
  );
}
