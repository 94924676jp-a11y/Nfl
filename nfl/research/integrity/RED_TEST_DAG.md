# The red surface as a root-cause DAG

Owner priority 2, 2026-09-23. Every one of the 42 red modules gets exactly one
category, with evidence. **Multiple modules failing from one cause are one
defect, and this file is organised that way** — the module list is the
symptom, the root cause is the thing to fix.

Categories: `REAL_PRODUCTION_DEFECT`, `STALE_FIXTURE`,
`HISTORICAL_ARTIFACT_MISSING`, `OBSOLETE_CONTRACT`,
`EXPECTED_GOVERNANCE_FAILURE`, `TEST_BUG`, `UNKNOWN`.

## The DAG

```
R1  refused runs treated as sealed boards        EXPECTED_GOVERNANCE_FAILURE
    +- CURRENT_SEASON_INPUT_STALE (3 inputs)        + TEST_BUG (discovery)
    |     -> test_draw_coherence, test_p8_tails_and_counts,
    |        test_publication_semantics, test_sealed_corpus_census,
    |        test_conservation, test_qb2_production,
    |        test_product_orchestration
    +- a derived zero-delta artifact is not a board
          -> the same discovery contract

R2  the Q9 freeze pin is a reproduction           POST_FREEZE_DEPENDENCY_DRIFT
    instruction, asserted as working-tree           (OBSOLETE_CONTRACT in part)
    equality
      -> test_appearance_candidate_b, test_appearance_team_scope,
         test_c1_denominator, test_p1_appearance_repair,
         test_qb_eligibility_den_kc

R3  the deployed capture surface does not          REAL_PRODUCTION_DEFECT
    match the approved release
      -> test_capture_deployment_integrity, test_capture_prod_deployment,
         test_preflight                              (D24-R1/R2/R3)

R4  no club has a 2026 week-1 injuries row in      HISTORICAL_ARTIFACT_MISSING
    any capture at or before the cut
      -> test_football_engine_r4, test_readiness_vintage_cut   (PRI-A)

R5  capture manifest digests do not match the      REAL_PRODUCTION_DEFECT
    bytes on disk for ['schedules']
      -> test_live_capture_den_kc, test_capture_obligations,
         test_p7_data_plane

R6  18 P6 reproductions still failing              REAL_PRODUCTION_DEFECT
      -> test_p6_false_greens                        (fenced, intentional)

R7  five pre-repair week-1 boards carry            REAL_PRODUCTION_DEFECT
    fractional carries
      -> test_stat_contract                          (fence correctly held)

R8  producers stopped emitting keys tests read     OBSOLETE_CONTRACT
      -> test_gate_ids, test_ownership_audit, test_system_state

R9  three modules expose no test_* function,       TEST_BUG
    so the runner never runs their checks
      -> test_harness_audit reports it;
         test_gadget_rush, test_rushing_survivorship, test_wired_product
         are the three

R10 regenerable inventories drifted                STALE_FIXTURE
      -> test_system_state, test_p7_dag
         BUT test_p7_dag also carries UNDECLARED_VINTAGE_READ ->  R11

R11 usage_vintage.py reads a vintage it never      REAL_PRODUCTION_DEFECT
    declared
      -> test_p7_dag                                 (leakage-adjacent)

R12 commit_claim.py shells to git for              REAL_PRODUCTION_DEFECT
    working-tree state from outside nfl/identity/
      -> test_determinism_proof

R13 a guard added after a fixture                  STALE_FIXTURE
      -> test_full_slate_rehearsal (ROSTER_CUT_REQUIRED),
         test_v1_draw_artifact (REQUIRED_SOURCE_NOT_DECLARED)

R14 the seal records an input set nothing can      REAL_PRODUCTION_DEFECT
    consume; replay re-selects
      -> test_replay_pins_its_inputs                 (D23)

R15 order- or state-dependent failures: green      TEST_BUG
    standalone, red in the full run
      -> test_agent_state, test_governance_transport,
         test_product_orchestration, test_v1_rushing_a1
```

## Module-by-module

| module | red | category | root | evidence |
|---|---|---|---|---|
| test_agent_state | 5 raise | TEST_BUG | R15 | passes standalone at this HEAD |
| test_appearance_candidate_b | 1+1 | OBSOLETE_CONTRACT | R2 | `b081a5b2` vs pin `481f005f` |
| test_appearance_team_scope | 1+1 | OBSOLETE_CONTRACT | R2 | same pin |
| test_c1_denominator | 1+1 | OBSOLETE_CONTRACT | R2 | same pin |
| test_capture_deployment_integrity | 1 | REAL_PRODUCTION_DEFECT | R3 | `SURFACE_DIFFERS`, `efab90d6…` |
| test_capture_obligations | 4 | REAL_PRODUCTION_DEFECT | R5 | `PERSISTED_CONTENT_SHA256_MISMATCH`, `RAW_ARTIFACT_MISSING_ON_DISK` |
| test_capture_prod_deployment | 5 | REAL_PRODUCTION_DEFECT | R3 | `CAPTURE_EXECUTOR_SURFACE_MISMATCH` |
| test_conservation | 3 | EXPECTED_GOVERNANCE_FAILURE | R1 | `CONSERVATION_RUN_INCOMPLETE` on the two refused runs |
| test_determinism_proof | 1 | REAL_PRODUCTION_DEFECT | R12 | names `commit_claim.py` |
| test_draw_coherence | 1+3 | TEST_BUG | R1 | `FileNotFoundError: …/board.json` on a REFUSED run |
| test_execution_identity | 1 | TEST_BUG | R15 | the check reads the CURRENT commit sha, so it moves with HEAD |
| test_football_engine_r4 | 2+1 | HISTORICAL_ARTIFACT_MISSING | R4 | `READY_BY_EARLY_VINTAGE_NO_LEAGUE_REPORT` |
| test_full_slate_rehearsal | 2+5 | STALE_FIXTURE | R13 | `ROSTER_CUT_REQUIRED` |
| test_gate_ids | 1 raise | OBSOLETE_CONTRACT | R8 | `KeyError: single_adjustment_ownership_verified` |
| test_governance_transport | 1 | TEST_BUG | R15 | passes standalone |
| test_harness_audit | 1+1 | TEST_BUG | R9 | names 3 vacuous modules; verified |
| test_inactives_substance | 4 | UNKNOWN | — | `48 of 50`, `382` vs D20; needs its own look |
| test_kicker_resolution | 1 | REAL_PRODUCTION_DEFECT | — | NYJ `KICKER_ELIGIBILITY_DISAGREES_ACROSS_VINTAGES` |
| test_live_capture_den_kc | 1+1 | REAL_PRODUCTION_DEFECT | R5 | `ARTIFACT_VERIFICATION_FAILED` on `['schedules']` |
| test_non_g0a_isolation | 2+1 | OBSOLETE_CONTRACT | R2-like | "the G0A workflow still carries its frozen identity — identity changed" |
| test_nonqb_r3 | 1+1 | REAL_PRODUCTION_DEFECT | — | `rushing_conversion` is blank where a declaration is required |
| test_ownership_audit | 2+3 | OBSOLETE_CONTRACT | R8 | `KeyError: n_files_scanned` |
| test_p1_appearance_repair | 1+1 | OBSOLETE_CONTRACT | R2 | same pin |
| test_p6_false_greens | 18+1 | REAL_PRODUCTION_DEFECT | R6 | its own docstring: the repository's state, not a defect in the file |
| test_p7_dag | 2 | REAL_PRODUCTION_DEFECT + STALE_FIXTURE | R11 + R10 | `UNDECLARED_VINTAGE_READ` on `usage_vintage.py`; inventory regenerable |
| test_p7_data_plane | 3 | REAL_PRODUCTION_DEFECT | R5 | declaration vs stored-capture mismatch |
| test_p8_tails_and_counts | 1 raise | TEST_BUG | R1 | `board.json` on a REFUSED run |
| test_preflight | 2 | REAL_PRODUCTION_DEFECT | R3 | `WORKFLOW_STALE` |
| test_product_orchestration | 1+1 | TEST_BUG | R15/R1 | passes standalone; in-suite `the reproduction run sealed REFUSED` |
| test_publication_semantics | 1+1 | TEST_BUG | R1 | `FileNotFoundError` on the refused run's board |
| test_q9_live_feature_builder | 5+1 | UNKNOWN | — | `record 482/0 vs run 481/0`; an off-by-one in a window comparison |
| test_qb2_production | 13+2 | EXPECTED_GOVERNANCE_FAILURE | R1 | `the run seals [REFUSED]` |
| test_qb_eligibility_den_kc | 2+1 | OBSOLETE_CONTRACT | R2 | same pin |
| test_r5_active_pool | 2+1 | UNKNOWN | — | "the R5 branch returns a fatal on a status refusal" |
| test_readiness_vintage_cut | 2+1 | HISTORICAL_ARTIFACT_MISSING | R4 | no 2026 wk-1 injuries row in any capture |
| test_replay_pins_its_inputs | 1 | REAL_PRODUCTION_DEFECT | R14 | `REPLAY_RE_SELECTS` (D23) |
| test_sc2_interception_reservation | 1+1 | REAL_PRODUCTION_DEFECT | — | fitted 0.5390 vs injected 0.9251 (open task SC2-A) |
| test_sealed_corpus_census | 1+1 | TEST_BUG | R1 | discovery treats a refused run as a board |
| test_stat_contract | 2 | REAL_PRODUCTION_DEFECT | R7 | 271,691 non-integer, all week 1 |
| test_system_state | 5+1 | OBSOLETE_CONTRACT + STALE_FIXTURE | R8 + R10 | `KeyError: items`; `regenerate: system_state.py --write` |
| test_v1_draw_artifact | 3 | STALE_FIXTURE | R13 | `REQUIRED_SOURCE_NOT_DECLARED`: declares `['schedules']`, selects four |
| test_v1_rushing_a1 | 3 | TEST_BUG | R15 | passes standalone |

## Where this leaves UNKNOWN

**Three modules, down from twenty.** `test_inactives_substance`,
`test_q9_live_feature_builder`, `test_r5_active_pool`. Each has a specific
message and needs one focused look; none is hand-waved.

## What is worth fixing first, by modules-per-fix

1. **R1** (7 modules) — teach discovery to read `run_status.json.status` and
   `ARTIFACT.json.artifact` instead of treating any `player_draws.npz`
   directory as a sealed board. One contract, seven modules, and it is a
   TEST_BUG rather than a production change.
2. **R2** (6 modules) — decide what the Q9 pin asserts. A governance decision,
   not code.
3. **R3** (3) and **R5** (3) — both real, both already tracked.
4. **R9** (3 modules' checks never run under the runner) — `test_gadget_rush`
   alone reports **58 passed, 1 failed** when invoked directly, and the suite
   has never seen either number.

## The one that should worry an owner most

**R9.** Three modules' checks have been invisible to the runner, and one of
them is currently failing. That is the false-green class *inside the
measurement system* — the same defect `run_suite.py` was written to end, one
level further out.

**V2 NOT YET EARNED.**
