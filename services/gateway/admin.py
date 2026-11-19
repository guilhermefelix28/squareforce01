"""Área oculta de dados (decisão do responsável DR-04, 2026-11-19).

A senha é verificada SOMENTE no servidor; o login devolve um token aleatório guardado em memória (some ao
reiniciar o servidor). As importações exigem esse token no cabeçalho `X-Admin-Token`.
"""

from __future__ import annotations

import secrets
import threading


class AdminAuth:
    def __init__(self, password: str):
        self._password = password
        self._tokens: set[str] = set()
        self._lock = threading.Lock()

    def login(self, password: str) -> str | None:
        if not secrets.compare_digest(password.encode(), self._password.encode()):
            return None
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens.add(token)
        return token

    def check(self, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            return any(secrets.compare_digest(token, t) for t in self._tokens)
