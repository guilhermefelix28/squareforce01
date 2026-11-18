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
