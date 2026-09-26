# Guard census — 89 guards

Emitted by `nfl/tools/guard_reachability.py --md`. Re-run it rather
than trusting these counts.

`classification`, `load_bearing_proof` and test determinism are
DECLARED in the tool, defaulting to `NOT_ESTABLISHED`: each is a
judgement, and a tool that guessed them would manufacture the
confidence this census exists to strip out.

| reachability | n | effect on failure | n | classification | n |
|---|---|---|---|---|---|
| NO_CALLER_AT_ALL | 3 | STOP | 36 | NOT_ESTABLISHED | 81 |
| NO_PROD_CALLER | 27 | NO_PRODUCTION_CALLER | 30 | LOAD_BEARING | 3 |
| INTERNAL_ONLY | 24 | ANNOTATE | 10 | ORPHANED_CONTROL | 2 |
| EXTERNALLY_CALLED | 35 | DOWNGRADE | 9 | TEST_NOT_RUNTIME | 1 |
|  |  | VERDICT_REGISTERED | 5 | SUPERSEDED | 1 |
|  |  | NOTHING | 1 | CANDIDATE_SCOPED | 1 |

## Guards with a load-bearing proof

A seeded bad state, the guard reporting FAIL, and the protected
action demonstrably not happening.

| guard | protects | proof | determinism |
|---|---|---|---|
| `assert_graded_row` | Every graded row proves how its actual arrived. No excepti | `test_missing_is_not_zero.py` | DETERMINISTIC_MEASURED |
| `assert_no_inactive_in_playable` | THE GATE. Checks EMITTED rows, not the fixture's intent. | `test_publication_refusal_is_load_bearing.py` | DETERMINISTIC_MEASURED |
| `assert_shared_draws` | DK-scored players must be players the football layers emit | `test_publication_refusal_is_load_bearing.py` | DETERMINISTIC_MEASURED |

## Every guard

| guard | effect | reach | direct test | proof | class | caller runnable | caller in a workflow |
|---|---|---|---|---|---|---|---|
| `assert_graded_row` | STOP | EXTERNALLY_CALLED | yes | yes | LOAD_BEARING | yes | **no** |
| `assert_no_inactive_in_playable` | STOP | EXTERNALLY_CALLED | yes | yes | LOAD_BEARING | yes | **no** |
| `assert_shared_draws` | STOP | EXTERNALLY_CALLED | yes | yes | LOAD_BEARING | yes | **no** |
| `assert_allocation_conserves` | VERDICT_REGISTERED | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_complete` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_counts_are_counts` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_draw_coherence` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_dropback_identity` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_events_within_opportunity` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_every_player_tagged` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_fresh` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_hard_invariants` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_identical_to_freeze` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_inactive_qbs_own_nothing` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_may_consume` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_named_owner_containment` | ANNOTATE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_no_inactive_survives` | VERDICT_REGISTERED | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_no_outcome_reader_imported` | DOWNGRADE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_no_outcome_shaped_inputs` | DOWNGRADE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_not_applicable_is_evidenced` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_not_dry_run` | DOWNGRADE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_not_mutated` | DOWNGRADE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_not_promoted` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_packet_is_clean` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_participation_supports_allocation` | VERDICT_REGISTERED | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_pregame_untouched` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_projection_excludes_outcomes` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_promotable` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_prospective_order` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_publishable` | ANNOTATE,DOWNGRADE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_redistribution_supported` | VERDICT_REGISTERED | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_role_state_supported` | VERDICT_REGISTERED | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_roster_legal` | ANNOTATE | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_summary_consistent` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_usable_for` | STOP | EXTERNALLY_CALLED | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_blockers_independent` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_coupling_has_joint_index` | ANNOTATE | INTERNAL_ONLY | **no** | — | NOT_ESTABLISHED | — | **no** |
| `assert_coupling_is_declared` | STOP | INTERNAL_ONLY | **no** | — | NOT_ESTABLISHED | — | **no** |
| `assert_currently_admissible` | DOWNGRADE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_cut_lawful` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_edge_fields_are_pregame` | DOWNGRADE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_edges_declarable` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_fallbacks_resolve` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_feature_schema_matches_freeze` | ANNOTATE,NOTHING | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_frame_closes` | STOP | INTERNAL_ONLY | **no** | — | NOT_ESTABLISHED | — | **no** |
| `assert_no_artifact_claims_12_of_12` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_no_live_outcome` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_no_postgame_inputs` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_no_roster_status` | ANNOTATE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_not_positional` | ANNOTATE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_pairs_are_usable` | ANNOTATE | INTERNAL_ONLY | **no** | — | NOT_ESTABLISHED | — | **no** |
| `assert_partition_covers_required` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_pit` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_player_review_complete` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_producer_coverage` | DOWNGRADE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | — | yes |
| `assert_scope_allowed` | ANNOTATE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_seal_path_governed` | STOP | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_single_divergence` | DOWNGRADE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | yes |
| `assert_sources_permitted` | ANNOTATE | INTERNAL_ONLY | yes | — | NOT_ESTABLISHED | yes | **no** |
| `assert_live_lineage` | NO_PRODUCTION_CALLER | NO_CALLER_AT_ALL | **no** | — | ORPHANED_CONTROL | — | **no** |
| `assert_no_inactive_survived` | NO_PRODUCTION_CALLER | NO_CALLER_AT_ALL | **no** | — | SUPERSEDED | — | **no** |
| `assert_prospective_matches_frozen` | NO_PRODUCTION_CALLER | NO_CALLER_AT_ALL | **no** | — | CANDIDATE_SCOPED | — | **no** |
| `assert_arm` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_arms_not_pooled` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_code_matches_policy` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_comparable` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_completeness` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_consumer` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_cross_player_eligible` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_event_named` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_gate` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_implementations_exist` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_lineup_legal` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_may_apply` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_may_optimize` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_may_project` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_may_train` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_metric_origin_complete` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | TEST_NOT_RUNTIME | — | **no** |
| `assert_no_auto_authorization` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_no_double_counted_qb_carries` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_no_stale_labels` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_not_a_dropback_column` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_ranking_admissible` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | ORPHANED_CONTROL | — | **no** |
| `assert_ready_for_slate` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_research_tree_unchanged` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_target_ownership_closure` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_verified` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_walk_matches_research` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |
| `assert_zero_opportunity_over_draws` | NO_PRODUCTION_CALLER | NO_PROD_CALLER | yes | — | NOT_ESTABLISHED | — | **no** |

## The column that decides VERIFIED

Only **27 of 89** guards have a caller referenced by any workflow,
runbook or doc. A guard reached only from a module nobody invokes is
protected by nothing, whatever its call graph says.
