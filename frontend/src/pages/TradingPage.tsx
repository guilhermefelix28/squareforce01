import { useEffect, useRef, useState } from "react";
import { ApiError, newIdempotencyKey } from "../api/client";
import { getSession, listClubs, startTrading } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Notice } from "../components/Notice";
import { formatMoneyShort } from "../domain/money";
import { TradingBoard } from "../features/trading/TradingBoard";
import { useTrading } from "../features/trading/useTrading";
import type { Club } from "../types/api";

export function TradingPage({ go }: { go: (page: "auction" | "session") => void }) {
  const { session, setSession } = useSession();
  const [clubs, setClubs] = useState<Club[]>([]);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const keyRef = useRef(newIdempotencyKey());

  const sid = session?.status === "active" ? session.id : null;
  const phase = session?.phase;
  const visible = phase === "trading" || phase === "competition";
  const { state, squads, error: pollError, refresh, left, remainingMs } = useTrading(sid, visible);

  useEffect(() => {
    listClubs().then((p) => setClubs(p.items)).catch(() => undefined);
  }, []);

  // mercado encerrado pelo relógio do servidor: atualiza a fase da sessão
  useEffect(() => {
    if (sid && state?.phase === "finished" && phase === "trading") getSession(sid).then(setSession).catch(() => undefined);
  }, [sid, state?.phase, phase, setSession]);

  async function begin() {
    if (!sid) return;
    setBusy(true);
    setError(null);
    try {
      await startTrading(sid, keyRef.current);
      setSession(await getSession(sid));
      void refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao iniciar o mercado.");
    } finally {
      keyRef.current = newIdempotencyKey();
      setConfirm(false);
      setBusy(false);
    }
  }

  const names = new Map(clubs.map((c) => [c.club_uid, c.short_name]));
  return (
    <div className="stack">
      <h2>Mercado de negociações</h2>
      {!sid && (
        <Notice kind="info" title="Nenhuma competição ativa">
          <button type="button" className="btn btn--small btn--ghost" onClick={() => go("session")}>Ir para Competição</button>
        </Notice>
      )}
      {sid && (phase === "setup" || phase === "auction") && (
        <Notice kind="info" title="Mercado indisponível">
          O mercado abre depois do leilão e da complementação dos elencos.{" "}
          <button type="button" className="btn btn--small btn--ghost" onClick={() => go("auction")}>Ir para o Leilão</button>
        </Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {pollError && visible && <Notice kind="warning">{pollError} Tentando novamente…</Notice>}

      {phase === "squad_completion" && (
        <section className="card">
          <h3>Elencos completos</h3>
          <p className="muted">
            O mercado dura 3 minutos, sem pausa. Trocas de um jogador por outro, com dinheiro adicional opcional pago por
            quem propõe. Cada clube pode concluir até 3 negociações e ter uma proposta pendente por vez.
          </p>
          <button type="button" className="btn btn--primary" onClick={() => setConfirm(true)} disabled={busy}>
            Iniciar negociações
          </button>
        </section>
      )}

      {phase === "trading" && state?.phase === "running" && sid && (
        <TradingBoard sessionId={sid} state={state} squads={squads} clubs={clubs} remainingMs={remainingMs} left={left} onChanged={refresh} />
      )}

      {state?.phase === "finished" && (
        <section className="card">
          <h3>Mercado encerrado</h3>
          <p className="muted">
            {state.history.length} negociações concluídas. Você fez {state.completed_trades} e terminou com saldo de{" "}
            {formatMoneyShort(state.budget)}. A preparação das partidas chega na próxima entrega.
          </p>
          <ol className="results">
            {state.history.map((r) => (
              <li key={r.proposal_id}>
                <span className="muted small">{names.get(r.proponent_club_uid) ?? r.proponent_club_uid} ⇄ {names.get(r.recipient_club_uid) ?? r.recipient_club_uid}</span>
                <span>{r.offered.name} ⇄ {r.requested.name}{r.money > 0 ? ` + ${formatMoneyShort(r.money)}` : ""}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      <ConfirmDialog
        open={confirm}
        title="Iniciar as negociações?"
        message="O relógio de 3 minutos começa imediatamente e não pode ser pausado."
        confirmLabel="Iniciar"
        busy={busy}
        onConfirm={() => void begin()}
        onCancel={() => setConfirm(false)}
      />
    </div>
  );
}
