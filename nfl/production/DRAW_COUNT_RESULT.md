# Draw-count sweep — the result, under the criterion written first

Sweep run on `V1_CANDIDATE_R9_W1P_G`, DET at BUF, 2026 week 2, five draw
counts. `DRAW_COUNT_PREDECLARATION.md` was written before any of these
existed and is not modified by this file.

## The decision

**No draw count on the grid meets every predeclared tolerance**, and the
binding constraint is the criterion, not the draw count.

| n | quantities checked | failing | degenerate | binding quantity | MCSE vs tol |
|---|---|---|---|---|---|
| 1,000 | 1,382 | 778 | 580 | `qb/pyds@00-0034577` | 1.5808 vs 0.1246 |
| 2,000 | 1,390 | 590 | 572 | `kicking/made_FG50+.p75` | 0.1147 vs 0.0050 |
| 4,000 | 1,394 | 407 | 568 | `receiving/receptions.p90` | 0.1243 vs 0.0200 |
| 8,000 | 1,386 | 284 | 576 | `receiving/receptions@00-0040194.p75` | 0.1141 vs 0.0200 |
| 16,000 | 1,386 | 170 | 576 | `receiving/receptions@00-0040194.p75` | **0.1141** vs 0.0200 |

**Read the last two rows together.** Doubling the draws from 8,000 to 16,000
moved the binding MCSE by **0.0000**. That is the whole finding: the binding
quantity's variability is not Monte Carlo noise and does not decay with n.

## By kind, which separates three different situations

| n | means failing | quantiles failing | probabilities failing |
|---|---|---|---|
| 1,000 | 134 | 496 | 148 |
| 2,000 | 92 | 423 | 75 |
| 4,000 | 71 | 334 | 2 |
| 8,000 | 51 | 233 | **0** |
| 16,000 | 21 | 149 | **0** |

**Probabilities clear at 8,000** and stay clear. They are the one class of
published quantity that meets its predeclared tolerance on this grid.

## Why the quantile tolerance is unreachable, and it is arithmetic

`kicking/made_FG50+` for Jake Bates is supported on {0, 1, 2, 3} with 1,500
of 2,000 draws at zero. Its p25 is 0.0 and its p75 is 0.25, so the IQR is
0.25 and 2% of it is **0.005**. But the quantile of a small-support integer
variable is a **step function**: across batches it jumps between adjacent
support points, so its batch-to-batch spread is a fraction of 1 whatever n
is. Measured MCSE 0.115, unchanged from 8,000 to 16,000.

The predeclaration said "any published quantile, MCSE ≤ 2% of the
interquartile range". It did not distinguish a continuous quantity from a
count that takes four values. That is a defect in the criterion, and the
criterion is what was fixed in advance, so it stands and the run does not
clear. **It was not relaxed to make a draw count pass.**

## Why the mean tolerance also does not clear, which is a different problem

Every failing mean at 16,000 is a **low-usage player**:

| quantity | mean | MCSE | tolerance | ratio |
|---|---|---|---|---|
| `qb/pyds@00-0033949` (Dobbs) | 8.98 | 0.2315 | 0.0898 | 2.6 |
| `qb/pyds@00-0034577` (K. Allen) | 11.22 | 0.2312 | 0.1122 | 2.1 |
| `receiving/receiving_yards@00-0040390` | 7.04 | 0.1363 | 0.0704 | 1.9 |
| `receiving/receiving_yards@00-0039471` | 3.51 | 0.0880 | 0.0500 | 1.8 |

**Not one failing mean has a value of 50 or more.** Every headline number on
the board — Gibbs' rushing yards, Goff's and Allen's passing yards — clears.
What fails is the tail of the roster, where a 1%-relative tolerance on a mean
of 3.5 yards is a demand for a twenty-eighth of a yard. Ratios are 1.3–2.6,
so these would clear at roughly 16,000 × 2.6² ≈ **110,000 draws**.

## What a corrected predeclaration has to say

Written here for the next one, and **not applied retroactively**:

1. **Exempt or re-scale quantiles of small-support integer quantities.** A
   quantile of a variable taking four values is a step function and no draw
   count converges it. Either exclude it or state the tolerance in support
   units ("the p75 must land on the same integer in 19 of 20 batches").
2. **Floor the relative mean tolerance at something a reader can act on.**
   1% of a 3.5-yard mean is 0.035 yards. Nobody makes a decision on a
   twenty-eighth of a yard, and demanding it costs ~7× the draws for numbers
   nobody reads.
3. **Say which players the criterion governs.** A board carries headline rows
   and a long tail; requiring the tail to meet the same relative standard as
   the headline is what makes the whole thing unreachable.

## What the draw count actually buys — reported, not a pass

This is a **separate and smaller claim** than convergence. Median MCSE over
the rows, in the reader's own units:

| n | DK points (top 8, mean 13.6) | QB pass yds (mean 123) | rushing yds (mean 19.3) | receiving yds (mean 34.7) |
|---|---|---|---|---|
| 1,000 | 0.265 | 2.150 | 0.855 | 1.127 |
| 2,000 | 0.194 | 1.654 | 0.530 | 0.786 |
| 4,000 | 0.128 | 0.990 | 0.353 | 0.469 |
| 8,000 | 0.095 | 0.656 | 0.320 | 0.384 |
| 16,000 | **0.066** | **0.486** | **0.192** | **0.232** |

At 1,000 draws a headline DK projection carries about a quarter of a point of
Monte Carlo error and a quarter-point does not change a decision. At 8,000
every published probability meets its predeclared tolerance and DK points are
inside a tenth of a point.

**That is not a convergence claim and must not be quoted as one.** It says
what the error is; the predeclared criterion says what the error had to be,
and it was not met.

## What this does not say

MCSE measures how precisely the model's own answer has been computed. It says
nothing about whether that answer is right. A board converged to four decimal
places on a badly specified distribution is precisely wrong, and no draw count
repairs that.
