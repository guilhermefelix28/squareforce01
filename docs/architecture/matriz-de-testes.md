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

## Entrega 2 — competições

| Requisito | Testes |
|---|---|
| Ligas 2, 3, 5, 7, 10, 19, 20 × turno único/returno (5 sementes cada): partidas, rodadas, folgas, mandos, usuário, confrontos | `tests/unit/test_competition_planner.py::test_league_schedule_invariants` (70 cenários) |
| Sequências de mando curtas | `test_league_home_sequences_are_short` |
| Folga não é partida | `test_bye_is_not_an_official_match` · `test_odd_league_has_byes` |
| Prioridade Série A → B, sem duplicações | `test_league_selection_prioritizes_serie_a` (35 cenários) · `test_league_falls_back_to_serie_b_when_a_is_short` · `test_real_league_of_20_with_serie_b_user` |
| Validador rejeita estruturas inválidas | `test_league_validator_rejects_corrupted_schedules` · `test_league_validator_rejects_unbalanced_home` · `test_cup_validator_rejects_corrupted_brackets` |
| Copas 2, 4, 8, 16, 32 (5 sementes): chaveamento, fases, sem duplicação | `test_cup_bracket_structure` (25 cenários) · `test_real_cup_of_32` |
| Progressão até a final e eliminação do usuário | `test_cup_progresses_to_the_final_even_after_user_elimination` (25 cenários) · `test_register_winner_rules` |
| Elegibilidade e divisões | `test_club_without_division_is_not_eligible` · `test_user_club_without_division_is_not_eligible` · `test_club_divisions_reference_has_20_a_and_20_b` |
| Determinismo por semente | `test_same_seed_same_plan_and_different_seed_differs` · `test_same_seed_reproduces_the_same_competition` |
| Contratos | `test_openapi_contract.py` (endpoint `/competition`) · `test_responses_validate_against_models` · `test_competition_api.py` |
| IDs gerados estáveis | `test_row_without_id_gets_stable_generated_id` · `test_generated_ids_are_stable_across_reimports` |
| Frontend | `CompetitionView.test.tsx` · `App.test.tsx` · `communication.e2e.test.ts` (Copa 16 real) |
