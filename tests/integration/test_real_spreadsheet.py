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
    assert body["rows_skipped"] == 0
    assert body["rows_imported"] == 1585  # 11 linhas sem unique_id recebem ID genérico estável
    codes = [w["code"] for w in body["warnings"]]
    assert codes.count("GENERATED_ID") == 11
    assert codes.count("POSSIBLE_DUPLICATE_PERSON") == 2  # Larson e Samuel aparecem em 2 clubes

    assert client.get("/api/catalog/players").json()["total"] == 1585
    gk = client.get("/api/catalog/players", params={"position": "GOL"}).json()["total"]
    assert gk > 0
    # nenhum arquivo foi copiado para o projeto e o original permanece idêntico
    assert hashlib.sha256(REAL_PLAYERS_XLSX.read_bytes()).hexdigest() == digest
    assert not list(settings.db_path.parent.glob("*.xlsx"))


def test_real_catalog_supports_all_competition_sizes(client):
    content = REAL_PLAYERS_XLSX.read_bytes()
    clubs = post_import(client, "clubs", content).json()
    assert not [w for w in clubs["warnings"] if w["code"] == "CLUB_WITHOUT_DIVISION"]
    post_import(client, "players", content)
    opts = client.get("/api/competitions/options").json()
    assert opts["available_clubs"] == 40 and opts["catalog_ready"]
    assert opts["eligible_clubs"] == 40 and opts["division_counts"] == {"A": 20, "B": 20}


def test_generated_ids_are_stable_across_reimports(client):
    content = REAL_PLAYERS_XLSX.read_bytes()
    post_import(client, "clubs", content)
    post_import(client, "players", content)

    def generated():
        items = []
        for offset in range(0, 1585, 200):
            page = client.get("/api/catalog/players", params={"limit": 200, "offset": offset}).json()
            items += [p["unique_id"] for p in page["items"] if p["id_generated"]]
        return sorted(items)

    first = generated()
    assert len(first) == 11
    post_import(client, "players", content)
    assert generated() == first
