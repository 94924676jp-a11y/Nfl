# ATL @ GB — unsealed research output

```
FOOTBALL MODEL EXECUTION : COMPLETE
ARTIFACT SEALING         : BLOCKED
REASON                   : STALE team_volume_history
                           newest ordinal 202518, required 202602
OUTPUT CLASS             : UNSEALED_RESEARCH_OUTPUT
```

**This is not a failed engineering run.** The system executed every football
stage and then refused to certify a forecast whose training-history contract
was not current enough under existing governance. The refusal is the control
working.

## Run identity

| | |
|---|---|
| run_id | `2fc4e9599f0889f1` |
| game | `2026_03_ATL_GB` · kickoff `2026-09-25T00:15:00Z` |
| candidate identity | `V1_CANDIDATE_R9_W1P_GSVUCYS` |
| code SHA | `a2605199a8f5677307d3e3cce70e63534c19d187` |
| arm | A · seed 20260908 · PCG64, per-row seed |
| written_at | `2026-09-24T15:30:00Z` |
| elapsed | 471.7 s |

## Stages

```
ok        capture_validation    INPUTS_VALIDATED
ok        identity_resolution   IDENTITY_RESOLVED
DEFERRED  feature_build         STAGE_DECLARED_UNIMPLEMENTED
ok        team_environment      TEAM_ENVIRONMENT_OK
ok        appearance            APPEARANCE_OK
ok        participation         PARTICIPATION_OK
ok        targets_carries       TARGETS_CARRIES_OK
ok        conversion            CONVERSION_OK
ok        td_layer              TD_LAYER_OK
ok        qb_layer              QB_LAYER_OK
ok        joint_reconciliation  JOINT_RECONCILED
ok        player_draws          DRAWS_BUILT
ok        scoring               SCORED
STOP      artifact_sealing      ARTIFACT_SEALING_FAILURE
publication                     NFL1_NOT_AUTHORIZED
```

`feature_build` is declared debt, not a defect: the accepted research baseline
has no production implementation and the stage says so rather than reporting
success.

## Output

`player_draws.npz` — 54 matrices, 10 layers, **8,000 draws per cell**,
3,344,000 draw cells, sha256 `4675cfac…`, content digest `c9283343…`.

Ten highest DK-point means, computed from the draws:

| player | tm | mean | median | sd | p90 | P(>15) |
|---|---|---|---|---|---|---|
| Bijan Robinson | ATL | 21.35 | 20.45 | 10.67 | 35.40 | 0.713 |
| Jordan Love | GB | 15.25 | 14.61 | 8.40 | 26.32 | 0.480 |
| Christian Watson | GB | 13.30 | 11.10 | 10.62 | 28.30 | 0.362 |
| MarShawn Lloyd | GB | 11.73 | 10.40 | 8.79 | 23.90 | 0.315 |
| Drake London | ATL | 11.09 | 9.40 | 8.54 | 22.60 | 0.260 |
| Matthew Golden | GB | 9.48 | 7.70 | 8.56 | 21.20 | 0.212 |
| Cooper Rush | ATL | 9.23 | 8.56 | 8.97 | 21.64 | 0.262 |
| Tucker Kraft | GB | 9.23 | 7.40 | 8.33 | 20.60 | 0.197 |
| Kyle Pitts | ATL | 7.95 | 6.30 | 6.92 | 17.30 | 0.135 |
| Brian Robinson | ATL | 7.15 | 5.40 | 6.77 | 16.30 | 0.120 |

**Probability at a line is exact here** — the share of draws strictly above,
plus half the ties, over all 8,000. Never interpolated from stored quantiles.
That property is why the full draws are kept.

## The one statistic refused rather than captioned

The artifact's manifest states its own draw-index semantics:

```
within_row_across_metrics : SAME_SIMULATED_WORLD
across_rows               : INDEPENDENT_STREAMS_COLUMN_ALIGNED
"Rows are seeded independently, so a CROSS-ROW correlation read off the same
 axis measures the generator's lack of coupling, not a football quantity."
```

So cross-metric dependence within a player is real. **Cross-player correlation
is refused by name and not computed.** Any stack, bring-back or duplication
figure taken off that axis would be reading the seeding. A number that looks
like a correlation gets used as one.

## Truth layer

`157/159` → **`159/159`** display names after correction. Two ATL identities
previously unnamed are resolved: **Colby Sorsdal** (OL) and **Robert
Longerbeam** (DB).

The earlier snapshot is preserved unmodified and the corrected one records why:
names had been drawn from weekly_rosters raw vintage `f7e970be` (weeks 1–2)
while the reduced artifact in use was `0efeaede` (weeks 1–3). Two vintages of
one family in one snapshot — the split-clock defect the run-input contract
exists to stop. Root cause was mine: the raw blob was picked by
`sorted(glob)[0]`, and I had separately concluded from a **truncated directory
listing** that recent captures retain no raw artifact. Capture-prod holds 15.

One unresolved identity remains, unchanged and named rather than counted:
`00-0008818` "Marlon Jones", GB RCB rank 3, on the current depth chart and not
on the week-3 roster.

## Blocker

```
team_volume_history  BLOCKED  newest ordinal 202518, required 202602
```

`nfl/research/inputs/denom_panel.csv.gz` holds 202001–202518 with zero 2026
rows. Of five metrics reading it, **one is genuinely degraded**:
`team_targets`, an EWMA whose most recent observation is 2025 week 18. The
other four are history-only by construction.

Owner ruling 2026-09-24: **do not extend the frozen panel, do not weaken or
scope away the invariant, and do not treat `assert_publishable` completeness
for current-season team volume as authorization to mutate a training panel.**

The scientific question is ticketed for post-game:
`nfl/research/tickets/2026_TEAM_VOLUME_HISTORY_EXTENSION.md`.

## Preserved

`nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1/`

`player_draws.npz` · `player_draws_manifest.json` · `run_status.json` ·
`refusals.jsonl` · `RUN_INPUT_CONTRACT.json` · `FIXTURE_source_hashes.json` ·
`TRUTH_SNAPSHOT_as_run.json` · `RESEARCH_SUMMARY.json`

## Still open

- **Official game-day inactives.** `nfl.com/inactives/` has never returned the
  list in 382 PASS captures; request is in `docs/AGENT_OUTBOX.md`. If a
  content-bearing artifact arrives, the same research pipeline reruns on the
  updated pinned truth state — and the result **remains unsealed** unless the
  training-panel blocker is legitimately resolved.
- **Sportsbook comparison.** No governed board captured. If one arrives,
  exact probability-at-line is computable from these draws for research only.
  Prices stay downstream; they are never predictive inputs.
- **DFS.** Queued. The Fantasy Cruncher-shaped file remains a salary and
  player-universe **candidate**, never first-party DK truth.

