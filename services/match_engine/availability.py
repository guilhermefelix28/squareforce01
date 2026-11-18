"""Disponibilidade entre partidas (GDD §9, §13): lesões e suspensões.

- Lesões (0–3 jogos) são cumpridas nas próximas partidas OFICIAIS do clube, em qualquer competição.
- Suspensões são controladas SEPARADAMENTE por competição e só diminuem com jogos daquela competição.
- Folgas (rodada sem jogo) não contam: o registro só muda quando o clube efetivamente joga.
- Emergenciais nunca entram no registro (não pertencem ao elenco).
- Condição física não é registrada: todo atleta apto começa cada partida com 100%.
Duração da suspensão por vermelho e acúmulo de amarelos: parâmetros PENDENTES (MatchParams).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .params import DEFAULT_PARAMS, MatchParams
from .types import MatchResult, TeamSheet


@dataclass
class AvailabilityLedger:
    params: MatchParams = DEFAULT_PARAMS
    injuries: dict[int, int] = field(default_factory=dict)  # jogador -> jogos restantes (qualquer competição)
    suspensions: dict[tuple[str, int], int] = field(default_factory=dict)  # (competição, jogador) -> jogos
    yellows: dict[tuple[str, int], int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)  # histórico disciplinar e médico

    def is_available(self, player: int, competition: str) -> bool:
        return self.injuries.get(player, 0) == 0 and self.suspensions.get((competition, player), 0) == 0

    def unavailable_reason(self, player: int, competition: str) -> str | None:
        if self.injuries.get(player, 0) > 0:
            return f"lesionado ({self.injuries[player]} jogo(s))"
        if self.suspensions.get((competition, player), 0) > 0:
            return f"suspenso ({self.suspensions[(competition, player)]} jogo(s) nesta competição)"
        return None

    def record_match(self, result: MatchResult, sheets: tuple[TeamSheet, TeamSheet],
                     squads: tuple[set[int], set[int]]) -> None:
        """Atualiza após uma partida oficial entre dois clubes.

        `squads` = elencos contratados dos dois clubes. Primeiro os afastamentos EXISTENTES dos atletas desses
        clubes são cumpridos (lesão: qualquer competição; suspensão: só desta competição); depois os novos
        desta partida são registrados — portanto a própria partida não conta para cumpri-los.
        """
        members = squads[0] | squads[1]
        comp = result.competition
        for player in [p for p in self.injuries if p in members]:
            self.injuries[player] -= 1
            if self.injuries[player] <= 0:
                del self.injuries[player]
        for key in [k for k in self.suspensions if k[0] == comp and k[1] in members]:
            self.suspensions[key] -= 1
            if self.suspensions[key] <= 0:
                del self.suspensions[key]

        emergency = {p.unique_id for s in sheets for p in (*s.starters, *s.bench) if p.is_emergency}
        for inj in result.injuries:
            if inj.player in emergency:
                continue
            if inj.matches > 0:
                self.injuries[inj.player] = max(self.injuries.get(inj.player, 0), inj.matches)
            self.history.append({"type": "injury", "player": inj.player, "matches": inj.matches,
                                 "match_id": result.match_id, "competition": comp})
        for card in result.cards:
            if card.player in emergency:
                continue
            self.history.append({"type": f"{card.color}_card", "player": card.player, "match_id": result.match_id,
                                 "competition": comp, "second_yellow": card.second_yellow})
            key = (comp, card.player)
            if card.color == "red":
                if self.params.red_card_suspension_matches > 0:
                    self.suspensions[key] = self.suspensions.get(key, 0) + self.params.red_card_suspension_matches
            else:
                self.yellows[key] = self.yellows.get(key, 0) + 1
                thr = self.params.yellow_accumulation_threshold
                if thr and self.yellows[key] % thr == 0:
                    self.suspensions[key] = self.suspensions.get(key, 0) + 1
