import { useCallback, useRef, useState } from "react";
import { ApiError, newIdempotencyKey } from "../../api/client";

/**
 * Comando POST com proteção contra duplicação: botão desabilitado durante a chamada e a MESMA
 * Idempotency-Key em repetições automáticas (falha de rede). Uma nova chave só após a resposta.
 */
export function useCommand() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const keyRef = useRef(newIdempotencyKey());
  const running = useRef(false);

  const run = useCallback(async <T,>(fn: (key: string) => Promise<T>): Promise<T | undefined> => {
    if (running.current) return undefined;
    running.current = true;
    setBusy(true);
    setError(null);
    try {
      return await fn(keyRef.current);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(0, { code: "UNKNOWN", message: "Falha inesperada.", retryable: true, details: {} }));
      return undefined;
    } finally {
      keyRef.current = newIdempotencyKey();
      running.current = false;
      setBusy(false);
    }
  }, []);

  return { busy, error, setError, run };
}
