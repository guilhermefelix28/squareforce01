/** Abertura do jogo: apresentação e "Nova partida" / "Continuar". */
import { Notice } from "../components/Notice";
import type { Connection } from "../hooks/useHealth";
import type { Health, Session } from "../types/api";

const PHASE_LABEL: Record<string, string> = {
  setup: "Escolha da tática",
  auction: "Leilão em andamento",
  squad_completion: "Completando elencos",
  trading: "Mercado de negociações",
  competition: "Temporada em andamento",
  finished: "Temporada encerrada",
};

export function HomePage({
  health,
  connection,
  error,
  session,
  onRetry,
  onStart,
  continueTo,
}: {
  health: Health | null;
  connection: Connection;
  error: string | null;
  session: Session | null;
  onRetry: () => void;
  onStart: () => void;
  continueTo: () => void;
}) {
  const db = health?.database;
  const ready = !!db && (db.clubs ?? 0) >= 2 && (db.players ?? 0) > 0;
  const active = session?.status === "active";
  return (
    <div className="intro">
      <img className="intro__logo" src="/brand/logo-dark.png" alt="SquadForce — Football Strategy Game" />
      <p className="intro__tagline">
        Monte seu time no <em>leilão</em>, negocie no <em>mercado</em> e dispute a <em>Liga</em> ou a <em>Copa</em> contra
        clubes comandados por bots.
      </p>

      {connection === "offline" && (
        <Notice kind="error" title="Sem comunicação com o servidor">
          {error} <button type="button" className="btn btn--small btn--ghost" onClick={onRetry}>Tentar novamente</button>
        </Notice>
      )}

      {active ? (
        <div className="stack" style={{ alignItems: "center" }}>
          <span className="intro__resume">
            <strong>Partida em andamento</strong>
            <span className="muted">· {PHASE_LABEL[session.phase] ?? session.phase}</span>
          </span>
          <button type="button" className="btn btn--cta" onClick={continueTo}>▶ Continuar</button>
        </div>
      ) : (
        <button type="button" className="btn btn--cta" onClick={onStart} disabled={connection === "offline" || (!!health && !ready)}>
          ▶ Nova partida
        </button>
      )}
      {health && !ready && !active && (
        <Notice kind="warning" title="Bases de dados não carregadas">
          O jogo precisa das bases de clubes e jogadores. Peça ao administrador para atualizá-las na área de dados.
        </Notice>
      )}

      <div className="pillars">
        <section className="pillar">
          <span className="pillar__n">01</span>
          <h3>Leilão</h3>
          <p>R$ 120 milhões, rodadas de 10 segundos e ofertas sigilosas. Monte um elenco de 18 jogadores.</p>
        </section>
        <section className="pillar">
          <span className="pillar__n">02</span>
          <h3>Mercado</h3>
          <p>Proponha trocas aos bots para ajustar posições e reforçar a formação escolhida.</p>
        </section>
        <section className="pillar">
          <span className="pillar__n">03</span>
          <h3>Temporada</h3>
          <p>Escale, defina a postura e acompanhe cada lance ao vivo, com os placares da rodada.</p>
        </section>
      </div>
      {db && (
        <p className="muted small">
          {db.clubs ?? 0} clubes · {db.players ?? 0} jogadores · servidor {connection === "online" ? "online" : "offline"}
        </p>
      )}
    </div>
  );
}
