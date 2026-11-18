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

## Entrega 3 — leilão

| Requisito | Testes |
|---|---|
| Regras/constantes do GDD, durações, limite de melhorias, reserva por vaga | `tests/unit/test_auction_rules.py` |
| Rodada (5 da mesma posição, 10 s), relógio contíguo, fim global, independência da frequência do relógio | `test_round_shape_and_global_clock` · `test_rounds_are_contiguous_and_never_exceed_global_end` · `test_tick_frequency_does_not_change_the_outcome` |
| Validações (mínimo, saldo/reserva exata, atleta fora da rodada, prazo, rodada obsoleta, reduzir/repetir) | `test_invalid_bids_are_rejected` · `test_reserve_boundary_is_exact` · `test_reserve_rule_with_partial_squad` · `test_closed_round_and_stale_round` · `test_bid_at_last_instant_*` · `test_raise_allowed_reduce_and_repeat_forbidden` |
| Troca de alvo atômica, um lance ativo | `test_change_target_is_atomic_and_failure_keeps_previous` · `test_each_club_wins_at_most_one_player_per_round` |
| Maior lance e desempate (timestamp do valor final, sequência) | `test_highest_bid_wins` · `test_tie_goes_to_whoever_reached_the_final_value_first` · `test_same_timestamp_tie_uses_acceptance_sequence` |
| Idempotência (op_id e Idempotency-Key) | `test_operation_id_prevents_duplicate_bids` · `test_bid_flow_errors_and_idempotency` · `test_start_is_idempotent_and_cannot_restart` |
| Encerramento antecipado, elenco cheio | `test_full_squad_cannot_bid_and_early_finish_when_all_full` |
| Regra das 14 rodadas, elegibilidade (≥ 5), vendidos não voltam | `test_every_eligible_position_appears_in_every_window_of_14_rounds` · `test_position_with_fewer_than_five_players_is_not_eligible` · `test_sold_players_never_return_and_unsold_are_counted` |
| Validação das saídas do modelo | `test_invalid_model_outputs_are_rejected` · `test_invalid_reserves_are_rejected` |
| Sigilo (bots e API) | `test_bot_view_has_no_rival_bids` · `test_bot_decision_does_not_depend_on_rival_secret_bids` · `test_hidden_information_never_leaves_the_server` · `test_auction_contracts_never_expose_hidden_fields` |
| Avaliação 80/20 e escalação ótima | `test_marginal_gain_is_80_percent_starters_20_percent_reserves` · `test_hungarian_matches_brute_force` · `test_squad_quality_uses_best_formation_*` |
| Bots (personalidades, limites) | `test_aggressive_bids_at_least_as_much_as_conservative` · `test_bot_bids_respect_minimum_and_reserve_rule` · `test_personalities_are_hidden_*` |
| Complementação (18, limite, 1 destaque, preços, justiça, sem compensação) | `test_completion_rules` · `test_completion_order_has_no_fixed_priority` · `test_highlight_threshold_is_85th_percentile_of_full_base` |
| Concorrência e carga | `tests/simulation/test_auction_load_and_simulation.py`: 16 threads de lances + relógio (vencedores recalculados de forma independente), ticks concorrentes, 2000 lances < 2 s |
| Base real: Liga 2/11/20 e Copa 16/32 terminam com 18 por clube | `test_real_base_full_auction_every_club_ends_with_18` |
| Reconexão e relógio sem pausa | `test_reconnection_sees_authoritative_clock_and_own_bid` |
| Bloqueio sem fórmulas | `test_auction_is_blocked_without_approved_model` · `AuctionBoard.test.tsx` (AuctionPage) |
| WebSocket e relógio real | `test_server_clock_publishes_round_events_over_websocket` · `communication.e2e.test.ts` (rodada real de 10 s) |
| Interface | `AuctionBoard.test.tsx` · `AuctionSummaryView.test.tsx` |

## Entrega 4 — mercado de negociações

| Requisito | Testes |
|---|---|
| Proposta válida | `test_valid_proposal` · `test_proposal_lifecycle_and_errors` |
| Proposta inválida (mesmo clube, jogador alheio, clube fora, dinheiro negativo) | `test_invalid_players_and_clubs` · `test_invalid_money` · `test_proposal_lifecycle_and_errors` |
| Saldo insuficiente | `test_invalid_money[INSUFFICIENT_FUNDS]` · `test_proposal_lifecycle_and_errors` · `TradingBoard.test.tsx` |
| Limite de três | `test_three_trade_limit_for_proponent_and_recipient` · `test_pending_proposals_are_invalidated_*` |
| Uma pendente por clube / propostas simultâneas | `test_only_one_pending_proposal_per_proponent` · `test_simultaneous_proposals_from_same_club_only_one_survives` · `test_a_club_may_receive_several_proposals` |
| Cancelamento | `test_cancel_while_pending` · `test_proposal_lifecycle_and_errors` · `TradingBoard.test.tsx` |
| Expiração (10 s exatos, limitada ao fim) | `test_expiration_at_exactly_ten_seconds` · `test_accept_after_expiry_is_refused` · `test_deadline_limited_by_market_end_and_market_closes` |
| Encerramento do mercado | `test_deadline_limited_by_market_end_and_market_closes` · `test_expiration_reconnection_and_market_end` · `test_websocket_events_from_server_clock` |
| Falha durante a confirmação | `test_failure_during_confirmation_changes_nothing` |
| Negociação entre bots | `test_bot_to_bot_negotiation_keeps_integrity` · `test_hidden_information_and_privacy_of_proposals` |
| Dupla aceitação / comando duplicado | `test_double_acceptance_executes_one_trade` · `test_incoming_proposal_accept_executes_trade_once` · `test_proposal_idempotency` |
| Aceitar × cancelar × expirar concorrentes | `test_concurrent_accept_cancel_and_expiry_yield_one_decision` (20 rodadas) |
| Reconexão e sincronização | `test_market_does_not_pause_without_requests` · `test_expiration_reconnection_and_market_end` |
| IA: perda pequena compensada, sem exploração | `test_small_sporting_loss_needs_economic_justification` · `test_bots_cannot_be_systematically_exploited` |
| Estresse concorrente (12 threads + relógio, 3 sementes): integridade e dinheiro conservado | `tests/simulation/test_trading_stress.py` |
| Interface | `TradingBoard.test.tsx` (busca e filtros, confirmação, dinheiro acima do saldo, aceitar/rejeitar, cancelar, limite) |
