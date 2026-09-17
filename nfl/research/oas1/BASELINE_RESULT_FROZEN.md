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

## `POST_HOC_STRONGEST_BASELINE` — deltas against the strongest observed baseline

**B5 remains the pre-registered comparator and has not moved.** The tables
below compare every other baseline against the baseline that turned out to
have the lowest MAE. That baseline was identified **by reading these
results**, so every interval here is conditional on that selection and is not
a test of the same kind as the B5 comparison. They are reported because the
effective hurdle a candidate faces is the strongest thing already on the
board, and they are labelled because presenting a post-hoc comparator as a
pre-registered one is exactly how a bar moves quietly.

Clustered bootstrap, R = 2,000; 272 game clusters, 32 team clusters.
**Positive delta = worse than the strongest baseline.**

### PASS — against **B4**, the strongest observed pass baseline

| Baseline | delta | game CI95 | excl. 0 | team CI95 | excl. 0 |
|---|---|---|---|---|---|
| B0 | +0.003931 | [+0.001455, +0.006385] | yes | [-0.001652, +0.011186] | no |
| B1 | +0.002250 | [+0.000779, +0.003812] | yes | [-0.000511, +0.005458] | no |
| B2 | +0.003492 | [+0.000739, +0.006243] | yes | [+0.000109, +0.007107] | yes |
| B3 | +0.002072 | [+0.000612, +0.003511] | yes | [+0.000180, +0.004069] | yes |
| B5 | +0.001443 | [+0.000535, +0.002477] | yes | [+0.000058, +0.002900] | yes |

Every baseline is worse than B4 under game clustering. Under team clustering
B0 and B1 are not separated from it. Against B5 — the comparison that was
pre-registered — B4 wins under both clusterings.

### RUSH — against **B3**, the strongest observed rush baseline

| Baseline | delta | game CI95 | excl. 0 | team CI95 | excl. 0 |
|---|---|---|---|---|---|
| B0 | +0.001182 | [-0.000641, +0.003081] | no | [-0.001827, +0.004511] | no |
| B1 | +0.000279 | [-0.001112, +0.001659] | no | [-0.001316, +0.001986] | no |
| B2 | +0.005163 | [+0.003787, +0.006643] | yes | [+0.003597, +0.006829] | yes |
| B4 | +0.001473 | [+0.000557, +0.002413] | yes | [+0.000202, +0.002760] | yes |
| B5 | +0.000774 | [-0.000473, +0.001982] | no | [-0.000715, +0.002412] | no |

**The rush result does not become a win by changing the comparator.** B3 has
the lowest rush MAE, but it does not separate from B0, B1 or B5 under either
clustering. The only two baselines it beats are B2 and **B4, the opponent
adjustment** — the same finding as before, read from the other side: on rush
the opponent-adjusted baseline is significantly worse than the EWMA under both
clusterings, and the EWMA is not distinguishable from a league constant.

### What the strongest-baseline hurdle now is

| Class | Pre-registered hurdle | Strongest observed | Candidate must clear |
|---|---|---|---|
| pass | B5 (MAE 1.14714) | B4 (MAE 1.14569) | **both** — and both were pre-registered, `PROMOTION_CRITERION` clause (b) already named B4 |
| rush | B5 (MAE 0.66117) | B3 (MAE 0.66040) | **B5 only.** The B3 comparison is reported and labelled post-hoc; it is not a promotion condition |

On pass the post-hoc comparator and the pre-registered one coincide, so nothing
was added to the bar. On rush they differ, and the pre-registered hurdle is the
one that governs.

### Practical effect, stated separately from significance

| Class | Strongest vs pre-registered B5 | Relative | Label |
|---|---|---|---|
| pass | B4 − B5 = **−0.001443** MAE | 0.13% of B5 MAE | `STATISTICALLY_DETECTABLE`; **not** asserted `OPERATIONALLY_MATERIAL` |
| rush | B3 − B5 = **−0.000774** MAE | 0.12% of B5 MAE | neither — the interval includes zero under both clusterings |

The full worst-to-best spread is 0.34% (pass) and 0.78% (rush). An interval
excluding zero inside a band that narrow can accompany a change no downstream
consumer would notice. `BASELINE_UNDERDISPERSION_OR_COMPRESSION` is unchanged
and no baseline has been calibrated in response to any of this.

`COLD_START_VALIDATION = NOT_EVALUATED`. The cold-start stratum is **empty in
both classes** (0 plays) because every club appears in the prior season. An
empty stratum is not a passing stratum and must not be reported as one.

Chain artifact re-run in full, both classes, 18 folds each:
`OAS1_BASELINE_CHAIN.json`, 274,160 bytes, sha256
`2703f2d91e569ccbfdaa83479b5bf7b7c0e7b1020091513f321a30a0921dbb5e`,
`candidate_fitted: false`.

**V2 NOT YET EARNED**
