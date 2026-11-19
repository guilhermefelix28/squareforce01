import { useEffect, useRef, useState } from "react";
import { useSound } from "../audio/crowd";
import { PhaseStepper, phaseStep } from "../components/GameUi";
import { useHealth } from "../hooks/useHealth";
import { AdminPage } from "../pages/AdminPage";
import { AuctionPage } from "../pages/AuctionPage";
import { EndPage } from "../pages/EndPage";
import { HomePage } from "../pages/HomePage";
import { LineupPage } from "../pages/LineupPage";
import { MatchPage } from "../pages/MatchPage";
import { PostMatchPage } from "../pages/PostMatchPage";
import { SeasonPage, type SeasonTab } from "../pages/SeasonPage";
import { SessionPage } from "../pages/SessionPage";
import { TacticPage } from "../pages/TacticPage";
import { TradingPage } from "../pages/TradingPage";
import type { Session } from "../types/api";
import { phaseHome } from "./phase";
import { SessionProvider, useSession } from "./SessionContext";
import { useTheme } from "./theme";

export type Route =
  | { page: "home" | "admin" | "session" | "tatica" | "auction" | "trading" | "escalacao" | "partida" | "encerramento" }
  | { page: "temporada"; tab: SeasonTab }
  | { page: "pos"; matchId: string };

const SEASON_TABS: SeasonTab[] = ["central", "elenco", "calendario", "classificacao", "estatisticas", "resultados"];
const SIMPLE = ["home", "admin", "session", "tatica", "auction", "trading", "escalacao", "partida", "encerramento"] as const;

export function parseHash(hash: string): Route {
  const [head, arg] = hash.replace(/^#\/?/, "").split("/");
  if (head === "temporada") return { page: "temporada", tab: SEASON_TABS.includes(arg as SeasonTab) ? (arg as SeasonTab) : "central" };
  if (head === "pos" && arg) return { page: "pos", matchId: decodeURIComponent(arg) };
  if (head === "nova") return { page: "session" };
  return { page: (SIMPLE as readonly string[]).includes(head) ? (head as (typeof SIMPLE)[number]) : "home" };
}

/** Atalhos do menu "⋯" para a fase atual (a navegação principal é a ação de cada tela). */
export function navItems(session: Session | null): { hash: string; page: string; label: string }[] {
  const phase = session?.status === "active" ? session.phase : null;
  const items = [{ hash: "#/home", page: "home", label: "Início" }];
  if (phase === "setup") items.push({ hash: "#/tatica", page: "tatica", label: "Tática" });
  if (phase === "setup" || phase === "auction" || phase === "squad_completion") items.push({ hash: "#/auction", page: "auction", label: "Leilão" });
  if (phase === "squad_completion" || phase === "trading") items.push({ hash: "#/trading", page: "trading", label: "Mercado" });
  if (phase === "competition" || phase === "finished") {
    items.push({ hash: "#/temporada/central", page: "temporada", label: "Central" });
    if (phase === "competition") {
      items.push({ hash: "#/escalacao", page: "escalacao", label: "Escalação" });
      items.push({ hash: "#/partida", page: "partida", label: "Partida" });
    } else items.push({ hash: "#/encerramento", page: "encerramento", label: "Encerramento" });
  }
  items.push({ hash: "#/session", page: "session", label: phase ? "Competição (detalhes e encerrar)" : "Nova partida" });
  return items;
}

export { phaseHome };

function Menu({ items, current }: { items: ReturnType<typeof navItems>; current: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    window.addEventListener("keydown", close);
    return () => {
      window.removeEventListener("mousedown", close);
      window.removeEventListener("keydown", close);
    };
  }, [open]);
  return (
    <div className="menu" ref={ref}>
      <button type="button" className="btn btn--ghost btn--small icon-btn" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        ☰ <span className="visually-hidden">Menu</span>
      </button>
      {open && (
        <nav className="menu__list" aria-label="Menu do jogo">
          {items.map((p) => (
            <a key={p.hash} href={p.hash} aria-current={current === p.page ? "page" : undefined} onClick={() => setOpen(false)}>
              {p.label}
            </a>
          ))}
        </nav>
      )}
    </div>
  );
}

function Shell() {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  const { theme, toggle } = useTheme();
  const sound = useSound();
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

  // mudança de fase vinda do servidor: o jogo conduz à tela da nova fase
  const phaseKey = session?.status === "active" ? `${session.id}:${session.phase}:${session.user_formation ?? ""}` : null;
  const lastPhase = useRef(phaseKey);
  useEffect(() => {
    const prev = lastPhase.current;
    lastPhase.current = phaseKey;
    if (!prev || !phaseKey || prev === phaseKey || prev.split(":")[0] !== phaseKey.split(":")[0]) return;
    const target = phaseHome(session);
    const here = window.location.hash || "#/home";
    // no leilão/mercado, a própria tela mostra o resumo e oferece o próximo passo
    if (here.startsWith("#/auction") || here.startsWith("#/trading") || here.startsWith("#/temporada") || here.startsWith("#/partida") || here.startsWith("#/pos")) return;
    if (here !== target) navigate(target);
  }, [phaseKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const importsBlocked = session?.status === "active" || !!health?.active_session;
  const active = session?.status === "active";
  const step = active ? phaseStep(session.phase, !!session.user_formation) : null;

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
          <img src="/brand/logo.png" alt="SquadForce" />
        </a>
        {step && <PhaseStepper current={step} />}
        <div className="topbar__end">
          <span className={`conn conn--${connection}`} role="status" aria-live="polite" title="Conexão com o servidor">
            <span className="conn__dot" aria-hidden />
            <span className="hide-sm">
              {connection === "online" ? (active && !live ? "Reconectando sessão…" : "Servidor online") : connection === "offline" ? "Servidor offline" : "Conectando…"}
            </span>
          </span>
          <button type="button" className="btn btn--ghost btn--small icon-btn" onClick={sound.toggle} aria-pressed={sound.on}
            aria-label={sound.on ? "Desligar som da torcida" : "Ligar som da torcida"} title="Som da torcida">
            {sound.on ? "🔊" : "🔇"}
          </button>
          <button type="button" className="btn btn--ghost btn--small icon-btn" onClick={toggle} aria-label={`Alternar para tema ${theme === "dark" ? "claro" : "escuro"}`}>
            {theme === "dark" ? "☀" : "☾"}
          </button>
          <Menu items={navItems(session)} current={route.page} />
        </div>
      </header>
      <main className="content" id="conteudo" tabIndex={-1}>
        {lostMessage && route.page !== "session" && (
          <div className="banner banner--warning" role="alert">
            <strong>Sua competição não pode mais ser recuperada.</strong> {lostMessage} O servidor não guarda progresso
            (sem salvamento persistente). <a href="#/session">Iniciar nova partida</a>
          </div>
        )}
        {restoring ? (
          <p className="muted" role="status">Reconectando à sessão…</p>
        ) : (
          <>
            {route.page === "home" && (
              <HomePage health={health} connection={connection} error={error} session={session} onRetry={refresh}
                onStart={() => navigate("#/session")} continueTo={() => navigate(phaseHome(session))} navigate={navigate} />
            )}
            {route.page === "admin" && <AdminPage importsBlocked={importsBlocked} onDataChanged={refresh} health={health} />}
            {route.page === "session" && <SessionPage onSessionChanged={refresh} navigate={navigate} />}
            {route.page === "tatica" && <TacticPage navigate={navigate} />}
            {route.page === "auction" && <AuctionPage go={go} navigate={navigate} />}
            {route.page === "trading" && <TradingPage go={go} navigate={navigate} />}
            {route.page === "temporada" && <SeasonPage tab={route.tab} navigate={navigate} />}
            {route.page === "escalacao" && <LineupPage navigate={navigate} />}
            {route.page === "partida" && <MatchPage navigate={navigate} />}
            {route.page === "pos" && <PostMatchPage matchId={route.matchId} navigate={navigate} />}
            {route.page === "encerramento" && <EndPage navigate={navigate} />}
          </>
        )}
      </main>
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
