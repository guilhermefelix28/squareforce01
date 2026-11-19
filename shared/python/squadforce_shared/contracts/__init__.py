"""Contratos tipados (Pydantic) da API pública e da comunicação entre serviços.

Esses modelos geram o OpenAPI (docs/api/openapi.json), do qual os tipos TypeScript
do frontend são gerados (frontend/src/types/openapi.d.ts).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from squadforce_shared.domain.competition import CompetitionFormat, LeagueRounds
from squadforce_shared.domain.positions import Position

T = TypeVar("T")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- erros
class ErrorBody(_Model):
    code: str = Field(description="Código estável do erro (ver squadforce_shared.errors.ErrorCode).")
    message: str = Field(description="Mensagem legível em português.")
    retryable: bool = Field(description="Se a mesma requisição pode ser repetida com chance de sucesso.")
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(_Model):
    error: ErrorBody


# ---------------------------------------------------------------- health
class DatabaseHealth(_Model):
    status: Literal["ok", "error"]
    schema_version: int | None = None
    clubs: int | None = None
    players: int | None = None


class HealthResponse(_Model):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    time: datetime
    database: DatabaseHealth
    active_session: bool
    services: dict[str, Literal["ready", "planned"]] = Field(
        description="Estado dos serviços. 'planned' = estrutura criada, implementação em entrega futura."
    )


# ---------------------------------------------------------------- catálogo
class Page(_Model, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ClubOut(_Model):
    club_uid: int
    name: str
    short_name: str
    nation_id: int
    player_count: int
    division: Literal["A", "B"] | None = Field(
        None, description="Série A ou B (temporada de referência). null = clube sem divisão: não elegível."
    )
    # club_reputation é armazenada, mas NÃO exposta: GDD seção 2 ("rankings internos ocultos").


class PlayerOut(_Model):
    unique_id: int
    name: str
    full_name: str
    birth_date: str
    age: int
    nation_id: int
    height_cm: int
    club_uid: int
    club_short_name: str
    natural_positions: list[Position]
    accomplished_positions: list[Position]
    id_generated: bool = Field(False, description="True se o ID foi gerado pelo SquadForce (linha sem unique_id).")
    # Atributos e familiaridades são armazenados, mas não expostos no catálogo público
    # (GDD seção 5: overall/atributos ocultos na interface do leilão). Pendência registrada.


class ClubPage(Page[ClubOut]):
    pass


class PlayerPage(Page[PlayerOut]):
    pass


# ---------------------------------------------------------------- importações
class ImportIssue(_Model):
    row: int | None = Field(None, description="Linha da planilha (1 = cabeçalho).")
    column: str | None = None
    code: str
    message: str


class ImportReport(_Model):
    base: Literal["clubs", "players"]
    status: Literal["imported", "rejected"]
    file_name: str
    sheet: str | None = None
    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    previous_count: int = 0
    critical_errors: list[ImportIssue] = Field(default_factory=list)
    critical_error_count: int = 0
    warnings: list[ImportIssue] = Field(default_factory=list)
    warning_count: int = 0


# ---------------------------------------------------------------- sessões
SessionStatus = Literal["active", "closed"]
SessionPhase = Literal["setup", "auction", "squad_completion", "trading", "competition", "finished"]


class CompetitionConfig(_Model):
    format: CompetitionFormat
    num_clubs: int = Field(description="Liga: 2 a 20. Copa: 2, 4, 8, 16 ou 32.")
    user_club_uid: int = Field(description="Clube do usuário; incluído obrigatoriamente, sem duplicação.")
    league_rounds: LeagueRounds | None = Field(
        None, description="Obrigatório na Liga (single = turno único, double = turno e returno)."
    )


class SessionCreateRequest(CompetitionConfig):
    confirm_replace: bool = Field(
        False,
        description="Encerra a competição ativa e cria outra. Exige confirmação explícita (GDD seção 23).",
    )


class SessionCloseRequest(_Model):
    expected_version: int | None = Field(
        None, description="Se informado, o encerramento só ocorre se a versão atual for igual (concorrência otimista)."
    )


class SessionOut(_Model):
    id: str
    version: int = Field(description="Incrementa a cada transição de estado.")
    status: SessionStatus
    phase: SessionPhase
    config: CompetitionConfig
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    participants: list[int] | None = Field(
        None, description="club_uid dos participantes (inclui o clube do usuário), na ordem de seleção/sorteio."
    )


# ---------------------------------------------------------------- competições
class LeagueOptions(_Model):
    min_clubs: int
    max_clubs: int
    rounds: list[LeagueRounds]


class CupOptions(_Model):
    allowed_sizes: list[int]


class CompetitionOptions(_Model):
    league: LeagueOptions
    cup: CupOptions
    available_clubs: int
    eligible_clubs: int = Field(description="Clubes importados com divisão (A/B) definida.")
    division_counts: dict[str, int] = Field(description="Clubes elegíveis por divisão, ex.: {'A': 20, 'B': 20}.")
    catalog_ready: bool = Field(description="Há clubes e jogadores importados para iniciar uma sessão.")
    imports_blocked: bool = Field(description="True enquanto houver competição ativa.")


# ---------------------------------------------------------------- estrutura da competição (Entrega 2)
DecidedBy = Literal["regular_time", "penalties"]


class LeagueMatch(_Model):
    id: str = Field(description="Identificador estável: L-R{rodada:02}-M{jogo:02}.")
    round: int = Field(description="Rodada global (1..total).")
    turn: Literal[1, 2] = Field(description="1 = turno, 2 = returno.")
    home_club_uid: int
    away_club_uid: int


class LeagueRound(_Model):
    number: int
    turn: Literal[1, 2]
    matches: list[LeagueMatch]
    bye_club_uid: int | None = Field(None, description="Clube de folga (número ímpar de participantes). Folga não é partida.")


class LeagueSchedule(_Model):
    kind: Literal["league"] = "league"
    rounds_mode: LeagueRounds
    participants: list[int]
    rounds: list[LeagueRound]
    total_rounds: int
    total_matches: int
    matches_per_club: int


class CupRules(_Model):
    single_match: bool = True
    neutral_venue: bool = Field(True, description="Mando neutro em todos os confrontos da Copa (decisão de 2026-11-18).")
    regulation_minutes: int = 90
    extra_time: bool = False
    draw_decided_by: Literal["penalties"] = "penalties"
    penalties_count_as_goals: bool = False


class CupMatch(_Model):
    id: str = Field(description="Identificador estável: C-R{fase}-M{jogo:02}.")
    round: int
    slot: int = Field(description="Posição do confronto na fase (1..n).")
    club_a_uid: int | None = Field(None, description="Definido no sorteio (1ª fase) ou pelo vencedor de source_a.")
    club_b_uid: int | None = None
    source_a: str | None = Field(None, description="ID do confronto cujo vencedor ocupa club_a.")
    source_b: str | None = None
    next_match_id: str | None = Field(None, description="Confronto para onde avança o vencedor (null na final).")
    winner_club_uid: int | None = None
    decided_by: DecidedBy | None = None


class CupRound(_Model):
    number: int
    name: str
    matches: list[CupMatch]


class CupBracket(_Model):
    kind: Literal["cup"] = "cup"
    participants: list[int]
    rules: CupRules = Field(default_factory=CupRules)
    rounds: list[CupRound]
    total_rounds: int
    total_matches: int
    champion_club_uid: int | None = None


CompetitionStructure = Annotated[LeagueSchedule | CupBracket, Field(discriminator="kind")]


class CompetitionOut(_Model):
    session_id: str
    version: int
    format: CompetitionFormat
    user_club_uid: int
    structure: CompetitionStructure


# ---------------------------------------------------------------- leilão (Entrega 3)
# Regra de visibilidade (GDD §5): NUNCA expor overall, atributos, valor de mercado interno, perfis
# dos bots nem ofertas de outros clubes. Somente dados públicos + o lance do próprio usuário.
class AuctionPlayerOut(_Model):
    unique_id: int
    name: str
    age: int
    club_short_name: str = Field(description="Clube de origem do atleta (base importada).")
    position: Position = Field(description="Posição principal.")
    minimum_bid: int
    has_photo: bool = Field(False, description="Há foto em /api/assets/players/{unique_id}.")


class AuctionRoundOut(_Model):
    number: int
    position: Position
    players: list[AuctionPlayerOut]
    remaining_ms: int = Field(description="Tempo restante da rodada no relógio do servidor.")
    duration_ms: int


class AuctionBidOut(_Model):
    round: int
    player_id: int
    amount: int
    seq: int = Field(description="Ordem de aceitação no servidor (desempate).")


class AuctionContractOut(_Model):
    player_id: int
    name: str
    position: Position
    age: int
    price: int
    source: Literal["auction", "improvement", "basic"]
    round: int | None = None


class AuctionSaleOut(_Model):
    player_id: int
    player_name: str
    club_uid: int
    price: int


class AuctionRoundResultOut(_Model):
    number: int
    position: Position
    sales: list[AuctionSaleOut]
    unsold_player_ids: list[int]


class AuctionClubOut(_Model):
    """Informação pública de cada clube (elenco e saldo são públicos; lances não)."""

    club_uid: int
    is_user: bool
    squad_count: int
    budget: int


class AuctionStateOut(_Model):
    session_id: str
    phase: Literal["pending", "running", "completed"]
    global_remaining_ms: int
    global_duration_ms: int
    round: AuctionRoundOut | None = None
    user_club_uid: int
    budget: int
    max_bid: int = Field(description="Maior lance permitido agora (saldo − R$ 500 mil por vaga que restará).")
    open_slots: int
    active_bid: AuctionBidOut | None = None
    squad: list[AuctionContractOut]
    clubs: list[AuctionClubOut]
    recent_results: list[AuctionRoundResultOut] = Field(description="Últimas rodadas encerradas (mais recente primeiro).")
    rounds_completed: int
    finish_reason: Literal["all_squads_complete", "time_up", "no_eligible_players"] | None = None
    bid_increments: list[int]


class AuctionBidRequest(_Model):
    player_id: int
    amount: int = Field(gt=0, description="Valor em R$ (inteiro).")
    round_number: int | None = Field(None, description="Rodada visível ao usuário; recusado se já encerrada.")


class AuctionBidAck(_Model):
    round: int
    player_id: int
    amount: int
    seq: int
    replaced_player_id: int | None = Field(None, description="Alvo anterior, quando o lance trocou de atleta.")
    replayed: bool = False


class AuctionSquadOut(_Model):
    club_uid: int
    is_user: bool
    budget: int
    spent: int
    auction_signings: int
    improvement_limit: int
    contracts: list[AuctionContractOut]


class AuctionSummaryOut(_Model):
    session_id: str
    finish_reason: str
    rounds_completed: int
    squads: list[AuctionSquadOut]


# ---------------------------------------------------------------- mercado de negociações (Entrega 4)
# Visibilidade: elencos, saldos e trocas concluídas são públicos; propostas só aparecem para as duas
# partes envolvidas. Overall, atributos, valores internos e personalidades nunca são expostos.
ProposalStatus = Literal["pending", "accepted", "rejected", "cancelled", "expired", "invalidated"]


class TradingPlayerOut(_Model):
    unique_id: int
    name: str
    age: int
    position: Position
    club_uid: int


class TradingClubOut(_Model):
    club_uid: int
    is_user: bool
    budget: int
    completed_trades: int


class TradingSquadOut(TradingClubOut):
    players: list[TradingPlayerOut]


class ProposalOut(_Model):
    id: str
    direction: Literal["outgoing", "incoming"]
    proponent_club_uid: int
    recipient_club_uid: int
    offered: TradingPlayerOut = Field(description="Jogador que o proponente entrega.")
    requested: TradingPlayerOut = Field(description="Jogador que o proponente recebe.")
    money: int = Field(description="Dinheiro adicional pago pelo proponente (>= 0).")
    status: ProposalStatus
    reason: str | None = None
    remaining_ms: int = Field(description="Tempo restante (0 se decidida).")


class TradeRecordOut(_Model):
    proposal_id: str
    proponent_club_uid: int
    recipient_club_uid: int
    offered: TradingPlayerOut
    requested: TradingPlayerOut
    money: int
    elapsed_ms: int = Field(description="Instante da conclusão desde o início do mercado.")


class TradingStateOut(_Model):
    session_id: str
    phase: Literal["running", "finished"]
    remaining_ms: int
    duration_ms: int
    user_club_uid: int
    budget: int
    completed_trades: int
    max_trades: int
    outgoing: ProposalOut | None = Field(None, description="Proposta pendente do usuário (no máximo uma).")
    incoming: list[ProposalOut] = Field(description="Propostas recebidas pendentes, com contagem regressiva.")
    recent_decisions: list[ProposalOut] = Field(description="Últimas propostas do usuário já decididas (enviadas ou recebidas).")
    history: list[TradeRecordOut] = Field(description="Todas as trocas concluídas (públicas), mais recentes primeiro.")
    clubs: list[TradingClubOut]


class ProposalCreate(_Model):
    recipient_club_uid: int
    offered_player_id: int
    requested_player_id: int
    money: int = Field(0, ge=0, description="Dinheiro adicional opcional pago pelo proponente.")


# ---------------------------------------------------------------- temporada (Entrega 7)
SeasonPhase = Literal["ready", "awaiting_advance", "finished"]


class PointsSystemOut(_Model):
    win: int
    draw: int
    loss: int
    status: str = Field(description="Escala não definida no GDD: provisória (PC-09).")


class StandingRowOut(_Model):
    position: int = Field(description="Posição; clubes empatados sem critério oficial compartilham a posição.")
    club_uid: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: list[Literal["V", "E", "D"]] = Field(description="Últimos 5 resultados.")
    tied_with: list[int] = Field(description="Clubes empatados sem critério de desempate oficial (PC-01 pendente).")


class SeasonFixtureOut(_Model):
    match_id: str
    round: int
    home_club_uid: int = Field(description="Mandante (Liga) ou clube A (Copa, mando neutro).")
    away_club_uid: int
    is_user_match: bool
    played: bool
    score: tuple[int, int] | None = Field(None, description="Gols da partida (90 min).")
    official_score: tuple[int, int] | None = None
    shootout: tuple[int, int] | None = Field(None, description="Pênaltis, registrados à parte (Copa).")
    winner_club_uid: int | None = None


class SeasonStateOut(_Model):
    session_id: str
    kind: Literal["league", "cup"]
    phase: SeasonPhase = Field(description="ready: rodada pronta; awaiting_advance: pós-rodada (avanço manual); finished.")
    round_number: int
    total_rounds: int
    round_label: str | None
    fixtures: list[SeasonFixtureOut] = Field(description="Confrontos da rodada/fase atual.")
    byes: list[int] = Field(description="Clubes de folga na rodada (Liga ímpar).")
    failed_matches: list[str] = Field(description="Partidas que falharam; nada foi consolidado. Jogar de novo repete só estas.")
    standings: list[StandingRowOut] = Field(description="Classificação oficial (Liga); vazia na Copa.")
    bracket: CupBracket | None = None
    points_system: PointsSystemOut | None = None
    tiebreakers: list[str] = Field(description="Critérios de desempate em uso (vazio: PC-01 pendente).")
    user_club_uid: int
    user_eliminated: bool
    champion_club_uid: int | None = None
    tied_champions: list[int] = Field(description="Empate no topo sem critério oficial: campeão indefinido.")


class MatchEventOut(_Model):
    seq: int
    minute: int
    second: float
    period: int
    type: str
    side: int | None = None
    club_uid: int | None = None
    player: int | None = None
    player_name: str | None = None
    other: int | None = None
    other_name: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class PlayerRatingOut(_Model):
    player: int
    name: str
    club_uid: int
    rating: float = Field(description="Nota exibida (uma casa decimal).")
    minutes: float


class MatchReportOut(_Model):
    match_id: str
    round: int
    home_club_uid: int
    away_club_uid: int
    status: str
    score: tuple[int, int]
    official_score: tuple[int, int]
    shootout: tuple[int, int] | None = None
    winner_club_uid: int | None = None
    events: list[MatchEventOut] = Field(description="Principais acontecimentos.")
    stats: dict[str, dict[str, Any]] = Field(description="Estatísticas por lado: home/away.")
    ratings: list[PlayerRatingOut]
    man_of_the_match: PlayerRatingOut | None = None
    final_postures: tuple[str, str]
    engine_version: str
    params_version: str
    lineups: list["TeamLineupOut"] = Field(default_factory=list, description="Escalações dos dois clubes (mandante, visitante).")


class AwardEntryOut(_Model):
    player: int
    name: str
    club_uid: int
    value: float
    appearances: int


class ClubCampaignOut(_Model):
    club_uid: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    shootouts_won: int
    shootouts_lost: int
    result: str = Field(description="Liga: posição final; Copa: campeão ou fase de eliminação.")
    matches: list[SeasonFixtureOut]


class SeasonSummaryOut(_Model):
    session_id: str
    finished: bool = Field(description="Premiações são finais apenas com a competição encerrada.")
    champion_club_uid: int | None = None
    tied_champions: list[int]
    top_scorers: list[AwardEntryOut]
    top_assists: list[AwardEntryOut]
    best_average_rating: list[AwardEntryOut] = Field(description="Mínimo: 50% das partidas da própria equipe (arredondado para cima).")
    most_man_of_the_match: list[AwardEntryOut]
    campaigns: list[ClubCampaignOut]
    user_campaign: ClubCampaignOut
    history: list[SeasonFixtureOut] = Field(description="Todas as partidas consolidadas, em ordem.")


# ---------------------------------------------------------------- interface e integração (Entrega 8)
FitLevel = Literal["natural", "boa", "regular", "improvisada"]
Posture = Literal["retranca", "defensiva", "equilibrada", "ofensiva", "ataque_total"]
Speed = Literal["15s", "30s", "60s", "instant"]


class LineupPlayerOut(_Model):
    player: int
    name: str
    slot: str = Field(description="Vaga (código interno GK, DR, DL, DC, DM, MC, STC).")


class TeamLineupOut(_Model):
    club_uid: int
    formation: str
    starters: list[LineupPlayerOut]
    bench: list[LineupPlayerOut] = Field(description="Reservas (slot = posição natural).")
    initial_posture: str


class FormationOut(_Model):
    id: str = Field(description="Nome da formação (ex.: 4-3-3). Lista oficial pendente (PM-01): provisória.")
    positions: list[str] = Field(description="11 vagas na ordem do campo (código interno).")


class SquadPlayerOut(_Model):
    player: int
    name: str
    age: int | None = None
    position: str = Field(description="Posição natural (código interno).")
    available: bool
    unavailable_reason: str | None = None
    fit: dict[str, FitLevel] = Field(description="Adequação a cada posição (indicador visual do próprio elenco).")
    appearances: int
    goals: int
    assists: int
    average_rating: float | None = None
    motm: int
    yellow_cards: int
    red_cards: int


class LineupSlotOut(_Model):
    index: int
    position: str
    player: int
    name: str
    fit: FitLevel


class OpponentPreviewOut(_Model):
    club_uid: int
    campaign: "ClubCampaignOut"
    previous_formations: list[str] = Field(description="Formações usadas nas partidas anteriores (públicas).")
    top_players: list["AwardEntryOut"] = Field(description="Destaques públicos: artilheiros e melhores médias.")


class LineupOut(_Model):
    has_match: bool = Field(description="false: folga, eliminado ou competição encerrada.")
    match_id: str | None = None
    opponent: OpponentPreviewOut | None = None
    is_home: bool | None = Field(None, description="null na Copa (mando neutro).")
    formation: str | None = None
    starters: list[LineupSlotOut] = Field(default_factory=list)
    bench: list[LineupPlayerOut] = Field(default_factory=list)
    posture: Posture | None = None
    source: Literal["user", "auto"] = "auto"
    note: str | None = Field(None, description="Motivo de a escalação do usuário não ter sido usada.")
    locked: bool = Field(description="true: partida já iniciada ao vivo ou rodada jogada.")
    formations: list[FormationOut]


class LineupIn(_Model):
    formation: str
    starters: list[int] = Field(min_length=11, max_length=11, description="IDs na ordem das vagas da formação.")
    bench: list[int] = Field(default_factory=list, max_length=7)
    posture: Posture = "equilibrada"


class LiveStartIn(_Model):
    speed: Speed = "30s"


class LiveSpeedIn(_Model):
    speed: Speed


class PostureIn(_Model):
    posture: Posture


class LivePlayerOut(_Model):
    player: int
    name: str
    slot: str
    condition: float = Field(description="Condição física (0–100) do PRÓPRIO atleta.")
    on_field: bool
    yellow_cards: int


class LiveStateOut(_Model):
    session_id: str
    match_id: str
    home_club_uid: int
    away_club_uid: int
    user_side: int
    speed: Speed
    minute: int
    game_second: float
    finished: bool
    score: tuple[int, int]
    shootout: tuple[int, int] | None = None
    events: list[MatchEventOut] = Field(description="Somente eventos já revelados pelo relógio do servidor.")
    stats: dict[str, dict[str, Any]]
    postures: tuple[str, str] = Field(description="Posturas observáveis atuais (mandante, visitante).")
    own_players: list[LivePlayerOut]
    own_bench: list[LineupPlayerOut]
    substitutions_used: int
    max_substitutions: int = 5


class PlayerSeasonStatsOut(_Model):
    player: int
    name: str
    club_uid: int
    appearances: int
    goals: int
    assists: int
    average_rating: float | None = None
    rating_eligible: bool = Field(description="Atingiu 50% das partidas da própria equipe (arredondado para cima).")
    motm: int
    yellow_cards: int
    red_cards: int


class ClubSeasonStatsOut(_Model):
    club_uid: int
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    totals: dict[str, float] = Field(description="Somas das estatísticas do motor nas partidas do clube.")
    against: dict[str, float] = Field(description="Mesmas estatísticas, dos adversários.")


class SeasonStatsOut(_Model):
    session_id: str
    matches_played: int
    players: list[PlayerSeasonStatsOut]
    clubs: list[ClubSeasonStatsOut]


class CalendarRoundOut(_Model):
    number: int
    label: str
    fixtures: list[SeasonFixtureOut]
    byes: list[int]


class CalendarOut(_Model):
    session_id: str
    kind: Literal["league", "cup"]
    current_round: int
    rounds: list[CalendarRoundOut]


# ---------------------------------------------------------------- websocket
class WsEnvelope(_Model):
    """Envelope de mensagens WebSocket. Tipos na Entrega 1: session.snapshot, session.closed, pong, error."""

    type: str
    session_id: str | None = None
    version: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _non_empty_type(self) -> "WsEnvelope":
        if not self.type:
            raise ValueError("type obrigatório")
        return self


MatchReportOut.model_rebuild()
OpponentPreviewOut.model_rebuild()
