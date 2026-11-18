"""Contratos: endpoints obrigatórios, esquema de erro e sincronia com docs/api/openapi.json."""

import json
from pathlib import Path

import pytest

from services.gateway.app import create_app
from squadforce_shared.contracts import (
    ClubPage,
    CompetitionOptions,
    CompetitionOut,
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
    ("get", "/api/sessions/{session_id}/competition"),  # Entrega 2
    ("post", "/api/sessions/{session_id}/auction/start"),  # Entrega 3
    ("get", "/api/sessions/{session_id}/auction"),
    ("post", "/api/sessions/{session_id}/auction/bids"),
    ("get", "/api/sessions/{session_id}/auction/summary"),
    ("post", "/api/sessions/{session_id}/trading/start"),  # Entrega 4
    ("get", "/api/sessions/{session_id}/trading"),
    ("get", "/api/sessions/{session_id}/trading/squads"),
    ("post", "/api/sessions/{session_id}/trading/proposals"),
    ("post", "/api/sessions/{session_id}/trading/proposals/{proposal_id}/{action}"),
]


def test_auction_contracts_never_expose_hidden_fields(spec):
    schemas = spec["components"]["schemas"]
    for name in ("AuctionPlayerOut", "AuctionStateOut", "AuctionRoundOut", "AuctionClubOut", "AuctionSquadOut",
                 "TradingPlayerOut", "TradingClubOut", "TradingSquadOut", "ProposalOut", "TradingStateOut", "TradeRecordOut"):
        props = set(schemas[name]["properties"])
        assert not props & {"overall", "attributes", "market_value", "personality", "bids", "reputation"}, name


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
    s = SessionOut.model_validate(create_session(loaded_client).json())
    CompetitionOut.model_validate(loaded_client.get(f"/api/sessions/{s.id}/competition").json())
    ErrorResponse.model_validate(loaded_client.get("/api/sessions/x").json())
    ErrorResponse.model_validate(loaded_client.get("/api/rota-inexistente").json())


def test_options_contract_matches_game_design(loaded_client):
    o = loaded_client.get("/api/competitions/options").json()
    assert o["league"] == {"min_clubs": 2, "max_clubs": 20, "rounds": ["single", "double"]}
    assert o["cup"] == {"allowed_sizes": [2, 4, 8, 16, 32]}
    assert o["available_clubs"] == 4 and o["catalog_ready"] is True
    assert o["eligible_clubs"] == 4 and o["division_counts"] == {"A": 2, "B": 2}
