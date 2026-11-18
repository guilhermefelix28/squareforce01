"""Comportamento da IA tática em lotes (Entrega 6): coerência, estabilidade e ausência de trapaça."""

from __future__ import annotations

import pytest

from services.bot_ai.tactics_report import run_behaviour
from support.match_fixtures import team

pytestmark = pytest.mark.simulation


@pytest.fixture(scope="module")
def both_ai():
    return run_behaviour(team(1), team(2), 150, seed=3, personalities=("aggressive", "conservative"))


def test_all_matches_with_bots_are_valid(both_ai):
    assert both_ai.invalid == 0


def test_changes_are_not_excessive(both_ai):
    assert both_ai.changes_per_team < 4.0
    assert both_ai.max_changes <= 8


def test_reactions_are_coherent_with_the_score(both_ai):
    assert both_ai.toward_attack_when_trailing >= 0.8  # perdendo: quase toda mudança aumenta o ataque
    assert both_ai.toward_defense_when_leading >= 0.8  # vencendo: quase toda mudança protege
    assert both_ai.late_trailing_attacking_share >= 0.6
    assert both_ai.late_leading_defending_share >= 0.6


def test_ai_has_no_artificial_advantage_but_is_not_worse_than_static():
    """IA × equipe estática de mesma força: sem bônus de atributos, a vantagem só pode vir da gestão de risco."""
    r = run_behaviour(team(1), team(2), 300, seed=5, ai_both=False)
    assert r.invalid == 0
    assert r.ai_points_per_game >= r.static_points_per_game - 0.15  # não piora de forma relevante
    assert r.ai_points_per_game <= r.static_points_per_game + 0.6  # nenhuma vantagem "milagrosa"
