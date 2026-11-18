import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { getTrading, getTradingSquads } from "../../api/endpoints";
import type { TradingSquad, TradingState } from "../../types/api";

/** Estado do mercado: consulta periódica (relógio do servidor) + elencos recarregados após cada troca. */
export function useTrading(sessionId: string | null, enabled: boolean, pollMs = 800) {
  const [state, setState] = useState<TradingState | null>(null);
  const [squads, setSquads] = useState<TradingSquad[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState(0);
  const [now, setNow] = useState(() => performance.now());
  const inflight = useRef(false);
  const tradesSeen = useRef(-1);

  const loadSquads = useCallback(async () => {
    if (!sessionId) return;
    try {
      setSquads(await getTradingSquads(sessionId));
    } catch {
      /* mantém a última versão; a próxima consulta tenta de novo */
    }
  }, [sessionId]);

  const refresh = useCallback(async () => {
    if (!sessionId || inflight.current) return;
    inflight.current = true;
    try {
      const s = await getTrading(sessionId);
      setState(s);
      setFetchedAt(performance.now());
      setError(null);
      if (s.history.length !== tradesSeen.current) {
        tradesSeen.current = s.history.length;
        void loadSquads();
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao consultar o mercado.");
    } finally {
      inflight.current = false;
    }
  }, [sessionId, loadSquads]);

  useEffect(() => {
    if (!enabled || !sessionId) return;
    void refresh();
    const poll = setInterval(() => void refresh(), pollMs);
    const clock = setInterval(() => setNow(performance.now()), 200);
    return () => {
      clearInterval(poll);
      clearInterval(clock);
    };
  }, [enabled, sessionId, refresh, pollMs]);

  const elapsed = state ? Math.max(0, now - fetchedAt) : 0;
  const left = (ms: number) => Math.max(0, ms - elapsed);
  return { state, squads, error, refresh, left, remainingMs: state ? left(state.remaining_ms) : 0 };
}
