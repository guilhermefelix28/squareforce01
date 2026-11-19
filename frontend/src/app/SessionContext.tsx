/**
 * Sessão ativa no cliente.
 * O servidor é a fonte da verdade: o navegador guarda apenas o ID para reconexão automática
 * (GDD seção 23). Se o servidor perdeu o estado, a competição não pode ser restaurada.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { getSession, sessionSocketUrl } from "../api/endpoints";
import type { Session, WsMessage } from "../types/api";

const STORAGE_KEY = "squadforce.sessionId";

function readStoredId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}
function writeStoredId(id: string | null) {
  try {
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* armazenamento indisponível: apenas sem reconexão após recarregar */
  }
}

interface SessionCtx {
  session: Session | null;
  restoring: boolean;
  lostMessage: string | null;
  live: boolean;
  setSession: (s: Session | null) => void;
  reload: () => Promise<void>;
  /** Recebe os eventos do canal WebSocket (ex.: season.round_played). Retorna a função de cancelamento. */
  subscribe: (fn: (msg: WsMessage) => void) => () => void;
}

const Ctx = createContext<SessionCtx | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSessionState] = useState<Session | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [lostMessage, setLostMessage] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const retryRef = useRef(0);
  const listeners = useRef(new Set<(msg: WsMessage) => void>());
  const subscribe = useCallback((fn: (msg: WsMessage) => void) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  }, []);

  const setSession = useCallback((s: Session | null) => {
    setSessionState((prev) => (prev && s && prev.id === s.id && prev.version > s.version ? prev : s));
    writeStoredId(s && s.status === "active" ? s.id : null);
    if (s) setLostMessage(null);
  }, []);

  const reload = useCallback(async () => {
    const id = readStoredId();
    if (!id) {
      setRestoring(false);
      return;
    }
    try {
      setSession(await getSession(id));
    } catch (e) {
      if (e instanceof ApiError && e.code === "SESSION_NOT_FOUND") {
        writeStoredId(null);
        setSessionState(null);
        setLostMessage(e.message);
      }
    } finally {
      setRestoring(false);
    }
  }, [setSession]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // Canal WebSocket com reconexão automática enquanto a sessão estiver ativa.
  const activeId = session?.status === "active" ? session.id : null;
  useEffect(() => {
    if (!activeId || typeof WebSocket === "undefined") return;
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const connect = () => {
      ws = new WebSocket(sessionSocketUrl(activeId));
      ws.onopen = () => {
        retryRef.current = 0;
        setLive(true);
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(String(ev.data)) as WsMessage;
        listeners.current.forEach((fn) => fn(msg));
        if (msg.type === "session.snapshot" || msg.type === "session.closed") {
          setSession(msg.data as unknown as Session);
          if (msg.type === "session.closed") stopped = true;
        }
      };
      ws.onclose = (ev) => {
        setLive(false);
        if (stopped) return;
        if (ev.code === 4404) {
          void reload();
          return;
        }
        const delay = Math.min(15_000, 1000 * 2 ** retryRef.current++);
        timer = setTimeout(connect, delay);
      };
    };
    connect();
    const ping = setInterval(() => ws?.readyState === 1 && ws.send(JSON.stringify({ type: "ping" })), 25_000);
    return () => {
      stopped = true;
      clearInterval(ping);
      clearTimeout(timer);
      ws?.close();
    };
  }, [activeId, reload, setSession]);

  return (
    <Ctx.Provider value={{ session, restoring, lostMessage, live, setSession, reload, subscribe }}>{children}</Ctx.Provider>
  );
}

export function useSession(): SessionCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession fora de SessionProvider");
  return ctx;
}
