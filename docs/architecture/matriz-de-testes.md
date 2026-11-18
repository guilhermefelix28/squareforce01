# Matriz de testes — Entrega 1

| # | Requisito | Testes |
|---|---|---|
| 1 | Inicialização dos serviços | `tests/end_to_end/test_server_boot.py` (uvicorn real) · `tests/integration/test_health_and_assets.py::test_startup_creates_schema_and_reports_services` · `test_migrations_are_idempotent` |
| 2 | Comunicação frontend/backend | `frontend/src/api/communication.e2e.test.ts` (cliente real × uvicorn real) · `test_cors_allows_frontend_origin` · verificação manual no navegador (proxy Vite) |
| 3 | Validação dos contratos | `tests/contracts/test_openapi_contract.py` · `tests/contracts/test_skills.py` |
| 4 | Criação e consulta por importação | `test_valid_import_creates_queryable_clubs_and_players` · `test_catalog_filters_by_display_position_and_search` · `test_pagination` |
| 5 | IDs duplicados | `test_duplicate_ids_are_critical` · `test_invalid_import_preserves_previous_base[DUPLICATE_ID]` · `test_strict_types_and_checks` (PK) |
| 6 | Tipos inválidos | `test_invalid_types_are_critical[*]` · `test_out_of_range_values_are_critical[*]` · `test_strict_types_and_checks` |
| 7 | Relacionamentos inválidos | `test_invalid_relationship_is_critical` · `test_clubs_reimport_cannot_orphan_players` · `test_players_require_clubs_base` · `test_foreign_keys_enforced` |
| 8 | Normalização de posições | `tests/unit/test_positions.py` · `test_display_positions_are_normalized_on_import` · `frontend/src/domain/positions.test.ts` |
| 9 | Importação válida | `test_real_file_imports_and_is_not_modified` (planilha real) · `test_dedicated_clubs_sheet_is_supported` |
| 10 | Importação inválida com rollback | `test_failure_during_write_rolls_back_completely` · `test_clubs_failure_during_write_rolls_back` |
| 11 | Preservação da base anterior | `test_invalid_import_preserves_previous_base[*]` · `test_reimport_replaces_only_the_players_base` |
| 12 | Criação e encerramento de sessões | `test_create_get_and_close` · `test_close_increments_version_and_is_idempotent` · `App.test.tsx` (criar e encerrar com confirmação) |
| 13 | Configurações inválidas | `test_invalid_configs_are_rejected_without_creating_session[*]` · `test_league_rejects_out_of_range` · `test_cup_rejects_other_sizes` · `validation.test.ts` |
| 14 | Bloqueio de importações | `test_imports_blocked_while_competition_active` · `test_import_guard_*` · `ImportCard.test.tsx` |
| 15 | Comandos duplicados | `test_duplicate_create_command_returns_same_session` · `test_duplicate_close_command_is_safe` · `test_duplicate_import_command_is_replayed_not_reexecuted` · `test_concurrent_creation_yields_exactly_one_session` · `tests/unit/test_idempotency.py` |
| 16 | Falhas de comunicação recuperáveis | `client.test.ts` (rede cai e volta; repetição com a mesma chave; erros retryable; esgotamento → NETWORK_ERROR) · `test_retryable_errors_are_not_memoized` · `test_reconnection_receives_current_state` · `App.test.tsx` (servidor offline; sessão perdida) |
