"""Regressão do motor esportivo: partidas SEM controladores táticos devem permanecer idênticas bit a bit.

- `LEGACY`: hashes do motor da Entrega 5 (commit 8a93e80, parâmetros `provisorio-0.5`), capturados ANTES do gancho
  de IA tática da Entrega 6. Continuam valendo quando executados com o parâmetro antigo (`xg_intercept=0.75`):
  isso prova que o CÓDIGO do motor não mudou desde então.
- `CALIBRATED`: hashes com os parâmetros atuais `provisorio-0.6` (Entrega 9: calibração do intercepto do xG
  0,75 → 0,88 contra as faixas de docs/homologacao/criterios.md). Única diferença: esse parâmetro.
Se um hash mudar, o comportamento do motor mudou: só atualize com justificativa registrada e nova versão.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from services.match_engine.engine import simulate
from services.match_engine.params import DEFAULT_PARAMS
from services.match_engine.types import PostureChange
from support.match_fixtures import match, team


def digest(res) -> str:
    h = hashlib.sha256()
    for e in res.events:
        h.update(json.dumps([e.seq, e.second, e.period, e.type, e.side, e.player, e.other, sorted(e.data.items())],
                            default=str).encode())
    h.update(json.dumps([res.score, res.official_score, [(r.player, r.rating) for r in res.ratings]]).encode())
    return h.hexdigest()[:16]


SCENARIOS = {
    "base-1": lambda p: simulate(match(1), p),
    "base-2": lambda p: simulate(match(2), p),
    "base-3": lambda p: simulate(match(3), p),
    "base-7": lambda p: simulate(match(7), p),
    "base-42": lambda p: simulate(match(42), p),
    "posture-21": lambda p: simulate(match(21), p, decisions=[PostureChange(1800.0, 0, "ofensiva"),
                                                               PostureChange(4000.0, 1, "retranca")]),
    "knockout-5": lambda p: simulate(dataclasses.replace(match(5), knockout=True), p),
    "uneven-9": lambda p: simulate(match(9, team(1, level=72), team(2, level=55)), p),
}
LEGACY = {
    "base-1": "f08141ac916f8f83", "base-2": "944dac772e606d3f", "base-3": "8527ff43d243d173",
    "base-7": "995ddf35f62eebc5", "base-42": "cb9b9063f8100343", "posture-21": "d3cf68172816ea4e",
    "knockout-5": "7bbe667f961d0274", "uneven-9": "2a610da710f0216b",
}
CALIBRATED = {
    "base-1": "1de20ccfd3725c29", "base-2": "0190d4c025f15f09", "base-3": "c353ef8ce2814aa8",
    "base-7": "007338e7615adf56", "base-42": "391c89419d0770ef", "posture-21": "0a56522412d79da9",
    "knockout-5": "e7f491174f31f381", "uneven-9": "4eb3d477bd09fe01",
}
LEGACY_PARAMS = dataclasses.replace(DEFAULT_PARAMS, xg_intercept=0.75)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_engine_code_unchanged_since_delivery_5(name):
    assert digest(SCENARIOS[name](LEGACY_PARAMS)) == LEGACY[name]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_engine_output_with_calibrated_parameters(name):
    assert DEFAULT_PARAMS.version == "provisorio-0.6"
    assert digest(SCENARIOS[name](DEFAULT_PARAMS)) == CALIBRATED[name]
