"""Formações oficiais (PM-01), escolhidas pelo responsável em 2026-11-19.

Usam somente os 7 códigos do GDD §3: meias abertos e meias-atacantes são MC; alas são DR/DL. Por isso alguns
pares têm as mesmas vagas e diferem só no nome: 3-5-2 = 5-3-2 e 4-3-2-1 = 4-2-3-1. A ORDEM das vagas é
diferente em cada formação, para que o nome escolhido seja preservado (a tupla de vagas identifica a formação).
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
    Formation("4-4-2", (GK, DR, DC, DC, DL, MC, MC, MC, MC, STC, STC)),
    Formation("4-3-3", (GK, DR, DC, DC, DL, DM, MC, MC, STC, STC, STC)),
    Formation("4-2-3-1", (GK, DR, DC, DC, DL, DM, DM, MC, MC, MC, STC)),
    Formation("3-5-2", (GK, DC, DC, DC, DR, DL, DM, MC, MC, STC, STC)),
    Formation("3-4-3", (GK, DC, DC, DC, DR, DL, DM, MC, STC, STC, STC)),
    Formation("5-3-2", (GK, DR, DC, DC, DC, DL, DM, MC, MC, STC, STC)),
    Formation("4-1-4-1", (GK, DR, DC, DC, DL, DM, MC, MC, MC, MC, STC)),
    Formation("4-5-1", (GK, DR, DC, DC, DL, MC, MC, MC, MC, MC, STC)),
    Formation("4-3-2-1", (GK, DR, DC, DC, DL, DM, MC, DM, MC, MC, STC)),  # mesma composição do 4-2-3-1, outra ordem
    Formation("4-3-1-2", (GK, DR, DC, DC, DL, DM, MC, MC, MC, STC, STC)),
    Formation("5-4-1", (GK, DR, DC, DC, DC, DL, DM, MC, MC, MC, STC)),
)


def formation_by_name(name: str) -> Formation | None:
    return next((f for f in OFFICIAL_FORMATIONS if f.name == name), None)


def official_name(slots) -> str | None:
    """Nome oficial de uma tupla de vagas (None se não for uma formação oficial)."""
    t = tuple(slots)
    return next((f.name for f in OFFICIAL_FORMATIONS if f.slots == t), None)


__all__ = ["Formation", "OFFICIAL_FORMATIONS", "formation_by_name", "official_name"]
