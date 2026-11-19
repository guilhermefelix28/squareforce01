"""Inicializa o servidor real (uvicorn, processo separado) e comunica via HTTP/WebSocket reais."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    port = _free_port()
    env = {**os.environ, "SQUADFORCE_DB_PATH": str(tmp_path / "e2e.db"), "SQUADFORCE_GRAPHICS_DIR": str(tmp_path)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "services.gateway", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.kill()
        pytest.fail("servidor não iniciou: " + proc.stdout.read().decode(errors="replace"))
    yield base, tmp_path
    proc.terminate()
    proc.wait(10)


def test_server_boots_and_serves_contracts(server):
    base, tmp = server
    h = httpx.get(f"{base}/api/health").json()
    assert h["status"] == "ok" and h["database"]["schema_version"] == 3
    assert (tmp / "e2e.db").exists()
    assert httpx.get(f"{base}/api/competitions/options").json()["cup"]["allowed_sizes"] == [2, 4, 8, 16, 32]
    assert httpx.get(f"{base}/openapi.json").status_code == 200
    r = httpx.post(f"{base}/api/sessions", json={})
    assert r.status_code in (400, 422) and "error" in r.json()
