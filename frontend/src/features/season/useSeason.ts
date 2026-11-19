import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../api/client";
import { getSeason, listClubs } from "../../api/endpoints";
import { useSession } from "../../app/SessionContext";
import type { SeasonState } from "../../types/api";

let clubCache: Map<number, string> | null = null;

/** Nomes curtos dos clubes (catálogo), carregados uma vez. */
export function useClubNames(): Map<number, string> {
  const [names, setNames] = useState<Map<number, string>>(clubCache ?? new Map());
  useEffect(() => {
    if (clubCache) return;
    listClubs({ limit: 200 })
      .then((p) => {
        clubCache = new Map(p.items.map((c) => [c.club_uid, c.short_name || c.name]));
        setNames(clubCache);
      })
      .catch(() => undefined);
  }, []);
  return names;
}

export function resetClubCache() {
  clubCache = null;
}

/**
 * Estado da temporada no servidor. Recarrega ao receber eventos `season.*` pelo WebSocket
 * (reconexão automática) e quando `refresh` é chamado após um comando.
 */
export function useSeason() {
  const { session, subscribe, reload } = useSession();
  const sid = session?.status === "active" && (session.phase === "competition" || session.phase === "finished") ? session.id : null;
  const [state, setState] = useState<SeasonState | null>(null);
  const [loading, setLoading] = useState(false);
  const [notStarted, setNotStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  const refresh = useCallback(async () => {
    if (!sid) return;
    const mine = ++seq.current;
    setLoading(true);
    try {
      const s = await getSeason(sid);
      if (mine !== seq.current) return; // resposta antiga: descarta (versões fora de ordem)
      setState(s);
      setNotStarted(false);
      setError(null);
      // a fase da sessão muda no servidor quando a temporada termina: sincroniza a versão da sessão
      if (s.phase === "finished" && session?.phase !== "finished") void reload();
    } catch (e) {
      if (mine !== seq.current) return;
      if (e instanceof ApiError && e.code === "SEASON_NOT_FOUND") {
        setState(null);
        setNotStarted(true);
      } else setError(e instanceof ApiError ? e.message : "Falha ao carregar a competição.");
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [sid, session?.phase, reload]);

  useEffect(() => {
    setState(null);
    void refresh();
  }, [refresh]);

  useEffect(
    () =>
      subscribe((msg) => {
        if (msg.type.startsWith("season.")) void refresh();
      }),
    [subscribe, refresh],
  );

  return { sid, state, setState, loading, notStarted, error, refresh };
}
