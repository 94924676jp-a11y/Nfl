# CS2 stage 2 — preregistration, written before any result was looked at

`current_season_nonqb_panel.stage2_state()` has refused since it was written,
with `PREREGISTRATION_INCOMPLETE`, naming three quantities nobody had declared:
`half_life`, `min_opportunity`, `shrinkage_target`. This document declares how
they will be **estimated from the historical panel**, and fixes the selection
rule before the estimation runs.

They are not being chosen. A constant chosen to make a slate look right is
logged as a bug in this project. They are being measured, on data that does not
include the slate they will be used on.

---

## The question

Stage 6 needs one number per player: the centre of his expected class share
(carries, targets) for a game not yet played. Today it computes that number
from `ewma(history, hl=3.0)` over every prior APPEARED row, shrunk toward a
depth-derived tier mean with weight `n / (n + k)`.

Three things about that are undeclared and one is provably wrong:

1. **`hl = 3.0` was never estimated.** It is a literal in `p4c_build.ewma`.
2. **The ewma weights by POSITION IN THE LIST, not by time.** Observation
   *n-1* gets weight `0.5^(1/3)` whatever the gap. A week-18 row from last
   season and a week-1 row from this one are adjacent in the list and treated
   as adjacent in time.
3. **Opportunity count does not enter the weight at all.** A week in which a
   back had 1 carry counts exactly as much as a week in which he had 22.

And one thing about it is a semantic error the owner named directly: it cannot
see a **season boundary** or a **team change**, because neither is visible in a
flat list of shares.

## Hypotheses, stated before measuring

- **H1 (recency).** Some half-life predicts better than `hl = 3.0`. Direction
  not predicted.
- **H2 (season boundary).** A decay applied ACROSS a season boundary, in
  addition to the per-observation decay, predicts better than none. Predicted
  direction: an extra discount helps, because an off-season is a larger
  discontinuity than a bye week.
- **H3 (team change).** A discount applied when the observation was recorded at
  a DIFFERENT club than the one being forecast predicts better than none.
  Predicted direction: a discount helps, because workload share is a property
  of a player in a depth chart, not of the player alone.
- **H4 (opportunity weighting).** Weighting an observation by its own
  opportunity count predicts better than weighting every appeared row equally.
  Predicted direction: helps.
- **H5 (shrinkage target).** Of {positional mean, depth-tier mean, club-room
  mean}, one predicts better than the others. Direction not predicted.

## Design

**Forward-chained, never in-sample.** For each evaluated row at ordinal *t*,
every input comes from rows with `ord < t`. No row contributes to its own
prediction and no later row contributes to an earlier one. This is the same
PIT discipline the production cut enforces, applied to history.

**Evaluation frame.** Seasons 2022–2025, positions RB / WR / TE, rows with
`appeared == 1`. Earlier seasons are used as history for the 2022 rows but are
not themselves scored, so every scored row has a real history behind it.

**Targets.** `s_carries` and `s_targets`, fitted and reported separately. They
are different quantities with different dispersion and there is no reason one
half-life should serve both.

**Loss, predeclared.** Primary: **mean absolute error** on the share. Chosen
before seeing anything because the share distribution is heavily
right-skewed and zero-inflated, so squared error would let a handful of
lead-back rows choose the parameter for everyone. Secondary, reported but not
decisive: RMSE, and the sign of the mean error (bias).

**Clustering.** Rows are not independent — one player-season contributes many,
and one club-week contributes several competing for the same denominator.
Uncertainty on any loss difference is reported with a **bootstrap blocked by
player**, 400 resamples. A parameter difference whose blocked interval covers
zero is reported as NOT DISTINGUISHED and the simpler option is kept.

**Selection rule, fixed now.** For each target independently: take the grid
point with the lowest MAE; then, among all grid points whose blocked interval
overlaps that best point's, take the **simplest** one — fewest active
mechanisms, then the value closest to the existing production behaviour. This
is a deliberate bias toward not changing things without evidence.

## Grid

| Parameter | Values |
|---|---|
| `half_life` (observations) | 1, 2, 3, 4, 6, 8, 12, ∞ (flat mean) |
| `season_boundary_decay` | 1.00 (off), 0.85, 0.70, 0.50 |
| `team_change_discount` | 1.00 (off), 0.75, 0.50, 0.25 |
| `opportunity_exponent` | 0.0 (off), 0.5, 1.0 |
| `shrinkage_target` | positional mean, depth-tier mean, club-room mean |
| `shrinkage_k` | measured per position by the existing `role_prior.build`, not re-fitted here |

`min_opportunity` is **not** on the grid as a hard cut. A threshold invents a
cliff — 2 carries counts fully and 1 counts not at all — that nothing in the
football justifies. The opportunity exponent is the continuous form of the same
idea and is estimated instead. If H4 is not supported, the answer is that
opportunity count does not belong in the weight, and `min_opportunity` is then
declared as **NOT REQUIRED** with that measurement behind it.

## What this preregistration does not do

It does not set the evidence hierarchy between a governed role refusal and a
measured share — that is a governance rule, not an estimate, and it is declared
in `opportunity_centre.py` with its reasoning rather than fitted.

It does not touch absolute level. No scaling factor, no intercept. If the
global underprojection diagnostic changes once current-season evidence is
connected, that is a re-measurement, not a calibration.
