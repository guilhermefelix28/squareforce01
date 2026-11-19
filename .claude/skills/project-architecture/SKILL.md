---
name: project-architecture
description: Organização dos serviços FastAPI do SquadForce, contratos tipados, comunicação REST/WebSocket, idempotência, erros padronizados e padrões de código. Use ao criar ou mover serviços, rotas, contratos Pydantic, dependências entre serviços ou ao decidir onde um código deve morar.
---

# project-architecture

## Finalidade
Manter a arquitetura de serviços especializados coerente, com limites claros e contratos únicos.

## Quando utilizar
- Criar endpoint, serviço, contrato, evento WebSocket ou dependência entre serviços.
- Alterar `services/gateway/*`, `shared/python/squadforce_shared/*` ou a composição em `container.py`.

## Responsabilidades
| Pacote | Responsabilidade | Não pode |
|---|---|---|
| `services/gateway` | HTTP/WS, validação, idempotência, erros, composição | conter regra de jogo |
| `services/session` | estado em memória, versão, trava de importação | acessar banco/arquivos |
| `services/data` | SQLite, migrações, importação, catálogo | conhecer HTTP |
| `services/competition` | formatos (E1); calendário, chave, classificação (futuro) | acessar SQLite diretamente |
| `services/auction`, `trading`, `bot_ai` | ver README de cada um | ser implementados antes da entrega autorizada |
| `services/match_engine` | biblioteca pura do motor (sem I/O, sem relógio de parede) | acessar banco, rede ou estado global |
| `shared/python/squadforce_shared` | `domain/` regras puras, `contracts/` Pydantic, `errors/` códigos | ter I/O |

## Regras do Game Design aplicáveis
GDD §25: serviços especializados, operações idempotentes, relógios autoritativos, validações centrais,
controle de concorrência; SQLite só para bases importadas; progresso temporário.

## Contratos e dependências
- Pydantic (`squadforce_shared.contracts`) → OpenAPI (`docs/api/openapi.json`) → TS (`frontend/src/types/openapi.d.ts`).
- Erro padrão: `{"error": {code, message, retryable, details}}` via `AppError` + `services/gateway/errors.py`.
- POST exige `Idempotency-Key` (`services/gateway/idempotency.py`).
- Dependência entre serviços somente por `Protocol` injetado (ex.: `ClubCatalog`, `import_guard`).

## Procedimentos recomendados
1. Definir/alterar o modelo em `contracts/` primeiro.
2. Implementar a lógica no serviço de domínio (sem FastAPI).
3. Expor a rota em `services/gateway/routes.py` com `response_model` e `responses=ERR`.
4. Rodar `python scripts/export_openapi.py` e `npm run gen:api` (em `frontend/`).
5. Adicionar testes de contrato e de efeito (ver `testing-validation`).
6. Atualizar `docs/api/contratos.md` e `docs/architecture/arquitetura.md` (ADR) quando houver decisão nova.

## Configuração de execução
`SQUADFORCE_MATCH_EXECUTOR` (process|thread), `SQUADFORCE_MATCH_WORKERS` e, SOMENTE para testes/demonstração,
`SQUADFORCE_CLOCK_SCALE` (acelera relógios do servidor). Workers do pool saem sozinhos se o gateway morrer
(`exit_with_parent`).

## Restrições e comportamentos proibidos
- Introduzir mensageria persistente, Redis, filas ou novos processos sem necessidade demonstrada.
- Um serviço importar a implementação de outro (use portas).
- Rotas mutáveis sem idempotência; erros fora do formato padrão; `HTTPException` com `detail` livre.
- Tratar HTTP 200 como prova de consistência.

## Critérios de teste
- `tests/contracts/test_openapi_contract.py` verde (endpoints, Idempotency-Key, esquema de erro, OpenAPI sincronizado).
- `tests/end_to_end/test_server_boot.py` inicia o uvicorn real.

## Referências
- [Arquitetura e ADRs](../../../docs/architecture/arquitetura.md)
- [Contratos da API](../../../docs/api/contratos.md)
- [Especificação técnica](../../../docs/architecture/especificacao-tecnica-v5.2.md)
