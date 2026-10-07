# NFL suite remediation backlog (certified run 20261007T083657Z-18364)

Machine-readable version: `nfl/tests/REMEDIATION_BACKLOG.json` (one row per module, with the failing
checks, root cause, evidence, whether it can be fixed locally, the fix applied and what is left).

## What was measured

- Population: the 67 modules with defects in the certified run at a77fa3e4. That is 58 FAIL modules
  plus 9 modules whose functions raised while the module tally read OK. The certificate also listed 4
  OWN_PROCESS modules as failing. Each of those reported 0 failing checks, and
  `certify_suite.failing_modules()` already excludes them (certify_suite.py:143-150).
- Each module was run alone with `python3.12 nfl/tests/run_suite.py --modules <stem> --watch <the 10
  mutated paths>`. The tracked outputs were restored to HEAD bytes between modules, so no module was
  judged on another module's leftovers.
- Before pass: HEAD d3634c1f. After pass: HEAD 16fd3ae6 at the start, 5ba94c83 by the end. Other agents
  committed five times in between. None of their commits touched a file this work changed. They did,
  however, add a fifth 2026 play-by-play vintage, new vintage blobs, a populated (ignored) `nfl_vintage/raw`,
  and rebuilt derived caches. Any before/after change not listed under "Fixes applied" comes from those
  commits, not from this work.

## Counts per class

| Class | Meaning | Modules | Failing before (this tree) | Failing after |
|---|---|---|---|---|
| a | Genuine defect: model, code, test-contract drift, or a ratchet that rose | 37 | 37 | 34 |
| b | Missing external data | 9 | 9 | 8 |
| c | Deployment / governance state | 10 | 10 | 10 |
| d | Generated file / environment | 11 | 8 | 4 |
| **Total** | | **67** | **64** | **56** |

Three modules already passed in this tree before any change: test_own9_write_guard (it failed only
because the certification worktree's path did not name the NFL root), and test_rc1_receiving and
test_td2_recoverability (fixed upstream in fba8cddb).

Of the 8 modules that went from failing to passing, **6 are due to this work**: test_gate_ids,
test_ownership_audit, test_non_evidentiary_refusal, test_guard_census_is_not_stale, test_agent_state and
test_system_state. **2 are due to other agents**: test_vintage_selector passed once `nfl_vintage/raw` was
populated, and test_lineage passed once the derived caches were rebuilt.

Two modules got worse. Neither was caused by this work; both are environment changes made by others:

- test_showdown_family went from 1 failing check to 10 failing and 11 raised. A new pbp_2026 vintage
  (0a81c60b) was picked up as the seal's depth vintage, with an mtime-based retrieved_at later than the
  seal's written_at. This is the same root cause as the one remaining defect.
- test_r5_active_pool gained one failing check. Its expectation assumed the raw store is absent.

## Fixes applied (all local, none changes a production output)

1. **Ownership disposition.** In `nfl/production/ownership_audit.py`, the new postgame script
   `nfl/postgame/showdown_atl_no_coherence.py` had one application-candidate hit with no read disposition.
   The hit is `wp`, which there means world points: each club's final score in every simulated world.
   I read the site and recorded it as HOMONYM_NOT_APPLICATION, the same pattern as the existing
   `football_points.py` `wp` entry. The audit now returns BLOCKED[OWNERSHIP_AUDIT_NO_APPLICATIONS], which
   is what the tests require.
   - Fixes test_gate_ids, test_ownership_audit and test_non_evidentiary_refusal.
   - The UNVALIDATED_CONTROL_DID_NOT_TRIP detector (ownership_audit OWNERSHIP_AUDIT_NO_APPLICATIONS) now
     trips.
2. **Generated files, each rebuilt with the repo's own generator.**
   - `nfl/DISCOVERY.json` (`nfl/tools/discovery.py --write`).
   - `nfl/research/v4/p7/P7_DECLARED_READS.json` (`nfl/production/pipeline.py --write-read-inventory`).
   - `nfl/research/audit/GUARD_REACHABILITY.json` (`nfl/tools/guard_reachability.py --json`).
   - `SYSTEM_STATE.json` and `CURRENT_STATE.md` (`nfl/tools/system_state.py --write`).
   - `nfl/AGENT_STATE.json` and `nfl/HANDOFF.md` (`nfl/tools/agent_state.py --write`).
3. **Stopped tests writing tracked files (test-side only).** Each of these tests now writes to a
   temporary directory instead of the tracked path. Each module has the same check count and result as
   before, and the watch reports zero changes.
   - `test_contest_ownership`: `CO.MANIFEST`.
   - `test_q9_prospective_shadow`: `SEAL.DRYRUN_SEAL_LEDGER`. Every suite run used to append its seals
     to the tracked dry-run ledger.
   - `test_readiness` and `test_lineage`: `readiness.OUT`.
   - `test_role_depth_adversarial`: `SSS.OUT`. **This one was an order dependence.** The test overwrote
     the committed PIT@CLE `SHOWDOWN_TONIGHT_STATE.json` with an altered ATL@NO fixture. That produced
     exactly the certified test_showdown_family result (11 failing, 12 raised; reproduced). With the
     redirect, the pair run gives 1 failing check, which is the genuine one.

Not done, by rule:
- No ratchet or baseline was lowered.
- No test was deleted, skipped or weakened.
- No protected file, workflow or production model code was edited.
- No data was fabricated or rehydrated.

## Generated files that cannot stay green, and newly exposed failures

- **test_agent_state "names the current HEAD".** This check cannot pass on a committed tree, because a
  file cannot contain the hash of the commit that contains it. It passes in the working tree now and
  will fail after the next commit.
  - PROPOSAL for the owner (the test was not edited): accept HEAD or HEAD~1 when HEAD changes only
    generated files.
  - SYSTEM_STATE has the same property.
- **test_uncalled_governance_guards** now fails "the old one still has no caller". The regenerated
  census shows `assert_no_inactive_survived` has 5 test callers, so its reachability is NO_PROD_CALLER.
  The check passed only because it read the stale census, so it was a false green. The census must not
  be reverted to keep it green. Remedy: assert "no production caller".
- **test_p7_dag** still has 2 failing checks, but a different pair. The committed inventory used to
  record PASS while the live audit fails. It now records FAIL honestly, and the remaining defect is the
  five undeclared reads.

## What remains, by class, with remedy and owner

### (a) genuine defects (34 failing)

- **Q9 freeze broken.** `layers.py` has hashed differently from the freeze (481f005f, 8e586509) since
  45f0ff4c on 2026-09-16. Affects test_c1_denominator, test_governance_transport, p6 FG8 and
  test_q9_live_feature_builder's candidate drift. Owner decision: re-freeze or revert. Reverting
  changes production, so it was not done here.
- **DET_BUF non-board draw directories.** Two directories in live/ hold player_draws.npz but no
  board.json (committed in 1ad9d57e, after the corpus fences froze at 112 runs). Affects
  test_conservation, test_draw_coherence, test_p8_tails_and_counts, test_publication_semantics,
  test_sealed_corpus_census and test_stat_contract. Remedy: decide whether they are boards; move them
  or unify `live_draw_files()` with `discover_all()`.
- **Model and engine defects.**
  - test_detbuf_conservation: passing TD differs from receiving TD in about 24% of draws.
  - test_product_orchestration: shared_pass halts (23 completions against 21 completable attempts) and
    feature_build is unimplemented.
  - test_full_slate_rehearsal: every game refuses.
  - test_sc2_interception_reservation: known open.
  - test_fullslate_adjudication: correlation literals at `dependence.py:307-308`.
- **Ratchets that rose.**
  - test_completeness_ratchet: FIXTURE_PINNED 24→37 (13 single-game postgame and market scripts from
    2026-10-04..06); untested refusal codes 511→741; orphaned guard modules 19→20
    (`projection_source.py`).
  - test_discovery_boundary: 42→45 (`readiness.py:202` mtime, `run_archive.py:251,304` iterdir).
  - Remedy: route through the declared contract or move the scripts to research/. The baselines were
    not raised.
- **Capture-surface verifier defects.** The fixes are small but release-gated: any edit to nfl/capture
  needs a new approved capture release.
  - `live_game_evidence.verify_on_disk` rejects 3,055 rows whose `sha256_is_of` is "uncompressed_bytes",
    although the bytes verify (test_live_capture_den_kc).
  - `coverage.py` hashes decompressed bytes against a digest of the served .gz file, which produces 4
    false PERSISTED_CONTENT_SHA256_MISMATCH (test_capture_obligations).
  - The registry lacks pbp, dk_entries and dk_salaries_early (test_p7_data_plane).
- **Undeclared reads** (test_p7_dag): `usage_vintage.py:107`, `early_only.py:92`, `emit_package.py:78`,
  `manifest_store.py:124,177`.
- **Tests lagging a deliberate contract change.** The owner or test owner should reconcile; the tests
  were not edited here.
  - REQUIRED_SOURCE_NOT_DECLARED fixtures: test_qb2_production, test_v1_draw_artifact.
  - Status refusal now falls back instead of being fatal: test_r5_active_pool, test_qb_eligibility_den_kc.
    These are two of the owner's recorded rules in conflict.
  - test_nonqb_r3: rushing_conversion is now IMPLEMENTED.
  - test_v1_rushing_a1: the committed pbp corpus is now a declared source.
  - test_inactives_drill: the parser was re-segmented in 86f426db.
  - test_draw_coherence check 820: a string match broken by formatting. PROPOSAL: an AST check.
- **Selection and clock defects.**
  - test_kicker_resolution: NYJ kicker eligibility is pooled across vintages, not selected at the cut.
  - test_gadget_rush: the test's roster class is taken first-by-hash, not from the engine's capture.
  - test_showdown_family: the seal enumerates every capture on disk and uses mtime as an evidence clock.
  - test_qb_room_composition: showdown_live seals lack the room membership source.
  - test_rushing_survivorship: the audit artifact is stale (22,821 vs 21,895).
  - test_determinism_proof: `commit_claim.py:157` runs `git status --porcelain` outside nfl/identity.
- **test_p6_false_greens:** 18 deliberate reproductions. Each is repaired by the owner of the module it
  names.
- **New production finding, not fixed.** `nfl/production/kicking.py:108` globs `pbp_20*.csv.gz` without
  de-duplicating. The overlapping 2026 vintages mean `kicking.fit(202602)` reads 7,573 rows for 2,756
  unique 2026 week-1 plays (now five vintages), and the per-club TD tallies are counted again for each
  duplicate. The same overlap inflates test_stat_contract (223,910 plays vs the frozen 211,755).

### (b) missing external data (8 failing)

- **`nfl/vintage/weekly_rosters.197453cb51cb7383.raw.csv.gz`** (capture 20260922T124141Z; only
  .reduced exists). Affects test_audit_migration, test_availability_semantics, test_canonical_state,
  test_dossier_migration, and 2 raises in test_gate_migration.
- **Raw captures under `nfl_vintage/raw/`.**
  - weekly_rosters bdab6ecee12d44a4 and cef497eaeddef07b, needed by test_eligibility_gate. All 9
    UNVALIDATED_CONTROL_NOT_EXECUTED detectors are this module's controls.
  - The 9 recovered_from paths in test_persisted_provenance (depth_charts 76d7bcb3, a14e8dfe, db0a0945;
    weekly_rosters 3b0d5d40, 5ec59c52, cef497ea, fb79560b).
  - CSV payloads for test_volatility.
  - bdab6ecee12d44a4 *is* byte-recoverable from the durable `.raw.csv.gz` (sha256 verified). It was not
    materialised, because one check asserts that the ephemeral store retained it.
- **nflverse `play_by_play_2020..2025.csv.gz`** in `nfl/research/track1/raw/` (test_q7_panel_nondegeneracy).
- Owner: the networked agent (capture-prod raw store / nflverse).

### (c) deployment / governance (10 failing)

- **Capture release not approved.** The surface is 2a59c19e; the approved release CAPREL-361a020a is
  8094370a (test_capture_deployment_integrity, test_capture_prod_deployment). Owner approves a new
  release.
- **Protected `gate.py`.**
  - PLAYER_REVIEW_NO_DOSSIERS proposal pending (test_gate_migration).
  - OPPORTUNITY_CONSERVATION_* codes are not declared in ADVERTISED/OBSERVED_INTEGRITY
    (test_integrity_producers).
- **Workflows.**
  - nfl-t90.yml is the week-4 schedule (test_t90_workflow, test_preflight).
  - The G0A frozen identity conflicts with the weekly roll (test_non_g0a_isolation).
  - Unpinned checkouts, edits stranded off main, and nfl-capture-liveness.yml absent from main
    (test_scheduled_workflow_pinning).
  - Owner deploys or rules; workflows were not touched here.
- **D20 record counts are stale against new captures** (test_inactives_substance, 382 vs 374). The D20
  owner re-adjudicates.
- **test_sunday_run.** The product is NOT_PRODUCTION_READY, so the delivered-run checks cannot pass.

### (d) generated / environment (4 failing)

- **test_execution_lineage, test_recheck_methods_name_their_tree.** origin/capture-prod is not fetched,
  and origin/main is stale. The networked agent runs `git fetch origin '+refs/heads/*:refs/remotes/origin/*'`.
  The same fetch is the root cause of the 4 zero-check functions in test_capture_surface_is_executable.
  Their `not_executed()` is not counted as BLOCKED by run_suite; a proposal to fix that is recorded in
  the JSON.
- **test_football_only_arm.** `nfl/derived/SHOWDOWN_TONIGHT_ROLE_STATE.json` (gitignored) is absent and
  no generator is named for it.
- **test_discovery.** Still fails two checks:
  - GAP-DEPTH-CHART-PIT is not queued in WORK_QUEUE.md. That is an owner decision.
  - The "injuries" detector check depends on the wall clock.
- test_inactives_propagation's zero-check function is the missing raw roster store (b), with a silent
  "skipped" return.

## The tracked files the suite mutates, and who writes them

| Path | Writer (test → code) | Status |
|---|---|---|
| nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json | test_contest_ownership → contest_ownership.status() | fixed (redirect) |
| nfl/prospective/q9shadow/Q9_SHADOW_DRYRUN_SEAL_LEDGER.jsonl | test_q9_prospective_shadow → seal.seal_season(dry_run=True) | fixed (redirect) |
| nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json | test_role_depth_adversarial → showdown_slate_state.build() | fixed (redirect); caused the test_showdown_family order dependence |
| nfl/production/READINESS.json | test_readiness, test_lineage, test_sunday_run → readiness.build() | partly fixed (first two redirected); test_sunday_run proposal only |
| nfl/production/SUNDAY_RUN_REPORT.json | test_sunday_run → sunday.run() | proposal: run_archive needs an injectable output map |
| nfl/dfs/salaries/DK_WEEK3_PROJECTION_SOURCE_LEDGER.json | test_fc_firewall_and_projection_source → projection_source.run() (hard-coded path, timestamped) | proposal: needs an OUT constant in the tool first |
| nfl/dfs/salaries/DK_WEEK3_PLACEHOLDER_PORTFOLIO_AUDIT.json | same module → portfolio_audit.run() (PA.OUT) | proposal: test-side redirect; changes only in suite order |
| nfl/dfs/salaries/SLATE_STATUS_BOARD.json/.md | test_slate_to_portfolio → slate_to_portfolio | proposal: redirect OUT_BOARD/OUT_MD/OUT_CSV together |
| nfl/research/v2/r5/active_board_pointer.json | test_quality_gates → board_pointer swap/begin_candidate/_write_pointer | proposal: redirect STATE_DIR+POINTER to a seeded temp copy |
| nfl/tests/_suite_progress.jsonl (not in the certificate list) | run_suite.py itself, every non-certified run | proposal: gitignore it or default it outside the tree |
