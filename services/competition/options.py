"""Opções de competição expostas em GET /api/competitions/options."""

from __future__ import annotations

from squadforce_shared.contracts import CompetitionOptions, CupOptions, LeagueOptions
from squadforce_shared.domain.competition import (
    CUP_SIZES,
    EligibleClub,
    LEAGUE_MAX_CLUBS,
    LEAGUE_MIN_CLUBS,
    LeagueRounds,
)


def competition_options(
    available_clubs: int, eligible: list[EligibleClub], catalog_ready: bool, imports_blocked: bool
) -> CompetitionOptions:
    counts = {"A": 0, "B": 0}
    for c in eligible:
        counts[c.division] += 1
    return CompetitionOptions(
        league=LeagueOptions(
            min_clubs=LEAGUE_MIN_CLUBS,
            max_clubs=LEAGUE_MAX_CLUBS,
            rounds=[LeagueRounds.SINGLE, LeagueRounds.DOUBLE],
        ),
        cup=CupOptions(allowed_sizes=list(CUP_SIZES)),
        available_clubs=available_clubs,
        eligible_clubs=len(eligible),
        division_counts=counts,
        catalog_ready=catalog_ready,
        imports_blocked=imports_blocked,
    )
