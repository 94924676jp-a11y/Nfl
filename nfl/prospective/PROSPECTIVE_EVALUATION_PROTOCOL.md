# Prospective evaluation protocol — pre-declared

Written 2026-09-08, **before any eligible 2026 result exists**. The 2026 season
opens 2026-09-09; no forecast has been written under this protocol and no 2026
outcome has been inspected for promotion.

This document is the promotion rulebook. It is fixed now precisely because
fixing it later, with results visible, would make every subsequent promotion
unfalsifiable.

## 1. What 2022–2025 can and cannot do

**2022–2025 are heavily mined.** They selected the month-drift finding, the
choice of CRPS, the rejected mechanisms, the P4C architecture, the RC1
decomposition and the RC2 repair family. Freezing them does not make them a
holdout, and a pre-registration written after inspecting them does not restore
independence.

**They may not confirm or promote any current research candidate.**
Prospective evidence begins **only** with forecasts actually written under the
frozen prospective rule, before their games.

**Week 1 may not be backfilled.** If the model was not genuinely live before a
game, that game produces no eligible forecast — ever. There is no retroactive
entry.

**G0A must be satisfied first.** No forecast written before G0A is discharged
counts toward promotion.

## 2. Definitions — fixed now

| term | definition |
|---|---|
| **eligible forecast** | one artifact passing `nfl/prospective/artifact.validate`: complete, hashed inputs, `retrieved_at ≤ written_at < kickoff`, a declared arm, and `completeness == COMPLETE` |
| **eligible game** | a REG-season game for which at least one eligible forecast exists for every player the protocol requires, and whose outcome has been captured |
| **eligible week** | a week in which at least 90% of its games are eligible; below that the week is reported as `PARTIAL` and is **not** dropped |
| **missing forecast** | no artifact exists for a required player-game. Counted, never imputed |
| **partial player coverage** | an artifact with `completeness == PARTIAL_PLAYER_COVERAGE`. Scored only over the players it actually covers, and the shortfall is reported alongside every metric |
| **late forecast** | `written_at >= kickoff`. **Not eligible, at any margin.** There is no grace period |
| **revised forecast** | a new artifact naming `supersedes`. **The FIRST eligible artifact for a game is the one scored.** A revision is recorded and is not scored, or the protocol would reward late information |
| **source unavailable** | a required capture returned `NOT_PUBLISHED` / `NO_EGRESS`. The forecast may be `REFUSED`; a refusal is a recorded outcome, not a missing one |
| **prediction refusal** | an artifact with `completeness == REFUSED` and a `refusal_codes` list. Counted in the denominator of coverage and excluded from accuracy metrics |

**A refusal is not a free pass.** Refusal rate is reported with every metric
set. A model that refuses the hard games and scores well on the rest has not
performed well, and the two numbers must be read together.

## 3. First admissible forecast

The first forecast written under the frozen prospective rule, for a game whose
kickoff is after G0A is discharged, with `written_at` strictly before that
kickoff, and with every required input capture retrieved at or before
`written_at`.

## 4. Sample floors — fixed now

| purpose | floor |
|---|---|
| any reported metric | **≥ 200 eligible player-game forecasts** |
| any benchmark comparison | **≥ 400** eligible forecasts **and ≥ 8 eligible weeks** |
| any promotion decision | **≥ 800** eligible forecasts **and ≥ 12 eligible weeks** |
| any position-stratified claim | **≥ 200 within that position** |

Below a floor the result is `UNDERPOWERED` and is reported as such. **An
underpowered result is not a small result** — it is not a result.

## 5. Metrics — the full set, always together

CRPS, MAE, RMSE, bias, Pearson r, SD ratio, coverage at 50/80/90/95, mean
interval width, randomized PIT (chi-square and max bin deviation), log score
where the predictive distribution supports it, tail calibration at the 90th and
99th percentiles, and Brier for binary outcomes such as `TD ≥ 1`.

**No single score may be reported alone**, and **calibration never substitutes
for discrimination**. RC1 and RC2 both produced arms that improved one while
damaging the other; the protocol has to make that visible by construction.

## 6. Uncertainty

**All intervals are game-clustered**, 1,000 bootstrap resamples over games.
Player-games in one game share opponent, script and weather. Naive intervals
are forbidden and the reporting layer must refuse to emit one.

Evaluation is **weekly and rolling**: each week reported on its own, plus a
cumulative rolling figure. Neither substitutes for the other.

## 7. Stratification

Position (QB/RB/WR/TE), volume tercile (prior-only), history cohort
(`<4`/`4-9`/`10-24`/`25+`), and role-change cohort. Each stratum carries its own
sample floor from §4.

## 8. Multiplicity

Every metric × stratum × arm combination is a test. The pre-declared family is
fixed in §5 and §7 and **may not be extended after results are seen**.
Promotion claims use a **Holm–Bonferroni** correction across the declared
family. A finding surviving only uncorrected is reported as `EXPLORATORY`.

## 9. Promotion rules

A candidate may be promoted only when **all** hold:

1. it is a registered frozen prospective candidate before its first eligible forecast;
2. its arm is declared and its forecasts were never pooled with another arm;
3. sample floors in §4 are met;
4. it beats the accepted model on **CRPS**, game-clustered, after Holm–Bonferroni;
5. it does not lose more than **0.01** of Pearson r against the accepted model;
6. randomized PIT is not worse;
7. no eligible week shows a `> 5%` CRPS regression that the candidate cannot explain;
8. **the owner makes the decision explicitly.** Nothing here promotes anything by passing.

## 10. Retirement rules

A candidate is retired when it loses on CRPS at the §4 floor after correction,
or when its frozen spec can no longer be executed reproducibly, or when its
inputs become unavailable prospectively. Retirement is recorded, never a silent
removal.

## 11. Season transition

A frozen candidate does not automatically carry into a later season. Carrying
it forward requires re-declaring its inputs are still available and its spec
still executes, and that re-declaration is itself recorded. Cross-season pooling
of prospective evidence requires an explicit owner decision.

## 12. Arms

**A, B and C are never pooled**, in any metric, stratum or week.
`artifact.assert_arms_not_pooled` enforces it, and a test proves that guard is
load-bearing.
