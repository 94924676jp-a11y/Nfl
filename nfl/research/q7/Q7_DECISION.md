# Q7 — efficiency calibration: decision

# REJECT

**The verdict is on the three candidate repairs. The diagnosis is the
deliverable, and it is unambiguous: the efficiency distributions ARE
systematically biased and miscalibrated after conditioning on opportunity.**

Research only. Nothing promoted, no arm refit on 2026, no market quantity an
input, every fit on strictly earlier seasons. Forward-chained 2022–2025,
93,961 scored rows over 2,653 QB-games and 17,323 receiver-games, intervals
block-bootstrapped over 1,087 games.

---

## The isolation

Every arm received the **realised** attempts, completions, targets and
receptions. There is no volume error at all in the isolated condition, so
none can disguise an efficiency error — met by construction, not controlled
for.

---

## Finding 1 — the conditional mean is badly wrong at high volume

`pyds | cmp`, BASELINE, by attempt regime:

| regime | n | bias (yards) | calibration slope | CRPS |
|---|---|---|---|---|
| `<20` | 601 | +0.89 | 1.029 | 10.63 |
| `20-29` | 722 | −3.92 | 0.990 | 24.84 |
| `30-39` | 937 | +4.50 | **0.755** | 27.48 |
| `40+` | 393 | **+19.80** | **0.728** | 32.01 |

A twenty-yard over-prediction in the highest-volume regime, with a slope a
quarter below 1. This is a **mean** defect. None of the three candidate arms
addresses it — `Q7_WIDTH` preserves the mean by construction and `Q7_SHRINK`
moves it by 0.2 yards.

## Finding 2 — the width defect is real, monotone, and exactly as predicted

RMSE ÷ predictive SD (above 1 is under-dispersed, below 1 over-dispersed):

| regime | BASELINE | after `Q7_WIDTH` |
|---|---|---|
| `<20` | **1.460** | 0.847 |
| `20-29` | 0.879 | 0.828 |
| `30-39` | 0.738 | 0.796 |
| `40+` | **0.710** | 0.869 |

The spec predicted this before the run, from the mechanism: a **whole-game**
yards-per-completion is resampled and multiplied by the completion count, so
the predictive spread of per-completion yardage does not depend on how many
completions there are. Low-volume games come out too tight (90 % intervals
cover **0.704**) and high-volume games too loose. The range is a factor of
2.06 and the fix collapses it to 1.09.

## Finding 3 — and flattening it buys nothing on a proper score

This is the whole reason the arms are rejected, and it is the trap the
directive named.

| `pyds\|cmp` regime | ΔCRPS | significant |
|---|---|---|
| `<20` | −0.888 % | no |
| `20-29` | **+0.550 %** | **yes, worse** |
| `30-39` | −0.630 % | yes, better |
| `40+` | +0.242 % | no |
| overall | −0.143 % | **CI spans zero** |

90 % coverage at `<20` went from 0.704 to 0.945 and PIT χ² from 83 to 56.
**CRPS did not move.** A wider interval is not an improvement, the decision
function refuses to treat it as one, and that refusal is what produced REJECT
rather than a soft pass.

## Finding 4 — the inherited shrinkage constant is not costing anything

`K = 4.0` and half-life 2 are, in the QB2 pre-registration's own words,
"inherited constants" with no grid search — a live violation of this project's
rule that a shrinkage strength is estimated or cross-validated. So it was
estimated, forward-chained, by the same within/between-player variance
estimator the role prior and the R8 appearance weight already use:

| | K | weight at 1 game | at 3 | at 8 | at 16 |
|---|---|---|---|---|---|
| inherited | 4.00 | 0.200 | 0.429 | 0.667 | 0.800 |
| estimated, completion rate | 4.74 | 0.174 | 0.387 | 0.628 | 0.771 |
| estimated, yards per completion | 3.32 | 0.232 | 0.475 | 0.707 | 0.828 |

The inherited value sits between the two estimates. `Q7_SHRINK` is
**significantly worse** on `pyds|cmp` (+0.300 %, CI [+0.016, +0.122]). The
constant's provenance is still undocumented and that is worth fixing on paper;
its *value* is not costing measurable accuracy, and saying so is more useful
than replacing it to satisfy a rule.

## Finding 5 — passing-TD efficiency is the worst-calibrated QB quantity

`ptd | cmp`: calibration slope **0.812**, PIT χ² **267**, 50 % intervals
covering **0.794**. Both candidate arms improve its CRPS significantly
(−0.358 %, −0.325 %) — the only estimand where an improvement survives the
game-clustered bootstrap. Part of the coverage excess is the discrete
low-count artefact `qb_v1.KNOWN_LIMITATIONS` already records; the slope is not.

Touchdown efficiency is evaluated **for passing only**.
`receiving/receiving_td` and `rushing/rushing_td` are refused by name, citing
the governed list: *ESTIMAND_UNVERIFIED — touchdown attribution across rushing
and receiving has not been reconciled with the allocation layer.*

---

## Finding 6 — most of RC2's confirmed receiving defect is NOT an efficiency error

This is the new fact, and it is the one that changes what to do next.

RC2 reached `CALIBRATION_DEFECT_CONFIRMED` on receiving yards with a bias of
**+2.1801**, and its entire predeclared repair family failed. RC2 scored
**unconditional** yards. Conditioning on realised opportunity:

| | bias |
|---|---|
| RC2, unconditional receiving yards | **+2.180** |
| Q7, `rec_yds \| targets` | +0.779 |
| Q7, `rec_yds \| rec` | **+0.602** |

**About 72 % of the confirmed bias lives in the opportunity layer, not in
per-reception yardage.** The RC2 repair family was aimed substantially at the
wrong layer, which is a better explanation of why three of its four arms
failed than "the repairs were badly chosen".

What efficiency defect remains is concentrated, not diffuse:

| targets | n | bias | slope | RMSE ÷ SD |
|---|---|---|---|---|
| 1-2 | 7,223 | +0.510 | 0.935 | **1.213** |
| 3-5 | 5,688 | +0.198 | 0.941 | 1.071 |
| 6-9 | 3,301 | +0.849 | 0.917 | 1.061 |
| 10+ | 1,111 | **+2.538** | **0.855** | 1.017 |

The same shape as the QB side: fine in the middle, over-predicting and
slope-deficient at high volume, under-dispersed at low volume. No repair arm
was run here — RC2 closed that family and this work does not reopen it.

Catch rate carries its own problem: `rec | targets` PIT χ² **2,870** with 50 %
intervals covering 0.806. Largely the discrete low-count artefact, but the
magnitude is recorded rather than waved at.

---

## The required decomposition

**ISOLATED** (opportunity oracled): `opportunity_error` is 0 by construction,
so `combined_error` equals the efficiency contribution (+4.150 yards mean) and
`same_sign_or_offsetting` is recorded as `OPPORTUNITY_ORACLED` rather than
computed from a zero.

**COMPOSED** (one fixed opportunity model, byte-identical across arms),
n = 2,653 QB-games:

| | value |
|---|---|
| mean opportunity error | +0.816 attempts |
| mean efficiency error | +0.217 yards/attempt |
| mean combined error | +9.356 yards |
| mean \|opportunity error\| | 8.726 attempts |
| mean \|efficiency error\| | 2.172 yards/attempt |
| mean \|combined error\| | 71.009 yards |
| **offsetting** | **1,351 (50.9 %)** |
| same sign | 1,241 (46.8 %) |
| one component zero | 61 (2.3 %) |

Half of QB passing-yard forecasts have their two components pulling opposite
ways. The Track-1 55.7 % figure motivated asking; it is a different layer and a
different quantity, it is not a threshold here, and it appears in no fit.

**Sample depth** (`pyds|cmp`, BASELINE): cold start carries both defects at
once — 0 prior games, bias +7.21, RMSE ÷ SD 1.364; at 9–16 games, bias +0.95
and 0.762.

---

## Decision

| arm | verdict | estimands improved | regimes improved | significantly worse |
|---|---|---|---|---|
| `Q7_WIDTH` | REJECT | 3/4 | 10/16 | `pyds\|cmp@20-29`, `pyds\|att@20-29` |
| `Q7_SHRINK` | REJECT | 2/4 | 7/16 | `pyds\|cmp` overall |
| `Q7_BOTH` (headline) | **REJECT** | 3/4 | 10/16 | `pyds\|cmp@20-29`, `pyds\|att@20-29` |

The headline arm was fixed in the specification before the run. All three
verdicts are published.

---

## What this says to do next, and what it says not to

**The defect is in the conditional MEAN at high opportunity, not in the
width.** A twenty-yard bias and a 0.73 slope at 40+ attempts will not be fixed
by any change to dispersion, and the width repair — which works, and flattens
a 2.06-fold dispersion spread to 1.09 — bought no proper-score improvement
because it was aimed at the second-order problem.

**The receiving defect is mostly upstream of efficiency.** Any further work on
RC2's confirmed bias should start in the opportunity layer, where roughly 72 %
of it is, rather than in per-reception yardage where the remaining 0.60 lives.

**Do not re-estimate `K`.** It was tested, the estimate brackets the inherited
value, and replacing it is measurably worse on the main yardage estimand. Its
missing provenance is a documentation defect, not an accuracy one.

**Nothing is promoted.**

## Artifacts

| file | what it is |
|---|---|
| `Q7_SPEC.md` | the specification, frozen before evaluation |
| `Q7_FORWARD_CHAIN_RESULTS.json` | every estimand, arm, regime, depth, season and interval |
| `Q7_SCORED_ROWS.csv.gz` | all 93,961 scored rows, so the summary is re-derivable |
| `Q7_DIAGNOSTICS.csv` | 2,653 composed decomposition rows, four fields each |
| `Q7_RAW_PROVENANCE.json` | the six source files, url and sha256 each |
