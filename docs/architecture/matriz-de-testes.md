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

## Entrega 5 — motor esportivo

| Requisito | Testes (`tests/unit/test_match_engine.py`, salvo indicação) |
|---|---|
| Gols e finalizações; placar = gols | `test_goals_come_only_from_shot_events_and_match_the_score` · `test_every_match_is_structurally_valid` (40 sementes) |
| Posses e estatísticas derivadas | `test_statistics_are_derived_from_events` |
| xG contextual sem dupla contagem | `test_contextual_xg_depends_only_on_context` · `test_shooter_skill_changes_conversion_not_xg` · `test_goalkeeper_skill_reduces_goals_without_changing_xg` |
| Defesas | `test_saves_are_made_by_the_defending_goalkeeper` |
| Lesões (0–3 jogos, saída de campo, equipe reduzida) | `test_injuries_have_0_to_3_matches_and_injured_leave_the_pitch` · `test_injury_without_substitutes_leaves_team_short` |
| Cartões e expulsões | `test_second_yellow_is_red_and_sent_off_player_never_acts_or_is_replaced` |
| Menos de 7 jogadores | `test_fewer_than_seven_players_abandons_with_official_3_0` |
| Substituições (≤ 5, sem retorno) e desgaste | `test_at_most_five_substitutions_and_no_return` · `test_fatigue_grows_during_match_and_depends_on_posture` |
| Limite de jogadores em campo, eventos sem duplicação | `validation.validate_result` aplicado em todos os testes e lotes |
| Emergenciais | `tests/unit/test_match_availability.py::test_emergency_players_only_when_fewer_than_eleven_available` · `test_emergency_players_never_enter_the_ledger` |
| Suspensões por competição, lesões em qualquer competição, folgas | `test_match_availability.py` (6 testes) · `tests/simulation/test_match_batches.py::test_season_of_real_matches_with_ledger` |
| Notas e Craque | `test_ratings_in_range_with_one_decimal_and_motm_is_best` · `test_ratings_depend_on_events_not_on_overall` · `test_goal_raises_rating_and_red_card_lowers_it` · `test_motm_tie_breaks_*` · `test_short_cameo_counts_less_than_full_match` |
| Determinismo e velocidades | `test_same_input_reproduces_same_events` · `test_stepwise_and_presentation_speeds_reproduce_identical_events` |
| Mudanças de postura (só eventos futuros, efeito moderado) | `test_posture_change_only_affects_future_events` · `test_postures_change_attack_moderately` |
| 0 × 0, goleadas e resultados inesperados | `test_nil_nil_and_thrashings_are_possible` · `test_stronger_team_wins_more_but_upsets_happen` · `test_score_is_not_predetermined` |
| Lote exploratório na base real | `tests/simulation/test_match_batches.py` · relatório `scripts/match_engine_report.py` |
| Pênaltis da Copa (sem prorrogação, fora do placar e da artilharia) | `test_knockout_draw_goes_to_penalties_recorded_separately` · `test_league_draw_has_no_penalties` |

## Entrega 6 — IA tática

| Requisito | Testes (`tests/unit/test_tactics.py`, salvo indicação) |
|---|---|
| Time perdendo perto do final | `test_losing_near_the_end_goes_on_the_attack` · lote: `late_trailing_attacking_share` |
| Time vencendo com vantagem mínima | `test_winning_by_minimum_margin_late_protects_the_lead` · lote: `late_leading_defending_share` |
| Time com jogador expulso | `test_red_card_makes_the_team_more_cautious_when_ahead` · `test_opportunist_presses_against_ten_men` |
| Forte desgaste | `test_heavy_fatigue_penalizes_intense_postures` |
| Precisa vencer (título) / evitar derrota | `test_must_win_title_race_attacks_when_drawing` · `test_avoid_defeat_protects_the_draw` · `test_league_situation_rule` |
| Copa com risco de eliminação | `test_cup_elimination_risk_trailing_attacks` · `test_cup_draw_superior_presses_inferior_waits_for_penalties` |
| Equipe muito superior / muito inferior | `test_much_stronger_and_much_weaker_teams_choose_different_starts` |
| Repetição determinística | `test_decisions_are_deterministic` |
| Sem mudanças excessivas | `test_stability_interval_and_decisive_exceptions` · `test_small_gains_do_not_trigger_changes` · `test_hysteresis_makes_reverting_harder` · `test_no_excessive_changes_and_valid_matches_with_bots` · lote `test_changes_are_not_excessive` |
| Personalidades moderadas | `test_personality_moderately_shifts_risk_appetite` |
| Informação permitida / sem trapaça | `test_observation_exposes_only_own_team_and_this_match` · `test_bot_cannot_see_user_future_decisions` · `test_passive_controller_does_not_touch_engine_probabilities` · lote `test_ai_has_no_artificial_advantage_but_is_not_worse_than_static` |
| Substituições legais | `test_tactical_substitutions_are_legal` |
| Formação e escalação | `test_lineup_excludes_unavailable_and_respects_formation` · `test_lineup_prefers_positional_fit_over_raw_attributes` · `test_recent_performance_breaks_ties` · `test_reference_formation_and_opponent_history_shape_the_choice` · `test_emergency_players_only_below_eleven_available` · `test_no_formations_is_an_explicit_error` |
| Regressão do motor | `tests/unit/test_match_engine_regression.py` (8 hashes da Entrega 5) + suíte do motor |
| Lotes de comportamento | `tests/simulation/test_tactics_batches.py` · relatório `scripts/tactics_report.py` |

## Entrega 7 — Liga, Copa e execução paralela

| Requisito | Testes (`tests/unit/test_season.py`, salvo indicação) |
|---|---|
| Liga 2 a 20 clubes, ímpares, turno único e returno | `test_league_complete_any_size` (2,3,4,5,7,8 × turno/returno) · `test_league_with_20_clubs_double_round_completes` · simulação `test_full_20_club_league_integrity_and_strength_signal` |
| Classificação e pontuação; desempate sem critério oficial | `tests/unit/test_standings.py` |
| Copa 2, 4, 8, 16, 32; empates e pênaltis | `test_cup_complete_bracket` · `test_cup_penalties_recorded_separately_from_goals` · simulação `test_many_cups_of_32` |
| Eliminação antecipada do usuário | `test_user_eliminated_cup_continues_until_final` |
| Folgas | `test_byes_do_not_count_as_match_nor_reduce_absences` |
| Afastamentos e suspensões | `test_injuries_and_suspensions_are_consolidated_and_respected` |
| Rodadas paralelas / snapshot / isolamento | `test_standings_only_change_on_consolidation_and_snapshot_is_shared` · `test_parallel_processes_match_threads_and_order_independence` · `test_bot_matches_do_not_depend_on_the_user_match` · API `test_real_process_pool_round` |
| Falhas em partidas simultâneas | `test_failed_parallel_match_blocks_whole_round_and_retry_is_identical` · `test_invalid_result_is_rejected` · `test_identity_mismatch_is_rejected` · `test_failure_during_consolidation_leaves_state_untouched` · API `test_failed_match_blocks_consolidation_and_retry_replays_only_failures` |
| Reprocessamento determinístico | `test_deterministic_reprocessing` · `test_seed_is_per_match_and_stable` |
| Consolidação única e avanço manual | `test_consolidation_happens_once_and_advance_is_manual` · API `test_full_competition_flow` |
| Histórico, campeões e premiações | `test_awards_and_campaign` · API `test_full_competition_flow` |
| API (início após o mercado, pós-partida, resumo, sessão encerrada) | `tests/integration/test_season_api.py` |
