# Q8 repair specification — the team target budget's conditional mean

**Frozen before evaluation, after the attribution audit and because of it.
Research only: nothing is promoted.**

## What the audit licenses

`Q8_ATTRIBUTION_AUDIT.md` ranks five sources by exact Shapley over 32 oracle
subsets. The class-level prior, the player-level shrinkage weight and the
redistribution rule together carry **under 5 %** of the movement on every value
function, so none is repaired. The appearance channel carries the bias and is
fixed to production R8 by directive. The **team target budget** carries
**91.5 %** of the player-target CRPS movement and **106.9 %** of the
receiving-yard CRPS movement, and that is the only source both material and in
bounds.

## The one change

The budget's width is well calibrated (RMSE ÷ SD 0.91–0.99, 50 % intervals
covering 0.489–0.517) and its level is nearly unbiased. Its **calibration
slope is below 1 in every season** — 0.814, 0.365, 0.490, 0.597 — so the point
estimate is spread more widely than the correlation it carries supports.

```
p' = m + beta * (p - m)
```

`p` is the frozen P4B point estimate, `m` the training league mean, and `beta`
the ordinary-least-squares slope of realised team targets on `p`, **fitted on
seasons strictly before the one being forecast**. One parameter. Estimated,
never chosen, never searched on the evaluation season.

The residual pool is recomputed around `p'` on the same training rows, so the
predictive width stays honest rather than inheriting a spread fitted to a
different centre. Nothing else in the pipeline moves.

### What this is not

It is not a variance calibration, a zero-mass recalibration or a draw-centring
on targets — the three arms RC2 tried and closed. Those acted on **receiving
yards**; this acts on the **team target budget**, a different layer and a
different quantity, and no RC2 arm is reopened.

It is not a change to the P4B team-volume layer. `p` is read from the frozen
research output exactly as production reads it; the shrinkage is a calibration
applied downstream of it inside this pipeline.

### A scope question, stated rather than resolved quietly

The directive says "keep team volume fixed" and also requires "team target
budget error" to be evaluated and the objective to be improving "pregame
target opportunity". `team_targets` is both one of P4B's five team-volume
metrics and the first element of the required decomposition chain. I read the
fixed quantity as the D1 plays/dropbacks layer and the target budget as in
scope, and the repair is deliberately built as a calibration **outside** P4B so
that the frozen layer is untouched either way. If that reading is wrong the
result should be read as a measurement rather than a candidate.

## Arms

| arm | budget |
|---|---|
| `BASELINE` | the frozen P4B point plus its residual pool, as the audit ran it |
| `Q8_BUDGET_SHRINK` | `p'` plus the residual pool recomputed around `p'` |

Everything else is byte-identical: the union frame, production R8 appearance,
the class prior, the shrinkage weight, the redistribution rule, the receiving
efficiency (one catch rate and one per-catch yardage pool per season), the
touchdown layer, the draw count, the seed, and the random stream.

## Metrics

**Primary**: player-target CRPS; target-share calibration (OLS slope and
intercept of realised share on predicted); player-target PIT and interval
coverage at 50/80/90/95; downstream receiving-yard CRPS with efficiency held
fixed.

**Also reported**: team target budget error, zero-target probability against
the realised zero rate, starter dilution, and replacement effects on
team-weeks whose starter was absent.

**Stratified by**: WR / TE / RB; starter / rotational / fringe; target-volume
regime (0, 1-2, 3-5, 6-9, 10+); and appearance certainty from R8's own
probability (≥0.9 near-certain, ≥0.7 likely, ≥0.4 uncertain, below doubtful).

**Clustering**: players in one team-week share a budget, a simplex and an
opponent. The team-game is the cluster and every paired difference is block
bootstrapped over whole team-games.

## Decision rule, fixed here before the numbers are read

* **SUPPORT** — player-target CRPS improves overall and in a majority of
  strata, at least one improvement survives the team-game-clustered bootstrap,
  no stratum is significantly worse, and downstream receiving-yard CRPS does
  not degrade.
* **WEAK_SUPPORT** — player-target CRPS improves overall and nothing is
  significantly worse.
* **REJECT** — otherwise.

A gain in coverage or in bias with no gain in a proper score is not support;
`decide` enforces that rather than leaving it to the reader, because the audit
has already shown that bias on this population is substantially a selection
artefact.

**Nothing is promoted from this task.**
