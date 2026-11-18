"""Importação do arquivo REAL Dados/jogadores.xlsx (somente leitura) em banco temporário."""

import hashlib

import pytest

from conftest import REAL_PLAYERS_XLSX, post_import

pytestmark = [
    pytest.mark.real_data,
    pytest.mark.skipif(not REAL_PLAYERS_XLSX.exists(), reason="Dados/jogadores.xlsx ausente"),
]


def test_real_file_imports_and_is_not_modified(client, settings):
    content = REAL_PLAYERS_XLSX.read_bytes()
    digest = hashlib.sha256(content).hexdigest()

    clubs = post_import(client, "clubs", content, name="jogadores.xlsx")
    assert clubs.status_code == 200, clubs.json()
    assert clubs.json()["sheet"] == "Jogadores"
    assert clubs.json()["rows_imported"] == 40  # GDD: catálogo de 40 clubes

    players = post_import(client, "players", content, name="jogadores.xlsx")
    body = players.json()
    assert players.status_code == 200, body
    assert body["critical_error_count"] == 0
    assert body["rows_read"] == 1585
    assert body["rows_skipped"] == 11  # linhas sem unique_id na planilha real
    assert body["rows_imported"] == 1574
    assert {w["code"] for w in body["warnings"]} == {"ROW_WITHOUT_ID"}

    assert client.get("/api/catalog/players").json()["total"] == 1574
    gk = client.get("/api/catalog/players", params={"position": "GOL"}).json()["total"]
    assert gk > 0
    # nenhum arquivo foi copiado para o projeto e o original permanece idêntico
    assert hashlib.sha256(REAL_PLAYERS_XLSX.read_bytes()).hexdigest() == digest
    assert not list(settings.db_path.parent.glob("*.xlsx"))


def test_real_catalog_supports_all_competition_sizes(client):
    content = REAL_PLAYERS_XLSX.read_bytes()
    post_import(client, "clubs", content)
    post_import(client, "players", content)
    opts = client.get("/api/competitions/options").json()
    assert opts["available_clubs"] == 40 and opts["catalog_ready"]
