# Contract 3 — quantile stability, measured on the estimand itself

Written 2026-09-16, **before it is run**. Contracts 1 and 2 and both of their
results are preserved unchanged and neither is retroactively passed.

## Why this is not contract 2 with a different divisor

Both earlier contracts judged a quantile by an **MCSE compared against a
scale borrowed from somewhere else** — the interquartile range. Both failed,
and both failed on the same mechanism: a low-usage player's IQR collapses
toward zero for the same reason his mean does, so a tolerance scaled to it
becomes unreachable. Sione Vaki's rushing yards have an IQR of 2.0 and a p90
near 25.

Replacing IQR with the standard deviation, or with any other convenient
scale, would be the third instance of the same move. **The scale is not the
problem. Asking the question indirectly is.**

## The question, asked directly

> If this forecast were rerun with independent Monte Carlo draws, how far
> would the reported p10 / p25 / p50 / p75 / p90 move?

That is a property of the **empirical quantile as an estimator**, and it can
be measured on the estimator itself rather than inferred from a scale.

### Procedure — continuous quantities

Non-parametric bootstrap of the empirical quantile:

1. From the `n` sealed draws, resample `n` values **with replacement**.
2. Compute the quantile.
3. Repeat `R = 400` times.
4. Report the **standard deviation** of those 400 quantiles. That number is
   the answer to the question above, in the quantity's own units.

The bootstrap distribution of a sample quantile is the standard estimator of
its sampling variability and needs no assumption about the shape of the
underlying distribution — which matters here, because these distributions are
zero-inflated, skewed, and in places multimodal.

### Procedure — discrete quantities

Unchanged in spirit from contract 2, because it was the one quantile
instrument that was sound. For a quantity taking at most `DISCRETE_MAX = 12`
distinct integer values:

- **Batch agreement**: the quantile lands on the same value in at least 19 of
  20 non-overlapping batches; **and**
- **Jump-boundary reporting**: the fraction of the 400 bootstrap replicates
  landing on the modal value is reported whether it passes or fails. A
  quantile sitting astride a jump is a fact about the distribution and the
  reader is told, not shielded.

## Thresholds, in native units, fixed now

A quantile passes when its bootstrap standard deviation is **at or below the
smallest difference a reader would act on** in that metric. These are
judgements about decisions, stated before the data is seen, and they do not
depend on any player's dispersion:

| metric family | threshold |
|---|---|
| yardage — passing, rushing, receiving | **1.0 yard** |
| DraftKings points | **0.25 points** |
| event counts — carries, targets, receptions, attempts, touchdowns | **0.25 events** |
| probabilities | **0.01 absolute** |

Nobody changes a decision on a fifth of a yard or a quarter of a DK point.
These are deliberately tight enough to be demanding and loose enough to be
reachable, and being absolute they do not collapse on a low-usage player.

## Intrinsic instability is REPORTED, never forced to PASS

A quantile can be unstable for a reason no draw count fixes: it sits in a
sparse region, or between two modes. Contract 3 detects this and says so
rather than failing it as though more draws would help.

A quantile is flagged **INTRINSICALLY_UNSTABLE** when, over the 400 bootstrap
replicates, either

- the replicates span **more than 20%** of the full range of the underlying
  draws — the quantile is not localised at all; or
- the density of the sealed draws within ±1 bootstrap sd of the quantile is
  below **25%** of the density at the distribution's mode — the quantile sits
  in a sparse region between denser ones.

Such a quantity is reported as unstable **with its bootstrap sd and the
reason**, and it does **not** count as a failure to be fixed by raising `n`.
It counts as a quantity this board should not publish a point estimate for.

## The rule

Run n ∈ {1000, 2000, 4000, 8000, 16000}. The production draw count is the
smallest n at which every published quantity either **clears its threshold**
or is **reported INTRINSICALLY_UNSTABLE**.

If no n clears, report that, name the binding quantity, and do not extend the
grid or amend this contract.

## What would make contract 3 wrong

- **The thresholds are decision judgements, not measurements.** If a reader
  genuinely acts on half a yard, the yardage threshold is wrong and must be
  re-declared before a rerun, not after one.
- **The instability rule has two constants** — 20% of range and 25% of modal
  density — chosen to catch the sparse-region case without flagging ordinary
  skew. They are the most arguable numbers here and they are named as such.
- **Bootstrap resampling reuses the same draws.** It estimates sampling
  variability from the sample; it cannot detect a bias shared by every draw,
  and it says nothing about whether the distribution is right.
- This is per game board, as before.
