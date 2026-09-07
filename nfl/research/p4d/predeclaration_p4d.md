# P4D pre-declaration — appearance probability calibration and mid-range ranking

Written 2026-09-07. HEAD at task start `0a7b6cb`.

Written **after** two pre-fitting diagnostics of the *incumbent* (§1 and §2 —
both are properties of the control, not results about any candidate) and
**before** any candidate was fitted, any recalibration was applied, any
downstream CRPS or randomised PIT existed. Departures are labelled where they
occur; the original text stays.

## 1. A defect in the incumbent, found before anything was built

`stage_a.fit_logistic` is plain gradient descent, fixed step 0.5, **300
iterations**, with no convergence check. Measured on the 2024 training set
(34,603 rows, 49 features):

```
incumbent (GD, 300 iters) : objective 0.403347   ||grad||_inf 2.03e-03   ||w|| 2.0961
converged (Newton, 11 it) : objective 0.402229   ||grad||_inf 1.30e-16   ||w|| 2.7508
```

**The incumbent stops at 76.2% of the converged coefficient norm.** It needs
about 30,000 GD iterations to reach the Newton solution. That is an extra ~24%
of shrinkage on top of the declared L2 penalty — undeclared, and exactly the
shape that produces *compressed* probabilities: an intercept that converges
almost immediately (so calibration-in-the-large looks fine) with a ranking that
is still pulled toward the base rate. P4C reported precisely that symptom.

Out of sample on 2024 the gap is real but modest: Brier 0.12574 → 0.12505,
log loss 0.38881 → 0.38648, AUC 0.8783 → 0.8803.

**This is recorded as a defect in the control and it does not change the
control.** Per the directive, `A` remains the incumbent exactly as P2/P3/P4B/
P4C ran it. The converged fit is a *candidate*, `A1`.

## 2. Two pregame fields exist in the panel and are never used

`featurise_p3` omits four `f_*` fields that the panel builds. Two matter:

| field | coverage | chronology status | decision |
|---|---|---|---|
| `f_prev_report` | prior week's injury report status | **same as the incumbent injury feature** — a prior-week row whose own `date_modified` precedes this kickoff by more than a week | **eligible** |
| `f_depth` | depth-chart rank; 78–87% for 2020–2024, **0% for 2025** | **no timestamp of any kind exists on the depth-chart artifact** — it can be neither prospectively captured nor retrospectively chronology-tested | **NOT eligible; diagnostic arm only** |

`f_depth` is therefore excluded from every eligible system and run in a single
clearly labelled diagnostic arm, so the return can say what a timestamped depth
source would be worth without pretending we have one.

## 3. Estimand — unchanged

`A_i` = the player appears in the team-game, exactly as defined in P2/P3/P4B/
P4C: `appeared = 1 if did_not_appear == 0`. The pregame candidate universe is
unchanged (appeared for this team in any of the previous 4 team-games, and
`f_n_prior >= 1`). **If an integrity defect in this definition is found, the
work stops and reports it rather than silently changing the estimand.**

## 4. Systems

| id | ranking model | probability mapping | eligible |
|---|---|---|---|
| **A** | incumbent Stage-A (GD 300) | raw | **control** |
| **A+P** | incumbent | Platt / logistic recalibration | yes |
| **A+I** | incumbent | isotonic recalibration | yes |
| **A+S** | incumbent | monotone spline recalibration | yes |
| **A1** | **converged** incumbent, identical features and identical L2 | raw | yes |
| **A1+cal** | converged incumbent | best family, chosen on the inner season | yes |
| **R** | converged + new chronology-safe feature blocks | raw | yes |
| **R+cal** | R | best family, chosen on the inner season | yes |
| **X_depth** | R + depth-chart rank | raw | **NO — diagnostic only** |
| **O** | — | **realised appearance** | **NO — diagnostic only** |

## 5. Candidate feature blocks for R, all strictly prior-game

Named now so the ablation removes a *block*, never a column:

1. `streak` — consecutive prior appearances; consecutive prior absences already
   present as `f_consec_missed`; longest prior appearance run.
2. `long_window` — appearance rate over the prior 8 and 10 games and over the
   player's whole prior history (expanding), plus season-to-date rate.
3. `trajectory` — snap-share EWMA(3) minus EWMA(8); mean of the last 3 prior
   snap shares minus the 3 before those.
4. `depth_of_history` — `f_n_prior` interacted with `f_rate_ewma` and with
   `f_snap_ewma`, and a season-week index. **This block is the targeted fix for
   the mid-range**: a global logistic cannot otherwise distinguish "50% over 6
   games" from "50% over 20 games", and those are different probabilities.
5. `prior_injury_history` — count and rate of prior weeks on the injury report,
   and `f_prev_report` as an indicator set. Prior weeks only.
6. `teammate_context` — count of same-position candidates who appeared in the
   team's previous game (position-group competition depth).

**Do not assume any block helps.** Each is ablated as a block.

## 6. 2025 injury rule — unchanged

The 2025 nflverse injury artifact has no `date_modified`, so 2025 carries no
injury feature, exactly as P2/P3/P4C. **No historical point-in-time injury
availability is manufactured from a final file.** The existence of a 2026
injury file is not evidence about what the 2025 file looked like pregame and is
not used as such. `f_depth` is absent for 2025 anyway and is excluded for a
separate reason (§2).

## 7. Chronology — nested, and the calibrator never sees the evaluation season

For evaluation season *Y*:

- the **prediction model** is trained on seasons strictly before *Y*;
- the **calibrator** is fitted on pooled **out-of-fold** pairs
  `(p_hat_s, y_s)` for every season *s* with `2021 <= s < Y`, where `p_hat_s`
  came from a model trained on seasons strictly before *s*. So no calibrator
  ever sees a probability produced by a model that saw the row being calibrated;
- the **calibration family** is chosen by log loss on the **inner validation
  season** `Y-1`, with everything producing that season's probabilities fitted
  on seasons before `Y-1`. This is the P4B/P4C nesting, unchanged.

**No calibrator is fitted on the evaluation season. No family, threshold or
hyper-parameter is chosen using evaluation-season results of any kind, and in
particular never using randomised PIT.**

## 8. Probability bands, fixed now

Primary (from the directive): `p < 0.25`, `0.25 <= p < 0.50`,
`0.50 <= p < 0.80`, `0.80 <= p < 0.95`, `p >= 0.95`.
Also retained so results stay comparable with P4C: `p < 0.50`,
`0.50 <= p < 0.80`, `0.80 <= p < 0.95`, `p >= 0.95`.

Bands are assigned by the **system's own** probability, and reliability is also
reported on bands assigned by the **incumbent's** probability so the same rows
are compared across systems.

## 9. The calibration-versus-ranking test

A monotone recalibration **cannot change any ranking**. Therefore:

- if a monotone map fixes band reliability, the defect is **levels**;
- if it does not, the defect is **ranking**;
- **AUC computed within the 0.25–0.80 region** is invariant to any monotone map,
  so any change in it is attributable to a ranking change and to nothing else.

That within-band AUC is the discriminating statistic and it is named here
before it is computed.

## 10. Appearance metrics

Per season and per band: Brier, log loss, ROC AUC, PR AUC, calibration
intercept and slope (logistic regression of the outcome on the logit),
reliability table, ECE and maximum calibration error (10 equal-width bins),
within-region AUC for 0.25–0.80, and pairwise ranking accuracy on
discordant-outcome pairs. **Calibration-in-the-large is not evidence of
calibration and is never reported as such.**

## 11. Downstream test — the P4C machinery is frozen

Each eligible appearance system is fed into the P4C opportunity machinery with
**appearance as the only changing component**. Share point models, share
residual pools, reconciliation, stochastic residual mass and team-volume
distributions are byte-identical to P4C. The allocation system is P4C's
**C** (reserved stochastic mass), the reconciled system P4C selected, for all
five classes. Reported: CRPS, randomised PIT, coverage at 50/80/90/95, mean
interval width, threshold calibration on the P4C grids (unchanged, including
the `rz_carries` grid pre-declared in P4C), bias, and the discretised log score.

## 12. Selection rule, fixed before any result

A candidate is promoted over the incumbent **only if all four hold**:

1. **both** mean log loss and mean Brier improve;
2. ROC AUC does not fall by more than 0.002;
3. downstream CRPS does not worsen by more than 0.25% on **any** of the five
   classes;
4. downstream randomised PIT improves on `snaps` **and** `pass_snaps` — the two
   classes P4C attributed to appearance;

and the direction is consistent in at least **3 of the 4** seasons.

Ties are broken by downstream CRPS. **Randomised PIT alone never selects**, and
a candidate that buys calibration by flattening discrimination fails rule 2.
**If nothing clears the bar, the incumbent is retained and the return is a
negative result.**

## 13. What would count as a negative result

Stated in advance, in the words the return will use:

- If recalibration does not improve the mid-range bands, the return says the
  defect is not a levels problem.
- If added features do not improve within-region AUC, the return says the
  available pregame information does not contain the missing ranking signal,
  and reports what remains irreducible.
- If an improved appearance model does not lower downstream randomised PIT for
  `snaps` and `pass_snaps`, the return says P4C's attribution does not survive
  intervention — that the oracle-substitution result identified a **bound**, not
  an achievable gain.
- If `carries` stops passing the randomised PIT under a promoted candidate, that
  is a regression and the candidate is refused whatever else it improves.
