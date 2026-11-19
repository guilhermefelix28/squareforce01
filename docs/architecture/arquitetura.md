# Arquitetura — SquadForce (Entregas 1 a 8)

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
        ├── services/auction      leilão: motor, regras, complementação (modelo de fórmulas pendente)
        ├── services/trading      mercado: propostas, decisões únicas, trocas atômicas
        ├── services/bot_ai       avaliação 80/20 e decisões de lance dos bots
        └── services/match_engine motor de partidas determinístico (parâmetros provisórios)
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
| ADR-12 | **Fórmulas como ponto de extensão (`AuctionModel`)**: o motor implementa só as regras escritas no GDD; overall, valores, reservas, pesos, formações e perfis vêm de um modelo carregado por `SQUADFORCE_AUCTION_MODEL`. Sem modelo, o leilão é recusado. Toda saída do modelo é validada contra os limites do GDD. | Proibição de inventar fórmulas econômicas (decisão de 2026-11-18). |
| ADR-13 | **Motor do leilão determinístico e thread-safe**: estado sob uma `RLock`; o relógio é injetado; rodadas contíguas calculadas a partir do fim da anterior; ações dos bots agendadas em tempo de servidor. Uma tarefa asyncio no gateway avança os leilões a cada 100 ms e publica eventos sem dados sigilosos. | Relógio autoritativo, concorrência protegida e testes reprodutíveis (inclusive com saltos de tempo). |
| ADR-14 | **`PlayerProfile` no domínio compartilhado**: o serviço de dados carrega atributos e familiaridades para uso interno; nenhum contrato público os expõe. | Mantém o leilão sem acesso ao SQLite e preserva a ocultação de dados. |
| ADR-15 | **Mercado com decisão única e cópia-e-confirmação**: uma `RLock` por mercado; cada proposta tem exatamente uma decisão final; a troca monta e valida o novo estado (18, sem duplicação, saldo ≥ 0) antes de aplicá-lo; idempotência no gateway e no motor (inclusive para erros definitivos). Linha do tempo (expirações, bots, fechamento) processada em ordem de tempo do servidor. | Aceite/cancelamento/expiração concorrentes e comandos duplicados nunca produzem duas trocas nem estado parcial. |
| ADR-16 | **Motor como biblioteca pura e determinística**: `services/match_engine` não tem I/O, relógio de parede nem estado global; entrada imutável (`MatchInput`) + parâmetros versionados (`MatchParams`) + semente + decisões → eventos. Estatísticas e notas são funções dos eventos; `validate_result` confere todas as invariantes. A apresentação só converte tempo de tela em tempo de jogo. | GDD §16 (reprodutibilidade, velocidade sem efeito) e os critérios de aceitação da Entrega 5. |
| ADR-19 | **Partida ao vivo com relógio do servidor e revelação progressiva**: `LiveMatch` simula a `FixtureTask` do snapshot passo a passo e entrega só eventos já ocorridos; posturas viram `PostureChange`; a execução paralela da rodada usa as mesmas decisões e a consolidação exige resultado idêntico (`expect_result`). | Velocidade não altera eventos (GDD §16), sem espiar o futuro, sem pausa por desconexão (§23), integridade verificada. |
| ADR-18 | **Rodadas por snapshot imutável + executor paralelo limitado + consolidação atômica**: cada partida é uma `FixtureTask` serializável (estado inicial, semente derivada do `match_id`, contexto público, decisões) executada em `ProcessPoolExecutor` (limite configurável); resultados ficam num buffer e só são aplicados numa cópia do estado trocada de uma vez, após validar todos. Falhas não consolidam nada e são repetidas com a mesma tarefa. | GDD §19: isolamento real entre confrontos, determinismo independente da ordem, nenhuma consolidação parcial. |
| ADR-17 | **IA tática como controlador externo do motor**: o motor expõe `TacticalController` e `TacticalObservation` (só informação permitida); a IA (`services/bot_ai/tactics.py`) decide posturas de forma determinística, sem usar o RNG do motor. Decisões viram `PostureChange` no tempo de jogo atual, idênticas às do usuário. Sem controlador, o motor é bit a bit o da Entrega 5 (teste de regressão por hashes). | Separa responsabilidades, impede trapaça (observação limitada) e preserva o determinismo. |
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
