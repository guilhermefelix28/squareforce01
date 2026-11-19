/** Tática antes do leilão (DR-02): a formação escolhida orienta o leilão e vira a escalação inicial. Confirmar já abre o leilão. */
import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { chooseFormation, getOfficialFormations, getSession, startAuction } from "../api/endpoints";
import { useSession } from "../app/SessionContext";
import { ActionBar, PhaseBanner } from "../components/GameUi";
import { Notice } from "../components/Notice";
import { PositionBadge } from "../components/PlayerCard";
import { POSITION_ORDER, sector } from "../domain/positions";
import { slotLayout } from "../features/lineup/layout";
import { useCommand } from "../features/season/useCommand";
import type { Formation } from "../types/api";

export function MiniPitch({ formation }: { formation: Formation }) {
  const pts = slotLayout(formation);
  return (
    <div className="mini-pitch" aria-hidden>
      {formation.positions.map((p, i) => (
        <i key={i} className={`pcard--${sector(p)}`} style={{ left: `${pts[i].x}%`, top: `${pts[i].y}%` }} />
      ))}
    </div>
  );
}

/** Quantos jogadores de cada posição a formação usa. */
export function formationCounts(formation: Formation): Map<string, number> {
  const counts = new Map<string, number>();
  formation.positions.forEach((p) => counts.set(p, (counts.get(p) ?? 0) + 1));
  return counts;
}

export function FormationNeeds({ formation }: { formation: Formation }) {
  const counts = formationCounts(formation);
  return (
    <div className="vacancies">
      {POSITION_ORDER.filter((p) => counts.has(p)).map((p) => (
        <span key={p} className="vacancy"><PositionBadge position={p} size="sm" /> ×{counts.get(p)}</span>
      ))}
    </div>
  );
}

export function TacticPage({ navigate }: { navigate: (h: string) => void }) {
  const { session, setSession } = useSession();
  const [formations, setFormations] = useState<Formation[]>([]);
  const [chosen, setChosen] = useState<string | null>(session?.user_formation ?? null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const cmd = useCommand();

  useEffect(() => {
    getOfficialFormations()
      .then((f) => {
        setFormations(f);
        setChosen((c) => c ?? f[0]?.id ?? null);
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.message : "Falha ao carregar as formações."));
  }, []);

  if (session?.status !== "active") {
    return (
      <Notice kind="info" title="Nenhuma partida em andamento">
        Comece uma nova partida para escolher a tática.{" "}
        <button type="button" className="btn btn--small btn--ghost" onClick={() => navigate("#/session")}>Nova partida</button>
      </Notice>
    );
  }
  if (session.phase !== "setup") {
    return (
      <Notice kind="info" title="Tática já definida">
        A tática é escolhida antes do leilão. Durante a temporada, você muda a formação na escalação de cada jogo.
      </Notice>
    );
  }

  const selected = formations.find((f) => f.id === chosen) ?? null;
  const confirm = () =>
    void cmd.run(async (k) => {
      if (!chosen) return;
      await chooseFormation(session.id, chosen, k);
      // sem tela intermediária: a tática confirmada já começa o leilão (o relógio global inicia agora)
      await startAuction(session.id, `${k}-leilao`);
      setSession(await getSession(session.id));
      navigate("#/auction");
    });

  return (
    <div className="stack">
      <PhaseBanner kicker="Antes do leilão" title="Escolha sua tática">
        A formação define quantos jogadores de cada posição você vai buscar no leilão e será a escalação inicial do time.
        Ao confirmar, o leilão começa: rodadas de 10 segundos com 5 jogadores da mesma posição e R$ 120 milhões para
        montar 18 jogadores. O relógio é global e não pausa.
      </PhaseBanner>
      {loadError && <Notice kind="error">{loadError}</Notice>}
      {cmd.error && <Notice kind="error" title="Tática não salva">{cmd.error.message}</Notice>}
      <div className="tactic-layout">
        <ul className="formation-grid" role="radiogroup" aria-label="Formações oficiais">
          {formations.map((f) => (
            <li key={f.id}>
              <button type="button" role="radio" aria-checked={chosen === f.id} className={`formation-tile${chosen === f.id ? " is-on" : ""}`} onClick={() => setChosen(f.id)}>
                <MiniPitch formation={f} />
                <strong>{f.id}</strong>
              </button>
            </li>
          ))}
        </ul>
        {selected && (
          <section className="card" aria-live="polite">
            <h3>{selected.id}</h3>
            <MiniPitch formation={selected} />
            <span className="muted small">Jogadores por posição</span>
            <FormationNeeds formation={selected} />
            <p className="muted small">Elenco final: 18 jogadores (11 titulares + 7 reservas).</p>
          </section>
        )}
      </div>
      <ActionBar>
        <button type="button" className="btn btn--cta" disabled={!chosen || cmd.busy} onClick={confirm}>
          {cmd.busy ? "Abrindo o leilão…" : "Confirmar tática e começar o leilão ▶"}
        </button>
      </ActionBar>
    </div>
  );
}
