# Contratos da API — Entrega 1

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
| GET | `/api/catalog/clubs?search&limit&offset` | Clubes paginados (sem reputação). | 422 |
| GET | `/api/catalog/players?club_uid&position&search&limit&offset` | Jogadores paginados; `position` aceita GK… ou GOL… (posição natural). | 422 |
| POST | `/api/imports/clubs` | `multipart/form-data` campo `file` (.xlsx). Substitui só a base de clubes. | 400, 409 `IMPORT_BLOCKED_ACTIVE_COMPETITION` / `IMPORT_IN_PROGRESS`, 413, 415, 422 `IMPORT_VALIDATION_FAILED` / `INVALID_WORKBOOK`, 500 `IMPORT_FAILED` |
| POST | `/api/imports/players` | Idem para jogadores. | idem |
| POST | `/api/sessions` | Cria a competição (`format`, `num_clubs`, `user_club_uid`, `league_rounds`, `confirm_replace`). 201. | 409 `SESSION_ALREADY_ACTIVE` / `CATALOG_EMPTY` / `IMPORT_IN_PROGRESS`, 422 `INVALID_COMPETITION_CONFIG` / `CLUB_NOT_FOUND` / `VALIDATION_ERROR` |
| GET | `/api/sessions/{id}` | Estado da sessão (ativa ou encerrada recentemente). | 404 `SESSION_NOT_FOUND` |
| POST | `/api/sessions/{id}/close` | Encerra (corpo opcional `{"expected_version": n}`). Idempotente. | 404, 409 `VERSION_CONFLICT` |
| GET | `/api/competitions/options` | Formatos válidos, clubes disponíveis, `catalog_ready`, `imports_blocked`. | — |
| GET | `/api/assets/clubs/{club_uid}` · `/api/assets/players/{unique_id}` | Escudo/foto por identificador (`Graphics/`). | 404 |

### Regras de configuração (`POST /api/sessions`)

| Formato | `num_clubs` | `league_rounds` |
|---|---|---|
| `league` | 2 a 20 (inteiro) | obrigatório: `single` (turno único) ou `double` (turno e returno) |
| `cup` | 2, 4, 8, 16 ou 32 | deve ser `null` |

`num_clubs` não pode exceder os clubes importados; `user_club_uid` deve existir. `participants` permanece `null`
até a entrega de competições (seleção/sorteio).

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
