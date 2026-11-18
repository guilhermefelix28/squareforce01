import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getHealth } from "../api/endpoints";
import type { Health } from "../types/api";

export type Connection = "checking" | "online" | "offline";

export function useHealth(pollMs = 10_000) {
  const [health, setHealth] = useState<Health | null>(null);
  const [connection, setConnection] = useState<Connection>("checking");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const h = await getHealth();
      setHealth(h);
      setConnection("online");
      setError(null);
    } catch (e) {
      setConnection("offline");
      setError(e instanceof ApiError ? e.message : "Falha de comunicação com o servidor.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (!pollMs) return;
    const id = setInterval(() => void refresh(), pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { health, connection, error, refresh };
}
