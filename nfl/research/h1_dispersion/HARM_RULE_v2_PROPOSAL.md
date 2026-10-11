# Proposal: stratified harm rule v2 (for future protocols only)

Status: **PROPOSAL.** It does not apply to H1 v1.0 or its addendum, and must never be re-applied to data those already
cover. A study adopts it only by naming it in a new pre-registration, committed before any of that study's
evaluation data is computed.

## Why v1.0's point-estimate rule is inadequate

The reviewer's simulation is in `INDEPENDENT_REVIEW_H1.md`, section 4. The v1.0 rule is: no position's MAE worse by
more than 1 %, and no decile's by more than 2 %.

| problem | evidence |
|---|---|
| False-harm rate is uncontrolled | A candidate with zero true effect fails 19-78 %, depending on dataset and weeks |
| Cannot show non-harm | A +1.9 % estimate with SD 5 passes; harm up to about 12 % is consistent with it |
| Vacuous strata | A top-only candidate leaves deciles 1-5 mechanically unchanged |
| Composition drift | Deciles are pooled across positions, so their mix shifts week to week |
| Power at 6 weeks | TE and decile 8-10 standard deviations are 1.5-5 %, as large as the margins |

## Rule v2

For every stratum s (each position; each projection decile **formed within position-week**), compute
d_s = the percentage change in MAE, candidate against incumbent, paired on the same player-weeks.

1. **Non-inferiority (required for acceptance).**
   - The one-sided 95 % upper bound of d_s must be at most the margin: +1 % for a position, +2 % for a decile.
   - The bound comes from a week-block bootstrap with B ≥ 4,000, where each block is one week, all games and
     players together.
   - The bound must be **simultaneous across strata**: use the max-statistic bootstrap, or Holm's method over the
     strata's p-values.
2. **Harm flag (forces REJECT).** Any stratum whose one-sided 95 % lower bound of d_s exceeds 0.
3. **Vacuous strata are declared, not counted.** A stratum the candidate cannot change by construction is listed as
   NOT TESTED and does not count as a pass.
4. **Rank preservation.** The mean within-position-week Spearman correlation with outcomes must not fall by more than
   0.01 (one-sided 95 % bound). Ties the candidate creates are reported.
5. **Sample size is planned in advance.**
   - The pre-registration states the number of weeks needed so that a stratum whose true change is 0 passes
     non-inferiority with at least 80 % probability.
   - It uses the bootstrap SD measured on development data.
   - With fewer weeks, the verdict is **INCONCLUSIVE**, never PASS.
6. **Verdict gaps closed.** A level hypothesis states all three outcomes:
   - confirmed (interval above the threshold);
   - refuted (interval contains the null);
   - **reversed** (interval entirely on the other side).

## Cost

Measured on the harness, at a 1 % margin, TE needs an SD of about 0.5. That is roughly 40 or more weeks of
harness-equivalent volume. A prospective study of 6 weeks therefore cannot pass non-inferiority at TE. Under v2 it
would say INCONCLUSIVE, which is the honest answer.
