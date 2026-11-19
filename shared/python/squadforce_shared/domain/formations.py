"""Formações oficiais (PM-01), redefinidas pelo responsável em 2026-11-19 (DR-08 e DR-11).

Lista definida pelo responsável em DR-11: cada nome descreve as faixas DEF-VOL-ME-ATA (ou DEF-ME-ATA quando não
há volante). Usam somente os 7 códigos do GDD §3; linhas de 3 são três ZAG, linhas de 4 e 5 têm LD e LE. Toda
formação tem composição própria, então a tupla de vagas identifica a formação.
Valem para o leilão, os bots, a escalação e o motor. Ver docs/architecture/proposta-auction-model.md §6.
"""

from __future__ import annotations

from dataclasses import dataclass

from .positions import Position

GK, DR, DL, DC, DM, MC, STC = (Position.GK, Position.DR, Position.DL, Position.DC, Position.DM, Position.MC,
                               Position.STC)


@dataclass(frozen=True)
class Formation:
    """Formação: nome e exatamente 11 posições (com repetição, ex.: dois DC)."""

    name: str
    slots: tuple[Position, ...]


OFFICIAL_FORMATIONS: tuple[Formation, ...] = (
    # DR-11 (2026-11-19): lista definida pelo responsável (20 formações; 4-5-1, 3-5-2 e 3-4-3 saíram)
    Formation("4-2-2-2", (GK, DR, DC, DC, DL, DM, DM, MC, MC, STC, STC)),
    Formation("4-1-2-3", (GK, DR, DC, DC, DL, DM, MC, MC, STC, STC, STC)),
    Formation("4-2-3-1", (GK, DR, DC, DC, DL, DM, DM, MC, MC, MC, STC)),
    Formation("4-3-2-1", (GK, DR, DC, DC, DL, DM, DM, DM, MC, MC, STC)),
    Formation("4-3-1-2", (GK, DR, DC, DC, DL, DM, DM, DM, MC, STC, STC)),
    Formation("4-1-3-2", (GK, DR, DC, DC, DL, DM, MC, MC, MC, STC, STC)),
    Formation("4-1-4-1", (GK, DR, DC, DC, DL, DM, MC, MC, MC, MC, STC)),
    Formation("4-2-1-3", (GK, DR, DC, DC, DL, DM, DM, MC, STC, STC, STC)),
    Formation("3-1-3-3", (GK, DC, DC, DC, DM, MC, MC, MC, STC, STC, STC)),
    Formation("3-2-3-2", (GK, DC, DC, DC, DM, DM, MC, MC, MC, STC, STC)),
    Formation("3-1-4-2", (GK, DC, DC, DC, DM, MC, MC, MC, MC, STC, STC)),
    Formation("3-1-5-1", (GK, DC, DC, DC, DM, MC, MC, MC, MC, MC, STC)),
    Formation("3-2-4-1", (GK, DC, DC, DC, DM, DM, MC, MC, MC, MC, STC)),
    Formation("5-4-1", (GK, DR, DC, DC, DC, DL, MC, MC, MC, MC, STC)),
    Formation("5-3-2", (GK, DR, DC, DC, DC, DL, MC, MC, MC, STC, STC)),
    Formation("5-2-3", (GK, DR, DC, DC, DC, DL, MC, MC, STC, STC, STC)),
    Formation("5-1-3-1", (GK, DR, DC, DC, DC, DL, DM, MC, MC, MC, STC)),
    Formation("5-1-2-2", (GK, DR, DC, DC, DC, DL, DM, MC, MC, STC, STC)),
    Formation("5-2-2-1", (GK, DR, DC, DC, DC, DL, DM, DM, MC, MC, STC)),
    Formation("5-2-1-2", (GK, DR, DC, DC, DC, DL, DM, DM, MC, STC, STC)),
)


def formation_by_name(name: str) -> Formation | None:
    return next((f for f in OFFICIAL_FORMATIONS if f.name == name), None)


def official_name(slots) -> str | None:
    """Nome oficial de uma tupla de vagas (None se não for uma formação oficial)."""
    t = tuple(slots)
    return next((f.name for f in OFFICIAL_FORMATIONS if f.slots == t), None)


__all__ = ["Formation", "OFFICIAL_FORMATIONS", "formation_by_name", "official_name"]
