# WS11 — FALSE GREEN AUDIT

**Tests that validate stored artifacts instead of re-running the behaviour they claim to prove.**

    Repo            /home/user/nfl @ 57d38ad
    Interpreter     python3.12
    Scope           nfl/tests/test_*.py + sportsplatform/**/test_*.py
    Population      90 modules, 1019 test functions, 4541 `check(...)` call sites
    Date            2026-09-14
    CODE CHANGED    NO

No file outside `nfl/research/parallel_pass/ws11/` was created, edited or deleted.
No frozen evidence artifact was rewritten. Every module named below was read;
17 modules were additionally executed to distinguish a **latent** risk from a
**live** one.

---

## 1. What "false green" means here, precisely

A test is a FALSE_GREEN_RISK when all three hold:

1. It names a **behavioural property** of running code — determinism, identity,
   chronology, sealing, authorization, promotion, parity.
2. It **does not execute** the code path that would establish that property.
   It reads a record that a previous execution left behind, or it reads the
   source text of the implementation, or it asserts over a collection that can
   be empty.
3. There exists a **single plausible edit** to the implementation after which
   the property is false and the test is still green.

Point 3 is what separates a FALSE_GREEN_RISK from a legitimate
ARTIFACT_CONTENT_ASSERTION. Reading `j1_results.json` to check that a *frozen
historical experiment* declared its pre-registration and was labelled
EXPLORATORY is a correct use of an artifact: the claim is about the record, and
the record is the thing. Reading `Q9_PRODUCTION_PARITY.json` to check that
*production still reconciles bit-for-bit with the research harness* is not: the
claim is about code that is running today, and the record cannot know.

### The classes

| Class | Definition |
|---|---|
| `EXECUTABLE_BEHAVIORAL_PROOF` | Runs the implementation and asserts on what it computed. A regression fails it. |
| `ARTIFACT_CONTENT_ASSERTION` | Asserts on the content of a stored artifact. Legitimate when the claim is *about the record*. |
| `SNAPSHOT_TEST` | Asserts that the implementation's **source text** or a stored digest still contains/equals something. Catches deletion, not breakage. |
| `SMOKE_TEST` | Executes a path and checks only that it did not refuse. Two checks or fewer. |
| `FALSE_GREEN_RISK` | Meets all three conditions above. Assigned by hand, never mechanically. |

---

## 2. Calibration — both confirmed

### 2.1 `test_q9_prospective_shadow.py::test_21_the_dry_run_proof_holds` — CONFIRMED, and it is LIVE

The test reads `nfl/prospective/q9shadow/Q9_PROSPECTIVE_DRYRUN_PROOF.json`
(`_load()` at L78 is `json.loads(p.read_text()) if p.exists() else None`) and
asserts `pr['n_failed'] == 0 and pr['n_checks'] == 10`, plus six statements
about the *contents* of `pr['checks']`. It never calls
`nfl.prospective.q9shadow.dryrun`. Re-running the producer today:

    $ python3.12 -m nfl.prospective.q9shadow.dryrun
      FAIL  DETERMINISTIC   two seals of identical inputs DIFFER;
                            the sealing path is not deterministic
      PASS  OUTCOME_READERS_POISONED ... (9 others)
    status : DRY_RUN_PROOF_FAILED  (9/10)
    EXIT=1

The stored artifact still says `"state": "PASS"` for `DETERMINISTIC` with two
matching identity blocks. **The sealing path has already regressed and the
suite is green.** WS1 owns the repair; this audit only classifies it.

**What exactly moved, measured from the re-run's own output before it was
reverted.** The draws are *not* the problem. Across both runs and both teams,
`draw_artifact_sha256` and `draw_content_sha256` reproduced the stored values
exactly (`b370646b...` / `8c195431...` for ARI, `58b74c59...` / `9ff7c5e6...`
for BUF), and `spec_hash` and `feature_set_hash` were unchanged. What differed
was `artifact_id`, `forecast_id`, `seal_payload_sha256` and
`identity_fingerprint` — and they differed **between run1 and run2 of the same
invocation**, not merely from the record. So the non-determinism lives in the
seal payload / execution-identity construction, not in the model. That is a
narrower and more actionable statement than `DRY_RUN_PROOF_FAILED (9/10)`, and
it is offered to WS1 as a starting point, not as a diagnosis.

Note the second-order defect: the test's own check
`'draw_content_sha256' in c['DETERMINISTIC'].get('identity_keys_compared', [])`
reads as a guard against a weakened determinism comparison, and it too is
satisfied by the stale record.

### 2.2 `test_product_orchestration.py::test_identical_inputs_and_frozen_model_give_identical_draws` — the CORRECTED pattern

At HEAD this builds the board **twice under the code running now**
(`build_one(...)` into two temp dirs), compares all arrays and the
`draw_content_digest` between those two live builds, and only *then* compares
against the stored board — separately, under an explicit
`DECLARED_DRAW_CHANGES` allow-list. Its own comment states the principle:

> A guard that cannot tell "the draws are not reproducible" from "the model was
> deliberately changed" reports the wrong defect, and the fix is to measure the
> two separately.

That is the template every P0/P1 below should be repaired to: **re-run, compare
run-to-run, and treat drift-from-record as a separate, declared question.**

---

## 3. Ranked FALSE_GREEN_RISK list

### P0

#### FG-1 · `test_q9_prospective_shadow.py::test_21_the_dry_run_proof_holds`
- **Family** determinism / sealing / replay proof
- **Appears to claim** the Q9 shadow sealing path passed all ten dry-run proofs, determinism included.
- **Actually asserts** that a JSON file on disk contains `n_failed: 0`, `n_checks: 10`, and specific strings inside `checks`.
- **Regression not caught** the one that already happened: `seal.py` / `dryrun.py` producing two different seals from identical inputs. Also any future weakening of the identity key set, any outcome reader re-entering the namespace, any post-kickoff input — all ten proofs are record-only.
- **Severity** P0 — the claim is false *today*.

#### FG-2 · `test_q9b_model_family.py::test_i_parity_is_bit_for_bit_and_the_guard_fires`
- **Family** production/research parity, candidate identity
- **Appears to claim** the research allocator and the production layer (`nfl.production.nonqb.layers.appearance`, `nfl.research.q9.hurdle.allocate_hurdle`) reconcile bit-for-bit, and the TEST_ONLY mark propagates.
- **Actually asserts** that `nfl/research/q9b/Q9_PRODUCTION_PARITY.json` lists every invariant as `true`, that its `status` string agrees with its own invariants dict, and that `mismatches == []`. The module `production_parity` **is imported** (`PAR`) but only `PAR.INVARIANTS` is read — a name list. `PAR.run()` exists at `nfl/research/q9b/production_parity.py:150` and is **never called by any test in the repository** (verified by grep across all 90 modules).
- **Regression not caught** any edit to `layers.appearance`, `layers.targets_carries`, or `hurdle.allocate_hurdle` that breaks reconciliation, drops the shared upstream budget, or stops propagating `TEST_ONLY`. The only evidence of parity is a file that cannot change by itself.
- **Severity** P0 — sole parity proof for the production/research seam; nothing else in the suite covers it.

#### FG-3 · `test_q9_live_feature_builder.py::test_05_the_parity_artifact`
- **Family** candidate identity / sealing
- **Appears to claim** the live feature builder is EXACT-parity with the frozen historical builder inside week 1, that the out-of-window divergence is confined to history features, and that the containment check is non-vacuous.
- **Actually asserts** the contents of `Q9_LIVE_FEATURE_PARITY.json`, including the artifact's own self-report `wd['containment_check_is_not_vacuous'] is True`. `live_features.parity()` exists at `nfl/prospective/q9shadow/live_features.py:735` and is never called by a test. `test_06` does call `LF.build_team_week(2026, 1, 'ATL', ...)` but only checks `o.state is State.PASS` — it never compares the vector to the historical builder.
- **Regression not caught** any change to `live_features.build`, `live_rows`, or `_vector` that silently diverges from `_historical`. A non-vacuity flag that the *producer* writes cannot prove non-vacuity to a *consumer* that never re-runs the producer.
- **Severity** P0.

### P1

#### FG-4 · `test_q9b_model_family.py::test_j_the_freeze_records_identity_and_consumes_no_future`
- **Family** candidate identity / freeze
- **Appears to claim** the frozen Q9 candidate's identity is recorded and still holds.
- **Actually asserts** `mechanism_spec_version == Q9.SPEC_VERSION` and `stage_1_features_in_order == list(Q9.FEATURE_NAMES)` — both genuinely live — but for the four executing modules it asserts only
  `len(ci['module_source_sha16']) >= 4 and all(len(v) == 16 for v in ... .values())`. **The hashes are checked for length, never recomputed.** `freeze._module_hash(mod)` is a two-line helper sitting in the same package.
- **Verified during this audit** all four currently match (`q9.hurdle bb51133641338547`, `q9b.family 5b411b4f00e28e6f`, `q9b.production_parity 1f320b1ee3170e64`, `production.nonqb.layers 481f005f682cd721`), so the risk is **latent, not live**. `production_interface.version_sha16` likewise matches.
- **Regression not caught** any edit to any of the four modules. The freeze would silently stop describing the candidate it names, which is precisely the failure the freeze exists to prevent.
- **Severity** P1. One-line repair: recompute and compare.

#### FG-5 · `test_capture_manifest_integrity.py::test_the_guards_fail_when_bypassed`
- **Family** capture proof / guard-deletion control
- **Appears to claim** "Seed each defect and require rejection" — a falsification control proving the three capture guards are load-bearing.
- **Actually asserts** three `str not in str` comparisons between **string literals written inside the test body**:
  `'manifest rows appended: [1-9]' not in "if grep -qE '^FAIL '"`, and two more of the same shape. It opens no workflow YAML, no `capture_vintage.py`, no manifest. It is a tautology that increments `caught` to 3 unconditionally.
- **Regression not caught** deleting the `manifest rows appended: [1-9]` gate from both workflows, removing the `SOURCE_RAISED` row, removing `CAPTURE_WROTE_NO_MANIFEST_ROW` — this function stays green through all of it. (Partially redundant with `_wf_gate` and `test_a_run_that_writes_no_manifest_row_fails_loudly`, which do grep the real files; that redundancy is the only reason this is P1 rather than P0.)
- **Severity** P1. This is the most structurally hollow function found in the suite.

#### FG-6 · `test_q9_live_feature_builder.py::test_11_the_complete_parity_artifact`
- **Family** sealing / completeness / promotion guard
- **Appears to claim** the paired arm build shows exactly one divergence, the completeness gate is non-vacuous, and completeness today is truthfully PARTIAL.
- **Actually asserts** the contents of `Q9_COMPLETE_SHADOW_PARITY.json`, including its self-declared `completeness_gate.gate_is_not_vacuous`. `complete.run()` at `nfl/prospective/q9shadow/complete.py:269` is never called by a test.
- **Regression not caught** `assert_single_divergence`, `matrix`, or `completeness_value` breaking; a second layer starting to diverge; the completeness label silently becoming COMPLETE.
- **Severity** P1.

#### FG-7 · `test_r8_synthesis.py::test_k_is_not_estimated_from_the_forecast_season`
- **Family** chronology / leakage
- **Appears to claim** the reliability constant *k* is not estimated from the forecast season.
- **Actually asserts** nothing at all if `R8.enriched_frame()` does not PASS: `fr = R8.enriched_frame()` then `if fr.state is not State.PASS: return` — **a bare return with no `check()` before it.** The function then contributes **zero checks** and the module still passes, because `run_suite.py`'s VACUOUS branch is **module-scoped**, not function-scoped (`run_suite.py:105`, `elif ok == 0 and fns`).
- **Regression not caught** any data-availability change that makes `enriched_frame()` return non-PASS silently deletes a leakage guard. Verified today it runs and records 2 checks, so **latent**.
- **Severity** P1 — a leakage proof that can disappear without a sound.

#### FG-8 · `test_r7_appearance_frame.py::test_the_censoring_this_repair_exists_for_is_still_measurable`
- Same construction as FG-7, twice over: `if st.state is not State.PASS: print(...); return` and then `if fr.state is not State.PASS: return`. Records 2 checks today; can record zero.
- **Severity** P1.

#### FG-9 · `test_v1_entrypoint_integration.py` — four functions, halting and completeness semantics proven by windowed string search
  - `test_derived_gate_returns_a_named_refusal_not_a_raise`
  - `test_a_blocked_nonqb_layer_does_not_refuse_the_whole_game`
  - `test_blocked_layers_are_counted_as_absent_so_completeness_is_honest`
  - `test_required_stages_still_halt`
- **Appears to claim** that a blocked non-QB layer degrades to NOT_APPLICABLE rather than refusing the game; that blocked layers are counted absent so completeness is honest; that the required stages still halt.
- **Actually asserts** that literals (`'Outcome.not_applicable'`, `'o.code'`, `'layer_state'`, `'NONQB_CHAIN'`) appear inside a byte window of `nfl/production/run_forecast.py` delimited by `src.find(...)`. No forecast is run; no `Outcome` is inspected.
- **Regression not caught** inverting the branch, putting `Outcome.not_applicable` on a dead path, moving the required-stage tuple, or reaching the same window through a refactor that changes behaviour but keeps the tokens. The module credits itself with the strongest claims in the production path and executes none of them.
- **Severity** P1. (The module does contain genuine AST checks — the empty-placeholder-argument scan is good work — so this is a repair, not a rewrite.)

#### FG-10 · `test_warm_session.py::test_d_warm_and_cold_produce_identical_football`
- **Family** determinism
- **Appears to claim** warm-session and cold-cache sealing produce identical football.
- **Actually asserts** that two or more **already-stored** `board.json` files under `nfl/research/live/2026_01_BUF_HOU/` share a `draw_content_digest`. It seals nothing. It is a statement about seals written in the past by the code of their day.
- **Additionally** `if not reseals: print('  ..   ...skipped'); return` — zero checks, module still green.
- Verified today: it finds 7 re-seals of `pre_inactives_V1_CANDIDATE_R8` and records 6 checks. **Latent.**
- **Regression not caught** the warm-session cache becoming stale-serving *today*. The stored digests cannot move.
- **Severity** P1.

#### FG-11 · The silent-skip family — 25 functions, structural
A function that returns before recording any `check()` is invisible to
`run_suite.py`. The runner refuses a **module** that measured nothing
(`VACUOUS`, `run_suite.py:105`) but has no equivalent for a **function**.
`test_harness_audit.py::test_C_every_module_is_observed` audits the same
property at module granularity and inherits the same blind spot.

Full list (all verified **latent** — none is firing at HEAD; the 17 modules
exercised for this audit all reached their checks):

| Module::function | Skip condition |
|---|---|
| `test_forecast_completeness::test_b_a_qb_only_board_is_reported_as_qb_only` | `not got` |
| `test_forecast_completeness::test_c_a_complete_board_is_reported_as_full` | `not got` |
| `test_inactives_drill::test_the_pre_inactives_artifacts_are_immutable` | `not base.exists()` |
| `test_inactives_drill::test_the_real_empty_page_is_refused_under_every_team_spelling` | fixture absent |
| `test_inactives_drill::test_each_guard_is_load_bearing_on_its_own` | fixture absent |
| `test_inactives_drill::test_a_supplied_name_must_come_from_the_stored_bytes` | fixture absent |
| `test_inactives_propagation::test_tonights_roster_capture_is_free_of_posthoc_contamination` | roster status not PASS |
| `test_market_cdf::test_i_the_frozen_snapshot_is_read_and_never_rewritten` | snapshot blob absent |
| `test_postgame_ingestion::test_b_the_receiving_yards_field_maps_to_the_realised_key` | `not nac` |
| `test_postgame_ingestion::test_c_the_automatic_scoring_reproduces_the_manual_review` | `not rows` |
| `test_postgame_ingestion::test_d_the_qb_room_is_scored_beside_the_individuals` | `not rows` |
| `test_postgame_ingestion::test_e_rerunning_on_unchanged_bytes_adds_nothing` | `not rows` |
| `test_postgame_ingestion::test_g_provenance_is_preserved_for_every_stored_outcome` | `not provs` |
| `test_q7_efficiency_calibration::test_f_the_log_score_is_exact_where_it_exists...` | `rows is None` (2 checks already banked) |
| `test_qb_pyds_market_eligibility::test_b_the_chain_reaches_ranking_eligible_for_qb_pyds` | `real is None` |
| `test_r7_appearance_frame::test_the_censoring_this_repair_exists_for_is_still_measurable` | panel / frame not PASS |
| `test_r8_synthesis::test_k_is_not_estimated_from_the_forecast_season` | frame not PASS |
| `test_research_daily_board::test_d_every_row_carries_its_candidate_and_promoted_stays_false` | no sealed boards |
| `test_research_daily_board::test_g_the_comparison_is_same_cutoff_and_actuals_only_when_known` | no sealed boards |
| `test_research_daily_board::test_i_it_reads_sealed_artifacts_and_runs_nothing` | `not found` |
| `test_slate_runner::test_a_discovery_needs_no_hand_supplied_game_list` | no schedule vintage |
| `test_volatility::test_B_the_three_valued_answer` | records `blocked()` — **honest, not a defect** |
| `test_volatility::test_F_the_rule_is_load_bearing` | records `blocked()` — **honest, not a defect** |
| `test_warm_session::test_d_warm_and_cold_produce_identical_football` | `not reseals` |
| `test_q9_live_feature_builder::test_04b/06`, `test_q9_prospective_shadow::test_11/22` | guarded by a preceding `check()` — **not silent** |

`test_volatility.py` shows the correct construction: a `blocked()` counter that
is "counted apart and never as a pass" (`test_volatility.py:51`). Every other
row in this table should adopt it.

- **Severity** P1 as a class; individually P1 for the chronology/determinism
  entries (FG-7, FG-8, FG-10) and P2 for the rest.

### P2

#### FG-12 · `test_nonqb_r3.py::test_l_recorded_slate_rehearsal_is_real_and_refused` and `::test_K_recorded_engine_rehearsal_is_quarantined`
Read `slate_rehearsal.json` / `engine_rehearsal.json` and assert that every layer
executed, that accounting reconciled over 100 000+ cells, and that publication is
refused on every game. The producers (`slate_rehearsal.build`, the engine
rehearsal driver) are runnable and not run. `test_l` already carries a scar from
exactly this: the committed artifact drifted off the shape the test asserted and
only surfaced when someone re-ran the producer by hand. **P2** because the
underlying layers are separately covered by 18 executable proofs in the same
module.

#### FG-13 · `test_accounting_invariants.py::test_e_the_real_data_audit`
Claims the invariants hold "measured on the real 2020-2025 pbp"; asserts that
`nfl/accounting/accounting_audit.json` says `state == 'PASS'` for eight named
invariants. The invariant *functions* are exercised on synthetic data elsewhere
in the module, so a logic break is caught; what is not caught is the audit going
stale against a changed corpus or a changed denominator. **P2.**

#### FG-14 · Vacuous-`all()` over a filtered collection
37 `all(...)` call sites iterate a comprehension with an `if` filter and no
accompanying non-emptiness assertion. Most are safe by construction. Two worth
naming:
- `test_v1_game_dependence.py::test_G_determinism_and_per_game_streams` L243 —
  `all(np.array_equal(...) for k in a.value if k[1] in ('NE', 'SEA'))`. The
  pair-order-invariance claim passes vacuously if the key tuple shape changes.
- `test_qb3_allocation.py::test_G_recorded_results_meet_the_predeclared_rule` —
  three `all(... for e in r['evaluation_seasons_run'])` over a list read from
  the artifact; an empty list passes all three.
Good counter-example: `test_td2_recoverability.py::test_f_training_never_sees_the_evaluation_season`
writes `all(r['season'] < ev for r in tr) and len(tr) > 100` — the non-emptiness
is part of the check. **P2.**

#### FG-15 · The source-text-proxy family
66 test functions carry 133 assertions of the form `'literal' in src` /
`in window` / `in body` against the text of a production module. They catch
deletion of a token and nothing else. Heaviest:
`test_c1_denominator::test_b` (9), `test_v1_draw_artifact::test_the_production_path_actually_uses_all_of_this` (8),
`test_td2_recoverability::test_b` (6), `test_xl1_shared_pass::test_L` (5).
Several are defensible (checking a constant is *estimated* rather than
hard-coded genuinely is a source-level property, and the repository has been
burned by comment-matching before — see the AST repair documented in
`test_v1_entrypoint_integration.py:113`). They are listed as SNAPSHOT_TEST, not
FALSE_GREEN_RISK, except where the claim is behavioural (FG-9). **P2.**

---

## 4. Legitimate artifact assertions — explicitly NOT defects

These read stored artifacts and that is correct, because the claim is about the
record and the record is frozen evidence. Recorded here so a later pass does not
"repair" them:

`test_j1_joint_volume::test_F_recorded_j1_result` · `test_own10_dependence_metric::test_results_record_the_rejection_and_promote_nothing`
· `test_xl1_shared_pass::test_A/test_I` · `test_v1_game_dependence::test_I/test_J`
· `test_v1_teammate_dependence::test_I` · `test_c1_denominator::test_g`
· `test_forensic_corrected::test_a..test_i` · `test_q6/q7/q8/q9_target_hurdle/track1` results blocks
· all `predeclaration_*.md` sha256 pins.

Each states a pre-registration hash, an EXPLORATORY label, a promoted-False flag,
or a recorded contrast. Re-running them would be a different experiment, not a
stronger test. Two of them are exemplary: `test_own10` refuses an absent artifact
with `check(..., False)` and a named cause rather than returning silently, and
`test_c1_denominator::test_c` **recomputes** `CAND.identity_sha256(CAND.identity(season))`
and compares it to the sealed value instead of trusting the seal's own copy.

---

## 5. Evidence ceiling

What this audit establishes, and what it does not.

**Established.**
- The population is exactly 90 modules / 1019 test functions / 4541 `check(...)`
  sites, enumerated from the filesystem by the same globs `run_suite.py` uses,
  not from any count written down.
- FG-1 is **live**: the producer was re-run and disagrees with the artifact the
  test reads. That is a measurement, not an inference.
- FG-2, FG-3, FG-6 rest on a grep across all 90 modules showing `PAR.run`,
  `LF.parity`, `complete.run`, `reuse.disposition_record` and `dryrun.run` have
  **no call site in any test**. That is a complete search of the test tree.
- FG-4's four module hashes were recomputed against the live source during this
  audit and all four match, so it is latent.
- The 25 silent skips were found by AST, and 17 modules were executed to confirm
  none is currently firing.
- `run_suite.py`'s VACUOUS rule is module-scoped: read at `run_suite.py:105`.

**Not established.**
- **73 of 90 modules were not executed.** The instruction was not to run the full
  suite while other agents are working. So "latent, not live" is asserted only
  for the 17 modules run: `test_q9_prospective_shadow` (producer only),
  `test_warm_session`, `test_forecast_completeness`, `test_postgame_ingestion`,
  `test_research_daily_board`, `test_inactives_drill`, `test_market_cdf`,
  `test_volatility`, `test_slate_runner`, `test_qb_pyds_market_eligibility`,
  `test_r7_appearance_frame`, `test_r8_synthesis`, `test_q7_efficiency_calibration`,
  `test_inactives_propagation`, plus targeted single functions. **Any of the
  other silent skips may be firing right now and this audit cannot say.**
- The classification of the 1019 functions into the four non-risk classes is
  **mechanical** (AST + regex heuristics: production-call count, artifact read,
  source-text membership count, check count). It is a triage aid. Every
  FALSE_GREEN_RISK above was assigned by reading the function; none was assigned
  by the classifier.
- The mechanical classifier will over-report `SMOKE_TEST` for functions whose
  assertions live in a helper (`_covers`, `_wf_gate`, `_is`), and will
  over-report `EXECUTABLE_BEHAVIORAL_PROOF` for functions that call production
  code only to build a fixture and then assert on an artifact. Module-level
  counts in §6 should be read as a distribution, not a verdict per cell.
- No claim is made that the FALSE_GREEN_RISK list is exhaustive. It is the result
  of four mechanical sweeps (skip guards, artifact-only reads, vacuous `all`,
  source-text membership) plus hand-reading every test function in the nine
  priority claim families. A fifth pattern — a test that mutates global state a
  later test depends on — was not searched for.
- Whether FG-1's determinism failure is a defect in `seal.py` or in the dry-run
  harness was **not** diagnosed. WS1 owns that.

---

## 6. Full classification table, by module

`E` = EXECUTABLE_BEHAVIORAL_PROOF · `A` = ARTIFACT_CONTENT_ASSERTION ·
`S` = SNAPSHOT_TEST · `K` = SMOKE_TEST. FALSE_GREEN_RISK is assigned by hand in
§3 and overrides the mechanical class for the 15 functions named there.

| Module | n | E | A | S | K |
|---|---|---|---|---|---|
| `test_accounting_invariants` | 8 | 8 | 0 | 0 | 0 |
| `test_align_geometry` | 7 | 6 | 1 | 0 | 0 |
| `test_attribution` | 3 | 3 | 0 | 0 | 0 |
| `test_availability_retention` | 11 | 11 | 0 | 0 | 0 |
| `test_availability_watch` | 20 | 18 | 0 | 0 | 2 |
| `test_c1_denominator` | 7 | 3 | 1 | 3 | 0 |
| `test_capture_manifest_integrity` | 10 | 7 | 1 | 1 | 1 |
| `test_capture_schedule` | 9 | 9 | 0 | 0 | 0 |
| `test_capture_states` | 11 | 10 | 0 | 0 | 1 |
| `test_capture_windows` | 12 | 12 | 0 | 0 | 0 |
| `test_coverage` | 10 | 10 | 0 | 0 | 0 |
| `test_daily_board` | 9 | 7 | 0 | 0 | 2 |
| `test_delivered_injury_ingest` | 13 | 7 | 6 | 0 | 0 |
| `test_denominator_validation` | 12 | 11 | 0 | 0 | 1 |
| `test_discharge_identity` | 12 | 6 | 0 | 0 | 6 |
| `test_draw_row_identity` | 10 | 2 | 0 | 1 | 7 |
| `test_effective_scope` | 13 | 13 | 0 | 0 | 0 |
| `test_execution_target` | 19 | 19 | 0 | 0 | 0 |
| `test_football_engine_r4` | 17 | 12 | 1 | 0 | 4 |
| `test_forecast_completeness` | 7 | 6 | 0 | 0 | 1 |
| `test_forecast_stage_product` | 6 | 6 | 0 | 0 | 0 |
| `test_forensic_corrected` | 10 | 3 | 7 | 0 | 0 |
| `test_full_slate_rehearsal` | 7 | 7 | 0 | 0 | 0 |
| `test_harness_audit` | 5 | 3 | 0 | 2 | 0 |
| `test_identifier_mapping` | 9 | 6 | 0 | 0 | 3 |
| `test_inactives_drill` | 9 | 7 | 1 | 0 | 1 |
| `test_inactives_propagation` | 19 | 6 | 2 | 0 | 11 |
| `test_injury_parser` | 15 | 15 | 0 | 0 | 0 |
| `test_j1_joint_volume` | 7 | 5 | 1 | 0 | 1 |
| `test_market_cdf` | 12 | 11 | 0 | 0 | 1 |
| `test_market_quote_accounting` | 8 | 6 | 2 | 0 | 0 |
| `test_non_g0a_isolation` | 12 | 11 | 0 | 0 | 1 |
| `test_nonqb_r3` | 28 | 18 | 2 | 1 | 7 |
| `test_own10_dependence_metric` | 10 | 4 | 5 | 1 | 0 |
| `test_own9_write_guard` | 6 | 5 | 1 | 0 | 0 |
| `test_perishable_immutability` | 13 | 9 | 1 | 0 | 3 |
| `test_postgame_guards` | 14 | 12 | 2 | 0 | 0 |
| `test_postgame_ingestion` | 9 | 8 | 1 | 0 | 0 |
| `test_preflight` | 6 | 5 | 0 | 0 | 1 |
| `test_product_layer` | 17 | 12 | 0 | 0 | 5 |
| `test_product_orchestration` | 14 | 10 | 2 | 2 | 0 |
| `test_production_pipeline` | 9 | 5 | 0 | 1 | 3 |
| `test_prospective_contract` | 8 | 8 | 0 | 0 | 0 |
| `test_provenance_read_before_write` | 7 | 5 | 0 | 0 | 2 |
| `test_q6_appearance_role` | 14 | 13 | 0 | 0 | 1 |
| `test_q7_efficiency_calibration` | 13 | 13 | 0 | 0 | 0 |
| `test_q8_target_opportunity` | 12 | 11 | 1 | 0 | 0 |
| `test_q9_live_feature_builder` | 34 | 28 | 5 | 1 | 0 |
| `test_q9_prospective_shadow` | 24 | 17 | 3 | 0 | 4 |
| `test_q9_target_hurdle` | 11 | 10 | 0 | 0 | 1 |
| `test_q9b_model_family` | 11 | 2 | 8 | 0 | 1 |
| `test_qb2_production` | 20 | 16 | 0 | 1 | 3 |
| `test_qb3_allocation` | 8 | 7 | 1 | 0 | 0 |
| `test_qb_inactive_ownership` | 15 | 15 | 0 | 0 | 0 |
| `test_qb_pyds_market_eligibility` | 5 | 4 | 0 | 0 | 1 |
| `test_quarantine` | 10 | 9 | 0 | 0 | 1 |
| `test_r5_active_pool` | 8 | 4 | 0 | 2 | 2 |
| `test_r6_role_prior` | 8 | 4 | 0 | 2 | 2 |
| `test_r7_appearance_frame` | 20 | 10 | 0 | 1 | 9 |
| `test_r8_synthesis` | 20 | 9 | 0 | 3 | 8 |
| `test_rc1_receiving` | 11 | 8 | 3 | 0 | 0 |
| `test_readiness_vintage_cut` | 9 | 6 | 0 | 0 | 3 |
| `test_research_daily_board` | 10 | 5 | 3 | 0 | 2 |
| `test_routes_adapter` | 5 | 3 | 0 | 1 | 1 |
| `test_schema_and_scoring` | 8 | 4 | 0 | 1 | 3 |
| `test_seal_ordering` | 10 | 9 | 1 | 0 | 0 |
| `test_sealed_index` | 7 | 6 | 0 | 0 | 1 |
| `test_shadow_evaluation` | 12 | 3 | 0 | 0 | 9 |
| `test_slate_runner` | 10 | 10 | 0 | 0 | 0 |
| `test_source_registry` | 9 | 8 | 1 | 0 | 0 |
| `test_t90_synthetic_eligibility` | 10 | 9 | 0 | 1 | 0 |
| `test_t90_workflow` | 7 | 7 | 0 | 0 | 0 |
| `test_td2_recoverability` | 8 | 5 | 1 | 2 | 0 |
| `test_track1_state_offense` | 18 | 16 | 0 | 0 | 2 |
| `test_v1_composition_fidelity` | 7 | 4 | 0 | 0 | 3 |
| `test_v1_draw_artifact` | 17 | 16 | 0 | 1 | 0 |
| `test_v1_entrypoint_integration` | 8 | 4 | 0 | 4 | 0 |
| `test_v1_game_dependence` | 11 | 8 | 2 | 0 | 1 |
| `test_v1_game_stream_separation` | 7 | 5 | 0 | 2 | 0 |
| `test_v1_nonqb_production` | 8 | 5 | 0 | 2 | 1 |
| `test_v1_rushing_a1` | 22 | 21 | 0 | 0 | 1 |
| `test_v1_scramble_coherence` | 10 | 5 | 0 | 0 | 5 |
| `test_v1_teammate_dependence` | 10 | 9 | 1 | 0 | 0 |
| `test_volatility` | 15 | 14 | 1 | 0 | 0 |
| `test_warm_session` | 7 | 4 | 1 | 1 | 1 |
| `test_xl1_shared_pass` | 17 | 13 | 2 | 1 | 1 |
| `test_artifact_reference` | 8 | 5 | 3 | 0 | 0 |
| `test_outcome` | 11 | 11 | 0 | 0 | 0 |
| `test_provenance` | 6 | 6 | 0 | 0 | 0 |
| `test_scorecard` | 8 | 8 | 0 | 0 | 0 |
Totals: **776 E · 74 A · 38 S · 131 K** across 1019 functions.

---

## 7. The one structural repair that closes most of this

Three of the four patterns above share a single enabler: **a test function is
allowed to record zero checks.**

`run_suite.py` already refuses a module that measured nothing. Extending the
same rule to functions — record the tally before and after each `getattr(mod, n)()`
and report `VACUOUS FUNCTION` when it did not move — turns all 25 silent skips
from invisible into loud, without touching a single test. It is a change to the
runner, not to any evidence.

The second repair is smaller and specific: the four artifact-only proofs
(FG-1, FG-2, FG-3, FG-6) each have a producer function sitting one import away.
Calling it and comparing its output to the stored artifact — the
`test_product_orchestration` pattern of §2.2, run-twice-then-compare-to-record —
converts each from a record assertion into an executable proof. The stored
artifacts stay exactly where they are; nothing frozen is rewritten.

The third is one line: `test_q9b_model_family::test_j` should call
`freeze._module_hash` on the four modules it names and compare, instead of
checking that the recorded hashes are 16 characters long.

---

## 8. Provenance of this document

Method, in order:
1. AST enumeration of all `test_*` functions in the two glob sets `run_suite.py`
   uses. 90 modules, 1019 functions, 4541 `check(...)` sites.
2. Sweep 1 — early-return guards (93 functions), then refined to distinguish
   guards preceded by a recorded `check()` (49, loud) from bare returns
   (25, silent).
3. Sweep 2 — functions that read a file and call no production function
   (102 functions).
4. Sweep 3 — `all(...)` over a filtered comprehension (37 sites).
5. Sweep 4 — `'literal' in src|window|body` membership (66 functions, 133 sites).
6. Hand-reading of every test function in the nine priority claim families.
7. Execution of `nfl.prospective.q9shadow.dryrun` and of 17 test modules /
   isolated functions to separate live from latent.
8. Grep of the full test tree for call sites of the five producer functions.

Commands used are reproducible from this repository with `python3.12` and no
network. No test was modified to produce any result above.

**CODE CHANGED: NO**

---

## 9. A side effect of this audit, and its reversal

Running `python3.12 -m nfl.prospective.q9shadow.dryrun` to obtain the evidence
in §2.1 **wrote to the repository**: it overwrote
`nfl/prospective/q9shadow/Q9_PROSPECTIVE_DRYRUN_PROOF.json` with the failing
9/10 result and appended six rows to
`nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl`. That was not
intended and is outside this workstream's write boundary.

Both files were restored with `git checkout --` to their committed state. The
diffs were inspected first and were **100% attributable to this run** — the
proof file matched HEAD before the run, and all six ledger rows carried
forecast_ids this run produced — so nothing belonging to another agent was
reverted. Verified after restore: the artifact again reads
`DETERMINISTIC: PASS`, `n_checks 10`, `n_failed 0`. The sealed dry-run
forecasts under `dryrun/2024_01_ARI_BUF/` (dated 09-12) were not touched; only
the parent directory's mtime moved, from a temporary subdirectory the run
created and removed.

The failing output itself is preserved outside the repository, in this
session's scratchpad, and is quoted verbatim in §2.1. It is not re-committed
here: **the stale artifact is the evidence of FG-1** and replacing it would
destroy the finding while appearing to fix it. WS1 should re-derive it.

Recorded rather than quietly cleaned up, because a producer that writes into the
tree as a side effect of being *measured* is itself worth knowing about: any
agent who runs this dry-run to check on it will silently rewrite the artifact
the test reads, and the suite will then go red for a reason unrelated to their
change.

**CODE CHANGED: NO** — two artifacts were written by a producer invocation and
restored to their committed bytes in the same session. No source file, no test,
and no frozen evidence was altered.
