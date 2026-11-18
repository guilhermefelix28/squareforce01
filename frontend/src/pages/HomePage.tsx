import { Notice } from "../components/Notice";
import type { Connection } from "../hooks/useHealth";
import type { Health, Session } from "../types/api";

const SERVICE_LABELS: Record<string, string> = {
  gateway: "Gateway / API",
  session: "Sessão",
  data: "Dados e importações",
  competition: "Competições",
  auction: "Leilão",
  trading: "Negociações",
  bot_ai: "IA dos bots",
  match_engine: "Motor de partidas",
};

export function HomePage({
  health,
  connection,
  error,
  session,
  onRetry,
  go,
}: {
  health: Health | null;
  connection: Connection;
  error: string | null;
  session: Session | null;
  onRetry: () => void;
  go: (page: "data" | "session") => void;
}) {
  const db = health?.database;
  const ready = !!db && (db.clubs ?? 0) >= 2 && (db.players ?? 0) > 0;
  return (
    <div className="stack">
      <section className="hero card">
        <h2>Central de gerenciamento</h2>
        <p className="muted">
          Importe as bases, confira o catálogo e configure sua competição. Leilão, negociações e partidas chegam nas
          próximas entregas.
        </p>
        <div className="hero__actions">
          <button type="button" className="btn btn--primary" onClick={() => go(ready ? "session" : "data")}>
            {session?.status === "active" ? "Ver competição ativa" : ready ? "Configurar competição" : "Importar bases"}
          </button>
          <button type="button" className="btn btn--ghost" onClick={() => go("data")}>
            Gerenciar dados
          </button>
        </div>
      </section>

      {connection === "offline" && (
        <Notice kind="error" title="Sem comunicação com o servidor">
          {error} <button type="button" className="btn btn--small btn--ghost" onClick={onRetry}>Tentar novamente</button>
        </Notice>
      )}

      <div className="grid-3">
        <section className="card metric">
          <span className="muted small">Clubes</span>
          <strong>{db?.clubs ?? "—"}</strong>
        </section>
        <section className="card metric">
          <span className="muted small">Jogadores</span>
          <strong>{db?.players ?? "—"}</strong>
        </section>
        <section className="card metric">
          <span className="muted small">Competição</span>
          <strong>{session?.status === "active" ? "Ativa" : "Nenhuma"}</strong>
        </section>
      </div>

      {health && (
        <section className="card">
          <h3>Serviços</h3>
          <ul className="services">
            {Object.entries(health.services).map(([k, v]) => (
              <li key={k}>
                <span>{SERVICE_LABELS[k] ?? k}</span>
                <span className={`pill ${v === "ready" ? "pill--ok" : "pill--muted"}`}>
                  {v === "ready" ? "pronto" : "próximas entregas"}
                </span>
              </li>
            ))}
          </ul>
          <p className="muted small">
            API v{health.version} · banco {db?.status === "ok" ? `ok (esquema v${db.schema_version})` : "com erro"}
          </p>
        </section>
      )}
    </div>
  );
}
