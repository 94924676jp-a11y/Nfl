# Q9 — target hurdle / zero-opportunity architecture: decision

# SUPPORT

**Research only. Nothing promoted. The Q8 budget repair is absent from this
experiment, no 2026 row was fitted, and no market quantity is an input.**

Forward-chained 2022–2025. 69,420 scored rows across both arms, 34,710
player-games, intervals block-bootstrapped over 2,174 team-games. The only
change in the pipeline is stage 1 and the one-target floor.

---

## The four blocks, reported separately

### 1. Zero-target probability — improved on every measure

| | BASELINE | Q9_HURDLE |
|---|---|---|
| Brier | 0.131861 | **0.130193** |
| log loss | 0.422519 | **0.417337** |
| expected calibration error | 0.02604 | **0.01565** |
| predicted zero rate | 0.4797 | **0.5000** |
| observed zero rate | 0.5044 | 0.5044 |
| **absolute gap** | **0.0247** | **0.0044** |

The ≈2.5-point under-prediction of zero-target probability that Q8 recorded is
**essentially eliminated** — the gap falls to 0.44 points. The paired Brier
difference is −0.00167 with a team-game-clustered CI of [−0.00229, −0.00100],
excluding zero.

### 2. Positive-target count distribution — not materially degraded

CRPS **+0.286 %**, CI [−0.00004, +0.00663] — **spans zero**, so not
significantly worse. The conditional bias improves markedly in the process:
**−0.1343 → +0.0204**.

### 3. Full marginal target distribution — improved, significantly

CRPS **−0.591 %**, CI [−0.00644, −0.00338], excluding zero. Zero-mass
calibration 0.4797 → 0.5000 against an observed 0.5044.

### 4. Downstream receiving yards — neutral, and not read by the rule

CRPS −0.011 %, CI spanning zero. **The decision function never reads this
metric**, because the directive says a yardage gain alone is insufficient and
leaving that to the reader is how a rule gets bent.

---

## Coherence

**Team targets reconcile exactly on every draw in both arms** — maximum
absolute reconciliation error **0.0** across 2,174 team-games per arm.
That is by construction: every clearer receives one target and the remainder
is drawn by multinomial among the clearers.

### The two fallbacks, named, governed and measured

Over **869,600** hurdle draws:

| state | n | rate | what it did |
|---|---|---|---|
| `HURDLE_NO_CLEARERS` | **1** | 0.00012 % | degraded that draw to the baseline mechanism over every appearing player. The budget was not dropped and no player was forced active. |
| `HURDLE_MORE_CLEARERS_THAN_BUDGET` | **2,210** | 0.254 % | drew the budget's worth of clearers without replacement, weighted by each clearer's own hurdle probability, so the declared probabilities are preserved in proportion rather than the tail truncated by an arbitrary rule. |

Neither fallback forces a player active. Both are counted on every run.

---

## It improves in every stratum

Marginal CRPS, by the four required strata — **14 of 14 improve**, 11 of them
significantly:

| stratum | n | ΔCRPS | significant |
|---|---|---|---|
| RB | 10,223 | −0.855 % | yes |
| WR | 15,532 | −0.432 % | yes |
| TE | 8,955 | −0.727 % | yes |
| starter | 6,572 | −0.224 % | no |
| rotational | 13,221 | −0.765 % | yes |
| fringe | 14,917 | −0.782 % | yes |
| near-certain | 14,201 | −0.465 % | yes |
| likely | 7,337 | −0.596 % | yes |
| uncertain | 4,459 | **−1.462 %** | yes |
| doubtful | 8,713 | −0.679 % | yes |
| prior depth 0 | 1,369 | **−7.297 %** | yes |
| prior depth 1-3 | 2,446 | −0.200 % | no |
| prior depth 4-8 | 3,123 | −0.341 % | no |
| prior depth 9-16 | 4,438 | −0.586 % | yes |
| prior depth 17+ | 23,334 | −0.487 % | yes |

The zero-target Brier improves in 14 of 15 cells and the zero-rate gap narrows
in 14 of 15.

**The largest gain is at cold start** — a player with no prior appeared game
improves by 7.3 %, which is where a hurdle should help most and does. The
smallest is the established starter, who was never the problem.

---

## Two things that did not improve, reported rather than buried

**Marginal PIT χ² rises 8,824 → 9,040.** The distribution is better on CRPS
and on zero mass while its rank histogram is marginally worse. Both are true;
the CRPS and zero-mass gains are what the rule reads, and the PIT movement is
recorded because a reader is entitled to it.

**Two cells buck the trend.** Prior depth 4-8 is the one cell where zero-target
Brier does not improve (the gap still narrows). Near-certain appearance is the
one cell where the zero-rate gap does not narrow (the Brier still improves).
Neither is significant and neither is smoothed away.

---

## Why this and not the Q8 repair

Q8 established that the class prior, the shrinkage weight and the
redistribution rule each carry under 5 % of the movement, and that a global
budget repair **helps positive-target players and harms zero-target ones**.
This work does not touch the budget at all. It attacks the zero/positive
boundary directly, which is the axis Q8's strata were split along — without
tuning any gate from those strata, and without reading realised target counts
anywhere the decision can see them.

The realised-volume breakdown is emitted in a block named
`diagnostic_not_read_by_the_decision`, and `decide` does not read it.

---

## Decision

All four conditions in the frozen rule are met:

* zero-target calibration improved — Brier, log loss and the absolute gap all
  move the right way ✓
* positive-target CRPS not significantly worse ✓
* full marginal target CRPS improved, significantly ✓
* exact team reconciliation on every draw ✓

**SUPPORT.** Nothing is promoted.

## What would have to happen before this could be

The forward chain is historical and the gain is under 1 % of marginal CRPS
outside cold start. Three things are missing before promotion could be
discussed: a prospective result on unseen games, a run through the production
interfaces rather than this harness, and a decision on whether a 0.25 %
fallback rate is acceptable operationally. None of that is this task.

## Artifacts

| file | what it is |
|---|---|
| `Q9_SPEC.md` | the specification, frozen before evaluation |
| `Q9_FORWARD_CHAIN_RESULTS.json` | four blocks, every stratum, every interval, both fallback rates |
| `Q9_HURDLE_ROWS.csv.gz` | 69,420 scored rows, both arms |
| `Q9_DIAGNOSTICS.csv` | team-game rows with per-draw reconciliation error |
