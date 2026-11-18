# Arquitetura — SquadForce (Entregas 1 e 2)

## Visão geral

```text
 Navegador (React + TS, Vite)
        │  REST /api/*  ·  WebSocket /ws/sessions/{id}
        ▼
 services/gateway  ── HTTP, validação de entrada/saída, idempotência, erros padronizados, WebSocket
        │ chamadas Python tipadas (contratos em shared/python/squadforce_shared)
        ├── services/session      estado da competição em memória, versão, trava de importação
        ├── services/data         ÚNICO acesso ao SQLite: migrações, importação Excel, catálogo
        ├── services/competition  opções de formato; planner: seleção, calendário, chaveamento
        ├── services/auction      planejado
        ├── services/trading      planejado
        ├── services/bot_ai       planejado
        └── services/match_engine planejado
```

## Decisões (ADR resumidas)

| # | Decisão | Motivo |
|---|---|---|
| ADR-01 | **Serviços separados como pacotes Python independentes, compostos em um único processo pelo gateway.** Os serviços de domínio não importam FastAPI nem uns aos outros; dependências cruzadas passam por portas (`Protocol`) injetadas em `gateway/container.py`. | Atende à separação de responsabilidades sem introduzir rede/mensageria entre processos antes de haver necessidade (Regra 2). Cada serviço pode ser extraído para processo próprio trocando a porta por um cliente HTTP. |
| ADR-02 | **Estado da competição só em memória** (`SessionManager`), protegido por `RLock`. | GDD seção 23: sem salvamento, backup ou restauração. Reinício do processo = competição perdida (testado). |
| ADR-03 | **Trava de importação pertence ao serviço de sessão** (`import_guard`): bloqueia com sessão ativa e serializa importações; criar sessão durante importação retorna `IMPORT_IN_PROGRESS`. | Evita condição de corrida entre "verificar sessão" e "substituir base". |
| ADR-04 | **Idempotência obrigatória** em todo POST via `Idempotency-Key` (memória, TTL 1 h). Respostas determinísticas (sucesso, 422) são memorizadas; falhas transitórias não. | Permite que o cliente repita comandos com segurança após falhas de rede. |
| ADR-05 | **Substituição transacional:** jogadores = `DELETE` + `INSERT` em `BEGIN IMMEDIATE`; clubes = *upsert* + remoção dos ausentes, com FK `RESTRICT` impedindo órfãos. Qualquer exceção → `ROLLBACK`. | Base anterior preservada integralmente em caso de erro (testado com falha injetada no meio da gravação). |
| ADR-06 | **Planilha lida só em memória** (`BytesIO`), limite de 25 MB, apenas `.xlsx`. | Regra 5/6: sem cópias permanentes do Excel. |
| ADR-07 | **Contrato único:** modelos Pydantic → OpenAPI (`docs/api/openapi.json`) → tipos TS gerados (`frontend/src/types/openapi.d.ts`). Um teste falha se o OpenAPI versionado divergir do código. | Frontend e backend não divergem silenciosamente. |
| ADR-08 | SQLite em modo **WAL**, `foreign_keys=ON`, tabelas **STRICT**. | Tipos corretos e integridade garantidos pelo próprio banco. |
| ADR-09 | **Planejador injetado na sessão** (`CompetitionPlanner`): `SessionManager` recebe `plan_competition` via `container.py`; o serviço de sessão não importa o de competições. | Mantém os limites entre serviços e permite testar a sessão com planejadores falsos. |
| ADR-10 | **Planejamento puro e determinístico:** `services/competition/planner.py` só usa o `random.Random` recebido; semente automática por sessão (`secrets.randbits`), não exposta. Toda estrutura é validada por `validate_league_schedule`/`validate_cup_bracket` antes de ser aceita; violação → `COMPETITION_PLANNING_FAILED`, nada é criado. | GDD §16 (sementes automáticas, reprodutibilidade) e §19 (consolidação só com validação). |
| ADR-11 | **Divisões como dados de referência** (`club_divisions`, migração 0002), sem FK para `clubs`. | Reimportar clubes não apaga as divisões; clubes sem divisão ficam inelegíveis. |

## Limites de responsabilidade

- **gateway** não contém regra de jogo. Traduz HTTP ↔ chamadas de serviço e erros.
- **data** é o único que abre conexão SQLite. Outros serviços leem o catálogo pela porta `ClubCatalog`.
- **session** não acessa banco nem arquivos; não persiste nada.
- **competition** publica opções válidas e, via `planner.py`, seleciona participantes e gera calendário/chaveamento (sem executar partidas). Validação de formato e `EligibleClub` vivem em `squadforce_shared/domain/competition.py`.

## Fluxo de importação

1. `POST /api/imports/{base}` com `Idempotency-Key` → gateway lê o upload (memória).
2. `DataService` entra em `import_guard()` (bloqueia se houver competição ativa).
3. `importer.read_workbook` → `parse_clubs`/`parse_players` (validação completa, sem banco).
4. Erro crítico → `422 IMPORT_VALIDATION_FAILED` com relatório; banco intocado.
5. Sem erro crítico → transação SQLite; falha → `ROLLBACK` + `500 IMPORT_FAILED (retryable)`.

Detalhes do mapeamento: [importacao-excel.md](importacao-excel.md). Contratos: [../api/contratos.md](../api/contratos.md).
