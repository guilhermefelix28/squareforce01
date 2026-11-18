import { useEffect, useState } from "react";
import { useHealth } from "../hooks/useHealth";
import { DataPage } from "../pages/DataPage";
import { HomePage } from "../pages/HomePage";
import { SessionPage } from "../pages/SessionPage";
import { SessionProvider, useSession } from "./SessionContext";
import { useTheme } from "./theme";

type Page = "home" | "data" | "session";
const PAGES: { id: Page; label: string }[] = [
  { id: "home", label: "Início" },
  { id: "data", label: "Dados" },
  { id: "session", label: "Competição" },
];

function pageFromHash(): Page {
  const h = window.location.hash.replace("#/", "");
  return (PAGES.find((p) => p.id === h)?.id ?? "home") as Page;
}

function Shell() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const { theme, toggle } = useTheme();
  const { health, connection, error, refresh } = useHealth();
  const { session } = useSession();

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const go = (p: Page) => {
    window.location.hash = `#/${p}`;
    setPage(p);
  };

  const importsBlocked = session?.status === "active" || !!health?.active_session;

  return (
    <div className="app">
      <header className="topbar">
        <a href="#/home" className="brand" onClick={() => go("home")} aria-label="SquadForce — início">
          <img src={theme === "dark" ? "/brand/logo-dark.png" : "/brand/logo-light.png"} alt="SquadForce" />
        </a>
        <nav className="tabs" aria-label="Navegação principal">
          {PAGES.map((p) => (
            <a
              key={p.id}
              href={`#/${p.id}`}
              className={page === p.id ? "is-active" : ""}
              aria-current={page === p.id ? "page" : undefined}
              onClick={() => setPage(p.id)}
            >
              {p.label}
            </a>
          ))}
        </nav>
        <div className="topbar__end">
          <span className={`conn conn--${connection}`} role="status" aria-live="polite">
            <span className="conn__dot" aria-hidden />
            {connection === "online" ? "Servidor online" : connection === "offline" ? "Servidor offline" : "Conectando…"}
          </span>
          <button type="button" className="btn btn--ghost btn--small" onClick={toggle} aria-label="Alternar tema">
            {theme === "dark" ? "☀ Claro" : "☾ Escuro"}
          </button>
        </div>
      </header>
      <main className="content">
        {page === "home" && (
          <HomePage
            health={health}
            connection={connection}
            error={error}
            session={session}
            onRetry={refresh}
            go={(p) => go(p)}
          />
        )}
        {page === "data" && <DataPage importsBlocked={importsBlocked} onDataChanged={refresh} />}
        {page === "session" && <SessionPage onSessionChanged={refresh} />}
      </main>
      <footer className="footer muted small">SquadForce · Football Strategy Game · Entrega 2</footer>
    </div>
  );
}

export function App() {
  return (
    <SessionProvider>
      <Shell />
    </SessionProvider>
  );
}
