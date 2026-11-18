---
name: session-management
description: Estado temporário da competição do SquadForce em memória — criação, consulta, versão, encerramento, substituição com confirmação, reconexão via WebSocket e bloqueio de importações. Use ao alterar services/session, transições de fase, o canal /ws/sessions ou o comportamento de reconexão do frontend.
---

# session-management

## Finalidade
Gerenciar a única competição ativa com estado autoritativo no servidor, sem nenhuma persistência.

## Quando utilizar
- Alterar `services/session/manager.py`, rotas `/api/sessions*`, `/ws/sessions/{id}` ou `frontend/src/app/SessionContext.tsx`.
- Adicionar uma fase nova (leilão, mercado, competição) ao estado da sessão.

## Responsabilidades
- Uma sessão ativa por servidor; `id` UUID; `version` incrementada a cada transição.
- Validar configuração (via `squadforce_shared.domain.competition`) contra os clubes **elegíveis**, existência e elegibilidade do clube do usuário.
- Na criação, chamar o `CompetitionPlanner` injetado com semente automática; guardar `participants`, `structure` e `seed` (privada) no `SessionState`. Falha de planejamento → nada é criado.
- `import_guard()`: bloqueia importações com sessão ativa e serializa importações.
- Encerramento explícito, idempotente, com `expected_version` opcional (concorrência otimista).
- Tombstones de sessões encerradas (memória, limitados) para consulta pós-encerramento.
- Fases: `setup` → `auction` → `squad_completion` via `SessionManager.transition(id, de, para)` (versão + 1).
  Encerrar ou substituir a sessão descarta o leilão em memória (`AuctionService.discard`).

## Regras do Game Design aplicáveis
- §23: uma competição ativa; encerrar/substituir exige **confirmação**; sem salvamento, backup ou restauração; reconexão automática enquanto o estado existir; relógios não pausam por desconexões individuais.
- §2/§17/§18: Liga 2–20 (turno único ou turno e returno); Copa 2/4/8/16/32; clube do usuário obrigatório, sem duplicação.
- §24: importações bloqueadas durante competição ativa.

## Contratos e dependências
- `SessionCreateRequest` / `SessionOut` / `SessionCloseRequest` (`squadforce_shared.contracts`).
- Porta `ClubCatalog` (implementada pelo `DataService`): `club_count`, `club_exists`, `catalog_ready`, `eligible_clubs`.
- Porta `CompetitionPlanner` (implementada por `services/competition/planner.py`).
- `GET /api/sessions/{id}/competition` → `SessionState.to_competition_out()`.
- WebSocket: `session.snapshot`, `session.closed`, `pong`, `error`; recusa com código 4404.

## Procedimentos recomendados
1. Toda mutação dentro de `self._lock` e gerando novo `SessionState` imutável (`dataclasses.replace`) com `version + 1`.
2. Transições novas: validar fase de origem, publicar evento WS após a mutação, cobrir com teste de concorrência.
3. Frontend guarda apenas o `id` em `localStorage`; o servidor é a fonte da verdade.

## Restrições e comportamentos proibidos
- Persistir estado em SQLite, JSON, Redis ou qualquer armazenamento permanente.
- Tentar "restaurar" sessões após reinício do processo.
- Definir participantes, sortear ou montar calendário aqui (pertence a `competition-system`).
- Substituir sessão ativa sem `confirm_replace: true`.

## Critérios de teste
`tests/unit/test_session_manager.py` (formatos, concorrência: 8 threads → 1 sessão), `tests/integration/test_sessions_api.py`
(duplicidade, conflito de versão, perda no reinício), `tests/integration/test_websocket.py`, `frontend/src/app/App.test.tsx`.

## Referências
- [Contratos — sessões e WebSocket](../../../docs/api/contratos.md)
- [Arquitetura ADR-02/03/04](../../../docs/architecture/arquitetura.md)
- [Game Design §23](../../../docs/game-design/game-design-v5.2.md)
