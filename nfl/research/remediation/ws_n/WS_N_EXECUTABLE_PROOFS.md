# WS-N — EXECUTABLE PROOFS

    Repo          /home/user/nfl @ 837d52f, branch claude/nfl-greenfield-architecture-stsxmk
    Interpreter   python3.12
    Date          2026-09-14
    Owns          nfl/tests/run_suite.py
                  nfl/tests/test_q9_prospective_shadow.py
                  nfl/tests/test_q9b_model_family.py
                  nfl/tests/test_q9_live_feature_builder.py
    Touched       exactly those four. No production module, no frozen artifact,
                  no other workstream's test file.

---

## DEFECT

Three P0 tests named a behavioural property and asserted only the contents of a
stored file. The producers that would establish those properties exist, are
correct, and had **no call site in any of the 90 test modules** — confirmed by
grep across the whole test tree before anything was changed.

| | Test | Named property | What it actually read |
|---|---|---|---|
| FG-1 | `test_q9_prospective_shadow::test_21_the_dry_run_proof_holds` | the Q9 sealing path passes all ten dry-run proofs, determinism included | `Q9_PROSPECTIVE_DRYRUN_PROOF.json` says `n_failed: 0, n_checks: 10` |
| FG-2 | `test_q9b_model_family::test_i_parity_is_bit_for_bit_and_the_guard_fires` | research allocator and production layer reconcile bit-for-bit | `Q9_PRODUCTION_PARITY.json` lists every invariant `true` |
| FG-3 | `test_q9_live_feature_builder::test_05_the_parity_artifact` | live feature builder is EXACT-parity with the frozen historical builder | `Q9_LIVE_FEATURE_PARITY.json`, including its own `containment_check_is_not_vacuous: true` |

FG-3 is the sharpest statement of the class: a non-vacuity flag that the
**producer** writes cannot prove non-vacuity to a **consumer** that never
re-runs the producer.

A fourth, structural defect sat underneath them. `run_suite.py` refused a
**module** that recorded zero checks but had no equivalent for a **function**,
so a test function that hit `if not rows: return` before its first `check()`
contributed nothing and said nothing, while its siblings kept the module's
counter above zero.

## ROOT CAUSE

One cause, three instances, and it is not carelessness. Each of these tests was
written at the moment its producer was run, when the artifact on disk and the
behaviour of the code were the same thing. Nothing in the harness noticed when
they stopped being the same thing, because the test was reading the half that
cannot change by itself. The artifact is a photograph; the suite was checking
that the photograph still looked like the photograph.

The runner's module-scoped VACUOUS rule has the same shape: it was written
against the failure it had seen (a whole module measuring nothing) and the same
failure one level down was invisible.

## REPAIR

**Re-run the property, and ask drift-from-record as a separate, named
question.** This is the pattern `test_product_orchestration::test_identical_
inputs_and_frozen_model_give_identical_draws` already uses and that WS11 §2.2
nominated as the template. Each of the three became two functions:

* an `EXECUTABLE_BEHAVIORAL_PROOF` that calls the producer and asserts on what
  today's code computed;
* an `ARTIFACT_CONTENT_ASSERTION`, declared as one in its docstring, that keeps
  the stored record and asks only whether it still describes the behaviour.

No artifact was deleted, rewritten, or moved. Where record and behaviour
disagree the check fails and says which is which; the behaviour is the truth.

And in the runner: the module tally is now read **around every test function**,
not once around the module. A function whose delta is zero is named and fails
the suite.

### The escape hatch is `blocked()`, and there is deliberately no allow-list

A function that genuinely cannot run says so by incrementing a BLOCKED counter.
`test_volatility.py:51` shows the construction and states the rule — "counted
apart and never as a pass". The runner now reads that counter too: a function
that recorded only blocked checks is printed as BLOCKED and does not fail the
suite. It is still not a pass.

There is no list of functions exempted by name. An exemption list is how a
silent skip comes back wearing a permit.

### One structural exemption, recognised by shape and not by name

50 modules end with

    def test_zz_every_check_passed():
        if FAILED:
            raise AssertionError(...)

which records no check and never could — it re-raises the counter the runner
already reads, so that a bare `python3.12 nfl/tests/test_x.py` turns red too.
Counting all 50 would put 50 false entries in front of the real ones, and a
list nobody can read is a list nobody reads.

`run_suite.tally_tripwires()` recognises them **structurally**: a function
qualifies only if it raises or asserts, mentions a failure counter, and calls
nothing except `print` and `AssertionError`. Anything that calls production
code, or `check`, or reads an artifact is not a tripwire whatever it is called,
so this cannot become a hiding place. Verified: it matches exactly the 50
aggregators and nothing else.

## POST-REPAIR RESULT

Measured with `python3.12 nfl/tests/run_suite.py --only <module>`, one module at
a time. **The full suite was not run**, by instruction. The machine was carrying
twenty-odd concurrent workstreams throughout, which matters for FG-1 below and
for nothing else.

| Module | functions | checks | failing | raised | zero-check | blocked | verdict |
|---|---|---|---|---|---|---|---|
| `test_q9b_model_family` | 12 (was 11) | 78 (was 68) | 0 | 0 | 0 | 0 | **SUITE PASS** |
| `test_q9_live_feature_builder` | 35 (was 34) | 382 | 0 | 0 | 0 | 0 | **SUITE PASS** |
| `test_q9_prospective_shadow` | 25 (was 24) | see below | — | 0 | 0 | 0 | **SUITE FAIL — FG-1** |

`test_q9b_model_family` is the one module with a genuine before-number: it was
run under the new runner *before* the test edit and recorded 11 functions / 68
checks / SUITE PASS. The other two were not run before editing, so their
"was" columns are function counts from `git show HEAD:` and their check counts
have no pre-image. Said rather than implied.

### FG-2 — production/research parity: **PASSES when it is run**

`PAR.run(2024, 200 draws, seed 20260925, 12 games)` executed inside the suite.
All eight invariants true on today's code, `PARITY_HOLDS`, `mismatches == []`,
reconciliation error exactly 0.0 on all 12 games, every game bit-identical to
the research harness, TEST_ONLY propagating on every game. The stored artifact
agrees with the run on slice, seed, spec version, every invariant, status,
budget estimator and the per-game reconciliation error.

So the claim the old test made was true — but it was true by luck, not by
evidence, and it is now held up by something that would notice if it stopped
being true.

### FG-3 — live feature parity: **PASSES when it is run**

`LF.parity(2024, 48)` executed inside the suite. `builder_parity == EXACT`,
482 players compared inside week 1 and **0 differing on any of the 25
features**, `mismatches == []`. Outside the window, 156 of 232 players differ
and every differing feature is a history feature —
`non_history_features_that_differed == []`.

The non-vacuity is now established **in the consumer**: 13 of the 25 features
are outside the history set, the two sets partition the schema exactly and do
not intersect, so containment could have failed and did not. Measured, not
read off the producer's own flag.

Worth recording because it was checked rather than assumed: at 24 team-games
the out-of-window comparison is **empty** (0 compared, 0 differing) and the
containment check passes vacuously. 48 is the span that makes it mean
something. That is why the configuration is declared in the test.

### FG-1 — Q9 sealing determinism: **FAILS, twice, for two different reasons**

This is the one that was expected to fail, and the honest test was written and
left failing. What actually happened is more interesting than that.

**Measurement 1, 11:47 UTC, before WS-E's repair landed.**

    status          DRY_RUN_PROOF_FAILED  (9/10)
    DETERMINISTIC   FAIL -- two seals of identical inputs DIFFER

    run 1   ARI  NFLFP-1b5e17a5e51854e4
            BUF  NFLFP-73b47367675b3a26
    run 2   ARI  NFLFP-73b47367675b3a26      <- run 2's FIRST == run 1's SECOND
            BUF  NFLFP-73b47367675b3a26

Draws reproduced exactly in every case (`draw_content_sha256`,
`draw_artifact_sha256`, `spec_hash`, `feature_set_hash` all stable). Only the
identity moved, and it moved **within** run 1 — which is the fingerprint of a
run changing its own identity by writing its own outputs.

**Measurement 2, 12:12 UTC, after WS-E's repair.**

    status          DRY_RUN_PROOF_FAILED  (9/10)
    DETERMINISTIC   FAIL

    run 1   ARI  NFLFP-447f1c44e371d3a6
            BUF  NFLFP-447f1c44e371d3a6      <- run 1 is internally consistent
    run 2   ARI  NFLFP-f7489809e3990b25
            BUF  NFLFP-f7489809e3990b25      <- so is run 2, and they differ

**The shape changed and the shape is the diagnosis.** Run 1's two seals now
agree with each other and run 2's two agree with each other; the two runs
disagree. Against WS-E's table that is row 1 — **in-scope source changed
between the two seals** — not row 2 (sealed body reading outside state) and not
row 3 (predictive nondeterminism, still never observed). WS-E measured in-scope
dirty source going 9 → 20 in under an hour as other workstreams edited
`nfl/production/**` and `nfl/product/**`; this run straddled some of that.

So: **WS-E's repair did what it claims**, and the residual failure is a property
of a checkout twenty-four workstreams are writing to, not of the sealing path.
The test is nonetheless right that the two runs were not identical, and it was
**not** softened to accommodate the shared tree — it now classifies its own
failure against WS-E's three rows and prints which one it hit. On a quiescent
tree it should pass with no edit.

`nfl/tests/**` is deliberately outside WS-E's dirty-source scope
(`code_identity.SOURCE_ROOTS`), so no edit made by this workstream can move a
run id. A failure here is never caused by the test's own changes.

### And the finding that belongs in the reclassification table

WS-E established that the **pre-repair `DETERMINISTIC` check was itself inert
against the defect it appeared to cover**: `git status --porcelain` collapses an
untracked directory to one line, so writing a second file into `dryrun/proof/`
often did not move the count. It passed while the defect was live — not because
it was wrong, but because it was not measuring.

That is a false green **nested inside the proof that FG-1 was asserting about**,
and it is the strongest single argument for this whole change. FG-1 read a file;
the file was written by a check that was not measuring; nobody could see either
layer. Two records stacked on each other, and no execution anywhere in the
chain.


---

## WHY THIS REPAIR AND NOT ANOTHER

Three alternatives were available and each is worse.

**Delete the artifact assertions.** Rejected. A stored proof is evidence of
what was measured on the day it was written, and WS11 §4 correctly lists a
class of tests whose claim genuinely *is* about the record. Deleting them
destroys evidence to make a point about method. They stay, reclassified.

**Re-run and compare only against the artifact.** Rejected, and this is the
subtle one. A guard that cannot tell "the property no longer holds" from "the
model was deliberately changed" reports the wrong defect. Run-to-run is the
property; run-against-record is a different question with a different answer,
and they are asked separately here.

**Mark FG-1 expected-fail so the suite stays green.** Refused. See below.

## PRE-REPAIR FAILURE — what the old tests could not have caught

Not hypothetical for FG-1. The producer was re-run on 2026-09-14 and disagrees
with the artifact the test reads:

    $ python3.12 -c "from nfl.prospective.q9shadow import dryrun; dryrun.run()"
      DETERMINISTIC   FAIL  two seals of identical inputs DIFFER
      status          DRY_RUN_PROOF_FAILED  (9/10)

while `Q9_PROSPECTIVE_DRYRUN_PROOF.json` still reads `"state": "PASS"` on ten
of ten. **The sealing path had already regressed and this module was green.**

What moved is narrow, and saying so tells WS-E where not to look.
`draw_artifact_sha256` and `draw_content_sha256` reproduce exactly across runs,
and so do `spec_hash` and `feature_set_hash` — the model is deterministic. What
differs is `artifact_id`, `forecast_id`, `seal_payload_sha256` and
`identity_fingerprint`, and they differ **between two runs of one invocation**,
not merely from the record. The execution identity is unstable; the football is
not.

**Measured mechanism, offered as a lead and not as a diagnosis** — `seal.py` is
WS-E's and was not touched. `seal._code_commit()` (`seal.py:162`) returns
`<rev>+dirty[n]` where *n* is the number of lines `git status --porcelain`
prints. The run's own outputs are new untracked paths, so *n* moves underneath
it. The observed identities fit that exactly:

| | run 1 | run 2 |
|---|---|---|
| ARI `identity_fingerprint` | `NFLFP-1b5e17a5e51854e4` | `NFLFP-73b47367675b3a26` |
| BUF `identity_fingerprint` | `NFLFP-73b47367675b3a26` | `NFLFP-73b47367675b3a26` |

Run 2's *first* team matches run 1's *second* team. `_code_commit()` is called
before `out_dir.mkdir()`, so ARI in run 1 is stamped at *n*, and every seal
after it at *n+1*, because writing ARI's draws added a `git status` line. A
code version that counts the artifacts the run is producing is not a code
version.

### FG-1 is left failing, on purpose

The honest test fails today. It was not skipped, softened, marked
expected-fail, or pointed at a smaller slice. A red test that describes reality
is worth more than a green one that does not, and the repair belongs in the
sealing path. The reasoning is written into the module above the function so
that the next reader does not "fix" it by making it green.

---

## NEWLY-VISIBLE ZERO-CHECK FUNCTIONS

### What "newly visible" can and cannot mean here

The runner change makes a function visible **when it fires**. At HEAD almost
none of them is firing — WS11 executed 17 modules and found none live, and this
pass was instructed not to run the full suite while other workstreams are
editing the tree, so a dynamic list would be a list of 3 modules, not 90.

What is delivered instead is the **complete structural population**: every test
function in all 90 modules that can reach a `return` with nothing banked. That
is strictly more complete than a dynamic list at HEAD, where these are latent
by definition. Enumerated by AST over the same globs `run_suite.py` uses.

**19 functions across 10 modules. All 19 are dishonest.**

| # | Module::function | Skip condition | Verdict |
|---|---|---|---|
| 1 | `test_forecast_completeness::test_b_a_qb_only_board_is_reported_as_qb_only` | `not got` → print, return | DISHONEST |
| 2 | `test_forecast_completeness::test_c_a_complete_board_is_reported_as_full` | `not got` → print, return | DISHONEST |
| 3 | `test_inactives_drill::test_the_pre_inactives_artifacts_are_immutable` | `not base.exists()` | DISHONEST |
| 4 | `test_inactives_drill::test_the_real_empty_page_is_refused_under_every_team_spelling` | fixture absent | DISHONEST |
| 5 | `test_inactives_drill::test_each_guard_is_load_bearing_on_its_own` | fixture absent | DISHONEST |
| 6 | `test_inactives_drill::test_a_supplied_name_must_come_from_the_stored_bytes` | fixture absent | DISHONEST |
| 7 | `test_inactives_propagation::test_tonights_roster_capture_is_free_of_posthoc_contamination` | roster status not PASS | DISHONEST |
| 8 | `test_market_cdf::test_i_the_frozen_snapshot_is_read_and_never_rewritten` | snapshot blob absent | DISHONEST |
| 9 | `test_postgame_ingestion::test_c_the_automatic_scoring_reproduces_the_manual_review` | `not rows` | DISHONEST |
| 10 | `test_postgame_ingestion::test_d_the_qb_room_is_scored_beside_the_individuals` | `not rows` | DISHONEST |
| 11 | `test_postgame_ingestion::test_e_rerunning_on_unchanged_bytes_adds_nothing` | `not rows` | DISHONEST |
| 12 | `test_postgame_ingestion::test_g_provenance_is_preserved_for_every_stored_outcome` | `not provs` | DISHONEST |
| 13 | `test_r7_appearance_frame::test_the_censoring_this_repair_exists_for_is_still_measurable` | panel not PASS | DISHONEST |
| 14 | `test_r8_synthesis::test_k_is_not_estimated_from_the_forecast_season` | frame not PASS — **bare return, not even a print** | DISHONEST, worst of the 19 |
| 15 | `test_research_daily_board::test_d_every_row_carries_its_candidate_and_promoted_stays_false` | no sealed boards | DISHONEST |
| 16 | `test_research_daily_board::test_g_the_comparison_is_same_cutoff_and_actuals_only_when_known` | no sealed boards | DISHONEST |
| 17 | `test_research_daily_board::test_i_it_reads_sealed_artifacts_and_runs_nothing` | `not found` | DISHONEST |
| 18 | `test_slate_runner::test_a_discovery_needs_no_hand_supplied_game_list` | no schedule vintage | DISHONEST |
| 19 | `test_warm_session::test_d_warm_and_cold_produce_identical_football` | `not reseals` | DISHONEST |

**Why 18 of them printing "skipped" does not make them honest.** `run_suite.py`
captures each function's stdout into a buffer and prints it only when a check
fails. A `print('.. skipped')` inside a passing module is written to a buffer
that is then discarded. The line exists, and no runner and no human ever sees
it. Only a counter the runner reads can carry that information out, which is
what `blocked()` is for. Entry 14 does not even print.

Two of the 19 are the ones that matter most on their own terms and both were
named by WS11: **#14** is a leakage guard and **#19** a determinism guard.
Either can delete itself on a data-availability change and leave the suite
green.

### Honest constructions, kept distinct and not to be flattened

| Module::function | Why it is honest |
|---|---|
| `test_volatility::test_B_the_three_valued_answer` | records `blocked(...)`; counted apart, never as a pass |
| `test_volatility::test_F_the_rule_is_load_bearing` | same |
| `test_q9_live_feature_builder::test_04b`, `::test_06` | a `check(...)` is banked before the guard returns |
| `test_q9_prospective_shadow::test_11`, `::test_22` | same |
| 15 functions of the `if not check(...): return` form | the *condition itself* is a check: it records a FAILING check and then returns. `test_product_orchestration` (6 functions), `test_inactives_drill::test_the_drill_runs_end_to_end_on_a_synthetic_root`, `test_inactives_propagation` (2), `test_r7_appearance_frame` (2), `test_r8_synthesis::test_the_reliability_weight_is_estimated_not_chosen` and others. This is the correct pattern and the runner leaves it alone. |

### A correction to WS11 §3 FG-11

WS11's silent-skip table has 24 named functions plus one combined row. Measured
against the AST, that set resolves as **19 genuinely silent + 2 honest
`blocked()` + 3 that bank a check before returning and therefore cannot record
zero**. The three that cannot fire are
`test_postgame_ingestion::test_b_the_receiving_yards_field_maps_to_the_realised_key`,
`test_q7_efficiency_calibration::test_f_the_log_score_is_exact_...` (WS11 noted
this itself) and
`test_qb_pyds_market_eligibility::test_b_the_chain_reaches_ranking_eligible_for_qb_pyds`.
WS11 also missed none in the other direction: no silent function outside its
table was found. The list narrows; it does not grow.

None of these 19 was edited. They are not this workstream's files and the
repair in each is the same one line — replace the bare `return` with a
`blocked()` — which their owners should make.

---

## RECLASSIFICATION TABLE

No test was deleted. Each of the three became two, one of each class, and both
halves say in their own text which class they are.

| Function | Class before | Class after | Executes |
|---|---|---|---|
| `test_q9_prospective_shadow::test_21_the_dry_run_proof_holds` | FALSE_GREEN_RISK (P0) | *split* | — |
| → `::test_21_the_dry_run_proof_holds_when_it_is_run` | — | **EXECUTABLE_BEHAVIORAL_PROOF** | `dryrun.run()` — two full seals, all ten proofs |
| → `::test_21b_the_stored_dry_run_proof_agrees_with_the_run` | — | **ARTIFACT_CONTENT_ASSERTION** | compares the stored proof to the re-run, check by check |
| `test_q9b_model_family::test_i_parity_is_bit_for_bit_and_the_guard_fires` | FALSE_GREEN_RISK (P0) | *split* | — |
| → `::test_i_parity_is_bit_for_bit_when_it_is_run` | — | **EXECUTABLE_BEHAVIORAL_PROOF** | `PAR.run()` at the frozen slice |
| → `::test_i2_the_parity_artifact_agrees_with_the_run` | — | **ARTIFACT_CONTENT_ASSERTION** | record vs re-run |
| `test_q9_live_feature_builder::test_05_the_parity_artifact` | FALSE_GREEN_RISK (P0) | *split* | — |
| → `::test_05_builder_parity_when_the_comparison_is_re_run` | — | **EXECUTABLE_BEHAVIORAL_PROOF** | `LF.parity(2024, 48)` |
| → `::test_05b_the_parity_artifact_agrees_with_the_run` | — | **ARTIFACT_CONTENT_ASSERTION** | record vs re-run, span-dependent counts excluded by name |

### Three artifact assertions that are legitimate and stay

Stated so a later pass does not "repair" them. In each, the claim is about the
record and the record is the thing:

* `test_21b`, `test_i2`, `test_05b` above — they assert that a frozen piece of
  evidence still describes today's behaviour. That is a claim about the record
  *and* about the code, asked in the only way that is honest: by having both
  numbers in hand at once.
* Everything listed in WS11 §4 is untouched.

### The non-vacuity claim, moved out of the producer's mouth

`test_05` previously asserted `wd['containment_check_is_not_vacuous'] is True`
— the producer's own word for it. The re-run version derives it in the
consumer: it counts `LF.SOURCE_FEATURES` from the frozen schema, asserts the
two sets partition `Q9.FEATURE_NAMES` exactly and do not intersect, and only
*then* asks the run whether it agrees. If every feature were called a history
feature the containment would pass on anything, and the consumer can now see
that it was not.

---

## BLAST RADIUS

**Files changed: four, all owned exclusively by this workstream.** No
production module, no `nfl/prospective/q9shadow/**`, no
`nfl/research/q9b/production_parity.py`, no other workstream's test file, no
frozen artifact, no freeze file.

`seal.py`, `live_features.py` and `production_parity.py` are **called** and not
edited. All three producers write their artifacts only in `main()`; the
`run()` / `parity()` entry points this pass calls return a dict and write
nothing. `dryrun.run()` creates `nfl/prospective/q9shadow/dryrun/proof/` and
removes it again (`keep=False`), leaving the tree as it found it. Verified: no
committed artifact's bytes changed.

**Runtime.** Three re-runs were added to the suite, measured unloaded on
2026-09-14:

| Proof | Producer | Configuration | Cost |
|---|---|---|---|
| FG-1 | `dryrun.run()` | 2024, 1 game, 120 draws | ~62 s |
| FG-2 | `PAR.run()` | 2024, 12 games, 200 draws, seed 20260925 | ~39 s |
| FG-3 | `LF.parity()` | 2024, 48 team-games | ~108 s |

About 3.5 minutes added to a full-suite run. Each is memoised per process so
the paired artifact-assertion function reuses the same result rather than
running it twice.

**The FG-3 configuration is declared, and it is not the artifact's.** The
committed artifact was produced at 96 team-games; the test runs 48 — the
smallest span that still covers all 32 week-1 team-games, so the in-window
comparison is the same 482 players, *and* reaches into week 2, so the
out-of-window divergence is measured on something rather than asserted on an
empty set. At 24 team-games the out-of-window set is empty and the containment
check would pass vacuously; that was measured, not assumed. Quantities that
scale with the span — out-of-window counts, the duplicate-exclusion count — are
therefore **not** compared against the artifact, and `test_05b` says so in a
check rather than skipping them quietly.

**Runner semantics.** The per-function rule can turn a module red that was
green, at any point in the tree, whenever one of the 19 fires. That is the
intended effect and it is the reason the list above is exhaustive rather than
illustrative. `test_harness_audit.py` was read and its three seeded styles
still behave correctly under the change: the `vacuous` seed is now caught twice
(VACUOUS module *and* ZERO-CHECK function) and still exits non-zero; the
`exception-only` seed has no tally so the per-function rule does not apply to
it; the clean seed in `test_B` increments `PASSED` and stays green.

## IDENTITY IMPACT

**None.** No engine, allocator, layer, coefficient, seed, stream or artifact
was touched, and nothing this pass changed can alter a draw. `SIM_FORMULA`-
equivalent inputs are untouched; the Q9 freeze
(`Q9_PROSPECTIVE_FREEZE.json`, sha16 `a28e8832430b1420`) and the four hashed
modules it names are unmodified.

The one thing that *did* change is what the suite is willing to call proof, and
that is a change in the measurement system rather than in the model. It is also
the direction that makes execution identity legible: FG-1 now fails precisely
because the execution identity is unstable, which is the defect WS-E is
repairing.

---

## ATTRIBUTION — which hunks in the dirty file are WS-N's

`nfl/tests/test_q9_prospective_shadow.py` was already modified before this pass
began, as part of the 7-file / 1,272-insertion q9shadow diff dated 2026-09-12
recorded in `WAVE0_BASELINE.json` under
`pre_existing_diff_sha256: 9ced29bcb739140da7540095da086e2816a8e13eb2c7e40d4e996f893625ba76`.
**Nothing pre-existing was reverted, stashed, reformatted or cleaned up.**

WS-N's hunks in that file, and no others:

| Hunk | Post-edit lines | What |
|---|---|---|
| `@@ -22 +22,5 @@` | 19–26 | one docstring bullet, extended to say the ten proofs are re-run |
| `@@ -55,0 +60 @@` | 60 | `from nfl.prospective.q9shadow import dryrun as DR` |
| `@@ -605,6 +669,57 @@` … `@@ -630,3 +772,34 @@` | 668–806 | the `# the proof` block: the commentary, `_DRYRUN`/`_dryrun()`, `test_21_the_dry_run_proof_holds_when_it_is_run`, `test_21b_the_stored_dry_run_proof_agrees_with_the_run` |

Every other hunk in that file — the blocks at post-edit lines ~320–465 and
~872–890 — is pre-existing 2026-09-12 work and is **not** WS-N's.

The other three files (`run_suite.py`, `test_q9b_model_family.py`,
`test_q9_live_feature_builder.py`) were clean at HEAD, so their entire diff is
WS-N's.

---

## EVIDENCE CEILING

What this report establishes, and what it does not.

**Established.**
- FG-1's honest test fails, and the failure is a measurement: `dryrun.run()`
  was executed and its DETERMINISTIC check returned FAIL with two differing
  identity blocks.
- The identity-vs-draws split in that failure is measured from the run's own
  output, not inferred.
- The tripwire recogniser matches exactly 50 functions, all named
  `test_zz_every_check_passed`, and no others — run against all 90 modules.
- The 19-function zero-check population is complete over the test tree, by AST
  over the same globs `run_suite.py` uses.

**Not established.**
- **The full suite was not run**, by instruction, because other workstreams are
  editing the tree. The three owned modules were run with `--only`. Baseline
  figures (90 modules / 1,019 functions / 5,850 checks) cannot be compared
  against a post-repair full-suite figure from here; the coordinator's
  integration run is where that happens.
- Consequently, **which of the 19 is firing right now is unknown for 80 of the
  90 modules.** WS11 measured 17 modules and found none live; that is the only
  dynamic evidence in existence and it is 3 weeks of coverage short of the
  tree. The static list says which functions *can* go silent, not which are.
- FG-2 and FG-3 are proved at one configuration each — the frozen slice and 48
  team-games of 2024. A divergence that appears only outside those spans would
  not be caught. That is a narrower claim than "parity holds", and it is the
  claim the tests now make.
- Whether FG-1's failure is a defect in `seal._code_commit()` or in the dry-run
  harness's choice of output location is **not** settled here. The mechanism
  above fits every observation, and it is handed to WS-E as a lead.

---

## HANDOFFS

**To WS-E.** FG-1's honest test is red and will stay red until the sealing
path's execution identity is stable across two runs of identical inputs. The
lead above (`_code_commit()` counting `git status --porcelain` lines that the
run's own outputs move) fits every observation including the run2-ARI ==
run1-BUF coincidence. When it is repaired, `test_21_the_dry_run_proof_holds_
when_it_is_run` and `test_21b_the_stored_dry_run_proof_agrees_with_the_run`
should both go green with no edit to either. If `test_21b` stays red after
`test_21` goes green, the stored proof has drifted for some *other* reason and
that is a separate finding, not a reason to rewrite the artifact.

**To the owners of the 19.** Each repair is one line: replace the bare
`return` with a `blocked(label, why)` against a module-level BLOCKED counter,
exactly as `test_volatility.py:51` does. `run_suite.py` reads `BLOCKED`,
`blocked_count` and `SKIPPED`. Until then, those functions fail the suite when
their fixture is absent, which is the correct answer to "did this measure
anything".

**To the coordinator.** Two P1 false greens in files WS-N owns were **left
alone** rather than folded into this change, to keep the diff attributable:

* **FG-4** `test_q9b_model_family::test_j_the_freeze_records_identity_and_
  consumes_no_future` checks the four `module_source_sha16` values for *length
  16* and never recomputes them. `freeze._module_hash(mod)` is a two-line
  helper in the same package. One-line repair, latent today (all four match).
* **FG-6** `test_q9_live_feature_builder::test_11_the_complete_parity_artifact`
  reads `Q9_COMPLETE_SHADOW_PARITY.json` including its own
  `gate_is_not_vacuous`; `complete.run()` has no call site. Same repair shape
  as FG-3.

Both are in scope for a follow-up in these files and neither was touched here.

---

## A MISROUTED INSTRUCTION, RECORDED RATHER THAN ACTED ON

Mid-task, a coordinator message arrived carrying six raw-retention rules from
WS-L (RL-1 … RL-6): `persisted_content_sha256` verification counts,
`CONSUMED(src) ⊆ reduce_cols(src)`, `dt`-slice persistence,
`reduce_recoverability_assumption`, a per-field retention declaration, and
transformation identity. It addresses "your two-field split" and "your
transformation-identity requirement".

**WS-N has neither.** Those rules land on `nfl/tests/test_persisted_provenance.py`
(WS-K), on `nfl/capture/**` and on `check_retention.py` / `coverage.py` /
`preflight_t90.py` (WS-J) — every one of which is on WS-N's explicit
**MUST NOT touch** list. Acting on it would have meant editing another
workstream's files during a concurrent pass.

It was therefore **not acted on and not silently dropped**. It is recorded here
verbatim in substance so it is not lost, and flagged to the coordinator for
delivery to WS-K/WS-J. Nothing in it was used to alter anything in this report.
---

## APPENDIX — the runner change, in full

Four changes to `nfl/tests/run_suite.py`, all additive:

1. `blocked_tally(mod)` reads a module's `BLOCKED` / `blocked_count` /
   `SKIPPED` counter, guarded with `isinstance(v, int)` because
   `test_volatility.py` defines **both** a counter `BLOCKED` and a function
   `blocked()`.
2. `tally_tripwires(path)` recognises the 50 `test_zz_every_check_passed`
   aggregators structurally, by AST.
3. The main loop reads `tally(mod)` and `blocked_tally(mod)` **around every
   function** instead of once around the module, and attributes the delta.
4. The summary line gains `ZERO-CHECK FUNCTIONS n  BLOCKED FUNCTIONS n`,
   blocked functions are listed under a heading that says they are neither a
   pass nor a failure, and zero-check functions are listed and added to the
   failure total.

Proved against a seeded four-function module (written, run, deleted):

    modules 1  test functions 4  checks 1  FAILING CHECKS 0  RAISED 0
    ZERO-CHECK FUNCTIONS 1  BLOCKED FUNCTIONS 1
    blocked (declared, not a pass, not a failure):
      ...::test_b_says_it_could_not_run
    ZERO-CHECK FUNCTIONS: 1 test function(s) ran and recorded ZERO checks. ...
      ...::test_c_returns_silently
    SUITE FAIL

One function measured and was counted silently; one declared itself blocked and
was named without failing; one returned silently and failed the suite; the
tally tripwire was exempt and invisible. That is the whole contract.
