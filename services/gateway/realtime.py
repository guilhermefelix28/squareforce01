"""Infraestrutura WebSocket (Entrega 1: somente snapshot, ping/pong e aviso de encerramento).

Canal: /ws/sessions/{session_id}
- Ao conectar: {"type": "session.snapshot", "session_id", "version", "data": SessionOut}
- Cliente envia {"type": "ping"} -> servidor responde {"type": "pong"}
- Ao encerrar a sessão: {"type": "session.closed", ...} e o socket é fechado (código 1000).
Reconexão: o cliente reabre o canal e compara `version` com o estado local.
Eventos de leilão, mercado e partidas pertencem a entregas futuras.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

from squadforce_shared.contracts import WsEnvelope

log = logging.getLogger("squadforce.realtime")


class SessionHub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets[session_id].add(ws)

    async def leave(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._sockets[session_id].discard(ws)
            if not self._sockets[session_id]:
                self._sockets.pop(session_id, None)

    def connections(self, session_id: str) -> int:
        return len(self._sockets.get(session_id, ()))

    async def broadcast(self, session_id: str, message: WsEnvelope, close_after: bool = False) -> None:
        async with self._lock:
            targets = list(self._sockets.get(session_id, ()))
        payload = message.model_dump(mode="json")
        for ws in targets:
            try:
                await ws.send_json(payload)
                if close_after:
                    await ws.close(code=1000)
            except Exception as exc:  # conexão já perdida: o cliente reconecta
                log.info("drop websocket for %s: %s", session_id, exc)
                await self.leave(session_id, ws)
