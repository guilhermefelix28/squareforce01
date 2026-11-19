import { useEffect, useState } from "react";
import { useHealth } from "../hooks/useHealth";
import { AuctionPage } from "../pages/AuctionPage";
import { DataPage } from "../pages/DataPage";
import { EndPage } from "../pages/EndPage";
import { HomePage } from "../pages/HomePage";
import { LineupPage } from "../pages/LineupPage";
import { MatchPage } from "../pages/MatchPage";
import { PostMatchPage } from "../pages/PostMatchPage";
import { SeasonPage, type SeasonTab } from "../pages/SeasonPage";
import { SessionPage } from "../pages/SessionPage";
import { TradingPage } from "../pages/TradingPage";
import type { Session } from "../types/api";
import { SessionProvider, useSession } from "./SessionContext";
import { useTheme } from "./theme";

export type Route =
  | { page: "home" | "data" | "session" | "auction" | "trading" | "escalacao" | "partida" | "encerramento" }
  | { page: "temporada"; tab: SeasonTab }
  | { page: "pos"; matchId: string };

const SEASON_TABS: SeasonTab[] = ["central", "elenco", "calendario", "classificacao", "estatisticas", "resultados"];
const SIMPLE = ["home", "data", "session", "auction", "trading", "escalacao", "partida", "encerramento"] as const;

export function parseHash(hash: string): Route {
  const [head, arg] = hash.replace(/^#\/?/, "").split("/");
  if (head === "temporada") return { page: "temporada", tab: SEASON_TABS.includes(arg as SeasonTab) ? (arg as SeasonTab) : "central" };
  if (head === "pos" && arg) return { page: "pos", matchId: decodeURIComponent(arg) };
  return { page: (SIMPLE as readonly string[]).includes(head) ? (head as (typeof SIMPLE)[number]) : "home" };
}

/** Navegação contextual (GDD §22): cada fase mostra as telas que fazem sentido nela. */
export function navItems(session: Session | null): { hash: string; page: string; label: string }[] {
  const phase = session?.status === "active" ? session.phase : null;
  const items = [{ hash: "#/home", page: "home", label: "Início" }];
  items.push({ hash: "#/session", page: "session", label: "Competição" });
  if (phase === "setup" || phase === "auction" || phase === "squad_completion") items.push({ hash: "#/auction", page: "auction", label: "Leilão" });
  if (phase === "squad_completion" || phase === "trading") items.push({ hash: "#/trading", page: "trading", label: "Mercado" });
  if (phase === "competition" || phase === "finished") {
    items.push({ hash: "#/temporada/central", page: "temporada", label: "Central" });
    if (phase === "competition") {
      items.push({ hash: "#/escalacao", page: "escalacao", label: "Escalação" });
      items.push({ hash: "#/partida", page: "partida", label: "Partida" });
    } else items.push({ hash: "#/encerramento", page: "encerramento", label: "Encerramento" });
  }
  if (!phase) items.push({ hash: "#/data", page: "data", label: "Dados" });
  return items;
}

/** Tela principal da fase atual (botão "Continuar"). */
export function phaseHome(session: Session | null): string {
  if (session?.status !== "active") return "#/session";
  switch (session.phase) {
    case "setup":
    case "auction":
      return "#/auction";
    case "squad_completion":
    case "trading":
      return "#/trading";
    case "competition":
      return "#/temporada/central";
    case "finished":
      return "#/encerramento";
    default:
      return "#/session";
  }
}

function Shell() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  const { theme, toggle } = useTheme();
  const { health, connection, error, refresh } = useHealth();
  const { session, live, lostMessage, restoring } = useSession();

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash(window.location.hash));
      window.scrollTo?.({ top: 0 });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const navigate = (hash: string) => {
    if (window.location.hash === hash) setRoute(parseHash(hash));
    else window.location.hash = hash;
  };
  const go = (p: string) => navigate(`#/${p}`);

  const importsBlocked = session?.status === "active" || !!health?.active_session;
  const active = session?.status === "active";
  const items = navItems(session);

  return (
    <div className="app">
      <a
        href="#conteudo"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault(); // o hash é usado pelas rotas: só move o foco
          document.getElementById("conteudo")?.focus();
        }}
      >
        Pular para o conteúdo
      </a>
      <header className="topbar">
        <a href="#/home" className="brand" aria-label="SquadForce — início">
          <img src={theme === "dark" ? "/brand/logo-dark.png" : "/brand/logo-light.png"} alt="SquadForce" />
        </a>
        <nav className="tabs" aria-label="Navegação principal">
          {items.map((p) => (
            <a key={p.hash} href={p.hash} className={route.page === p.page ? "is-active" : ""} aria-current={route.page === p.page ? "page" : undefined}>
              {p.label}
            </a>
          ))}
        </nav>
        <div className="topbar__end">
          <span className={`conn conn--${connection}`} role="status" aria-live="polite">
            <span className="conn__dot" aria-hidden />
            {connection === "online" ? (active && !live ? "Reconectando sessão…" : "Servidor online") : connection === "offline" ? "Servidor offline" : "Conectando…"}
          </span>
          <button type="button" className="btn btn--ghost btn--small" onClick={toggle} aria-label={`Alternar para tema ${theme === "dark" ? "claro" : "escuro"}`}>
            {theme === "dark" ? "☀ Claro" : "☾ Escuro"}
          </button>
        </div>
      </header>
      <main className="content" id="conteudo" tabIndex={-1}>
        {lostMessage && route.page !== "session" && (
          <div className="banner banner--warning" role="alert">
            <strong>Sua competição não pode mais ser recuperada.</strong> {lostMessage} O servidor não guarda progresso
            (sem salvamento persistente). <a href="#/session">Iniciar nova competição</a>
          </div>
        )}
        {restoring ? (
          <p className="muted" role="status">Reconectando à sessão…</p>
        ) : (
          <>
            {route.page === "home" && (
              <HomePage health={health} connection={connection} error={error} session={session} onRetry={refresh} go={go}
                continueTo={() => navigate(phaseHome(session))} />
            )}
            {route.page === "data" && <DataPage importsBlocked={importsBlocked} onDataChanged={refresh} />}
            {route.page === "session" && <SessionPage onSessionChanged={refresh} />}
            {route.page === "auction" && <AuctionPage go={go} />}
            {route.page === "trading" && <TradingPage go={go} />}
            {route.page === "temporada" && <SeasonPage tab={route.tab} navigate={navigate} />}
            {route.page === "escalacao" && <LineupPage navigate={navigate} />}
            {route.page === "partida" && <MatchPage navigate={navigate} />}
            {route.page === "pos" && <PostMatchPage matchId={route.matchId} navigate={navigate} />}
            {route.page === "encerramento" && <EndPage navigate={navigate} />}
          </>
        )}
      </main>
      <footer className="footer muted small">SquadForce · Football Strategy Game</footer>
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
