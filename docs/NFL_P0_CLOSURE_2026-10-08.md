# NFL P0 regression closure, 2026-10-08

Owner directive: execute the independent P0 regression closure, plus the Showdown performance-preservation
requirement. This document records evidence. **It does not claim production closure beyond what each row states.**

## Baseline

**Fixture pack.** `NFL_P0_Regression_Fixture_Pack.zip`, sha256 `e1c2e4d2…7309c`. `verify_bundle.py` matches its
inventory: 329 files, none missing, unexpected or changed.

**Environment.**
- Bubblewrap 0.9.0. It was absent from this container and installed from the Ubuntu archive. I checked that it gives
  a read-only root (a write probe was denied) and no network.
- Python 3.12.3 and NumPy 2.5.3, in a dedicated venv. The pack strips `PYTHONPATH`, so NumPy is reached through a
  `.pth` file. The pack itself is unchanged.
- The pack and its outputs live outside `/tmp`, because the sandbox mounts a fresh `/tmp` there.

| Run | Commit | Adapter | Passing | Failing | Unverified | Harness errors |
|---|---|---|---:|---:|---:|---:|
| Supplied audited snapshot | `d0cd2672` | bundled | 24 | 25 | 6 | 0 |
| Supplied current snapshot | `66990085` | bundled | 29 | 20 | 6 | 0 |
| Actual HEAD checkout | `66990085` | legacy | 29 | 20 | 6 | 0 |
| Repair 1 | `69fceb0d` | legacy | 40 | 9 | 6 | 0 |
| Repair 1 | `69fceb0d` | **reviewed** | **43** | **6** | 6 | 0 |
| Guards bypassed (mutant, never pushed) | `f3be2386` | reviewed | 30 | 19 | 6 | 0 |
| Repairs 1 + 2 | `0ea3bc21` | **reviewed** | **45** | **4** | 6 | 0 |

- **Reproduction.** Both supplied baselines reproduce exactly here.
- **Legacy-adapter failures on `69fceb0d`.** Its 3 extra failures are the valid controls (`READY-valid`,
  `QB-valid_backup_package`, `QB-valid_daniels_hypothesis`). The legacy calling convention carries no run context and
  no expectation, and the repaired functions refuse that by design.
- **The reviewed adapter** is `nfl/tests/p0/p0_reviewed_adapter.py`. It supplies the run context from each fixture's
  own facts and maps fixture artifacts to production names, documented field by field.
- **Evidence kept.** Raw results for every row are in `nfl/tests/p0/results/`.

**Showdown incumbent baseline (frozen, never edited).**
- Daniels R5 (`66990085`): upload `bba17b23…`.
- Mayfield R3 (`66990085`): upload `75756698…`.
- The earlier R3 (Daniels) and R2 (Mayfield) legacy-layout runs produced the same uploads.

## Repairs

Classification follows the owner's scheme: 1 validation-only, 2 execution/infrastructure, 3 model-affecting.

### R1: false READY, class 1. Commit `69fceb0d`.

**Code.**
- `showdown_next_slate.final_verify`.
- `showdown_run_guards.write_receipt` and `verify_receipt`.
- `showdown_tonight.run`: the receipt is the build's last act.
- `showdown_next_slate._run_body`: records the run context.

**Fixture verdicts.**

| Fixture | Before (`66990085`) | After (`69fceb0d`, reviewed) | Reason code after |
|---|---|---|---|
| `READY-nonzero_matching_upload` | fail | pass | `REPLAY_EXIT_NONZERO rc=17` |
| `READY-stale_certificate` | fail | pass | `RUN_RECEIPT_COMMIT_MISMATCH` |
| `READY-missing_completion` | fail | pass | `RUN_RECEIPT_ABSENT` |
| `READY-partial_world_bundle` | fail | pass | `ARTIFACT_MISSING football/…WORLDS.npz` and `REPLAY_FOOTBALL_STATE_ABSENT` |
| `READY-matching_upload_different_state` | fail | pass | `REPLAY_FOOTBALL_STATE_DIFFERS` |

**Controls still pass:** `READY-valid` (accepted), `READY-missing_board` and `READY-missing_replay_upload`.

**Bypass.** With the receipt check and replay exit-code check removed, all 5 fixtures fail again (`f3be2386`).

**Actual entrypoint.** Daniels R6 (`69fceb0d`) is a real precompute.
- It wrote `RUN_RECEIPT.json`: terminal COMPLETE, run `run:66f34c10…`, commit `69fceb0d`, 10 artifacts.
- The real `final_verify` consumed it. The receipt, replay, artifact, commit and starter-state checks raised no
  blocker. The one blocker was `STARTERS_NOT_CONFIRMED`, as expected.
- The upload was reproduced (`bba17b23…`).

**Forecast change:** none (see the regression section).

**Rollback:** `git revert 69fceb0d`.

### R2: starter-state integrity, class 1. Commit `69fceb0d`.

**Code.**
- `showdown_run_guards.verify_starter_state`, `expected_state`, `bind_scenario` and `identity_from_depth_chart`.
- `showdown_tonight.run`: the guard runs before `SR.run`, so role state, projection and simulation never start on a
  refusal.
- `showdown_next_slate.scenario_state_matches`: delegates to the guard and refuses when it cannot build an
  expectation.

**Fixture verdicts.** Before is `66990085`; after is `69fceb0d` with the reviewed adapter.

| Fixture | Before | After | Reason code after |
|---|---|---|---|
| `QB-missing_player` | fail | pass | `STARTER_MISSING` |
| `QB-wrong_team` | fail | pass | `TEAM` |
| `QB-false_starter` | fail | pass | `STARTING_FLAG` |
| `QB-wrong_canonical_id` | fail | pass | `IDENTITY` / `STARTER_MISSING` |
| `QB-overridden_out_status` | fail | pass | `OUT_OVERWRITTEN` / `ORDINARY_OUT` |
| `QB-wrong_scenario` | fail | pass | `SCENARIO` |
| `QB-missing_starter_evidence` | fail | pass | `STARTER_EVIDENCE` |
| `QB-designation_mismatch` | pass | pass | `DESIGNATION` |

**Controls still pass:** `QB-valid_backup_package` and `QB-valid_daniels_hypothesis`. There is no one-QB rule; an
active backup with no starting flag is legitimate.

**Bypass.** With the guard removed, all 8 refusal fixtures fail again.

**Actual entrypoint.**
- Probe `PROBE_STARTER_DESIGNATED_OUT` (a real TB@DAL config, Daniels named starter and designated OUT) refused in
  2.6 s with `SCENARIO_STATE_MISMATCH_BEFORE_PROJECTION [STARTER_AVAILABILITY:00-0041251:…]`. The scenario
  directory holds only `STATE.json` and `SCENARIO_GUARD.json`: no role state, projection, draws or worlds.
- On the real TB@DAL states (`nfl/tests/test_showdown_run_guards.py`, 27/27):
  - Valid bound states pass. Daniels `00-0041251`, Mayfield `00-0034855` and Prescott `00-0033077` are identified
    from the captured depth chart.
  - Every tampered variant refuses.
  - The **actual contaminated Daniels R2 state** refuses, even after binding.

**Forecast change:** none. The state gains `scenario_identity` and a starter `evidence` block. These are metadata
that no consumer reads, and the projection rows and draws are byte-identical.

**Rollback:** `git revert 69fceb0d`.

### R3: inherited environment, class 2. Commit `69fceb0d`.

**Code.** `showdown_next_slate.env_for` drops every inherited `SHOWDOWN_*` variable and sets tag, prefix, week, raw
directory and config explicitly.

**Fixture.** `ISO-inherited_environment`: fail → pass. This is the legacy adapter, unchanged.

**Forecast change:** none. The prefix and week are the same values `showdown_slate_env` derived before.

### R4: certificate added-key gap, class 1. Commit `69fceb0d`.

**Code.** `coherence_certificate.verify` now refuses on `added`.

**Fixture.** `PUB-added_array`: fail → pass. All 8 other PUB protections still pass.

**Repository test changed.** `test_coherence_certificate` asserted the opposite rule. It is updated per the
directive, with the reason recorded in the test.

**Classic path is safe.** `run_forecast` adds every layer before `certify` (`run_forecast.py:2400-2878` against
`:3084`) and nothing afterwards.

**Not claimed:** Showdown publication certification. The Showdown entrypoint does not call this certificate.
`LIVE-publication` stays UNVERIFIED.

### R5: cache keys, class 2. Commit `0ea3bc21`.

| Fixture | Before | After | Code |
|---|---|---|---|
| `DATA-kicking_cache` | fail | pass | `kicking.fit`: the key binds the sha256 of every play-by-play file read |
| `DATA-measurement_cache` | fail | pass | `sources.measure`: the key binds file content, not mtime |

**Correction.** Earlier today I allow-listed `SOURCE_MEASUREMENT_CACHE.json` saying "a miss measures the bytes
exactly as a cold run would". That rationale was **wrong** while the key was path, size and mtime, because a stale
hit was possible. It is true now, and the allow-list text is corrected.

### R6: foreign role artifact, class 1. Commit `0ea3bc21`.

**Code.** `showdown_slate_run.run` refuses `SHOWDOWN_RUN_ROLE_STATE_FOREIGN` unless the role state's lineage names
this run's slate state.

**Fixture.** `ISO-foreign_role_artifact` stays UNVERIFIED. The pack's probe reads `proj_v1`'s loader statements
only, and the binding lives one level up. A full-builder injection bridge is owed.

## Not applied: proposals needing the owner (model-affecting or destabilising)

| Item | Finding | Measured effect | Proposal |
|---|---|---|---|
| `FEATURE-chart_rank` | The conditional pass at `proj_v1.py:1328` drops `_chart_rank`, so the DEFECT-TE-ORDER ordering never reaches conditional volume. | Applied in a scratch worktree on Daniels R5's state: `conditional_volume` and `dk_points_if_plays` move (Malik Davis 3.87 → 2.42, Luepke 0.95 → 1.88, Abanikanda 3.05 → 2.09). Unconditional `dk_points`, every draw and the portfolio are unchanged (draws sha `c9445825` in both). | Class 3: `dk_points_if_plays` may feed boards and shadow features. Shadow-evaluate before applying. |
| `FEATURE-active_p_plays` | `p_plays` is emitted by the projection and not consumed by the draws. This is the known SC-APPEAR-1 plumbing defect. | none | Stays research-only per governance. Closing it needs either activation (not authorized) or a declared non-consumption contract. |
| `DATA-duplicate_pbp` | `nfl/research/postgame/` holds five 2026 PBP captures. `kicking.fit`, `gadget_rush` and `rushing_conversion` glob all of them. | 2026 FG attempts counted 619 against 259 distinct, about 6% of the 6,213 total. Classic `run_forecast` only. The Showdown path picks one capture per season (`dst_model._capture` and the others), so **TB@DAL is unaffected**. | Class 3 for the classic path: de-duplicating by `(game_id, play_id)` or selecting one vintage changes an approved fit. |
| `DATA-cohort_cache` | The `player_prior.cohort_estimate` key has no panel identity. | Production loads one panel per process, so no live effect. | The fix re-stamps `player_prior.py`, which would stale the global role artifact's lineage tonight (`test_lineage` 8/8 → 7/8, verified). Deferred to the permanent track. |

## Showdown performance preservation: matched-input regression

**Tool.** `nfl/tools/showdown_regression_compare.py`.

**Controls.**
- R3 vs R4, known identical: all checks identical.
- Daniels vs Mayfield: different.

| Pair | Commits | Result |
|---|---|---|
| Daniels R5 vs R6 | `66990085` → `69fceb0d` | **all 26 checks byte-identical** |
| Daniels R5 vs R7 | `66990085` → `0ea3bc21` | (see the update below) |
| Mayfield R3 vs R4 | `66990085` → `0ea3bc21` | (see the update below) |

**What the 26 checks cover:**
- projection rows, and QB/RB/WR/TE/K/DST points by position;
- every player's draws, world points, club worlds, DST components, interceptions and kickers;
- per-world stat lines;
- player correlations recomputed from the draws, and the correlation board;
- the projections CSV, simulation summary, stack, game-script, CPT and candidate boards;
- final lineups, exposures, CPT exposures and every upload file;
- legality (0 violations) and lineup uniqueness;
- the slate state with the binding metadata removed.

## Remaining unverified obligations

| Obligation | Status | Precise blocker |
|---|---|---|
| `LIVE-before_projection` | Real-entrypoint evidence exists (the probe above). | The pack accepts LIVE closure only through an independently reviewed entrypoint bridge with a trace; none exists. |
| `LIVE-ready_closure` | Real-entrypoint evidence exists (R6). | Same as above. |
| `LIVE-cross_scenario` | Run-level comparison exists: `SCENARIO_COMPARISON_DANIELS_R3_vs_MAYFIELD_R2.json`. | Same, plus the alone / A→B / B→A / concurrent order matrix is not run on full simulations. |
| `LIVE-market_forecast` | `market_firewall_check.py` reports PASS_MARKET_BLIND on Daniels R3, whole forecast, with positive controls. | A reviewed bridge is needed. |
| `LIVE-publication` | Open. | The Showdown entrypoint does not consume the coherence certificate; registered defect R1 (`efficiency_worlds`) breaks QB = receiving yards. |
| `ISO-foreign_role_artifact` | Open at the full builder. | A reviewed bridge must inject a foreign role into a full build. |
