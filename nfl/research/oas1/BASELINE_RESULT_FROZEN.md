# B0–B5 forward-chained result. FROZEN AS OBSERVED.

**Nothing below is reinterpreted to preserve architectural symmetry.** The
pass and rush classes gave different answers and both are recorded as they
came out. No baseline is calibrated, retuned, or deleted after the fact.

Frame: governed 2024+2025+2026 union, 67,277 kept rows. Folds: 2025 weeks 2–18
plus 2026 week 1, 18 scored per class. 2024 is history only. Chain artifact
`OAS1_BASELINE_CHAIN.json`.

## PASS — 18 folds

| Baseline | MAE | RMSE | CRPS | Calib. slope | pred sd | vs B5 |
|---|---|---|---|---|---|---|
| B0 league constant | 1.14962 | 1.57968 | 1.14962 | **None** | 0.00000 | +0.00249 |
| B1 prior-season | 1.14794 | 1.57913 | 1.14794 | 0.7201 | 0.06988 | +0.00081 |
| B2 rolling | 1.14918 | 1.58194 | 1.14918 | 0.4432 | 0.19192 | +0.00205 |
| B3 EWMA | 1.14776 | 1.57802 | 1.14776 | 0.6911 | 0.14531 | +0.00063 |
| **B4 opponent-adjusted** | **1.14569** | 1.57838 | 1.14569 | 0.6606 | 0.13157 | **−0.00144** |
| B5 shrunken (pre-registered) | 1.14714 | 1.57918 | 1.14714 | 0.6151 | 0.10335 | — |

Clustered delta vs B5: B4 **−0.001443**, game CI [−0.002477, −0.000535]
**excludes zero**, team CI [−0.002900, −0.000058] **excludes zero**.

**Strongest observed pass baseline: B4.** It beats B5 under both clusterings.

## RUSH — 18 folds

| Baseline | MAE | RMSE | CRPS | Calib. slope | pred sd | vs B5 |
|---|---|---|---|---|---|---|
| B0 league constant | 0.66158 | 0.98927 | 0.66158 | **None** | 0.00000 | +0.00041 |
| B1 prior-season | 0.66068 | 0.98894 | 0.66068 | 0.6238 | 0.05518 | −0.00049 |
| B2 rolling | 0.66556 | 0.99427 | 0.66556 | 0.2323 | 0.12876 | +0.00439 |
| **B3 EWMA** | **0.66040** | 0.99098 | 0.66040 | 0.4231 | 0.09591 | −0.00077 |
| B4 opponent-adjusted | 0.66187 | 0.98997 | 0.66187 | 0.4577 | 0.09120 | +0.00070 |
| B5 shrunken (pre-registered) | 0.66117 | 0.98961 | 0.66117 | 0.4718 | 0.07910 | — |

Clustered delta vs B5:

| Baseline | game CI | excl. 0 | team CI | excl. 0 |
|---|---|---|---|---|
| B0 | [−0.001159, +0.002039] | no | [−0.002762, +0.003827] | no |
| B1 | [−0.001018, +0.000063] | no | [−0.001431, +0.000463] | no |
| B2 | [+0.002194, +0.006675] | **yes, WORSE** | [+0.001663, +0.007233] | **yes, WORSE** |
| B3 | [−0.001982, +0.000473] | no | [−0.002412, +0.000715] | no |
| B4 | [+0.000077, +0.001345] | **yes, WORSE** | [−0.000152, +0.001610] | no |

**Strongest observed rush baseline: B3. It does NOT significantly beat B5.**
On rush no baseline is significantly better than B5, and two are significantly
worse.

## Two named research results

### `PASS_OPPONENT_ADJUSTMENT_SUPPORTED`

On pass, the opponent-adjusted baseline beats the shrunken one with a
clustered interval excluding zero under both clusterings. Opponent information
earns its place in the pass class on this evidence.

### `RUSH_OPPONENT_ADJUSTMENT_NOT_SUPPORTED_YET`

On rush, B4 is worse than B5 **and worse than the league constant B0**, and
significantly worse than B5 under game clustering. Opponent adjustment as
specified in B4 does not earn its place in the rush class.

**Neither is a permanent architectural law.** `NOT_SUPPORTED_YET` is a
statement about *this specification* on *this frame*, not about opponent
information in rushing. A better rush specification may still prove value, and
would need its own pre-registration. **B4 must not be shipped for rush merely
because pass uses it.**

## `BASELINE_UNDERDISPERSION_OR_COMPRESSION`

Every calibration slope that is defined sits below 1.0 — pass 0.4432 to
0.7201, rush 0.2323 to 0.6238. B0 correctly returns **None** in both classes
rather than a slope fitted to floating-point noise; a constant predictor is
uncalibratable, not badly calibrated.

**The baselines are NOT calibrated in response to this.** The candidate is
evaluated against this same unaltered family, and whether OAS1 improves or
worsens calibration is a question for after the candidate runs.

## Operational scale, which the significance does not convey

| Class | Worst→best MAE spread | Relative |
|---|---|---|
| pass | 0.00393 | **0.34%** |
| rush | 0.00516 | **0.78%** |

Six materially different estimators — a constant, a prior-season prior, a
rolling mean, an EWMA, an opponent adjustment, and a shrunken opponent
adjustment — are separated by under one percent. `STATISTICALLY_DETECTABLE`
and `OPERATIONALLY_MATERIAL` are different claims here and must be reported
separately.

## Strata and diagnostics

Cold-start plays: **0** in both classes — every club appears in the prior
season, so the cold-start stratum is **EMPTY, not passing**, and the
established-history stratum is the whole sample. B1 and B5 fallback counts are
zero. B4 converged 18/18 folds in both classes; zero non-convergence, fallback
never invoked.

Every baseline selected **one** configuration across all 18 folds in both
classes — no configuration churn, which on a flat surface means the tuning
surface is stable rather than that the tuner is learning.

**V2 NOT YET EARNED**
