# Q7 — efficiency calibration: specification

**Frozen before evaluation. Research only: nothing is promoted, no arm is
refit on 2026, no market quantity is an input, and every fit uses strictly
earlier seasons.**

The question: are the current passing and receiving efficiency distributions
systematically biased or miscalibrated **after conditioning on opportunity**,
without letting volume errors disguise efficiency errors.

---

## 0. What the audit found first, because it fixes the scope

**The QB efficiency mechanism, read out of `qb2_lib.simulate`:**

| quantity | how it is produced |
|---|---|
| completion rate | `rung_rate` — a POINT rate, `w·own + (1-w)·pool`, `w = h_games/(h_games + K)`; completions then `Binomial(attempts, rate)` |
| yards per completion | `_mix` — a per-draw RESAMPLE: with probability `w` one of the QB's own **whole-game** ypc values, otherwise one from the league pool. Passing yards are `completions × ypc_draw` |
| passing TD | `Binomial(completions, ptd_rate)`, the rate shrunk the same way |

Two things follow, and they are the two structural hypotheses this work tests.

* **`K = 4.0` and the half-life `2.0` are inherited constants.** The QB2
  pre-registration says so in terms: "half-life 2 and K = 4 are inherited
  constants", with no grid search. This project's own rule is that a shrinkage
  strength must be estimated or cross-validated. It has not been.
* **A whole-game yards-per-completion is resampled and multiplied by the
  completion count.** A game ypc is an average over however many completions
  that game happened to have; treating it as an exchangeable draw makes the
  predictive spread of *per-completion* yardage independent of how many
  completions there are. Real per-completion means concentrate roughly as
  `1/sqrt(n)`. So the mechanism should over-disperse high-volume games and
  under-disperse low-volume ones — a prediction about **calibration by
  opportunity regime**, which is exactly the split the directive asks for.

**The receiving side is not open ground.** RC2 already reached
`CALIBRATION_DEFECT_CONFIRMED` on receiving yards: bias **+2.1801**, PIT χ²
178.9, 50 % coverage 0.650 against nominal. Its predeclared repair family —
draw-centring, zero-mass recalibration, variance calibration — **all failed**
inside the bounds that protect CRPS and discrimination, and R3 (variance
calibration) failed catastrophically at PIT χ² 12,420.

Q7 therefore does **not** re-run RC2 or propose another repair there. What RC2
did not do is separate the defect into an opportunity part and an efficiency
part: it scored unconditional receiving yards. Conditioning on realised
targets and receptions and re-measuring the same defect is the new question,
and it is the directive's question.

---

## 1. Isolation: opportunity is oracled and identical in every arm

Every arm receives the **realised** attempts, completions, targets and
receptions. There is therefore no volume error at all in the isolated
condition, so no volume error can disguise an efficiency error — the
requirement is met by construction rather than by controlling for it.

Team volume, appearance, participation and allocation are untouched and
identical between arms.

---

## 2. Estimands, and what is refused

Taken from the governed list already enforced in
`nfl/research/postgame.EXACT_ESTIMANDS`.

**Evaluated** (EXACT in the governed list, or a ratio of two EXACT members):

* `qb/cmp` — completion rate given attempts
* `qb/pyds` — passing yards; and yards per completion, per attempt, per dropback
* `qb/ptd` — passing touchdowns given completions
* `receiving/receiving_yards` given `receiving/receptions` and
  `receiving/targets` — yards per reception and yards per target

**Refused by name, citing the governed list rather than a judgement made here:**

* `receiving/receiving_td` and `rushing/rushing_td` —
  `ESTIMAND_UNVERIFIED: touchdown attribution across rushing and receiving has
  not been reconciled with the allocation layer`. Touchdown efficiency is
  therefore evaluated **for passing only**, which is where an exact governed
  estimand exists. That is the directive's condition and the boundary is
  declared rather than stretched.

---

## 3. Arms

All four share the same opportunity, the same random indices where the pools
have the same shape, and the same pooled fallbacks. They differ only in the
efficiency mechanism.

| arm | what changes |
|---|---|
| `BASELINE` | the production mechanism, unchanged: `K = 4.0`, whole-game ypc resampled by the `_mix` switch |
| `Q7_WIDTH` | identical means. The resampled ypc is treated as an **estimate of a per-completion mean** and its dispersion around the QB's own conditional mean is scaled by `sqrt(n_ref / n_cmp)`, so a 30-completion game is predicted more tightly than a 10-completion one. `n_ref` is the training-frame mean completion count, so the scale is 1.0 at the average game and the arm cannot win by being globally wider or globally tighter. |
| `Q7_SHRINK` | identical structure. `K` is **estimated forward-chained** by empirical Bayes — the ratio of within-QB to between-QB variance of the rate, computed on strictly earlier seasons — instead of the inherited 4.0. |
| `Q7_BOTH` | both changes |

---

## 4. The three explicit tests

1. **Mean calibration.** Regress the realisation on the predicted mean, per
   opportunity regime and overall. Report the slope, the intercept and the
   conditional bias. A slope of 1 and an intercept of 0 is calibrated; a slope
   below 1 is over-confident spread in the means, above 1 under-confident.
2. **Variance / width calibration.** PIT, interval coverage at 50/80/90/95,
   and the ratio of realised RMSE to the predictive standard deviation. A
   ratio above 1 is under-dispersion; below 1, over-dispersion. Reported by
   opportunity regime, which is where the whole-game-ypc hypothesis predicts
   the two directions will disagree.
3. **Shrinkage strength.** The estimated `K` per season beside the inherited
   4.0, with what the difference does to CRPS, and the implied own-history
   weight at 1, 3, 8 and 16 prior games.

### A wider interval is not an improvement

The decision rests on **proper scores** — CRPS, and log score where the
distribution supports it. Coverage and PIT are reported as diagnostics. An arm
that raises coverage while worsening CRPS **cannot** reach SUPPORT, and the
decision function enforces that rather than leaving it to the reader.

---

## 5. Required decomposition

For every downstream yardage result:

```
opportunity_error  = E[opportunity] - realised opportunity
efficiency_error   = E[rate] - realised rate
combined_error     = E[yards] - realised yards
same_sign_or_offsetting
```

Reported in **two conditions**, because one of them is vacuous alone:

* **ISOLATED** — opportunity oracled. `opportunity_error` is 0 by
  construction, so `combined_error` equals the efficiency contribution and
  `same_sign_or_offsetting` is recorded as `OPPORTUNITY_ORACLED` rather than
  computed from a zero. Saying that is better than reporting a flag whose
  value is an artefact of the design.
* **COMPOSED** — opportunity from a fixed forward-chained model, byte-identical
  across arms. All four fields are real here, and this is where the offsetting
  question lives.

The Track-1 55.7 % cancellation figure is motivation for asking. It is not
training evidence, not a threshold, and appears in no fit.

---

## 6. Evaluation protocol

Forward-chained by season: evaluation seasons 2022–2025, every arm fitted on
seasons strictly before the one being scored. Training starts at 2020.

**Primary**: CRPS, PIT calibration, interval coverage, conditional bias.
**Secondary**: log score where the distribution supports it — exact for the
discrete counts (completions, passing touchdowns), and **not computed for
continuous yardage**, where a sample-based log score depends on a bandwidth
choice that is itself a free parameter; calibration by opportunity regime; and
calibration by pregame-known sample depth (prior appeared games).

### Opportunity regimes, predeclared

QB attempts: `<20`, `20-29`, `30-39`, `40+`. Receiver targets: `1-2`, `3-5`,
`6-9`, `10+`. Chosen as football-recognisable volume bands before any result
was seen, not by a search.

### Clustering

Quarterbacks and receivers in one game share an opponent, a game script and a
weather. The **game** is the cluster, and every paired difference is
block-bootstrapped over whole games.

---

## 7. Decision rule, fixed before the numbers are read

* **SUPPORT** — a candidate arm improves CRPS overall **and** in a majority of
  opportunity regimes, at least one improvement survives the game-clustered
  bootstrap, no regime is significantly worse on CRPS, and its calibration
  diagnostics do not degrade.
* **WEAK_SUPPORT** — a candidate improves CRPS overall and none is
  significantly worse.
* **REJECT** — otherwise, including any arm whose only gain is coverage.

The **headline arm is `Q7_BOTH`**, fixed here. Every arm is scored against the
rule and every verdict published, so adopting whichever scored best afterwards
is visibly not what happened.

If a finding is confined to a subset — one regime, one position, one season —
the subset is the finding and is reported as a boundary rather than averaged
away.

**Nothing is promoted from this task.**
