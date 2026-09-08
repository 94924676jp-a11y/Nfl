# P RECOVERABILITY RETURN

## Canonical state

| | |
|---|---|
| Start HEAD | `647f620` |
| Pre-registration commit | **`149faf8`** — canonical before any new comparative P result |
| Result commit | this commit |
| Final HEAD | see below |

## Baseline identity

| | |
|---|---|
| Artifact | `nfl/research/s2/s2_results.json` at `by_season/<pos>/ewma_hl2/pooled` |
| SHA256 | `cb7959e6f578…`, read through Rule 006, never transcribed |
| Exact reproduction | **PASS on all 15 checks** — 3 positions × {MAE, RMSE, r, R², SD ratio}, every one at `|diff| 0.0` |

Chronology masking audit **CLEAN** at four ordinals (11,977 / 16,646 / 11,194 /
12,644 feature values compared).

## Estimand

`P = player pass snaps / team dropbacks`, conditional on appearance, by Stage
2's exact construction.

**Appearance kept separate.** No combined A×P experiment was run; none was
pre-declared, and appearance was not permitted to absorb P.

**Route limitation, unweakened.** P is **PASS-SNAP PARTICIPATION — an UPPER
BOUND ON ROUTE PARTICIPATION**. A player on the field for a dropback may block.
It is **not routes run**, true routes are unavailable in this project, the
magnitude of the gap is unknown, and nothing here concludes anything about the
value of route information.

## Residual anatomy of the accepted control

Per season (n = 22,500 total):

| season | n | MAE | RMSE | r | R² | SD ratio | bias |
|---|---|---|---|---|---|---|---|
| 2022 | 5,645 | 0.1350 | 0.1882 | 0.808 | 0.648 | 0.868 | +0.0041 |
| 2023 | 5,704 | 0.1258 | 0.1772 | 0.830 | 0.684 | 0.896 | +0.0037 |
| 2024 | 5,575 | 0.1284 | 0.1792 | 0.823 | 0.674 | 0.882 | +0.0009 |
| 2025 | 5,576 | 0.1283 | 0.1788 | 0.819 | 0.664 | 0.900 | −0.0011 |

**The residual is dominated by role transitions, and it is a lag.**

| role transition | n | MAE | r | R² | bias |
|---|---|---|---|---|---|
| stable | 13,253 | **0.1108** | **0.872** | **0.753** | −0.0006 |
| up | 4,609 | 0.1570 | 0.712 | 0.496 | **−0.0274** |
| down | 4,638 | 0.1549 | 0.719 | 0.498 | **+0.0383** |

The control **under-predicts rising roles and over-predicts falling ones** — the
signature of an EWMA lagging a moving target. On stable players it is already
excellent (R² 0.753).

Residual structure:

| against | corr(signed residual) | corr(\|residual\|) |
|---|---|---|
| recent P change | **−0.1455** | +0.0063 |
| prior P | +0.1157 | −0.0116 |
| history length | +0.0645 | −0.0573 |
| appearance probability | −0.0513 | −0.0875 |
| P variance | +0.0259 | **+0.2660** |
| teammate role change | −0.0036 | +0.0242 |
| **residual autocorrelation, lag-1** | **+0.1957** | — |

Residual dispersion by group: player 727 groups, sd of group means 0.0461;
team 32 groups, 0.0045; week 18 groups, 0.0099 — against an overall residual sd
of 0.1809. **Structure is at the player level, not the team or week level.**

Recoverability is **not** inferred from residual size.

## Simple baselines

Pooled, all four seasons, versus the accepted `ewma_hl2` control.

| method | MAE | RMSE | r | R² | SD ratio | bias | vs control |
|---|---|---|---|---|---|---|---|
| `pos_mean` | 0.2621 | 0.3009 | 0.285 | 0.080 | 0.300 | −0.0068 | −102.59% |
| `last_obs` | 0.1375 | 0.1998 | 0.797 | 0.594 | 1.001 | +0.0001 | −6.26% |
| `expanding` / `career_prior` | 0.1623 | 0.2161 | 0.731 | 0.526 | 0.821 | +0.0010 | −25.48% |
| **`ewma_hl1`** | **0.1268** | **0.1803** | **0.824** | **0.670** | **0.920** | +0.0008 | **+1.95%** |
| `ewma_hl2` *(control)* | 0.1294 | 0.1809 | 0.820 | 0.668 | 0.887 | +0.0019 | — |
| `ewma_hl3` | 0.1327 | 0.1838 | 0.813 | 0.657 | 0.870 | +0.0028 | −2.55% |
| `ewma_hl5` | 0.1381 | 0.1892 | 0.800 | 0.636 | 0.852 | +0.0039 | −6.78% |
| `ewma_hl8` | 0.1438 | 0.1951 | 0.785 | 0.614 | 0.839 | +0.0045 | −11.13% |
| `eb_shrink` | 0.1305 | 0.1802 | 0.820 | 0.670 | 0.857 | +0.0057 | −0.86% |
| `prev_season` | 0.1935 | 0.2531 | 0.621 | 0.349 | 0.801 | +0.0192 | −49.57% |
| `role_persist` | 0.1287 | 0.1802 | 0.822 | 0.670 | 0.897 | +0.0040 | +0.51% |

**The winner is a shorter half-life.** `ewma_hl1` beats the accepted control on
MAE, RMSE, r, R² *and* SD ratio. Stage 2 tested half-lives 2, 3 and 5 — it never
tested 1. That is where the entire recoverable gain in this study turned out to
be.

The fitted empirical-Bayes constant hit the bottom of its grid (`k = 0.5`) in
every season: the data wants **less** shrinkage, not more, which is consistent
with the same story.

Role-persistence factors, fitted on prior seasons only, are stable and in the
expected direction: `down ≈ 0.93`, `stable ≈ 1.01`, `up ≈ 1.05`.

## Limited ladder

| rung | MAE | RMSE | r | R² | SD ratio | vs control |
|---|---|---|---|---|---|---|
| `CONTROL_hl2` | 0.1294 | 0.1809 | 0.820 | 0.668 | 0.887 | — |
| **`P0` = `ewma_hl1`** | **0.1270** | 0.1804 | 0.824 | 0.670 | 0.919 | **+1.86%** |
| `P_iso` (monotonic) | 0.1334 | 0.1800 | 0.820 | 0.671 | 0.807 | −3.14% |
| `P_base` | 0.1304 | 0.1761 | 0.828 | 0.685 | 0.808 | −0.77% |
| `P_A` | 0.1299 | 0.1762 | 0.828 | 0.685 | 0.816 | −0.42% |
| `P_B` | 0.1292 | 0.1752 | 0.830 | 0.688 | 0.820 | +0.13% |
| `P_C` | 0.1300 | 0.1753 | 0.830 | 0.688 | 0.810 | −0.46% |
| `P_D` | 0.1304 | 0.1761 | 0.828 | 0.685 | 0.808 | −0.77% |
| `P_E` | 0.1304 | 0.1761 | 0.828 | 0.685 | 0.809 | −0.79% |
| `P_ABCDE` | 0.1289 | **0.1747** | **0.831** | **0.690** | 0.823 | +0.33% |

Season stability of the candidate: **4 of 4 seasons better** — +2.24%, +2.55%,
+1.43%, +1.18%. **0 of 4 reach the pre-declared 5% bar. 0 of 3 positions reach
it** (WR +2.87%, TE +1.84%, RB −0.08%).

**MAE and RMSE disagree, and the disagreement is real.** Every ridge rung has
*better* RMSE and R² than both the control and the candidate, and *worse* MAE.
The ridge shrinks (SD ratio 0.81–0.82 against the control's 0.887 and the
candidate's 0.919), which helps squared error and hurts absolute error. The
pre-registration fixed MAE as the decision metric, so `P0` is the candidate —
but the ridge's RMSE advantage is a real property and is not hidden here.

**The one pre-declared monotonic family failed.** Isotonic recalibration
improves R² marginally (0.671) and loses 3.14% of MAE, shrinking dispersion to
0.807 — the opposite of what Stage 2's under-dispersion diagnosis suggested it
would do. Pre-declared, run, reported, rejected.

## Role-change analysis

Marginal P, control → candidate:

| cohort | n | control MAE | candidate MAE | change | bias control → candidate |
|---|---|---|---|---|---|
| **down** | 4,638 | 0.1549 | 0.1475 | **+4.82%** | **+0.0383 → −0.0076** |
| **up** | 4,609 | 0.1570 | 0.1523 | +2.99% | −0.0274 → +0.0147 |
| stable | 13,253 | 0.1108 | 0.1110 | −0.15% | −0.0006 → −0.0006 |
| appearance `<0.25` | 158 | 0.1518 | 0.1344 | **+11.46%** | +0.0349 → +0.0149 |
| prior role: rotation | 9,668 | 0.1493 | 0.1436 | +3.81% | +0.0040 → +0.0022 |
| prior role: starter | 7,537 | 0.1170 | 0.1170 | +0.01% | +0.0255 → +0.0243 |
| history `<4` | 1,180 | 0.1221 | 0.1238 | −1.35% | −0.0291 → −0.0220 |

The gain is **entirely in transitions and rotation players**, exactly where the
residual anatomy said it would be, and the lag bias on falling roles is almost
eliminated. Stable players and established starters gain nothing — they were
already well served.

## Downstream target CRPS

Only P substituted; A, T, R frozen. `W_new = P_new[:, None] × Rhat`, so the
entire draw structure in `Rhat` is untouched — R1's lesson applied, no draw
distribution replaced by a point estimate.

| | pooled CRPS | delta | seasons better | 95% block bootstrap |
|---|---|---|---|---|
| control | 0.9360 | — | — | — |
| **candidate P** | **0.9346** | **−0.0014** | **3/4** | **[−0.0026, −0.0002]** |

Per season: 2022 +0.0004, 2023 −0.0021, 2024 −0.0028, 2025 −0.0013.

The interval excludes zero **in the improving direction**. Unlike R1, a marginal
gain here does compose — but it is very small. The bootstrap describes
variability within heavily mined development data and is not confirmation.

Cohort deltas downstream:

| cohort | n | control | candidate | delta |
|---|---|---|---|---|
| role: **up** | 6,010 | 1.0773 | 1.0622 | **−0.0151** |
| role: stable | 18,245 | 0.9160 | 0.9144 | −0.0016 |
| role: **down** | 7,188 | 0.8686 | 0.8790 | **+0.0105** |
| high-confidence starter | 5,996 | 1.5835 | 1.5775 | −0.0060 |
| history 10–24 | 7,164 | 0.8085 | 0.8031 | −0.0054 |
| history 25+ | 18,747 | 1.0819 | 1.0819 | +0.0000 |

**An inversion worth naming**: on marginal P the candidate helps *falling* roles
most (+4.82%); downstream it helps *rising* roles most (−0.0151) and **hurts**
falling ones (+0.0105). Marginal improvement and composed improvement are not
the same cohorts.

## P oracle recovery

| | |
|---|---|
| Stage 4 P oracle component | 0.2849 / 0.2638 / 0.2548 / 0.2627 CRPS (2022–2025) |
| Raw P improvement | +1.86% pooled MAE, 4/4 seasons |
| Downstream improvement | −0.0014 target CRPS |
| **Percentage recovered** | **+0.53%** |

**This model family recovered 0.53% of the currently measured P oracle
opportunity.** Not "only 0.53% of P is recoverable" — no information ceiling is
inferred from one family.

## P/R interaction — diagnostic only

`R_R1` is **not accepted and not promoted**, and does not replace accepted R.

| cell | pooled target CRPS | vs control |
|---|---|---|
| `P_control × R_control` | 0.9360 | — |
| `P_candidate × R_control` | 0.9346 | −0.0014 |
| `P_control × R_R1` | 0.9462 | +0.0102 |
| `P_candidate × R_R1` | 0.9488 | +0.0128 |

R1 costs **+0.0102** under control P and **+0.0142** under candidate P.
**Interaction = −0.0040: a better P made R1 worse, not better.**

**This does not contradict R1's oracle finding, it bounds it.** R1 measured that
*oracle* P raises R's composed value from 1.97% to 17.71%. This candidate is
1.86% better than control on MAE — nowhere near oracle. The measurement says a
*small* P improvement does not unlock R1's signal, and says nothing about what a
large one would do.

## Joint diagnostic (Stage 3, consumer only)

Targets, 2024 / 2025, PRE and POST reconciliation:

| quantity | control PRE | control POST | candidate PRE | candidate POST |
|---|---|---|---|---|
| group sum > physical max (rate), 2024 | 0.5436 | 0.0000 | 0.5432 | 0.0000 |
| group sum max, 2024 | 2.7675 | 1.0000 | **2.7077** | 1.0000 |
| group sum max, 2025 | 2.6518 | 1.0000 | **2.5703** | 1.0000 |
| target CRPS, 2024 | 0.9343 | 0.9221 | 0.9315 | **0.9193** |
| bias, 2024 | 0.0942 | −0.0142 | 0.0925 | −0.0142 |
| randomised PIT, 2024 | 74.3 | 71.9 | 79.5 | 72.4 |
| randomised PIT, 2025 | 121.1 | 104.8 | 121.1 | 104.9 |

- **Reconciliation does not damage the new P marginal** — it improves target
  CRPS and PIT for both, and the post-reconciliation numbers are near-identical.
- Individual cap violations are **zero** in every cell.
- Pre-reconciliation physical incoherence persists (54–57% of draws above the
  cap), as Stage 3 found; the candidate reduces the peak slightly.
- PIT remains far above the 27.877 critical value in every cell — a standing
  Stage 3 flag, not a finding of this study.
- Dependence: realised rank1↔rank2 inside the model band for both.

## Cohorts

Full tables in `p_study.json`. One cohort definition was poorly chosen and is
reported as such rather than re-cut: **`teammate_change` put 22,030 of 22,500
rows into `returning_competitor`** because "any teammate absent last game with
prior history" is nearly universal. Thresholds were fixed before results and are
not being adjusted; the cohort simply carries no information as defined.

## Adversarial

**24 probes: 11 PASS, 13 UNRESOLVED, 0 FAIL.** Materiality 5% relative P MAE,
fixed in advance, not lowered.

| probe | state | detail |
|---|---|---|
| current-game P | PASS | 0.0003 vs 0.1277 — +99.7% |
| current-game pass snaps | PASS | +43.1% |
| current-game targets | PASS | +8.6% |
| future P | PASS | +8.5% |
| wrong denominator | PASS | +29.1%, hits the candidate directly |
| zero/N-A conflation | PASS | +18.2%, 13,057 rows |
| same-week duplicate chronology | PASS | 1,318 duplicate ordinals, 625 rows changed |
| manual rounded artifact reference | PASS | Rule 006 refuses a 4-decimal rounding |
| forbidden identifier scan | PASS | 0 hits across 6 modules |
| current-game team dropbacks | UNRESOLVED | +0.0% |
| future target data | UNRESOLVED | +2.8% |
| future teammate participation | UNRESOLVED | +3.9% |
| postgame roster state | UNRESOLVED | +0.0% |
| `weekly_rosters.status` proxy | UNRESOLVED | +0.0% |
| present-week depth chart | UNRESOLVED | −0.1% |
| identifier leakage | UNRESOLVED | +0.2% |
| market data / observed weather | UNRESOLVED | no such field exists here |
| evaluation-season fit leakage | UNRESOLVED | +0.5% |
| post-hoc hyperparameter selection | UNRESOLVED | +0.2% |
| future residual pool | UNRESOLVED | −0.1% |

**A note on leak surface that matters more than the counts.** The selected
candidate is `ewma_hl1`, a fixed-form estimator with **no feature channel** —
nothing can be injected into it except through the history construction. The
feature-injection probes were therefore run against the ridge rung, the only
fittable model here. The probes that bear on the candidate itself are the
history-construction ones — wrong denominator (+29.1%), zero/N-A conflation
(+18.2%) and same-week chronology (625 rows) — and all three fire.

## Guard deletion

| guard | deletion | effect | verdict |
|---|---|---|---|
| strictly-earlier-ordinal cut | removed | 625 rows' history changes; 1,318 same-week duplicate player-ordinals become readable | **PASS** |
| complexity ceiling (48 columns) | lowered to 4 | design refused | **PASS** |
| appeared-only condition on P history | removed | +0.2% | UNRESOLVED — required and in place, not shown load-bearing for the candidate |

## Scientific negatives

1. **No feature block improves P.** Every block alone is worse than or level
   with the control on MAE; the full ridge is +0.33%.
2. **The pre-declared monotonic family failed** (−3.14% MAE).
3. **Empirical-Bayes shrinkage failed** (−0.86%); the fitted constant pinned to
   the bottom of its grid, meaning the data wanted *less* shrinkage.
4. **Prior-season and career priors are far worse** than short-window recency
   (−49.6%, −25.5%).
5. **RB gains nothing** (−0.08%).
6. **Established starters and stable-role players gain nothing** (+0.01%,
   −0.15%) — the control was already good there.
7. **A better P does not unlock R1** — the interaction is −0.0040, the wrong
   sign.
8. **0 of 4 seasons and 0 of 3 positions reach the pre-declared 5% bar.**
9. **Only 0.53% of the measured P oracle opportunity is recovered.**
10. **The `teammate_change` cohort as pre-declared is uninformative** — 98% of
    rows in one level.
11. **Downstream cohort gains invert the marginal ones** — the candidate helps
    rising roles downstream and hurts falling ones, the reverse of its marginal
    profile.

## Defects

- **Implementation**: none found this study. The draw-preserving substitution
  rule was pre-declared from R1's lesson and applied from the start.
- **Estimator**: the accepted control's half-life is mildly suboptimal — hl1
  beats hl2 on every metric measured. Small, real, and a Stage 2 search-space
  gap rather than an error.
- **Data**: none. Baseline identity exact on 15 checks; chronology clean.
- **Governance**: none.

## Answers to the fifteen questions

1. **Can hl2 be beaten?** Yes, by hl1: +1.86% pooled, 4/4 seasons, but below the
   5% bar.
2. **Is the residual role-transition error or ordinary noise?** Predominantly
   role transition — R² 0.753 stable versus 0.496/0.498 up/down, with a
   systematic lag bias of ±0.03.
3. **Does longer history help stable players?** No — longer half-lives are worse
   everywhere, monotonically.
4. **Does shorter history help role-change players?** Yes, and that is the whole
   effect: +4.82% down, +2.99% up, −0.15% stable.
5. **Does appearance context improve P?** Marginally (block B +0.13%, the only
   positive block alone).
6. **Does teammate-role context improve P?** No (−0.46%).
7. **Do team/coach variables improve P?** No (−0.77%).
8. **Are WR/TE/RB materially different?** Not enough to justify separate models
   — block E is −0.79% alone. WR gains most, RB nothing.
9. **Is low-history P forecastable?** Partly — `<4` prior games has MAE 0.1221
   under the control, better than mid-history, but the candidate makes it
   slightly worse (−1.35%).
10. **Is role-change P forecastable?** Better than the control manages, and the
    bias is correctable — but the residual stays large (0.147 versus 0.111
    stable).
11. **Does a better P forecast improve target CRPS?** Yes, stably but tinily:
    −0.0014, 3/4 seasons, CI excluding zero.
12. **Does a better P unlock R1?** **No** — interaction −0.0040, the wrong sign.
    A *small* P gain does not; this says nothing about a large one.
13. **Does reconciliation improve or damage the new P marginal?** Improves it,
    and the post-reconciliation numbers are near-identical to the control's.
14. **How much of the P oracle does this family recover?** 0.53%.
15. **Is the residual model-class failure, missing routes, appearance
    uncertainty, estimator defect, or unresolved?** **UNRESOLVED, deliberately.**
    What is measured: the residual is concentrated in role transitions, carries
    lag-1 autocorrelation of +0.196, and varies at player level (sd 0.046) far
    more than team (0.005) or week (0.010). What is **not** established: whether
    the remainder is irreducible game-to-game noise, missing route information
    (unmeasurable — the pass-snap proxy gap is unbounded), or missing role
    information. No cause is claimed.

## FINAL SCIENTIFIC STATE

**P_SIGNAL_WEAK**

A stable improvement exists — `ewma_hl1` beats the accepted control on every
marginal metric, in all four seasons, and produces a downstream target CRPS
improvement whose bootstrap interval excludes zero in the improving direction.
It falls short of `P_SIGNAL_FOUND` on magnitude (0/4 seasons and 0/3 positions
reach the pre-declared 5% bar) and on effect size (0.53% of the P oracle
opportunity).

`P_MODEL_CLASS_FAILED` was considered and rejected — the family did not fail, it
succeeded slightly. `P_INFORMATION_CONSTRAINED_CANDIDATE` was considered and
rejected — that requires materially different approaches to fail, and two
families here (persistence/shrinkage and ridge-with-context) are not enough to
support the claim. `P_ESTIMATOR_DEFECT` was considered: the control's half-life
is mildly suboptimal, but that is a search-space gap in Stage 2 rather than a
defective estimator, and it is reported under Defects instead.

## ACTION STATE

**RETAIN_P_DEVELOPMENT_CANDIDATE** — `ewma_hl1`.

It improves P *and* improves downstream target CRPS, so the pre-declared
"improves P but worsens downstream → RETAIN_STAGE2_P" clause is not triggered.
It is a one-parameter change to a quantity Stage 2 never searched, with no
feature channel and therefore almost no leak surface.

**NO PROMOTION. NO PROSPECTIVE FREEZE** — this directive authorised neither, and
neither was performed. Stage 2's hl2 remains the accepted representation until
an owner decision says otherwise.

## OWNER DECISION NEEDED

**Decide whether the chain is worth continuing at all, given that both of its
two largest components have now been measured and both returned weak.**

R recovered 3.8% of its oracle and failed to compose. P recovered 0.53% of its
oracle and composed to −0.0014 CRPS on a 0.9360 baseline. Together they are
74.5% of target error by oracle accounting and under 1% of it by achieved
recovery. The one thing that would change this picture is information the
project does not have — true routes run — and the size of that gap is
unmeasurable from what is here.

The decision is therefore not "which layer next" but whether the next unit
should go to **acquiring new information** rather than to modelling the existing
information further. I am not authorised to pursue either, and both R1 and this
study were run in full before saying so.
