"""Inicialização dos serviços, health check e imagens por identificador."""

from fastapi.testclient import TestClient

from services.gateway.app import create_app


def test_startup_creates_schema_and_reports_services(client, settings):
    assert settings.db_path.exists()
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["database"] == {"status": "ok", "schema_version": 3, "clubs": 0, "players": 0}
    assert h["services"]["data"] == h["services"]["session"] == "ready"
    assert h["services"]["auction"] == "ready"  # AuctionModel oficial carregado por padrão
    assert h["services"]["bot_ai"] == h["services"]["match_engine"] == "ready"  # regressão: não mais "planned" fixo


def test_health_reports_degraded_database(settings, tmp_path):
    app = create_app(settings)
    with TestClient(app) as c:
        app.state.container.data.db_path = tmp_path / "pasta-inexistente" / "x.db"
        h = c.get("/api/health").json()
    assert h["status"] == "degraded" and h["database"]["status"] == "error"


def test_cors_allows_frontend_origin(client):
    r = client.options(
        "/api/sessions",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "Idempotency-Key, Content-Type"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_assets_by_identifier(client, settings):
    (settings.graphics_dir / "Clubes" / "club_100.png").write_bytes(b"\x89PNG fake")
    (settings.graphics_dir / "Faces" / "55.jpg").write_bytes(b"\xff\xd8 fake")
    assert client.get("/api/assets/clubs/100").content == b"\x89PNG fake"
    assert client.get("/api/assets/players/55").content == b"\xff\xd8 fake"
    r = client.get("/api/assets/clubs/101")
    assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/api/assets/clubs/abc").status_code == 422  # só identificadores inteiros
    assert client.get("/api/assets/clubs/..%2F..%2Fsecret").status_code == 404  # sem travessia de diretório
