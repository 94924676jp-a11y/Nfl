# Q8 attribution audit — where the receiving-opportunity error actually is

**Audit only. No repair is built in this document; the repair spec is frozen
separately, after this ranking, and is the smallest one this ranking
justifies.**

Forward-chained 2022–2025. 34,710 scored player-games, 22,521 of them in the
RC2-comparable population. Exact Shapley over all **32** subsets of the five
sources, using the repository's own `qb2_lib.shapley`. Every attribution adds
up to the total movement exactly.

---

## The ranking

| source | kind | receiving-yard **bias** | receiving-yard **CRPS** | player-target **CRPS** |
|---|---|---|---|---|
| **APPEAR** — who was available | realisation | **+2.118 (112.3 %)** | +0.009 (−3.3 %) | −0.006 (6.3 %) |
| **BUDGET** — team target total | realisation | −0.200 (−10.6 %) | **−0.299 (106.9 %)** | **−0.084 (91.5 %)** |
| **SHRINK** — n/(n+k) weight | parameter | −0.029 (−1.6 %) | +0.013 (−4.7 %) | −0.002 (1.8 %) |
| **REDIST** — after an absence | parameter | −0.006 (−0.3 %) | −0.002 (0.6 %) | −0.000 (0.4 %) |
| **CLASS** — class-level prior | parameter | +0.003 (0.2 %) | −0.001 (0.4 %) | +0.000 (−0.0 %) |

Two value functions, two different winners, and **that is the finding** rather
than a problem to resolve by picking one.

**The entire target-share machinery — the class prior, the shrinkage weight
and the redistribution rule — accounts for under 5 % of the movement on every
value function.** The three mechanisms the directive listed as candidates 2, 3
and 5 are measurably not where the error is.

---

## Finding 1 — most of the "bias" is a selection artefact, not a defect

The bias attributed to APPEAR is not a defect in R8's probabilities. It is
what happens when a **marginal** forecast is scored on a population **selected
by the outcome**: the forecast averages over draws in which the player did not
play, the evaluation keeps only games in which he did, and the difference is
mechanical.

The proof is in the two populations, same model, same draws:

| population | baseline receiving-yard bias |
|---|---|
| appeared players with prior history (RC2/Q7's rule) | **−1.998** |
| the whole union frame it actually forecasts | **+0.139** |

The model is very nearly unbiased on the population it forecasts. It looks
biased by two yards a game only on the sub-population the outcome selects.

This project's own governing rule names the error class: *"Define defects
against predictions, never against realised outcomes. Conditioning on the
outcome manufactures fake defects for any forecaster, including a perfect
one."* A substantial part of the receiving-yard bias RC2 confirmed and Q7
localised upstream is that.

It does not make RC2 wrong — RC2 measured what it measured, on a declared
population. It changes what "fix the bias" can mean: on the forecast
population there is little bias left to fix, and a repair aimed at the
appeared-only bias would be fitting an artefact of the scoring rule.

## Finding 2 — the genuine headroom is the team target budget

BUDGET carries **91.5 %** of the player-target CRPS movement and **106.9 %**
of the receiving-yard CRPS movement. CRPS is a proper score and is not
vulnerable to the selection artefact above, which is why it is the value
function the repair is chosen on.

The budget's own forward-chained calibration:

| season | estimator | bias | RMSE ÷ SD | cov50 | cov90 | **slope** | r |
|---|---|---|---|---|---|---|---|
| 2022 | coach_prior | +1.122 | 0.992 | 0.489 | 0.886 | **0.814** | 0.353 |
| 2023 | ewma | −0.038 | 0.913 | 0.517 | 0.930 | **0.365** | 0.175 |
| 2024 | ewma | −0.100 | 0.966 | 0.509 | 0.915 | **0.490** | 0.219 |
| 2025 | ewma | +0.594 | 0.947 | 0.511 | 0.903 | **0.597** | 0.270 |

Width is well calibrated and the level is nearly unbiased. **The calibration
slope is 0.37–0.81, below 1 in every season.** The point estimate is spread
too widely for the correlation it actually carries — the classic
over-confident conditional mean, and the one thing here that a single
estimated parameter can fix.

## Finding 3 — the shrinkage weight is badly set and it does not matter

The fitted k is 0.75–0.84 while the evaluation-season-optimal k is **4.0** in
every season: the share model trusts a player's own short history about five
times more than it should. Correcting it buys **1.8 %** of the target-CRPS
movement. Both facts are worth recording — a badly-set constant that costs
almost nothing is a different problem from one that costs a lot, and only the
second is worth a repair.

---

## One thing I checked because it would have invented the result

The first version of this audit handed every simulation draw the **same
integer team-target budget** — a point, with no spread. A budget with no
spread under-disperses every player's target count, inflates their CRPS, and
then hands the whole of that inflation to the BUDGET oracle when it is
removed. The contribution would have been a property of my harness rather than
of the system.

Rebuilt so the budget carries the residual pool P4B draws it with, the ranking
is unchanged — BUDGET 91.5 % of target-CRPS movement against 96.9 % before —
so the finding survives, and it survives for a stated reason rather than by
luck.

---

## What this licenses, and what it forbids

**Forbidden by the ranking:** any repair to the class-level prior, the
player-level shrinkage weight, or the redistribution rule. All three are
measured at under 5 % of the movement, and two of them at under 1 %.

**Out of bounds by directive:** the appearance mechanism, fixed to production
R8. The audit's largest bias source is therefore one this work may not touch —
and, per Finding 1, largely should not want to.

**What is left, and what the repair spec takes:** the team target budget's
conditional mean, one estimated parameter, chosen on CRPS.

## Method note

REALISATION oracles (BUDGET, APPEAR) hand the model a game-level fact it would
have had to predict. PARAMETER oracles (CLASS, SHRINK, REDIST) hand it the
right population value as an evaluation-season aggregate, never that
team-week's own answer. The two answer different questions — "how much comes
from not knowing this game" against "how much comes from estimating this
quantity wrong" — and every row of `Q8_ATTRIBUTION_AUDIT.json` carries which
kind it is.
