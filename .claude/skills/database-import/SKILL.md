---
name: database-import
description: Esquema SQLite, migrações e importação de planilhas Excel (clubes e jogadores) do SquadForce com validação, substituição transacional e rollback. Use ao alterar tabelas, migrações, mapeamento de colunas, regras de validação, consultas de catálogo ou o fluxo de importação.
---

# database-import

## Finalidade
Manter as bases persistentes de clubes e jogadores íntegras: entrada validada, substituição atômica e
preservação da base anterior em qualquer falha.

## Quando utilizar
- Mudanças em `database/migrations/`, `services/data/*` ou nas planilhas de origem.
- Nova coluna, novo atributo, nova regra de validação ou nova consulta de catálogo.

## Responsabilidades
- Migrações numeradas (`NNNN_nome.sql`), somente aditivas, aplicadas por `services/data/db.py`.
- Validação completa **antes** de abrir a transação (`services/data/importer.py`).
- Transação `BEGIN IMMEDIATE` com `ROLLBACK` integral (`services/data/service.py`).
- Catálogo paginado sem dados ocultos (reputação, atributos).

## Regras do Game Design aplicáveis
- §3: base importada de `jogadores.xlsx`, preservando **todos os jogadores válidos** (inclusive reservas e jovens); normalização GOL=GK, LD=DR, LE=DL, ZAG=DC, VOL=DM, ME=MC, ATA=STC.
- Linhas sem `unique_id` → ID genérico estável (`generated_player_id`, faixa ≥ 9e9, `id_generated = 1`) — PD-03 confirmada.
- Divisões (Série A/B 2026) em `club_divisions` (referência, sem FK) — PD-01 confirmada.
- §24: seleção pelo usuário, sem cópias permanentes do Excel, validar estrutura/valores/IDs, substituir só a base correspondente, transações, preservar em erro, sem backups/versionamento, bloquear com competição ativa.
- §2: escudos por ID; rankings internos ocultos.

## Contratos e dependências
- `POST /api/imports/clubs|players` → `ImportReport` (ver `docs/api/contratos.md`).
- Trava: `SessionManager.import_guard()` (serviço de sessão) — injetada como `import_guard`.
- Tabelas: `clubs`, `players` (+ `id_generated`), `attribute_definitions`, `player_attributes`, `player_positions`, `club_divisions` (STRICT, FKs, índices).
- `DataService.eligible_clubs()` alimenta o serviço de competições (porta `ClubCatalog`).

## Procedimentos recomendados
1. **Inspecionar a planilha real** antes de mudar mapeamentos (nomes exatos, tipos, nulos, duplicatas). Não inventar colunas.
2. Atualizar `importer.py` (colunas/limites) + migração nova + `attribute_definitions` se surgir atributo.
3. Erro por linha → `IssueCollector.error` (crítico) ou `.warn` (aviso). Decidir a severidade com `game-design-rules`.
4. Escrever testes: válido, inválido com preservação, falha injetada no meio da gravação, arquivo real (somente leitura).
5. Atualizar `docs/architecture/importacao-excel.md`.

## Restrições e comportamentos proibidos
- Gravar o upload em disco, copiar planilhas para o projeto ou modificar `Dados/`.
- Criar backups, tabelas de histórico, versionamento ou restauração.
- Migrações destrutivas (DROP/DELETE de dados) sem autorização explícita do usuário.
- Importação parcial: ou tudo grava, ou nada muda.
- Salvar progresso de competição no SQLite.
- Usar o banco `database/squadforce.db` em testes destrutivos (use `tmp_path`).

## Critérios de teste
`tests/unit/test_importer_validation.py`, `tests/unit/test_database_schema.py`,
`tests/integration/test_imports_api.py`, `tests/integration/test_real_spreadsheet.py` — incluindo duplicatas,
tipos inválidos, relacionamentos inválidos, normalização de posições, rollback e bloqueio com sessão ativa.

## Estado na homologação (Entrega 9)
Homologação: o SQLite NÃO muda durante uma competição inteira (impressão digital lógica das tabelas antes/depois, `test_no_persistence_of_competition_in_sqlite`); importações bloqueadas com sessão ativa.

## Referências
- [Importação Excel (mapeamento e achados)](../../../docs/architecture/importacao-excel.md)
- [Pendências PD-01…PD-06](../../../docs/game-design/pendencias.md)
- [Game Design §3 e §24](../../../docs/game-design/game-design-v5.2.md)
