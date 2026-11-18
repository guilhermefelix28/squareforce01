"""Planejamento estrutural de Liga e Copa (Entrega 2) — funções puras e determinísticas por RNG.

GDD v5.2: §2 (participantes, prioridade Série A), §17 (Liga), §18 (Copa), §16 (sementes automáticas).
Não executa partidas: apenas seleciona participantes, gera calendário/chaveamento e valida invariantes.
Toda aleatoriedade vem do `random.Random` recebido (sorteios reproduzíveis com a mesma semente).
"""

from __future__ import annotations

import math
import random
from collections import Counter
from typing import Sequence

from squadforce_shared.contracts import (
    CompetitionConfig,
    CupBracket,
    CupMatch,
    CupRound,
    DecidedBy,
    LeagueMatch,
    LeagueRound,
    LeagueSchedule,
)
from squadforce_shared.domain.competition import (
    CUP_SIZES,
    LEAGUE_MAX_CLUBS,
    LEAGUE_MIN_CLUBS,
    CompetitionFormat,
    EligibleClub,
    LeagueRounds,
)

CUP_ROUND_NAMES = {
    2: "Final",
    4: "Semifinal",
    8: "Quartas de final",
    16: "Oitavas de final",
    32: "Dezesseis-avos de final",
}


class PlanningError(ValueError):
    """Violação de pré-condição ou de invariante do planejamento."""


# ------------------------------------------------------------------ participantes
def _pools(user: int, eligible: Sequence[EligibleClub]) -> tuple[list[int], list[int]]:
    uids = [c.club_uid for c in eligible]
    if len(set(uids)) != len(uids):
        raise PlanningError("Lista de clubes elegíveis contém duplicatas.")
    if user not in uids:
        raise PlanningError(f"O clube do usuário ({user}) não é elegível.")
    a = sorted(c.club_uid for c in eligible if c.division == "A" and c.club_uid != user)
    b = sorted(c.club_uid for c in eligible if c.division == "B" and c.club_uid != user)
    return a, b


def select_league_participants(
    user: int, eligible: Sequence[EligibleClub], num_clubs: int, rng: random.Random
) -> list[int]:
    """Usuário + (n-1) clubes: primeiro da Série A, depois da Série B (GDD §2).

    Quando a Série A tem mais clubes do que as vagas restantes, a escolha dentro da série é por
    sorteio (decisão provisória PC-04: o GDD não define o critério dentro da mesma série).
    """
    a, b = _pools(user, eligible)
    need = num_clubs - 1
    if need > len(a) + len(b):
        raise PlanningError(f"Elegíveis insuficientes: {len(a) + len(b) + 1} para {num_clubs} vagas.")
    if need <= len(a):
        chosen = rng.sample(a, need)
    else:
        chosen = rng.sample(a, len(a)) + rng.sample(b, need - len(a))
    return [user, *chosen]


def draw_cup_participants(
    user: int, eligible: Sequence[EligibleClub], num_clubs: int, rng: random.Random
) -> list[int]:
    """Usuário + (n-1) sorteados entre todos os elegíveis, sem repetição (GDD §2/§18)."""
    a, b = _pools(user, eligible)
    pool = sorted(a + b)
    if num_clubs - 1 > len(pool):
        raise PlanningError(f"Elegíveis insuficientes: {len(pool) + 1} para {num_clubs} vagas.")
    return [user, *rng.sample(pool, num_clubs - 1)]


# ------------------------------------------------------------------ Liga
def _berger_rounds(n_even: int) -> list[list[tuple[int, int]]]:
    """Método do círculo (tabelas de Berger) para n par: lista de rodadas com (mandante, visitante)
    em índices de slot. Mandos alternados: diferença casa/fora <= 1 por clube no turno."""
    fixed = n_even - 1
    rounds = []
    for k in range(n_even - 1):
        matches = [(k, fixed) if k % 2 == 0 else (fixed, k)]
        for i in range(1, n_even // 2):
            a, b = (k + i) % (n_even - 1), (k - i) % (n_even - 1)
            matches.append((a, b) if i % 2 == 1 else (b, a))
        rounds.append(matches)
    return rounds


def build_league_schedule(
    participants: Sequence[int], rounds_mode: LeagueRounds, rng: random.Random
) -> LeagueSchedule:
    n = len(participants)
    if not LEAGUE_MIN_CLUBS <= n <= LEAGUE_MAX_CLUBS:
        raise PlanningError(f"Liga exige {LEAGUE_MIN_CLUBS}–{LEAGUE_MAX_CLUBS} clubes (recebido {n}).")
    slots: list[int | None] = list(participants)
    rng.shuffle(slots)  # posição no calendário sorteada (o usuário não tem posição fixa)
    if n % 2:
        slots.append(None)  # adversário fictício = folga
    base = _berger_rounds(len(slots))
    turns = [1] if rounds_mode is LeagueRounds.SINGLE else [1, 2]

    rounds: list[LeagueRound] = []
    number = 0
    for turn in turns:
        for pairs in base:
            number += 1
            matches, bye = [], None
            for h, a in pairs:
                home, away = slots[h], slots[a]
                if home is None or away is None:
                    bye = away if home is None else home
                    continue
                if turn == 2:  # returno espelhado: inverte o mando
                    home, away = away, home
                matches.append(
                    LeagueMatch(
                        id=f"L-R{number:02d}-M{len(matches) + 1:02d}",
                        round=number,
                        turn=turn,
                        home_club_uid=home,
                        away_club_uid=away,
                    )
                )
            rounds.append(LeagueRound(number=number, turn=turn, matches=matches, bye_club_uid=bye))

    schedule = LeagueSchedule(
        rounds_mode=rounds_mode,
        participants=list(participants),
        rounds=rounds,
        total_rounds=len(rounds),
        total_matches=sum(len(r.matches) for r in rounds),
        matches_per_club=(n - 1) * len(turns),
    )
    validate_league_schedule(schedule)
    return schedule


def validate_league_schedule(s: LeagueSchedule) -> None:
    """Invariantes da Liga (GDD §17). Lança PlanningError na primeira violação."""
    p = s.participants
    n = len(p)
    if len(set(p)) != n:
        raise PlanningError("Participantes duplicados.")
    if not LEAGUE_MIN_CLUBS <= n <= LEAGUE_MAX_CLUBS:
        raise PlanningError("Quantidade de clubes fora de 2–20.")
    turns = 1 if s.rounds_mode is LeagueRounds.SINGLE else 2
    per_turn = n - 1 if n % 2 == 0 else n
    if s.total_rounds != len(s.rounds) or len(s.rounds) != per_turn * turns:
        raise PlanningError(f"Número de rodadas incorreto: {len(s.rounds)} (esperado {per_turn * turns}).")
    expected_total = n * (n - 1) // 2 * turns
    all_matches = [m for r in s.rounds for m in r.matches]
    if s.total_matches != len(all_matches) or len(all_matches) != expected_total:
        raise PlanningError(f"Número de partidas incorreto: {len(all_matches)} (esperado {expected_total}).")
    if s.matches_per_club != (n - 1) * turns:
        raise PlanningError("matches_per_club incorreto.")

    members = set(p)
    ids = Counter(m.id for m in all_matches)
    if any(c > 1 for c in ids.values()):
        raise PlanningError("Identificadores de partida duplicados.")
    byes: Counter[int] = Counter()
    for i, r in enumerate(s.rounds, start=1):
        if r.number != i:
            raise PlanningError("Rodadas fora de ordem.")
        if len(r.matches) != n // 2:
            raise PlanningError(f"Rodada {i}: {len(r.matches)} partidas (esperado {n // 2}).")
        seen: list[int] = []
        for m in r.matches:
            if m.round != r.number or m.turn != r.turn:
                raise PlanningError(f"Partida {m.id} com rodada/turno inconsistente.")
            if m.home_club_uid == m.away_club_uid:
                raise PlanningError(f"Partida {m.id}: clube contra si mesmo.")
            seen += [m.home_club_uid, m.away_club_uid]
        if n % 2:
            if r.bye_club_uid is None:
                raise PlanningError(f"Rodada {i}: número ímpar exige um clube de folga.")
            seen.append(r.bye_club_uid)
            byes[r.bye_club_uid] += 1
        elif r.bye_club_uid is not None:
            raise PlanningError(f"Rodada {i}: folga indevida com número par de clubes.")
        if sorted(seen) != sorted(members):
            raise PlanningError(f"Rodada {i}: cada clube deve aparecer exatamente uma vez (jogo ou folga).")
        if r.turn != (1 if i <= per_turn else 2):
            raise PlanningError(f"Rodada {i}: turno incorreto.")

    if n % 2 and any(byes[c] != turns for c in p):
        raise PlanningError("Folgas mal distribuídas: cada clube deve folgar uma vez por turno.")

    ordered = Counter((m.home_club_uid, m.away_club_uid) for m in all_matches)
    unordered = Counter(frozenset(k) for k in ordered.elements())
    for a in p:
        for b in p:
            if a >= b:
                continue
            if unordered[frozenset((a, b))] != turns:
                raise PlanningError(f"Confronto {a}×{b} ocorre {unordered[frozenset((a, b))]} vez(es) (esperado {turns}).")
            if turns == 2 and (ordered[(a, b)] != 1 or ordered[(b, a)] != 1):
                raise PlanningError(f"Turno e returno: {a}×{b} deve ter um jogo em cada mando.")

    homes = Counter(m.home_club_uid for m in all_matches)
    for c in p:
        h, a = homes[c], (n - 1) * turns - homes[c]
        if (turns == 1 and abs(h - a) > 1) or (turns == 2 and h != a):
            raise PlanningError(f"Mandos desequilibrados para o clube {c}: {h} em casa, {a} fora.")


# ------------------------------------------------------------------ Copa
def build_cup_bracket(participants: Sequence[int], rng: random.Random) -> CupBracket:
    n = len(participants)
    if n not in CUP_SIZES:
        raise PlanningError(f"Copa exige {', '.join(map(str, CUP_SIZES))} clubes (recebido {n}).")
    order = list(participants)
    rng.shuffle(order)  # sorteio do chaveamento
    total_rounds = int(math.log2(n))
    rounds: list[CupRound] = []
    for r in range(1, total_rounds + 1):
        size = n // 2 ** (r - 1)  # clubes na fase
        matches = []
        for slot in range(1, size // 2 + 1):
            m = CupMatch(
                id=f"C-R{r}-M{slot:02d}",
                round=r,
                slot=slot,
                next_match_id=None if r == total_rounds else f"C-R{r + 1}-M{(slot + 1) // 2:02d}",
            )
            if r == 1:
                m.club_a_uid, m.club_b_uid = order[2 * slot - 2], order[2 * slot - 1]
            else:
                m.source_a, m.source_b = f"C-R{r - 1}-M{2 * slot - 1:02d}", f"C-R{r - 1}-M{2 * slot:02d}"
            matches.append(m)
        rounds.append(CupRound(number=r, name=CUP_ROUND_NAMES[size], matches=matches))
    bracket = CupBracket(
        participants=list(participants),
        rounds=rounds,
        total_rounds=total_rounds,
        total_matches=n - 1,
    )
    validate_cup_bracket(bracket)
    return bracket


def validate_cup_bracket(b: CupBracket) -> None:
    """Invariantes do chaveamento eliminatório (GDD §18)."""
    p = b.participants
    n = len(p)
    if len(set(p)) != n:
        raise PlanningError("Participantes duplicados.")
    if n not in CUP_SIZES:
        raise PlanningError("Tamanho de Copa inválido.")
    if b.total_rounds != int(math.log2(n)) or len(b.rounds) != b.total_rounds:
        raise PlanningError("Número de fases incorreto.")
    all_matches = [m for r in b.rounds for m in r.matches]
    if len(all_matches) != n - 1 or b.total_matches != n - 1:
        raise PlanningError(f"Copa de {n} clubes deve ter {n - 1} confrontos.")
    by_id = {m.id: m for m in all_matches}
    if len(by_id) != len(all_matches):
        raise PlanningError("Identificadores de confronto duplicados.")
    if not b.rules.single_match or b.rules.extra_time or b.rules.regulation_minutes != 90 or not b.rules.neutral_venue:
        raise PlanningError("Regras da Copa divergem do GDD (jogo único, 90 min, sem prorrogação, mando neutro).")

    first = b.rounds[0].matches
    entrants = [c for m in first for c in (m.club_a_uid, m.club_b_uid)]
    if sorted(entrants) != sorted(p):
        raise PlanningError("A primeira fase deve conter cada participante exatamente uma vez.")

    feeders: Counter[str] = Counter()
    for r_index, rnd in enumerate(b.rounds, start=1):
        if rnd.number != r_index or len(rnd.matches) != n // 2**r_index:
            raise PlanningError(f"Fase {r_index} com quantidade de confrontos incorreta.")
        for m in rnd.matches:
            if m.round != r_index:
                raise PlanningError(f"{m.id}: fase inconsistente.")
            if r_index == b.total_rounds:
                if m.next_match_id is not None:
                    raise PlanningError("A final não avança para outro confronto.")
            else:
                nxt = by_id.get(m.next_match_id or "")
                if nxt is None or nxt.round != r_index + 1 or m.id not in (nxt.source_a, nxt.source_b):
                    raise PlanningError(f"{m.id}: avanço para {m.next_match_id} inválido.")
                feeders[m.id] += 1
            if r_index > 1:
                for src in (m.source_a, m.source_b):
                    s = by_id.get(src or "")
                    if s is None or s.round != r_index - 1 or s.next_match_id != m.id:
                        raise PlanningError(f"{m.id}: origem {src} inválida.")
    if any(v != 1 for v in feeders.values()):
        raise PlanningError("Cada vencedor deve avançar para exatamente um confronto.")

    # clubes já posicionados nunca se repetem dentro da mesma fase
    for rnd in b.rounds:
        placed = [c for m in rnd.matches for c in (m.club_a_uid, m.club_b_uid) if c is not None]
        if len(placed) != len(set(placed)):
            raise PlanningError(f"Fase {rnd.number}: clube repetido.")


def register_cup_winner(b: CupBracket, match_id: str, winner: int, decided_by: DecidedBy) -> CupBracket:
    """Progressão estrutural: registra o vencedor e o posiciona no próximo confronto.

    Não simula partidas (motor = entrega futura). Empate nos 90 min => decided_by='penalties'.
    Retorna NOVO chaveamento; o original não é modificado. A Copa continua até a final mesmo
    após a eliminação do clube do usuário (GDD §18).
    """
    nb = b.model_copy(deep=True)
    by_id = {m.id: m for r in nb.rounds for m in r.matches}
    m = by_id.get(match_id)
    if m is None:
        raise PlanningError(f"Confronto {match_id} inexistente.")
    if m.winner_club_uid is not None:
        raise PlanningError(f"Confronto {match_id} já decidido.")
    if m.club_a_uid is None or m.club_b_uid is None:
        raise PlanningError(f"Confronto {match_id} ainda não tem os dois clubes definidos.")
    if winner not in (m.club_a_uid, m.club_b_uid):
        raise PlanningError(f"O clube {winner} não disputa {match_id}.")
    m.winner_club_uid, m.decided_by = winner, decided_by
    if m.next_match_id is None:
        nb.champion_club_uid = winner
    else:
        nxt = by_id[m.next_match_id]
        if nxt.source_a == m.id:
            nxt.club_a_uid = winner
        else:
            nxt.club_b_uid = winner
    validate_cup_bracket(nb)
    return nb


def pending_cup_matches(b: CupBracket) -> list[CupMatch]:
    """Confrontos prontos para disputa (dois clubes definidos, sem vencedor)."""
    return [
        m for r in b.rounds for m in r.matches
        if m.winner_club_uid is None and m.club_a_uid is not None and m.club_b_uid is not None
    ]


# ------------------------------------------------------------------ fachada usada pela sessão
def plan_competition(
    config: CompetitionConfig, eligible: Sequence[EligibleClub], rng: random.Random
) -> tuple[list[int], LeagueSchedule | CupBracket]:
    if config.format is CompetitionFormat.LEAGUE:
        participants = select_league_participants(config.user_club_uid, eligible, config.num_clubs, rng)
        return participants, build_league_schedule(participants, config.league_rounds, rng)
    participants = draw_cup_participants(config.user_club_uid, eligible, config.num_clubs, rng)
    return participants, build_cup_bracket(participants, rng)
