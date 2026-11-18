"""Infraestrutura WebSocket: snapshot, ping/pong, reconexão e aviso de encerramento."""

import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import create_session, key


def test_snapshot_ping_and_close_event(loaded_client):
    s = create_session(loaded_client).json()
    with loaded_client.websocket_connect(f"/ws/sessions/{s['id']}") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "session.snapshot" and snap["version"] == 1 and snap["data"]["id"] == s["id"]
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"
        ws.send_json({"type": "bid"})
        assert ws.receive_json()["data"]["code"] == "UNSUPPORTED_MESSAGE"

        loaded_client.post(f"/api/sessions/{s['id']}/close", headers={"Idempotency-Key": key()})
        evt = ws.receive_json()
        assert evt["type"] == "session.closed" and evt["version"] == 2


def test_reconnection_receives_current_state(loaded_client):
    s = create_session(loaded_client).json()
    with loaded_client.websocket_connect(f"/ws/sessions/{s['id']}") as ws:
        assert ws.receive_json()["version"] == 1
    # conexão caiu; o estado continua na memória e a reconexão recebe o snapshot atual
    with loaded_client.websocket_connect(f"/ws/sessions/{s['id']}") as ws:
        assert ws.receive_json()["data"]["status"] == "active"


def test_unknown_session_socket_is_refused(loaded_client):
    with pytest.raises(WebSocketDisconnect) as e:
        with loaded_client.websocket_connect("/ws/sessions/nao-existe") as ws:
            ws.receive_json()
    assert e.value.code == 4404
