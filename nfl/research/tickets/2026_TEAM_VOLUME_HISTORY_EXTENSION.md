# 2026_TEAM_VOLUME_HISTORY_EXTENSION

**Opened** 2026-09-24 · **Status** OPEN, POST-GAME · **Owner decision required**
**Do not solve tonight.** Owner ruling 2026-09-24, Option 1.

## What forced this open

Run `2fc4e9599f0889f1` (`2026_03_ATL_GB`, `V1_CANDIDATE_R9_W1P_GSVUCYS`, code
`a2605199`) executed **every football stage** and then failed artifact sealing:

```
current_season_input_freshness: BLOCKED
  denom_panel          PASS     CURRENT_SEASON_SOURCE_VERIFIED_THIS_RUN
  panel_p3             PASS     CURRENT_SEASON_INPUT_FRESH
  team_volume_history  BLOCKED  newest ordinal 202518, required 202602
```

`nfl/research/inputs/denom_panel.csv.gz` holds 202001–202518 and **zero 2026
rows**. `denom_panel` passes only because a passing
`current_season_team_volume.assert_publishable` supersedes its DECLARED block.
`team_volume_history` is not declared-blocked, so no verification applies to
it: it is a plain ordinal check against a genuinely stale training panel.

## What was explicitly NOT done, and why

The obvious move — append 2026 weeks 1–2 to the panel — is forbidden by the
registry's own words:

> "It is NOT repaired by refreshing the panel, because the 2026 source's
> vintage, completeness, coverage, field definitions and identity behaviour
> are not established. A partially complete denominator produces confidently
> wrong SHARES rather than a nameable refusal."

`assert_publishable` establishing completeness for current-season TEAM VOLUME
(32 clubs present in every week, `complete=True`) is **not** authorization to
mutate a frozen TRAINING panel. Those are different artifacts answering
different questions, and the owner ruled explicitly that the first does not
license the second.

## What the block actually costs, measured not guessed

The registry's own audit of which estimators consume recency:

| metric | estimator | dependence | state |
|---|---|---|---|
| `team_off_snaps` | league_mean | history only | unaffected |
| `team_dropbacks_part` | coach_prior | history only | unaffected |
| `team_carries` | coach_prior | history only | unaffected |
| `team_rz_carries` | coach_prior | history only | unaffected |
| **`team_targets`** | **EWMA** | **RECENCY** | **STALE** |

**One metric of five is genuinely degraded.** `team_targets` is an EWMA whose
most recent observation is 2025 week 18. The other four are history-only by
construction and a new season does not make them stale.

## What must be determined BEFORE any panel mutation

1. **Source vintage** — which artifact, which retrieval clock, which hash.
2. **Field definitions** — do the 2026 columns mean what the 2020–2025 columns
   mean? A renamed or re-derived field is a different estimand wearing the
   same header.
3. **Completeness** — per week, per club, with the refusal condition stated in
   advance rather than discovered.
4. **Identity behaviour** — how 2026 ids join to the historical spine, and
   what happens to a player who appears in one and not the other.
5. **Comparability with historical seasons** — whether 2026 rows are
   distributionally admissible alongside 2020–2025 or constitute a regime
   change the estimators were not fitted across.
6. **Whether `team_targets` can be updated consistently** — it is the only
   recency-sensitive consumer, so it is the whole question. If its EWMA cannot
   be extended coherently, extending the panel buys nothing and risks the
   other four.
7. **Whether a new candidate identity is required** — precedent says yes:
   `V1_CANDIDATE_R9_W1P` exists as a separate identity purely because an
   approximated numerator is a different estimand. A panel with 2026 rows is
   at least that different.
8. **Backtest impact** — every historical result computed against the current
   panel, recomputed.
9. **Calibration impact** — whether interval coverage and calibration slope
   move, and by how much.
10. **Whether extending the panel changes the estimand.** If it does, this is
    not a refresh; it is a new model, and it takes a new name.

## Preserved evidence

`nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1/` — full run artifacts,
54 draw matrices, 8,000 draws per cell, the pinned evidence contract, the
fixture hashes, the truth snapshot as run, the sealing refusal, and
`RESEARCH_SUMMARY.json`.

## The correct reading of that run

This is **not a failed engineering run**. The system executed the football and
then refused to certify a forecast whose training-history contract was not
current enough under existing governance. That refusal is the control working.

