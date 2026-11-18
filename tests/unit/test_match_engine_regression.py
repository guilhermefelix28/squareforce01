"""Regressão do motor esportivo: partidas SEM controladores táticos devem permanecer idênticas bit a bit.

Os hashes foram capturados com o motor da Entrega 5 (commit 8a93e80, parâmetros `provisorio-0.5`) ANTES de
adicionar o gancho de IA tática da Entrega 6. Se um hash mudar, o comportamento do motor mudou: só atualize
com justificativa técnica registrada e nova versão de parâmetros/motor.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pytest

from services.match_engine.engine import simulate
from services.match_engine.types import PostureChange
from support.match_fixtures import match, team


def digest(res) -> str:
    h = hashlib.sha256()
    for e in res.events:
        h.update(json.dumps([e.seq, e.second, e.period, e.type, e.side, e.player, e.other, sorted(e.data.items())],
                            default=str).encode())
    h.update(json.dumps([res.score, res.official_score, [(r.player, r.rating) for r in res.ratings]]).encode())
    return h.hexdigest()[:16]


CASES = {
    "base-1": (lambda: simulate(match(1)), "f08141ac916f8f83"),
    "base-2": (lambda: simulate(match(2)), "944dac772e606d3f"),
    "base-3": (lambda: simulate(match(3)), "8527ff43d243d173"),
    "base-7": (lambda: simulate(match(7)), "995ddf35f62eebc5"),
    "base-42": (lambda: simulate(match(42)), "cb9b9063f8100343"),
    "posture-21": (lambda: simulate(match(21), decisions=[PostureChange(1800.0, 0, "ofensiva"),
                                                          PostureChange(4000.0, 1, "retranca")]), "d3cf68172816ea4e"),
    "knockout-5": (lambda: simulate(dataclasses.replace(match(5), knockout=True)), "7bbe667f961d0274"),
    "uneven-9": (lambda: simulate(match(9, team(1, level=72), team(2, level=55))), "2a610da710f0216b"),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_engine_output_unchanged_without_tactical_controllers(name):
    run, expected = CASES[name]
    assert digest(run()) == expected
