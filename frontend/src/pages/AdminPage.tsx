/** Área oculta de dados (DR-04): sem link na navegação; senha verificada no servidor. */
import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { adminLogin, clearAdminToken, getAdminToken } from "../api/endpoints";
import { Notice } from "../components/Notice";
import type { Health } from "../types/api";
import { DataPage } from "./DataPage";

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

export function AdminPage({ importsBlocked, onDataChanged, health }: { importsBlocked: boolean; onDataChanged: () => void; health: Health | null }) {
  const [authed, setAuthed] = useState(() => !!getAdminToken());
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function login(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await adminLogin(password);
      setAuthed(true);
      setPassword("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Não foi possível entrar.");
    } finally {
      setBusy(false);
    }
  }

  if (!authed) {
    return (
      <form className="card gate" onSubmit={login} aria-label="Acesso à área de dados">
        <h2>Área restrita</h2>
        <p className="muted small">Atualização das bases de clubes e jogadores.</p>
        <label className="field">
          <span>Senha</span>
          <input type="password" inputMode="numeric" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus />
        </label>
        {error && <Notice kind="error">{error}</Notice>}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy || !password}>{busy ? "Verificando…" : "Entrar"}</button>
      </form>
    );
  }

  return (
    <div className="stack">
      <div className="season-head">
        <h2>Área de dados</h2>
        <button type="button" className="btn btn--ghost btn--small" onClick={() => { clearAdminToken(); setAuthed(false); }}>Sair</button>
      </div>
      <DataPage importsBlocked={importsBlocked} onDataChanged={onDataChanged} />
      {health && (
        <section className="card">
          <h3>Serviços</h3>
          <ul className="services">
            {Object.entries(health.services).map(([k, v]) => (
              <li key={k}>
                <span>{SERVICE_LABELS[k] ?? k}</span>
                <span className={`pill ${v === "ready" ? "pill--ok" : "pill--muted"}`}>{v === "ready" ? "pronto" : "indisponível"}</span>
              </li>
            ))}
          </ul>
          <p className="muted small">
            API v{health.version} · banco {health.database.status === "ok" ? `ok (esquema v${health.database.schema_version})` : "com erro"}
          </p>
        </section>
      )}
    </div>
  );
}
