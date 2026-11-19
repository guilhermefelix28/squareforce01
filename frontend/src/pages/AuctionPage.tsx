import { useEffect, useRef, useState } from "react";
import { ApiError, newIdempotencyKey } from "../api/client";
import { getAuctionSummary, getOfficialFormations, getSession, listClubs, startAuction } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { AuctionBoard, FormationVacancies } from "../features/auction/AuctionBoard";
import { AuctionSummaryView } from "../features/auction/AuctionSummaryView";
import { useAuction } from "../features/auction/useAuction";
import type { AuctionSummary, Club, Formation } from "../types/api";
import { MiniPitch } from "./TacticPage";

export function AuctionPage({ go, navigate }: { go: (page: string) => void; navigate: (h: string) => void }) {
  const { session, setSession } = useSession();
  const [clubs, setClubs] = useState<Club[]>([]);
  const [formations, setFormations] = useState<Formation[]>([]);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<AuctionSummary | null>(null);
  const keyRef = useRef(newIdempotencyKey());

  const sid = session?.status === "active" ? session.id : null;
  const phase = session?.phase;
  const live = phase === "auction";
  const { state, error: pollError, refresh, roundRemainingMs, globalRemainingMs } = useAuction(sid, live);
  const formation = formations.find((f) => f.id === session?.user_formation) ?? null;

  useEffect(() => {
    listClubs().then((p) => setClubs(p.items)).catch(() => undefined);
    getOfficialFormations().then(setFormations).catch(() => undefined);
  }, []);

  // leilão terminou: atualiza a sessão (fase) e carrega o resumo
  useEffect(() => {
    if (!sid) return;
    if (state?.phase === "completed" || phase === "squad_completion" || phase === "trading") {
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
        <PhaseBanner title="Leilão" />
        <Notice kind="info" title="Nenhuma partida em andamento">
          Comece uma nova partida antes de participar do leilão.{" "}
          <button type="button" className="btn btn--small btn--ghost" onClick={() => go("session")}>Nova partida</button>
        </Notice>
      </div>
    );
  }

  const finished = phase === "squad_completion" || phase === "trading" || state?.phase === "completed";
  return (
    <div className="stack">
      {error && (
        <Notice kind={error.code === "AUCTION_MODEL_NOT_CONFIGURED" ? "warning" : "error"}
          title={error.code === "AUCTION_MODEL_NOT_CONFIGURED" ? "Leilão desligado neste servidor" : "Não foi possível iniciar"}>
          {error.message}
        </Notice>
      )}
      {pollError && live && <Notice kind="warning">{pollError} Tentando novamente…</Notice>}

      {phase === "setup" && (
        <>
          <PhaseBanner kicker="Etapa 2" title="Leilão de jogadores">
            Rodadas de 10 segundos com 5 jogadores da mesma posição. R$ 120 milhões para montar 18 jogadores. O relógio é
            global e não pausa.
          </PhaseBanner>
          {!session?.user_formation && (
            <Notice kind="info" title="Escolha sua tática primeiro">
              A formação orienta quantos jogadores de cada posição buscar.{" "}
              <button type="button" className="btn btn--small btn--ghost" onClick={() => navigate("#/tatica")}>Escolher tática</button>
            </Notice>
          )}
          {formation && (
            <section className="card" style={{ maxWidth: 420, margin: "0 auto", width: "100%" }}>
              <h3>Sua tática: {formation.id}</h3>
              <MiniPitch formation={formation} />
              <FormationVacancies formation={formation} owned={[]} />
              <button type="button" className="btn btn--ghost btn--small" onClick={() => navigate("#/tatica")}>Trocar tática</button>
            </section>
          )}
          <ActionBar>
            <button type="button" className="btn btn--cta" onClick={() => setConfirm(true)} disabled={busy}>Começar leilão ▶</button>
          </ActionBar>
        </>
      )}

      {live && state && state.phase === "running" && (
        <AuctionBoard
          sessionId={sid}
          state={state}
          clubs={clubs}
          formation={formation}
          roundRemainingMs={roundRemainingMs}
          globalRemainingMs={globalRemainingMs}
          onChanged={refresh}
        />
      )}
      {live && !state && <p className="muted" role="status">Conectando ao leilão…</p>}
      {finished && (
        <>
          <PhaseBanner kicker="Leilão encerrado" title="Elencos formados" />
          {!summary && <p className="muted" role="status">Completando elencos…</p>}
          {summary && <AuctionSummaryView summary={summary} clubs={clubs} />}
          <ActionBar>
            <button type="button" className="btn btn--cta" onClick={() => navigate("#/trading")} disabled={!summary}>Ir para o mercado ▶</button>
          </ActionBar>
        </>
      )}

      <ConfirmDialog
        open={confirm}
        title="Começar o leilão?"
        message="O relógio global começa imediatamente e não pode ser pausado."
        confirmLabel="Começar"
        busy={busy}
        onConfirm={() => void begin()}
        onCancel={() => setConfirm(false)}
      />
    </div>
  );
}
