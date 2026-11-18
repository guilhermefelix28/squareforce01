"""Idempotência de comandos que alteram estado.

Contrato: todo POST mutável exige o cabeçalho `Idempotency-Key` (8–128 caracteres).
- Mesma chave + mesma requisição  -> devolve a resposta original (cabeçalho Idempotent-Replayed: true).
- Mesma chave + requisição diferente -> 409 IDEMPOTENCY_KEY_REUSED.
- Mesma chave ainda em execução -> 409 REQUEST_IN_PROGRESS (retryable).
Armazenamento apenas em memória, com expiração; não é persistido.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from squadforce_shared.errors import AppError, ErrorCode

KEY_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")


@dataclass
class StoredResponse:
    fingerprint: str
    status_code: int
    body: dict[str, Any]
    expires_at: float


def fingerprint(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode() if isinstance(p, str) else p)
        h.update(b"\x00")
    return h.hexdigest()


def validate_key(key: str | None) -> str:
    if not key:
        raise AppError(
            400, ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            "Cabeçalho Idempotency-Key obrigatório para comandos que alteram estado.",
        )
    if not KEY_RE.match(key):
        raise AppError(
            400, ErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            "Idempotency-Key inválida: use de 8 a 128 caracteres [A-Za-z0-9_-:.].",
        )
    return key


class IdempotencyStore:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 2000, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._done: dict[tuple[str, str], StoredResponse] = {}
        self._in_flight: dict[tuple[str, str], str] = {}

    def _purge(self) -> None:
        now = self._clock()
        for k in [k for k, v in self._done.items() if v.expires_at <= now]:
            del self._done[k]
        while len(self._done) > self._max:
            del self._done[next(iter(self._done))]

    def execute(
        self, scope: str, key: str, fp: str, fn: Callable[[], tuple[int, dict[str, Any]]]
    ) -> tuple[int, dict[str, Any], bool]:
        """Executa `fn` no máximo uma vez por (scope, key). Retorna (status, body, replayed)."""
        k = (scope, key)
        with self._lock:
            self._purge()
            stored = self._done.get(k)
            if stored is not None:
                if stored.fingerprint != fp:
                    raise AppError(
                        409, ErrorCode.IDEMPOTENCY_KEY_REUSED,
                        "Esta Idempotency-Key já foi usada com outra requisição.",
                    )
                return stored.status_code, stored.body, True
            if k in self._in_flight:
                if self._in_flight[k] != fp:
                    raise AppError(
                        409, ErrorCode.IDEMPOTENCY_KEY_REUSED,
                        "Esta Idempotency-Key já está em uso por outra requisição.",
                    )
                raise AppError(
                    409, ErrorCode.REQUEST_IN_PROGRESS,
                    "A mesma operação ainda está em processamento.", retryable=True,
                )
            self._in_flight[k] = fp
        try:
            try:
                status, body = fn()
            except AppError as err:
                # Resultados determinísticos (validação) são memorizados; falhas transitórias não.
                if not err.retryable and err.status_code == 422:
                    self._store(k, fp, err.status_code, err.to_body())
                raise
            self._store(k, fp, status, body)
            return status, body, False
        finally:
            with self._lock:
                self._in_flight.pop(k, None)

    def _store(self, k: tuple[str, str], fp: str, status: int, body: dict[str, Any]) -> None:
        with self._lock:
            self._done[k] = StoredResponse(fp, status, body, self._clock() + self._ttl)
