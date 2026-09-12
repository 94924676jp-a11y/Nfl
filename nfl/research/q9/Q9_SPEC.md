# Q9 — target hurdle / zero-opportunity architecture: specification

**Frozen before evaluation. Research only: nothing is promoted, no 2026
fitting, no market input, and the Q8 budget repair appears nowhere in the
headline experiment.**

The question: can player target allocation be improved by explicitly
separating the probability of receiving **zero** targets from the
**positive**-target allocation, while preserving team totals exactly and
without reusing outcome-conditioned information.

---

## 1. The two stages, and the event that is not one of them

```
P(appears)                        production R8, UNCHANGED, upstream
  x  P(targeted | appears)        STAGE 1 -- the hurdle, new
  ->  allocation | targeted       STAGE 2 -- positive-only, exact
```

`P(appears)` and `P(targeted | appears)` are **not collapsed**. Stage 1 is
fitted on appeared player-games only and is a conditional probability; the
marginal zero-target probability a player carries is
`1 - p_appear * p_hurdle`, composed at draw time and never fitted as one
quantity.

## 2. Stage 2 reconciles exactly, and the floor is what makes it a hurdle

A multinomial over the whole roster can hand a "positive" player zero targets,
which would make the hurdle decorative. So:

1. Draw the hurdle: each appearing player clears with probability `p_hurdle`.
2. **Every clearer receives one target.**
3. The remaining `budget - n_clearers` targets are allocated among the
   clearers by multinomial over the **unchanged** baseline share weights.

Team targets therefore reconcile **exactly** on every draw by construction,
and every positive player is genuinely positive.

### The two ways this can fail, both named, both counted

| state | when | what happens |
|---|---|---|
| `HURDLE_NO_CLEARERS` | nobody clears but the budget is positive | the draw degrades to the baseline mechanism — a multinomial over every appearing player's base share. The budget is never dropped and no player is forced active. |
| `HURDLE_MORE_CLEARERS_THAN_BUDGET` | more clearers than there are targets | `budget` of the clearers are chosen **without replacement, weighted by their own hurdle probability**, and receive one target each. This preserves the declared hurdle probabilities in proportion instead of truncating the tail arbitrarily. |

Both are counted on every run and reported per stratum. A fallback that is not
measured is a fallback nobody knows fired.

## 3. What is held fixed

Byte-identical across arms: the **team target budget** (frozen P4B point plus
its residual pool — the Q8 shrink repair is **not** applied), the
**appearance model** (production R8, read from the committed Q6 forward
chain), the **class-level prior**, the **share shrinkage weight**, the
**receiving efficiency** (one catch rate and one per-catch yardage pool per
season), and the **touchdown layer**.

Stage 2's weights are the **same `base` vector the baseline allocates on**.
The only change in the whole pipeline is the hurdle and the one-target floor.

## 4. Stage 1 inputs — pregame only

| feature | source |
|---|---|
| prior target frequency | share of prior appeared games with ≥1 target |
| prior zero-target frequency | its complement, carried explicitly |
| recent participation | EWMA of the prior had-a-target indicator, half-life 3 |
| prior share given positive targeting | mean target share over prior games with ≥1 target |
| prior opportunity depth | count of prior appeared games, capped |
| role class | starter / rotational / fringe, point-in-time |
| depth rank bucket | r1 / r2-3 / r4+ or unlisted, point-in-time |
| position | RB / WR / TE |
| injury designation and practice | under the existing timestamp governance: `stage_a.injuries` keeps only rows whose own `date_modified` precedes kickoff |
| expected team target budget | the frozen P4B point, standardised |

**Refused by name**: current-game realised availability, realised targets,
`weekly_rosters.status`, any market quantity, any 2026 row. The feature-name
list is checked at import against a forbidden-substring list, and the check is
on what this code builds — not on what some upstream file happens to contain.

## 5. Arms

| arm | mechanism |
|---|---|
| `BASELINE` | production R8 target allocation: appearance draw × base share, multinomial over the team budget |
| `Q9_HURDLE` | the same, plus stage 1 and the one-target floor |

## 6. Evaluation, forward-chained 2022–2025

Reported **separately**, as four blocks:

1. **Zero-target probability** — Brier, log loss, calibration in ten bins,
   expected calibration error, predicted against observed zero rate.
2. **Positive-target count distribution** — CRPS, PIT and bias, computed on
   the players who actually took ≥1 target, against the arm's predictive
   distribution conditioned on being positive.
3. **Full marginal player-target distribution** — CRPS and zero-mass
   calibration.
4. **Downstream receiving-yard CRPS**, efficiency held fixed.

### Strata

RB / WR / TE; starter / rotational / fringe; appearance certainty from R8's
own probability (≥0.9 near-certain, ≥0.7 likely, ≥0.4 uncertain, below
doubtful); and **prior opportunity depth** — prior appeared games in bands
0, 1-3, 4-8, 9-16, 17+.

**No stratum used by the decision is defined from the realised target count.**
A realised-volume breakdown is emitted in a section labelled
`diagnostic_not_read_by_the_decision`, and `decide` does not read it.

### Clustering

Players in one team-week share a budget, a simplex and an opponent. The
team-game is the cluster and every paired difference is block-bootstrapped
over whole team-games.

## 7. Decision rule, fixed here

**SUPPORT** requires all four:

* **improved zero-target calibration** — Brier and log loss both improve, and
  the absolute gap between predicted and observed zero rate narrows;
* **no material degradation in positive-target CRPS** — not significantly
  worse on the team-game-clustered bootstrap;
* **improved or non-worse full marginal target CRPS**;
* **exact team reconciliation** — maximum absolute reconciliation error 0 on
  every draw.

**WEAK_SUPPORT** — zero-target calibration improves and nothing above is
significantly worse, but the marginal CRPS does not improve.

**REJECT** — otherwise.

**A gain in receiving-yard CRPS alone is insufficient**, and `decide` enforces
that rather than leaving it to the reader.

If a finding is confined to a subset, the subset is the finding and is
reported as a boundary rather than averaged away.

**Nothing is promoted from this task.**
