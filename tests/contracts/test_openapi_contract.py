"""Contratos: endpoints obrigatórios, esquema de erro e sincronia com docs/api/openapi.json."""

import json
from pathlib import Path

import pytest

from services.gateway.app import create_app
from squadforce_shared.contracts import (
    ClubPage,
    CompetitionOptions,
    ErrorResponse,
    HealthResponse,
    PlayerPage,
    SessionOut,
)

ROOT = Path(__file__).resolve().parents[2]
OPENAPI_FILE = ROOT / "docs" / "api" / "openapi.json"

REQUIRED = [
    ("get", "/api/health"),
    ("get", "/api/catalog/clubs"),
    ("get", "/api/catalog/players"),
    ("post", "/api/imports/clubs"),
    ("post", "/api/imports/players"),
    ("post", "/api/sessions"),
    ("get", "/api/sessions/{session_id}"),
    ("post", "/api/sessions/{session_id}/close"),
    ("get", "/api/competitions/options"),
]


@pytest.fixture(scope="module")
def spec():
    return create_app().openapi()


@pytest.mark.parametrize("method,path", REQUIRED)
def test_required_endpoints_exist(spec, method, path):
    assert method in spec["paths"][path]


@pytest.mark.parametrize("method,path", [r for r in REQUIRED if r[0] == "post"])
def test_mutating_endpoints_declare_idempotency_key(spec, method, path):
    params = spec["paths"][path][method].get("parameters", [])
    assert any(p["name"] == "Idempotency-Key" and p["in"] == "header" for p in params)


def test_error_schema_is_published(spec):
    err = spec["components"]["schemas"]["ErrorBody"]
    assert set(err["required"]) >= {"code", "message", "retryable"}


def test_committed_openapi_is_in_sync(spec):
    assert OPENAPI_FILE.exists(), "Gere com: python scripts/export_openapi.py"
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(spec)), "OpenAPI desatualizado: rode scripts/export_openapi.py"


def test_responses_validate_against_models(loaded_client):
    from conftest import create_session

    HealthResponse.model_validate(loaded_client.get("/api/health").json())
    ClubPage.model_validate(loaded_client.get("/api/catalog/clubs").json())
    PlayerPage.model_validate(loaded_client.get("/api/catalog/players").json())
    CompetitionOptions.model_validate(loaded_client.get("/api/competitions/options").json())
    SessionOut.model_validate(create_session(loaded_client).json())
    ErrorResponse.model_validate(loaded_client.get("/api/sessions/x").json())
    ErrorResponse.model_validate(loaded_client.get("/api/rota-inexistente").json())


def test_options_contract_matches_game_design(loaded_client):
    o = loaded_client.get("/api/competitions/options").json()
    assert o["league"] == {"min_clubs": 2, "max_clubs": 20, "rounds": ["single", "double"]}
    assert o["cup"] == {"allowed_sizes": [2, 4, 8, 16, 32]}
    assert o["available_clubs"] == 4 and o["catalog_ready"] is True
