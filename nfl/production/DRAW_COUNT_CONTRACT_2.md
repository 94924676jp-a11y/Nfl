# Draw-count contract 2 — prospective, written before it is run

Written 2026-09-16, **after** contract 1 was run and failed, and **before**
any run is scored against this one. Contract 1 and its result are preserved
unchanged in `DRAW_COUNT_PREDECLARATION.md` and `DRAW_COUNT_RESULT.md`.

**Contract 1 is not retroactively passed and is not amended.** It failed, the
reason is recorded, and that record is the reason this file can be trusted:
a criterion that gets rewritten until it passes is not a criterion.

## Why contract 1 was impossible, in one paragraph

It applied one rule — MCSE ≤ 2% of the interquartile range — to *every*
published quantile, and a rule scaled to the **mean** to every published mean.
Both break on the tail of a roster:

- A quantile of a count supported on a handful of integers is a **step
  function**. Its batch-to-batch spread is a fraction of 1 and **does not
  decay with n**. Measured: `receiving/receptions` p75 held MCSE 0.1141
  against a tolerance of 0.0200 at 8,000 draws **and at 16,000** — doubling
  the draws moved it by 0.0000.
- A tolerance of 1% of the mean, on a mean of 3.5 yards, is a demand for a
  twenty-eighth of a yard. Nobody acts on that, and it costs ~7× the draws.

Neither is a Monte Carlo problem. Both are criterion-design errors.

## The three estimand classes, each with its own rule

The classes are declared by a property of the **published quantity**, not by
who the player is — so a rule cannot be chosen after seeing which players
would fail it.

### Class A — continuous means

Any published mean whose underlying draw takes more than `DISCRETE_MAX = 12`
distinct values.

> **MCSE ≤ 0.02 × sd** of that quantity's own draws.

Scaled to the quantity's own **dispersion**, not its level. A backup
quarterback's 11-yard mean with a 40-yard sd is asked for the same *relative
precision* as a starter's 250-yard mean with a 60-yard sd, which is what
"precisely enough to act on" actually means. It is also scale-free: it does
not change if the metric is reported in yards or points.

### Class B — probabilities

Any published probability: threshold crossings, `p_zero`, made/attempt rates.

> **MCSE ≤ 0.01 absolute.**

Unchanged from contract 1 — it was the one rule that worked, clearing at
8,000 draws and staying clear.

### Class C — discrete quantiles

Any published quantile of a quantity taking at most `DISCRETE_MAX = 12`
distinct integer values.

> **The quantile must land on the same value in at least 19 of 20 batches.**

Not an MCSE at all, because MCSE is the wrong instrument for a step function.
What a reader needs from a discrete quantile is that it is **stable** — that
the p75 of a receiver's receptions is 3 and would still be 3 on a rerun. That
is a statement about agreement across batches, and it *can* be met by raising
n, because more draws make the quantile less likely to sit astride a jump.

A quantity whose quantile genuinely sits on a boundary — 50/50 between 2 and
3 — will fail this and **should**: the honest report is that the board cannot
publish a stable p75 for him, not a number that flips on rerun.

### Class D — continuous quantiles

Any published quantile of a quantity with more than `DISCRETE_MAX` distinct
values.

> **MCSE ≤ 0.02 × IQR**, as in contract 1, which was never the problem for
> these.

## Degenerate rows

A row that is identically zero in every draw has no dispersion and cannot
converge. It is reported `NOT_APPLICABLE` with that reason, never as a pass
and never as a failure.

## The rule

Run n ∈ {1000, 2000, 4000, 8000, 16000}. The **production draw count is the
smallest n at which every class clears for every published quantity of every
player.**

If no n on the grid clears, report that, name the binding quantity and its
class, and **do not extend the grid or amend this contract**. The next
contract, if there is one, is written after that result and does not retitle
this one.

## What would make this contract wrong too

Written now so it can be checked later rather than argued about:

- **A published quantity in none of the four classes.** A joint probability
  over two players, or a correlation, is not covered and would need its own
  rule.
- **`DISCRETE_MAX = 12` is a judgement, not a measurement.** It separates
  "counts" from "yardage" on this board and would need re-examining if a
  metric with 15 distinct values started being published as a quantile.
- **This is per game board.** A sixteen-game slate is sixteen boards; the
  requirement does not change but the runtime budget does.
- **MCSE measures precision, never correctness.** A board converged to four
  decimals on a badly specified distribution is precisely wrong, and no draw
  count repairs that.
