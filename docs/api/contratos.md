# Contratos da API — Entregas 1 e 2

Contrato formal: [`openapi.json`](openapi.json) (gerado por `scripts/export_openapi.py`; o teste
`tests/contracts/test_openapi_contract.py` falha se estiver desatualizado). Swagger em `http://127.0.0.1:8000/docs`.

## Convenções

- JSON UTF-8. Datas em ISO 8601 (UTC).
- **Comandos (POST) exigem `Idempotency-Key`** (8–128 caracteres `[A-Za-z0-9_-:.]`).
  - Repetição com a mesma chave e mesmo corpo → mesma resposta, cabeçalho `Idempotent-Replayed: true`.
  - Mesma chave, corpo diferente → `409 IDEMPOTENCY_KEY_REUSED`.
  - Mesma chave ainda em execução → `409 REQUEST_IN_PROGRESS` (retryable).
- **Erro padronizado** (todas as rotas):

```json
{ "error": { "code": "SESSION_NOT_FOUND", "message": "…", "retryable": false, "details": {} } }
```

`retryable: true` indica que repetir a mesma requisição (com a mesma chave) pode ter sucesso.

## Endpoints

| Método | Rota | Descrição | Erros principais |
|---|---|---|---|
| GET | `/api/health` | Estado do gateway, banco (versão do esquema, contagens), sessão ativa e serviços (`ready`/`planned`). | — |
| GET | `/api/catalog/clubs?search&limit&offset` | Clubes paginados (sem reputação), com `division` (`A`/`B`/`null`). | 422 |
| GET | `/api/catalog/players?club_uid&position&search&limit&offset` | Jogadores paginados; `position` aceita GK… ou GOL… (posição natural); `id_generated` indica ID gerado. | 422 |
| POST | `/api/imports/clubs` | `multipart/form-data` campo `file` (.xlsx). Substitui só a base de clubes. | 400, 409 `IMPORT_BLOCKED_ACTIVE_COMPETITION` / `IMPORT_IN_PROGRESS`, 413, 415, 422 `IMPORT_VALIDATION_FAILED` / `INVALID_WORKBOOK`, 500 `IMPORT_FAILED` |
| POST | `/api/imports/players` | Idem para jogadores. | idem |
| POST | `/api/sessions` | Cria a competição (`format`, `num_clubs`, `user_club_uid`, `league_rounds`, `confirm_replace`), seleciona/sorteia os participantes e gera calendário ou chaveamento. 201. | 409 `SESSION_ALREADY_ACTIVE` / `CATALOG_EMPTY` / `IMPORT_IN_PROGRESS`, 422 `INVALID_COMPETITION_CONFIG` / `CLUB_NOT_FOUND` / `CLUB_NOT_ELIGIBLE` / `VALIDATION_ERROR`, 500 `COMPETITION_PLANNING_FAILED` (retryable) |
| GET | `/api/sessions/{id}` | Estado da sessão (ativa ou encerrada recentemente). | 404 `SESSION_NOT_FOUND` |
| GET | `/api/sessions/{id}/competition` | **(Entrega 2)** Estrutura da competição: `LeagueSchedule` ou `CupBracket` (campo `kind`). | 404 `SESSION_NOT_FOUND` |
| POST | `/api/sessions/{id}/close` | Encerra (corpo opcional `{"expected_version": n}`). Idempotente. | 404, 409 `VERSION_CONFLICT` |
| GET | `/api/competitions/options` | Formatos válidos, `available_clubs`, `eligible_clubs`, `division_counts`, `catalog_ready`, `imports_blocked`. | — |
| GET | `/api/assets/clubs/{club_uid}` · `/api/assets/players/{unique_id}` | Escudo/foto por identificador (`Graphics/`). | 404 |

### Regras de configuração (`POST /api/sessions`)

| Formato | `num_clubs` | `league_rounds` |
|---|---|---|
| `league` | 2 a 20 (inteiro) | obrigatório: `single` (turno único) ou `double` (turno e returno) |
| `cup` | 2, 4, 8, 16 ou 32 | deve ser `null` |

`num_clubs` não pode exceder os clubes **elegíveis** (importados e com Série A/B); `user_club_uid` deve existir e ser
elegível. `participants` traz o clube do usuário em primeiro lugar, seguido dos selecionados/sorteados.

### Sessão (`SessionOut`)

`id` (UUID) · `version` (1 na criação; +1 a cada transição) · `status` (`active`/`closed`) · `phase`
(`setup`; demais fases declaradas para entregas futuras) · `config` · `created_at` · `updated_at` · `closed_at` · `participants`.

## WebSocket — `/ws/sessions/{id}`

| Direção | Mensagem |
|---|---|
| servidor → cliente | `session.snapshot` ao conectar (`version`, `data` = SessionOut) |
| cliente → servidor | `{"type":"ping"}` → `pong` |
| servidor → cliente | `session.closed` ao encerrar/substituir; socket fechado com código 1000 |
| — | Sessão inexistente: conexão recusada com código **4404** |

Reconexão: o cliente reabre o canal com backoff e usa `version` para descartar estados antigos.
Eventos de leilão, mercado e partidas serão definidos nas respectivas entregas.

## Estrutura da competição (Entrega 2) — `CompetitionOut`

`session_id` · `version` · `format` · `user_club_uid` · `structure` (discriminado por `kind`).

### Liga — `LeagueSchedule` (`kind: "league"`)

| Campo | Descrição |
|---|---|
| `rounds_mode` | `single` (turno único) ou `double` (turno e returno) |
| `participants` | `club_uid` dos clubes (usuário primeiro) |
| `rounds[]` | `LeagueRound`: `number` (1..total), `turn` (1/2), `matches[]`, `bye_club_uid` (folga; `null` com número par) |
| `matches[]` | `LeagueMatch`: `id` estável `L-R{rodada:02}-M{jogo:02}`, `round`, `turn`, `home_club_uid`, `away_club_uid` |
| `total_rounds` | n−1 (par) ou n (ímpar) por turno |
| `total_matches` | n(n−1)/2 por turno |
| `matches_per_club` | (n−1) por turno; folga **não** é partida |

Seleção: usuário + (n−1) clubes, primeiro da Série A e, faltando vagas, da Série B (sorteio dentro da série — PC-04).

### Copa — `CupBracket` (`kind: "cup"`)

| Campo | Descrição |
|---|---|
| `participants` | usuário + (n−1) sorteados entre os elegíveis (A e B), sem repetição |
| `rules` | `single_match: true`, `regulation_minutes: 90`, `extra_time: false`, `draw_decided_by: "penalties"`, `penalties_count_as_goals: false` |
| `rounds[]` | `CupRound`: `number`, `name` (Dezesseis-avos, Oitavas, Quartas, Semifinal, Final), `matches[]` |
| `matches[]` | `CupMatch`: `id` estável `C-R{fase}-M{jogo:02}`, `slot`, `club_a_uid`/`club_b_uid` (1ª fase preenchida; demais `null` até o vencedor), `source_a`/`source_b` (confrontos de origem), `next_match_id`, `winner_club_uid`, `decided_by` (`regular_time`/`penalties`) |
| `total_rounds` / `total_matches` | log2(n) / n−1 |
| `champion_club_uid` | `null` até a final |

A progressão estrutural (`register_cup_winner`) existe no serviço de competições e é testada, mas **não** é
exposta pela API: os resultados virão do motor de partidas (entrega futura).

## Leilão (Entrega 3)

Detalhes, erros e eventos em [leilão](../architecture/leilao.md). Resumo:

| Método | Rota | Resposta | Erros principais |
|---|---|---|---|
| POST | `/api/sessions/{id}/auction/start` | `AuctionStateOut` (201) | 409 `AUCTION_MODEL_NOT_CONFIGURED` / `INVALID_PHASE`, 500 `AUCTION_REJECTED` |
| GET | `/api/sessions/{id}/auction` | `AuctionStateOut` | 404 `AUCTION_NOT_FOUND` |
| POST | `/api/sessions/{id}/auction/bids` | `AuctionBidAck` | 422 `BELOW_MINIMUM_BID` / `INSUFFICIENT_FUNDS` / `BID_NOT_INCREASED` / `PLAYER_NOT_IN_ROUND` / `SQUAD_FULL`, 409 `STALE_ROUND` / `ROUND_CLOSED` / `AUCTION_NOT_RUNNING` / `OPERATION_ID_REUSED` |
| GET | `/api/sessions/{id}/auction/summary` | `AuctionSummaryOut` | 409 `AUCTION_NOT_FINISHED` |

Fases da sessão: `setup` → `auction` (início do leilão) → `squad_completion` (leilão + complementação concluídos).
Nenhum contrato do leilão expõe overall, atributos, valor de mercado, personalidade, reputação ou lances de
outros clubes (teste `test_auction_contracts_never_expose_hidden_fields`).
