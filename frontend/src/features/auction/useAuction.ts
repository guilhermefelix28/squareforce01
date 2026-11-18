import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { getAuction } from "../../api/endpoints";
import type { AuctionState } from "../../types/api";

/**
 * Estado do leilão com o servidor como relógio autoritativo: consulta periódica e contagem
 * regressiva local a partir dos tempos restantes informados na última resposta.
 */
export function useAuction(sessionId: string | null, enabled: boolean, pollMs = 800) {
  const [state, setState] = useState<AuctionState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fetchedAt, setFetchedAt] = useState(0);
  const [now, setNow] = useState(() => performance.now());
  const inflight = useRef(false);

  const refresh = useCallback(async () => {
    if (!sessionId || inflight.current) return;
    inflight.current = true;
    try {
      const s = await getAuction(sessionId);
      setState(s);
      setFetchedAt(performance.now());
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Falha ao consultar o leilão.");
    } finally {
      inflight.current = false;
    }
  }, [sessionId]);

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
  return {
    state,
    setState,
    error,
    refresh,
    roundRemainingMs: state?.round ? Math.max(0, state.round.remaining_ms - elapsed) : 0,
    globalRemainingMs: state ? Math.max(0, state.global_remaining_ms - elapsed) : 0,
  };
}
