# How many draws, and why — predeclared BEFORE the sweep is run

Written 2026-09-16, before any draw count above 1,000 had been executed for
DET-BUF. The point of writing it first is that "how many draws" has an
obvious wrong answer — pick a big round number, call it converged — and the
only defence against picking the number that flatters the board is to fix the
criterion before seeing the numbers.

## What is being decided

The smallest `--draws` at which the published quantities are stable enough
that a reader may act on them, for a single game board.

Not: the smallest at which the board "looks the same". A board is a set of
distributions and nearly every summary on it moves with the draw count; the
question is whether it moves by **less than the amount a reader would care
about**.

## The estimand that governs, and why it is not the mean

The board publishes means, medians, p10/p25/p75/p90 and threshold
probabilities. Monte Carlo error on a **mean** falls as `sd/sqrt(n)` and is
the easiest of these; tail quantiles and small threshold probabilities are
harder and converge more slowly. Choosing n on the mean alone would declare
convergence while the p90 of a rushing line was still wandering.

So the criterion is applied to the **hardest** published quantity, not the
easiest, and n is chosen so every one of them clears.

## Predeclared tolerances

Judged against what changes a decision, per published quantity:

| Quantity | Tolerance | Why this number |
|---|---|---|
| Any published **mean** (yards, carries, targets, receptions, DK points) | MCSE ≤ **1%** of the mean, or ≤ 0.05 in absolute units, whichever is looser | A yard on a 100-yard line, or 0.05 of a carry, is below what a reader can act on |
| Any published **quantile** (p10/p25/p75/p90) | MCSE ≤ **2%** of the interquartile range | Quantiles are noisier than means and are read as a band, not a point |
| Any published **probability** (threshold crossings, p_zero) | MCSE ≤ **0.01** absolute | A one-point move in a percentage |

MCSE is estimated by **batch means** with 20 batches, not by the
i.i.d. formula. The draws within a game are NOT independent across players —
they share a team carry budget and a game script — so `sd/sqrt(n)` understates
the error on anything derived jointly. Batch means do not assume
independence across the quantities; they assume only that the batches are
exchangeable, which the seeding protocol delivers by construction.

## The rule

Run n ∈ {1000, 2000, 4000, 8000, 16000}. Choose the **smallest** n at which
every tolerance above is met for every published quantity of every player on
the board. If 16,000 does not clear, report that it does not clear and name
the quantity that fails — do not extend the grid until something passes, and
do not relax a tolerance to make 16,000 work.

## What would make this the wrong decision

Stated in advance so it can be checked later rather than argued about:

- **A quantity not on this list.** If the board later publishes something
  with a harder convergence profile — a joint probability over two players, a
  tail beyond p90 — this predeclaration does not cover it and n must be
  re-chosen against it.
- **A different slate.** These tolerances are per game board. A slate of
  sixteen games is sixteen boards, and the cost scales; the convergence
  requirement does not change but the runtime budget does.
- **The variance itself being wrong.** MCSE says how precisely we have
  computed the model's answer. It says nothing about whether the model's
  answer is right. A board converged to four decimal places on a bad
  distribution is precisely wrong, and no draw count fixes that.
