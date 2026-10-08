# Showdown release policy: modified Option B (owner ruling 2026-10-08)

**The ruling.** Basic QB substitution is separated from advanced QB-conditioned forecasting.
- The absent QB-conditioned environment model is a **disclosed limitation**, not a blocker of a verified substitution.
- Every other gate stays mandatory.
- Simulation accounting is reported, and stays FAIL until corrected and verified.
- A run that passes every mandatory gate while limitations remain is **PROVISIONAL**, never READY or certified.

**Code:**
- `showdown_run_guards.release_classification` (pure function; tests `nfl/tests/test_release_classification.py`, 30/30);
- `showdown_next_slate.final_verify`.

## The statuses

| Status | PASS when | Source |
|---|---|---|
| `PLAYER_SUBSTITUTION_VALID` | the starter-state guard ran on the built state and found no mismatch (identity, team, starting flag, starter evidence, OUT not overwritten, designations) | `scenario_state_matches` → `showdown_run_guards.verify_starter_state`. UNVERIFIED, and blocking, if it did not run |
| `DATA_AND_AVAILABILITY_VALID` | starters confirmed with a source; inactives officially verified; inputs unchanged during the run; not a rehearsal | `verify_football_inputs`, freeze hashes |
| `LINEUP_ELIGIBILITY_VALID` | verifier violations 0; no unclassified or blocked players; final board present; the upload reproduced byte for byte | the final board; the replay |
| `SIMULATION_ACCOUNTING_VALID` | zero violations of the ordinary-event laws on the **published** worlds | `world_accounting_check` → `WORLD_ACCOUNTING_<scenario>.json`. UNVERIFIED if it cannot be measured; never PASS by default |
| `QB_CONDITIONED_FORECAST_VALIDATED` | `NOT_REQUIRED` when every starter's club environment is predominantly his; otherwise `NOT_VALIDATED` (no validated model exists) | `football_model_status` |
| `DFS_DECISION_READINESS` | READY / PROVISIONAL / NOT_READY, below | `release_classification` |

| Decision | Meaning |
|---|---|
| **READY** (certified) | every mandatory gate passed **and** accounting PASS **and** no unmodelled QB change. No slate meets this today, because accounting fails everywhere |
| **PROVISIONAL** | every mandatory gate passed; known limitations disclosed in `RELEASE_STATUS_<scenario>.json`. **Not a certified forecast** |
| **NOT_READY** | a mandatory gate failed; the upload must not be used |

**Exit codes:** 0 READY, 5 PROVISIONAL, 4 NOT_READY, 3 refused before the build.

## Non-waivable gates, identified before the change, all still mandatory

`RUN_CONTEXT_ABSENT`, `INPUTS_CHANGED_DURING_RUN`, `UPLOAD_NOT_REPRODUCED`, `REPLAY_EXIT_NONZERO`, every receipt check,
`CODE_NOT_COMMITTED`, `SCENARIO_STATE_MISMATCH`, `VERIFIER_VIOLATIONS`, `UNCLASSIFIED_PLAYERS`, `BLOCKED_PLAYERS`,
`FINAL_BOARD_ABSENT`, `REHEARSAL_NOT_LIVE`, `STARTERS_NOT_CONFIRMED`, `INACTIVES_NOT_OFFICIALLY_VERIFIED`,
`PROP_SEAL_FAILED`, `FINAL_VERIFY_AFTER_KICKOFF`.

Two cases still block:
- **`FOOTBALL_MODEL_UNDETERMINED`:** the QB-environment check could not run, so the substitution's context is unknown.
- **An unchecked substitution.**

Each is tested in `test_mandatory_gates_not_waived`.

**What changed.** Only `FOOTBALL_MODEL_INCOMPLETE_QB_ENVIRONMENT` moved from blocker to disclosed limitation.

**The prelock board** used to say `READY` on its own input checks. It now says `PRELOCK_CHECKS_PASS` and points to
the release status. It never certified a release.

## Evidence that only classification changed

- **Independent P0 pack at `de70faff`:** every one of the 55 fixtures classifies exactly as at `7390def0`: 45
  protections, 4 deliberately unapplied defects, 6 unverified.
- **On the way, the pack found two defects of mine, both fixed:**
  - the release-status writer assumed an in-repo scenario;
  - the extracted kicking fit could not see the point-in-time module (the identity in live mode) since `e1e6d755`.
- **TB@DAL R9 (`eafc5b01`) vs R10 (new code):** see `REGRESSION_DANIELS_R9_vs_R10_RELEASE_POLICY.json` and §4 below.

## 4. R9 vs R10

- **Matched regression:** 26/26 identical (`REGRESSION_DANIELS_R9_vs_R10_RELEASE_POLICY.json`).
- **Byte level** (`RELEASE_POLICY_BYTE_IDENTITY_R9_vs_R10.json`): 20 of 37 scenario files are byte-identical. These
  include the four upload CSVs, `PROJ.json`, `WORLDS.npz`, the final lineups, exposures, candidates, correlations and
  the captain board.
- **The other 17 differ only in run-identity metadata.** That is the scenario name and paths, timestamps, run id,
  commit, freeze seal and scenario identity, plus the state hash those stamps feed. `DRAWS.json` differs only at
  `/state_sha256`; every draw is identical.
- **The one intended content change** is the prelock board's `RELEASE_DECISION` pointer.
- **R10's release status:**
  - `PLAYER_SUBSTITUTION_VALID` PASS;
  - `DATA_AND_AVAILABILITY_VALID` FAIL (`STARTERS_NOT_CONFIRMED`; a precompute);
  - `LINEUP_ELIGIBILITY_VALID` PASS;
  - `SIMULATION_ACCOUNTING_VALID` FAIL;
  - `QB_CONDITIONED_FORECAST_VALIDATED` NOT_VALIDATED;
  - **`DFS_DECISION_READINESS` NOT_READY** on the single mandatory blocker `STARTERS_NOT_CONFIRMED`.
- **Unrelated, found here, not changed:** the TB@DAL prelock board markdown header reads "ATL @ NO Showdown".
