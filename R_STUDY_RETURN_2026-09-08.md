# R STUDY RETURN

## Canonical state

| | |
|---|---|
| Start HEAD | `11ea949` |
| Pre-registration commit | **`322b567`** — canonical before any comparative R result was computed |
| Result commit | this commit |
| Final HEAD | see below |

## Baseline identity

| | |
|---|---|
| Artifact | `nfl/research/p4c/p4c_results.json` at `targets/<season>/scores/C/crps` |
| SHA256 | `5d8d34c22c01…` (read through Rule 006, never transcribed) |
| Exact reproduction | **PASS** — `|diff| 0.00e+00` in all four seasons, tolerance 0.0 |

## Estimand

**R definition**, taken from Stage 4 unchanged:
`R* = W*/P*` where `W* = target_share × appeared`, `P* = pass_snaps /
team_dropbacks`, and `R* = 0` where `P* = 0`.

**Verified identical to Stage 4, not merely similar.** Recomputed in float64 and
compared row-by-row against Stage 4's own `Rstar`: **max difference 0.000e+00**.
The 6e-08 seen on first comparison was exactly Stage 4's own float32 cast of
`Wstar`, and nothing else.

**P definition**: pass-snap participation — the share of team dropbacks on which
the player was on the field.

**Known limitation, unweakened**: P is an **upper bound** on route participation,
because a player on the field for a dropback may block. It is **not routes run**.
Nothing here concludes anything about the value of true route information, and
the magnitude of the gap remains unknown.

## Data

**Evaluation seasons** 2022–2025, reported separately, strict walk-forward.

| quantity | value |
|---|---|
| WR/TE/RB player-games in panel | 47,215 |
| appeared | 34,204 |
| `P* > 0` → R defined | 33,907 |
| appeared but `P* = 0` (structural, excluded) | 251 |
| `P*` missing | 70 |
| eligible for evaluation (≥1 prior game) | 22,327 across the four seasons |

**Position counts** (eligible): WR 10,059 · TE 6,147 · RB 6,121.

**R\* distribution**: mean 0.1823, sd 0.1717, range [0, 1.577]; quantiles
1/5/25/50/75/95/99 = 0 / 0 / 0.048 / 0.167 / 0.265 / 0.447 / 0.784.

**Zero/N-A treatment**: 8,170 rows are a **real zero rate** — the player was on
the field for dropbacks and drew no target — and are kept. A non-appearance is
**never** scored as rate zero; it is excluded, and the count is above.
`P* < 0.02` on 0.265% of rows, `< 0.05` on 6.4%, `< 0.10` on 14.3%. The
pre-declared 0.02 feature floor was therefore rarely load-bearing.

**Chronology audit**: masking at four ordinals, 14,455 / 20,090 / 13,510 /
15,260 feature values compared, **CLEAN at every one**.

## Simple baselines (Block 0)

Pooled MAE, all four seasons, appeared rows with `P* > 0`. `_w` = participation-
weighted history.

| method | WR | TE | RB | pooled MAE | RMSE | r | R² | bias |
|---|---|---|---|---|---|---|---|---|
| `pos_mean` | 0.1228 | 0.1142 | 0.1285 | 0.1220 | 0.1680 | 0.142 | 0.020 | +0.0020 |
| `last_obs` | 0.1451 | 0.1349 | 0.1516 | 0.1415 | 0.2203 | 0.161 | **−0.684** | +0.0003 |
| `ewma_hl2` | 0.1183 | 0.1097 | 0.1252 | 0.1165 | 0.1740 | 0.253 | −0.051 | +0.0014 |
| `ewma_hl8_w` | 0.1136 | 0.1032 | 0.1211 | **0.1128** | 0.1669 | 0.271 | 0.033 | +0.0019 |
| `expanding_w` | 0.1148 | 0.1055 | 0.1228 | 0.1141 | 0.1676 | 0.256 | 0.025 | +0.0040 |
| `prev_season_w` | 0.1189 | 0.1083 | 0.1302 | 0.1191 | 0.1713 | 0.207 | −0.019 | +0.0056 |
| **`eb_shrink_ewma3_w`** | **0.1134** | **0.1045** | **0.1221** | 0.1133 | **0.1617** | **0.306** | **0.092** | +0.0043 |
| `career_shrink_w` | 0.1142 | 0.1052 | 0.1229 | 0.1141 | 0.1618 | 0.305 | 0.091 | +0.0070 |

Empirical-Bayes `k`, fitted on prior seasons only, was stable at 3 (weighted
EWMA basis) in every evaluation season.

`eb_shrink_ewma3_w` is taken forward as **R0**. `ewma_hl8_w` has marginally
lower MAE but materially worse RMSE, r and R²; the shrinkage estimator wins on
every criterion except the one MAE is least able to see.

## Model ladder

| rung | features | reason | chronology | MAE | r | R² | vs R0 |
|---|---|---|---|---|---|---|---|
| **R0** | EB shrinkage only | persistence baseline | prior-only | **0.1133** | 0.306 | 0.092 | — |
| `R_base` | ridge on base history | does a fitted centre beat shrinkage? | prior-only | 0.1163 | 0.280 | 0.072 | **+2.58%** |
| `R_A` | + history quantity | Q3 | prior-only | 0.1140 | 0.289 | 0.083 | +0.59% |
| `R_B` | + role/participation | Q5 | prior-only | 0.1138 | 0.291 | 0.084 | +0.42% |
| `R_C` | + team opportunity | Q7 | prior-only | 0.1161 | 0.281 | 0.073 | +2.46% |
| `R_D` | + teammate competition | Q6 | prior-only | 0.1159 | 0.283 | 0.075 | +2.24% |
| `R_E` | + position context | Q8 | prior-only | 0.1161 | 0.279 | 0.073 | +2.47% |
| `R_AB` | | | | 0.1135 | 0.296 | 0.087 | +0.10% |
| `R_ABC` | | | | 0.1133 | 0.298 | 0.088 | −0.01% |
| **`R_ABCD`** | best rung | | | **0.1132** | 0.299 | 0.089 | **−0.10%** |
| `R_ABCDE` | | | | 0.1132 | 0.299 | 0.089 | −0.09% |

**Incremental delta: essentially zero.** Every block *alone* is worse than plain
shrinkage. The full ladder's best rung beats R0 by **0.10%** — a ridge with 34
columns and four context blocks recovers what a two-parameter shrinkage
estimator already had.

Against the pre-declared reference, the pooled position mean:

| | pos_mean | best | relative |
|---|---|---|---|
| ALL | 0.1220 | 0.1132 | **+7.18%** |
| WR | 0.1228 | 0.1132 | +7.82% |
| TE | 0.1142 | 0.1049 | +8.20% |
| RB | 0.1285 | 0.1217 | +5.24% |

Per season: 2022 +3.57%, 2023 +7.39%, 2024 +8.04%, 2025 +9.89%.
**Seasons reaching the pre-declared 10% bar: 0 of 4.**

**A larger comparison the pre-registration did not anticipate, reported because
it matters.** Against the R leg the Stage 4 pipeline actually carries
(`W/P̂c`, mean over draws):

| estimator | absolute MAE | absolute r | within-team-game MAE | within-team-game r |
|---|---|---|---|---|
| Stage 4 control R leg | 0.1353 | 0.112 | 0.1319 | 0.115 |
| R0 | 0.1133 | 0.306 | 0.1126 | 0.315 |
| R_ABCD | 0.1132 | 0.299 | 0.1125 | 0.309 |

**R is predicted 16.3% better than the accepted pipeline's own implied R leg,
with nearly three times the correlation** — and that holds on the
within-team-game pattern, which is the part reconciliation actually consumes.

## Downstream target results

Only the R leg of Stage 4 is substituted; A, T and P are frozen exactly.

| | pooled target CRPS | delta | seasons better | 95% block bootstrap |
|---|---|---|---|---|
| Stage 4 baseline | 0.9360 | — | — | — |
| **R substituted (centre)** | 0.9460 | **+0.0100** | **0/4** | [+0.0072, +0.0131] |
| R substituted, all rows | 0.9447 | +0.0088 | 0/4 | [+0.0051, +0.0127] |
| R substituted (point) | 0.9902 | +0.0542 | 0/4 | [+0.0502, +0.0585] |

The bootstrap describes variability **within heavily mined development data**. It
is not independent confirmation and is not offered as one.

**An implementation defect of mine is in that table and is left visible.** The
first downstream run substituted a **point estimate** into a slot carrying a
draw matrix whose coefficient of variation is **0.914** — destroying all
per-player dispersion. That is a change to the predictive distribution, not to
R's central tendency, and it accounted for **+0.0542 of the +0.0100** apparent
harm. The `centre` row is the faithful substitution: the model's value rescales
the control's own draw pattern, exactly as P4E and P4F changed a weight's centre
while keeping its residual structure. The point row is retained, labelled, as
the answer to a different question.

## Recoverability

**Wording as pre-declared: this is model-family recovery, not an information
ceiling.**

| | |
|---|---|
| Stage 4 R oracle component | 0.4140 / 0.4418 / 0.4422 / 0.4216 CRPS (2022–2025) |
| Candidate recovered, target CRPS | **−0.0100** (worse) |
| Percentage recovered | **−2.33%** |

On the composed target share `W`, which is what the pipeline consumes, the
picture is different and more informative:

| construction | mean \|estimate − W*\| | vs control |
|---|---|---|
| `P̂c × R_control` (Stage 4 baseline) | 0.04946 | — |
| `P̂c × R_model` | 0.04848 | **−1.97%** |
| `P* × R_control` | 0.04389 | −11.25% |
| `P* × R_model` | 0.04070 | **−17.71%** |
| `P̂c × R*` (R oracle) | 0.02370 | −52.07% |

**This model family recovered 1.97 of the 52.07 percentage points available on
the composed weight — 3.8% of the currently measured R oracle opportunity.**

## Cohorts

Best rung, pooled across seasons.

| dimension | level | n | MAE | r | bias |
|---|---|---|---|---|---|
| position | WR / TE / RB | 10059 / 6147 / 6121 | 0.1132 / 0.1049 / 0.1217 | +0.273 / +0.309 / +0.217 | +0.004 / +0.004 / −0.001 |
| prior games | `25+` | 14100 | **0.1032** | **+0.353** | +0.003 |
| | `10–24` | 4878 | 0.1215 | +0.251 | +0.004 |
| | `4–9` | 2175 | 0.1360 | +0.195 | +0.001 |
| | `<4` | 1174 | **0.1570** | **+0.150** | +0.005 |
| appearance prob | `≥0.95` | 5850 | **0.0811** | **+0.430** | +0.003 |
| | `0.50–0.80` | 4828 | 0.1486 | +0.180 | +0.001 |
| | `<0.25` | 152 | 0.1701 | +0.217 | +0.007 |
| participation | high | 8110 | **0.0817** | **+0.373** | +0.001 |
| | low | 6056 | **0.1613** | **+0.157** | +0.005 |
| role change | up / stable / down | 4571 / 13167 / 4589 | 0.1021 / 0.1149 / 0.1197 | +0.301 / +0.313 / +0.253 | +0.005 / +0.003 / +0.001 |
| target volume | high / medium / low | 9810 / 6642 / 5875 | 0.0941 / 0.1137 / 0.1447 | +0.341 / +0.247 / +0.167 | −0.001 / +0.004 / **+0.010** |
| team concentration | alpha / balanced / diffuse | 9625 / 11531 / 1171 | 0.1130 / 0.1134 / 0.1136 | +0.316 / +0.291 / +0.222 | +0.004 / +0.003 / −0.002 |

## P/R error coupling

**corr(P error, R error) = −0.0198** on n = 22,327. Mean participation forecast
error `|P̂c − P*| = 0.1292`.

**Interpretation.** R is defined conditional on P, so the two are not
independent by construction — yet their *forecast errors* are essentially
uncorrelated. That is the worst case for composition: the errors do not cancel,
they compound multiplicatively. It is recorded as a dependency finding. **The
simulator is not redesigned here.**

## Calibration

**No probabilistic R distribution was constructed, and none was forced.** The
pre-registration permitted that explicitly. Building one would have required
inventing a dispersion model that was not pre-declared, and the resulting CRPS,
PIT and coverage would have measured my invented dispersion rather than R.

Distributional evidence is reported where it is real: the downstream target CRPS
above, which scores the full composed predictive distribution.

## Adversarial

**25 probes: 8 PASS, 17 UNRESOLVED, 0 FAIL.** Materiality 10% relative R MAE,
fixed in advance and not lowered.

| probe | state | detail |
|---|---|---|
| current-game R | **PASS** | 0.0001 vs 0.1119 — +99.9% |
| current-game targets | **PASS** | 0.0868 — +22.4% |
| wrong denominator | **PASS** | +15.1% change |
| same-week duplicate chronology | **PASS** | 1,318 duplicate player-ordinals, 620 rows' history changed |
| manual rounded artifact reference | **PASS** | Rule 006 refuses a 4-decimal rounding |
| forbidden identifier scan | **PASS** | 0 hits across 5 modules |
| current-game participation | UNRESOLVED | −0.2% |
| future targets / future R / future participation | UNRESOLVED | +0.1% / +0.3% / −0.0% |
| future team target total | UNRESOLVED | −0.0% |
| postgame roster state | UNRESOLVED | +0.0% |
| `weekly_rosters.status` proxy | UNRESOLVED | −0.0% |
| present-week depth chart | UNRESOLVED | +0.0% |
| future teammate state | UNRESOLVED | +0.0% |
| identifier leakage | UNRESOLVED | −0.3% |
| forbidden market field / observed weather | UNRESOLVED | no such field exists in this project |
| evaluation-season fit leakage | UNRESOLVED | +0.3% |
| post-hoc hyperparameter selection | UNRESOLVED | +0.0% |
| zero/N-A conflation | UNRESOLVED | +3.7%, 13,308 rows |
| target-rate division instability | UNRESOLVED | −0.2% |

**The UNRESOLVED verdicts are informative, not evasive.** The harness plainly
can catch a leak — it caught current-game R at 99.9%. The future-quantity probes
do not fire because **next-game R genuinely carries almost no information about
this-game R**, which is the same low-persistence fact this whole study measured.
That is corroboration, not a blind spot. No threshold was lowered.

**One sign worth stating**: `wrong_denominator` fires with *lower* MAE (0.0950 vs
0.1119). That is not a better prediction — dividing by team targets rather than
team dropbacks changes R's scale, making an easier quantity. The probe correctly
detects that a denominator swap materially changes the result.

## Guard deletion

**Two firing**, against a minimum of two.

| guard | deletion | effect | verdict |
|---|---|---|---|
| strictly-earlier-ordinal cut | removed | 620 rows' history changes; 1,318 same-week duplicate player-ordinals become readable | **PASS** |
| complexity ceiling (48 columns) | lowered to 4 | design refused; at the real ceiling ABCDE fits in 34 columns | **PASS** |
| ≥1-prior-game training filter | relaxed | −0.2% | UNRESOLVED — required and in place, but not shown load-bearing |

## Scientific negatives

1. **No context block adds anything to simple shrinkage.** Every block alone is
   *worse* than R0; the best rung beats it by 0.10%.
2. **Raw recency is catastrophic.** `last_obs` has R² = **−0.684** — worse than
   predicting the position mean. Shrinkage beats it decisively.
3. **Recency does not help beyond long-window history.** hl8 > hl5 > hl3 > hl2,
   and the career mean matches hl8. This is the **opposite** of participation,
   where Stage 2 found hl2 best.
4. **Team passing environment adds nothing** after conditioning on participation
   (block C alone: +2.46% worse).
5. **Teammate competition adds nothing** (block D alone: +2.24% worse).
6. **Position-specific terms add nothing** (block E alone: +2.47% worse).
7. **Participation change adds almost nothing** (block B alone: +0.42% worse).
8. **The marginal gain does not compose.** A 16.3% better R leg makes downstream
   target CRPS 1.1% *worse*, 0/4 seasons.
9. **R is far less persistent than P.** Best r ≈ 0.31 here against 0.77–0.84 for
   participation in Stage 2.
10. **Signal is concentrated in established, high-participation players** and
    nearly absent for low-history, low-participation ones (r 0.150 at `<4` prior
    games versus 0.353 at `25+`).
11. **Low-history players are over-allocated, mildly**: bias +0.005 at `<4`
    prior games and +0.010 at low prior target volume.
12. **0 of 4 seasons reach the pre-declared 10% bar.**

## Defects found

- **Implementation (mine, fixed):** the downstream substitution replaced a draw
  matrix with a point estimate, destroying dispersion with CV 0.914 and
  accounting for +0.0542 of apparent harm. Fixed to a centre substitution; both
  are reported.
- **Implementation (mine, fixed):** one missing import path aborted the
  adversarial run mid-suite.
- **Estimator:** none found in the accepted pipeline by this study.
- **Data:** none. Chronology clean, denominators verified against Stage 4 at
  float64 equality.
- **Governance:** none.

## Answers to the twelve questions

1. **Persistence vs pooled mean** — yes, but modestly: +7.18% pooled, 0/4
   seasons above 10%.
2. **Shrinkage vs raw recency** — shrinkage wins decisively (R² 0.092 vs −0.684).
3. **Recency beyond long windows** — **no**; longer is better.
4. **Role change breaks persistence** — mildly; "down" is the weakest cohort
   (r 0.253 vs 0.313 stable).
5. **Participation change adds information** — almost none (+0.42% worse alone).
6. **Teammate competition** — no.
7. **Team passing environment** — no.
8. **Position-specific models justified** — no; block E is worse alone and adds
   nothing cumulatively.
9. **Signal concentrated in established players** — yes, strongly.
10. **Low-history over/under-allocation** — mild **over**-allocation.
11. **Meaningful share of R oracle recovered** — **no**: 3.8% on the composed
    weight, negative on target CRPS.
12. **Cause of the residual** — **UNRESOLVED, and deliberately so.** What is
    *measured* is that participation forecast error is a large multiplicative
    limiter: the same R model gains 17.7% on the composed weight with oracle
    participation and 1.97% without, and the two errors are uncorrelated
    (−0.0198) so they compound. What is **not** established is whether the
    remaining R error is noise, missing route information, or missing role
    information. The pass-snap proxy gap remains unmeasurable, so no claim is
    made about routes.

## FINAL SCIENTIFIC STATE

**SIGNAL_WEAK**

There is real, chronology-safe, repeatable out-of-sample signal in next-game
target rate conditional on participation: a two-parameter empirical-Bayes
shrinkage estimator beats the pooled position mean by 7.18% and the accepted
pipeline's own implied R leg by 16.3%, with nearly three times the correlation,
consistently in all four seasons and on the within-team-game pattern that
reconciliation consumes.

It is **weak**: 0 of 4 seasons reach the pre-declared 10% bar, no context block
adds anything, only 3.8% of the measured R oracle opportunity is recovered on
the composed weight, and downstream target CRPS gets *worse*.

`MODEL_CLASS_FAILED` was considered and rejected — the family did not fail, it
succeeded modestly. `INFORMATION_CONSTRAINED_CANDIDATE` was considered and
rejected — that requires two materially different families to fail, and one
narrow study is explicitly insufficient. `UPSTREAM_DEPENDENCY_LIMITED` was
considered: the P-dependency is real and measured, but it explains the
composition result rather than preventing clean interpretation, so it is
reported as a named finding rather than promoted to the primary label.

## ACTION STATE

**RETAIN_P4C.**

P4C system C target allocation is retained unchanged. No development candidate
is carried forward: the estimator predicts R better than the accepted pipeline's
implied R leg, but composing it makes the accepted pipeline worse, and an
estimator that improves a part while degrading the whole is not a candidate.

**NO PROMOTION.** No prospective freeze was performed; this directive did not
authorise one.

## OWNER DECISION NEEDED

**Decide whether the next research unit is participation forecasting (P) rather
than any further work on R.**

This study's most decision-relevant number is not about R. The same R model is
worth **1.97%** on the composed target weight with the current participation
forecast and **17.71%** with oracle participation — a factor of nine — and the
two errors are uncorrelated, so they compound rather than cancel. Stage 4 rated
P at 28.5% of target error with `ONE_NARROW_TEST` behind it; this study shows P
additionally gates whatever R could ever contribute.

The honest counter-argument, which is yours to weigh: Stage 2 already found P
well-forecast at r ≈ 0.80, so the remaining P error may itself be irreducible,
and this could be a chain where no link moves. Deciding that requires a P study,
not another R study.
