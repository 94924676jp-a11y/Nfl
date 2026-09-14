# C1 pre-registration — the carry allocator's `other` mass on A1's denominator

Written 2026-09-14, **after** the full-slate forensic audit
(`3f5fc82`) and **before** any line of the repair is written, any parameter is
refit, or any comparison is run.

This document does not authorise a change to production. R8 remains the
accepted baseline. Nothing here reaches a live board without a further owner
decision.

## 1. The defect

`p4c_lib.CLASSES['carries']` declares `den = 'team_carries'`,
`pos = ('RB',)`, `mode = 'simplex'`. `p4c_build` fits the `other` mass as

    pool[k] = clip(mall[k] - ms[k], 0, 0.95)

where `mall[k]` sums **every** position's share of team carries for team-game
`k`, and `ms[k]` sums only the modelled running backs'. Because the panel
closes, `mall[k] == 1.0`, so the fitted quantity is

    other = 1 - (modelled RBs' share of TEAM carries)

Measured: **0.198875**. The historical non-RB mass is **0.1918**. Those two
agreeing to three decimals is the identification: the fitted `other` is a
**team-denominator** residual, dominated by quarterback rushing (0.1568).

`run_forecast.py` does not supply `team_carries`. It supplies A1's `rb`
category:

    rushing_budget = {t: a1.value['carries'][(t, 'rb')] for t in teams}

A1 has already partitioned away `kneel`, `designed_qb`, `wr`, `te` and
`fringe`. Applying 0.199 to that budget removes the same categories a second
time. On the `rb` denominator the correct residual is **0.008754**, so the
mass is overstated **22.7x** and **0.1901** of the running-back budget is
subtracted twice.

## 2. Why the receiving side is the control, not a second instance

`CLASSES['targets']` declares `den = 'team_targets'` over
`pos = ('WR','TE','RB')` -- every target-taking position -- and production
feeds it that same team budget, with no partition in between. Its fitted
`other` is 0.011282. Same estimator, same allocator, same code path, and on
the graded slate targets are near-unbiased where carries are not. **The
repair must therefore not touch the targets class.** A change that moves
receiving numbers is out of scope and is evidence the repair is wrong.

## 3. The candidate

**C1.** The `other` mass for a simplex class is fitted on the SAME
denominator the production budget is on. Concretely: when the consuming
budget is a partition of the class denominator rather than the denominator
itself, `mall[k]` must be the mass of that partition, not 1.0.

For `carries`, whose production budget is A1's `rb` category:

    mall_rb[k] = sum of ALL running backs' share of team carries for k
    pool[k]    = clip(mall_rb[k] - ms[k], 0, 0.95) / mall_rb[k]

which is the share of the **running-back budget** taken by running backs the
pool does not model.

**What C1 may not do**, stated now so no later result can be reinterpreted:

- it may not change `CLASSES['targets']`, or any occupancy-mode class;
- it may not introduce a fitted constant, a floor, a cap or a hand-set share.
  The pool stays an empirical distribution resampled per draw, exactly as it
  is now;
- it may not alter A1, its category set, its parameters, or its closure;
- it may not change the team-volume layer, which the audit found strong;
- it may not touch QB3, the QB layer, or any participation model;
- it may not consume any sportsbook price, market-implied quantity or
  consensus projection, as a feature, a target, a prior, a calibration
  anchor or a sanity check;
- it may not consume any 2026 outcome. Today's slate is **strictly held
  out** and is used only in the diagnostic replay of section 7, which is
  labelled diagnostic and never counted as evidence.

## 4. Baseline, population and chronology

- **Baseline:** R8 exactly as it stands at `3f5fc82`, unmodified.
- **Walk-forward:** evaluation seasons **2022, 2023, 2024**. For evaluation
  season *Y*, every P4C parameter in both arms is fit on seasons `< Y`,
  excluding 2020 per the existing `MASS_POOL_EXCLUDE_SEASONS`.
- Both arms see the same team-games, the same draw index, the same seed and
  the same A1 budget. The ONLY difference is the `other` construction.
- 2025 and 2026 are not fitted on and not evaluated on.

## 5. Primary metric

**CRPS of the predicted per-player carry distribution against realised
carries**, per player-game, pooled over the evaluation seasons.

Reported alongside, and none of them may substitute for the primary:

- signed bias `projected_mean - actual`, overall and by pregame projected
  rank;
- MAE;
- interval coverage at 50 / 80 / 90;
- randomized PIT, with its histogram, not only its mean;
- **the allocation closure**, which must remain exact: the sum of player
  carries plus `other` equals the A1 `rb` budget in every draw.

Uncertainty: **team-game clustered bootstrap**, cluster counts reported
beside every interval. No interval is quoted without one. Player-games within
a team-game are not independent and are never pooled as though they were.

## 6. Protected metrics, checked on every candidate

A candidate that improves carries while damaging any of these is **rejected**:

- receiving CRPS, targets bias and receiving-yard bias -- these must not move
  at all beyond Monte Carlo noise, per section 2;
- team-volume bias on carries, targets and dropbacks;
- A1 closure: `team_carries - scrambles == rb + kneel + designed_qb + wr +
  te + fringe`, worst per-draw residual;
- draw-artifact integrity, lossless encoding, shared draw index;
- deterministic replay at a fixed seed;
- roster / inactive semantic separation;
- exact player and team identity joins.

## 7. Acceptance criteria, fixed before any result

C1 is preferred over the R8 baseline only if **all** of:

1. pooled carry CRPS improves; **and**
2. the team-game clustered 95% interval on the CRPS difference excludes
   zero; **and**
3. the direction is consistent in **all 3** evaluation seasons; **and**
4. signed carry bias moves toward zero and does not overshoot into
   over-projection; **and**
5. allocation closure remains exact, with a worst per-draw residual of zero;
   **and**
6. every protected metric in section 6 is unchanged within Monte Carlo noise.

If CRPS does not improve but the bias does, the return says **the
denominator correction removes the systematic underprojection without
improving the distribution, and is not adopted on that basis alone.**

## 8. Confirmation limitations

The defect was found by inspecting the 2026 week-1 slate and the fitted
parameters. That inspection selected the finding, so **every result under
this document is EXPLORATORY** and must be labelled so in every artifact.

Specifically:

- the "unmodelled running back" population is a proxy. The production pool
  comes from the depth chart and roster; the historical panel's
  `f_n_prior >= 1` rule is the closest reconstruction available and is not
  the production pool;
- the second defect the OWN-5 audit names -- that `other` is fitted as a
  share and consumed against an unnormalised weight sum -- is REAL and is
  **not** addressed by C1. It is registered separately and deliberately left
  alone here, so that one change is tested at a time;
- nine graded games is not a sample. Today's slate motivates the
  investigation and settles nothing.

## 9. Governance

New component. `PATH_C_STATE` is not edited, R8 parameters are not edited,
A1 is not edited, Q9 is untouched, NFL-1 remains unauthorized, and the
baseline contract file is not modified. Registered before any C1 estimator
exists; its sha256 is to be cited by any module that implements it.
