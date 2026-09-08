# Pre-registration — RC2, receiving baseline calibration repair

Written 2026-09-08, **before any repair was implemented, run, or scored**.
Start HEAD `9d026ab`.

This is an **estimator-repair study**, not a receiving feature search. No new
information enters the model. No 2026 data, no FTN, no market, no DFS, no
opponent information.

## 1. What RC1 left, and what the diagnosis actually found

RC1 recorded two baseline properties: bias **+2.18 yards** and coverage
**0.650 / 0.883 / 0.943 / 0.969** against nominal 0.50 / 0.80 / 0.90 / 0.95, and
described the intervals as "too wide". The diagnosis run before this
pre-registration (`nfl/research/rc2/diagnose.py`, results in
`rc2_diagnosis.json`) shows **that description is wrong in an important way**,
and the correction is recorded here before any repair is chosen.

### 1a. The bias is in target volume, not conversion

| component | predicted | actual | bias | relative |
|---|---|---|---|---|
| `T` targets | 3.2648 | 3.0048 | **+0.2599** | **+8.65%** |
| `R` receptions | 2.2078 | 2.0318 | +0.1759 | +8.66% |
| `V` yards/reception | 10.7400 | 10.6152 | +0.1248 | **+1.18%** |
| `Y` receiving yards | 24.3853 | 22.2052 | **+2.1801** | +9.82% |

`T`'s +8.65% and `V`'s +1.18% compound to +9.9%, against `Y`'s measured +9.8%.
**Essentially all of the receiving-yard bias is over-predicted target volume.**
`R`'s bias is `T`'s bias flowing through an almost unbiased catch rate.

### 1b. The bias is history-length dependent, and it changes sign

A player's own prior-target mean against his next game, 2024:

| prior appeared games | n | own mean | actual | bias |
|---|---|---|---|---|
| 1–3 | 274 | 1.363 | 1.708 | **−0.345** |
| 4–9 | 463 | 1.887 | 2.089 | −0.201 |
| 10–24 | 1,141 | 2.451 | 2.609 | −0.158 |
| **25+** | 3,707 | 3.649 | 3.361 | **+0.287** |

Short histories are **under**-predicted; long histories are **over**-predicted.
This is the same shape P4F found in RB carries, where the accepted reading was
that flattening emerging players is an **estimator defect**, not missing
information.

The position pool is **not** the culprit: pool mean `T` is 4.103 / 2.429 / 2.052
for WR / TE / RB against own-history means of 4.253 / 2.417 / 2.065 and actual
eval means of 4.039 / 2.450 / 1.926. The pool is close to both.

### 1c. The intervals are NOT globally too wide

| | |
|---|---|
| mean within-row predictive SD | 23.5587 |
| between-row SD of conditional means | 18.6274 |
| implied total predictive SD | 30.0331 |
| **actual SD of `Y`** | **29.9366** |
| ratio | **1.0032** |
| within-row SD / residual SD | **0.9851** |

Total predictive dispersion matches the outcome to 0.3%. If anything the
within-row spread is marginally **narrower** than the errors.

### 1d. The central over-coverage is largely an artifact of the zero point mass

`P(Y = 0)` is **0.3293** actual against **0.3004** predicted. **54.9%** of rows
have a predictive 25th percentile of exactly **0**. Splitting the nominal-50%
coverage on that:

| | n | nominal-50% coverage |
|---|---|---|
| rows with `q25 == 0` | 3,064 | **0.7862** |
| rows with `q25 > 0` | 2,521 | **0.4823** |
| rows with `Y > 0` | — | 0.5634 |

Among the `q25 == 0` rows, **49.45%** have `Y = 0` exactly — and an inclusive
interval `[0, hi]` contains `Y = 0` **by construction**. Where the interval has
a strictly positive lower bound, coverage is **0.4823 — slightly UNDER nominal**.

**So the headline over-coverage is a discrete-outcome artifact, not a width
defect.** A repair that squeezed intervals to move 0.650 toward 0.500 would be
attacking an artifact, would make the genuinely-under-covered rows worse, and is
exactly the "arbitrary interval squeezing" §2.3 forbids. **This
pre-registration therefore does not target the coverage headline.**

### 1e. What IS genuinely defective

1. **Mean location**: `T` over-predicted by 8.65%, with a sign flip by history length.
2. **Zero mass**: `P(Y=0)` under-predicted, 0.3004 against 0.3293.
3. **Low-volume dispersion**: within/residual SD ratio **1.124** on low-volume
   rows (nominal-50% coverage 0.771) against **0.996** on high-volume rows
   (coverage 0.537). Genuine over-dispersion, but **confined to low-volume
   players**, not global.

## 2. Frozen design

**Evaluation seasons** 2022–2025, walk-forward, fitted on strictly prior seasons.
**Baseline implementation**: `rc1_sim.simulate` unchanged, frozen as the control.
**Frame, eligibility, chronology, seed (20260908), draws (2000)**: identical to
RC1. No eligibility rule moves.

**All repair parameters are estimated on TRAINING seasons only** (`season < ev`)
and applied to the evaluation season. A repair fitted on the evaluation season
would be a different, invalid study.

## 3. Candidate repair families — closed list, fixed now

Each is mechanism-directed at a defect measured in §1e. Nothing else is tried.

| id | repair | targets defect |
|---|---|---|
| `R0` | control — the frozen baseline, unrepaired | — |
| `R1` | **draw-centring on `T`**: multiply each row's `T` draws by a factor estimated on prior seasons within that row's history-length cohort (`<4`, `4-9`, `10-24`, `25+`), so the cohort's mean predicted `T` matches its mean realised `T`. Mean-shifting, dispersion-preserving. | 1e.1 mean location |
| `R2` | **zero-mass recalibration**: recalibrate the probability of a zero-target game per position and history cohort, on prior seasons only. | 1e.2 zero mass |
| `R3` | **variance calibration on low-volume rows**: scale each row's draws about their own mean by a factor estimated per position and volume tercile on prior seasons, so within-row SD matches residual SD. Mean-preserving by construction. | 1e.3 dispersion |
| `R4` | `R1 + R2 + R3` | all three |

`R1` and `R3` are deliberately orthogonal: `R1` moves the centre and leaves the
spread, `R3` scales the spread about the centre and leaves the mean. Reporting
them separately is what makes it possible to say which defect a change fixed.

**Not allowed, restated:** broad feature search, opponent, market, DFS, 2026,
FTN, PFR-restricted fields, and any threshold changed after a result is seen.

## 4. Scoring — fixed now

**CRPS (primary), MAE, RMSE, bias, Pearson r, SD ratio, mean interval width at
each level, coverage at 50 / 80 / 90 / 95, and randomized PIT.**

**Randomized PIT is required, and the reason is in §1d.** With a point mass at
zero, the ordinary PIT is degenerate — every `Y = 0` maps to the whole interval
`[0, P(Y=0)]`. The randomized PIT draws uniformly inside that interval, which is
the standard correction for a discrete or mixed predictive distribution, and it
is the only diagnostic here that can distinguish a real calibration defect from
the zero-mass artifact. Reported as the deviation of the PIT histogram from
uniform (10 bins, chi-square statistic and the maximum bin deviation).

**Coverage is reported BOTH overall and split on `q25 > 0`**, because §1d shows
the pooled number is not interpretable on its own.

**Bootstrap:** 1,000 resamples clustered by `game_id`.

**Subgroups:** position (WR/TE/RB), volume (high/low at the training-season
median), history cohort (`<4`, `4-9`, `10-24`, `25+`).

## 5. Acceptance criteria — fixed now

A repair is called **`CALIBRATION_REPAIRED_DEVELOPMENT`** only if, pooled over
2022–2025:

1. `|bias|` falls below **1.00 yards** (from 2.18); **and**
2. CRPS does **not** worsen by more than **0.5% relative**; **and**
3. Pearson r does **not** fall by more than **0.01 absolute**; **and**
4. the randomized-PIT chi-square does not increase.

**Criterion 2 and 3 exist because a calibration repair that buys coverage by
destroying discrimination is a loss, and this project has to be able to say so.**
If bias improves while CRPS or r degrade past those bounds, the result is
`CALIBRATION_REPAIR_FAILED` and is reported as such.

If no repair meets (1), the state is `CALIBRATION_DEFECT_CONFIRMED` — the defect
is real and located but not repaired by this family.

**No promotion, under any outcome.** 2022–2025 are heavily mined; the best
possible result here is a development candidate.

## 6. Calibration repair versus predictive discrimination — the distinction

**Calibration repair** changes the shape or location of the predictive
distribution using information already in the model. It cannot, by construction,
add discrimination: it does not tell the model which player will do well, only
how to express what it already believes.

**Predictive discrimination** is the ability to rank player-games, measured by
Pearson r and by the between-row SD of the conditional means.

**A repair that improves calibration must leave discrimination essentially
unchanged.** If r moves materially, the "repair" has smuggled in a
re-weighting of the conditional means and is a model change wearing a
calibration costume. Criterion 3 is what detects that.

## 7. Result-driven changes forbidden

No threshold, family, metric, subgroup, seed or eligibility rule above may
change after a result is seen. If something proves unworkable it is recorded as
a defect and reported — the specification is not edited to match the outcome.
