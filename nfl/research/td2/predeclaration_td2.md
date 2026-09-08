# Pre-registration — TD2, touchdown recoverability and downstream composition

Written 2026-09-08, **before any TD2 evaluation result was computed or
inspected**. Start HEAD `536fd7a`.

**EXPLORATORY.** 2022–2025 are heavily mined. Nothing here may be promoted.

## 0. The known result that may NOT be used to choose thresholds

TD1 measured conversion at **76.55%** (receiving) and **75.07%** (rushing) of
the oracle CRPS attribution. **That number is already known and may not be used
to set, move or justify any threshold in this file after a result is seen.** It
is the motivation for TD2, not an input to TD2's criteria.

TD1 also recorded the confound TD2 exists to resolve: a perfect game-level
conversion oracle, conditional on realised opportunity, is close to being handed
a rare binary outcome. **A large oracle attribution is not modelability.**

## 1. Estimand — the denominator question, decided on causal grounds

Support measured before writing this (opportunities / TDs / base rate,
2022–2025):

| estimand | opps | TDs | base rate |
|---|---|---|---|
| receiving \| target | 68,411 | 3,124 | 0.04567 |
| receiving \| red-zone target | 8,978 | 2,203 | 0.24538 |
| receiving \| inside-10 target | 4,002 | 1,520 | 0.37981 |
| receiving \| inside-5 target | 1,895 | 903 | 0.47652 |
| receiving \| goal-to-go target | 3,391 | 1,301 | 0.38366 |
| rushing \| carry | 56,974 | 1,978 | 0.03472 |
| rushing \| red-zone carry | 9,949 | 1,719 | 0.17278 |
| rushing \| inside-10 carry | 5,096 | 1,490 | 0.29239 |
| rushing \| inside-5 carry | 2,952 | 1,220 | 0.41328 |
| rushing \| goal-to-go carry | 4,177 | 1,329 | 0.31817 |

All ten have sample support. **The primary estimand is chosen on causal
grounds, fixed now, and NOT on which one predicts best.**

**PRIMARY: `P(TD | opportunity)` — the unconditional per-target and per-carry
rate.** Reason: TD1's accepted identity already carries location as its **own**
component `Z`. Conditioning the conversion estimand on realised red-zone
opportunity would fold part of `Z` into `K` and confound two components the
decomposition deliberately separates. The unconditional rate is also the
quantity that composes directly back into that identity.

**SECONDARY, reported separately and never used to pick a winner:** the four
location-conditioned rates per kind. They answer a different question — *given
that he got a red-zone look, does he convert it?* — and their base rates
(0.25–0.48) make them a materially different statistical problem from the
0.03–0.05 unconditional rate.

**End-zone targets remain UNAVAILABLE** (TD1: `yardline_100` is the line of
scrimmage, not target depth). Not proxied.

**Unit of evaluation: the OPPORTUNITY, not the player-game.** A player-game with
`n` opportunities and `k` touchdowns contributes `n` Bernoulli trials at the
predicted rate. Counts are exact, so trial-level log loss, Brier and AUC are
computed exactly without per-play identity.

## 2. Frame

Evaluation seasons **2022, 2023, 2024, 2025**, walk-forward, fitted on strictly
prior seasons only. Positions **WR, TE, RB** for receiving; **WR, TE, RB, QB**
for rushing. **QB rushing is included**: 7,627 carries and 432 rushing TDs
support it, and designed rushes (1,838 TDs) are kept separate from scrambles
(140 TDs).

Appeared player-games with ≥1 prior appeared game and ≥1 opportunity in the
denominator being scored. Chronology by strict ordinal prefix cut — 1,318
player-ordinal pairs in this frame carry two rows.

## 3. Baselines — deliberately hard to beat

TD conversion may be dominated by base rates, so the pooled baselines are the
real opponent:

| id | baseline |
|---|---|
| `B_league` | league pooled conversion, prior seasons |
| `B_pos` | position pooled |
| `B_loc` | opportunity-location pooled |
| `B_pos_loc` | position × location pooled |

## 4. Closed ladder — five rungs, no more

| id | candidate |
|---|---|
| `L0` | the best pooled baseline |
| `L1` | empirical-Bayes shrinkage of the player's prior rate toward the pool; beta-binomial prior fitted **by method of moments on training seasons only** |
| `L2` | chronology-safe EWMA, half-life 2 over prior appeared games (inherited from Stage 2, not chosen here) |
| `L3` | shrunk EWMA |
| `L4` | one logistic model on already-PIT-safe variables only: position, opportunity-location mix, prior opportunity volume, history bucket |

**No hyperparameter is searched.** No markets, odds, DFS, FTN, 2026 outcomes,
current-game realised information, final injury status, unlicensed data, or
broad feature search.

## 5. Metrics — rare-event appropriate

**Ordinary MAE is not the primary metric.** Reported per arm:

log loss (primary), Brier, **Murphy decomposition of Brier into reliability −
resolution + uncertainty**, calibration table by predicted-probability bin,
base rate, AUC, n, event count, and the **standard deviation of the predicted
probabilities**.

**The shrinkage check is built into the metric set, not bolted on.** A model
that merely pulls every prediction toward the base rate improves reliability
while gaining **no resolution**. **Resolution is therefore the discrimination
test:** a candidate whose log-loss gain comes with no resolution gain over the
pooled baseline is recorded as **shrinkage, not signal**.

**Bootstrap: 1,000 resamples clustered by `game_id`.**

## 6. Persistence test

Measured, not assumed:

- **split-half**: player conversion on odd-indexed prior games against
  even-indexed, opportunity-weighted;
- **year-to-year**: player conversion in season *t* against *t+1*;
- prior-games-to-next-game, chronology-safe;
- split by established vs low-history, WR/TE/RB/QB, receiving vs rushing,
  red-zone vs non-red-zone, high vs low opportunity.

**The same statistics are computed for OPPORTUNITY as for CONVERSION.** The
hypothesis that opportunity persists while conversion does not is **tested, not
assumed**, and the comparison is only meaningful if both are measured the same
way.

## 7. Composition — mandatory gate

Any candidate improving conversion is substituted into the TD1 simulator with
**`V`, `S` and `Z` machinery frozen**. Substitution is **draw-preserving**: the
candidate supplies a rate and the binomial draw structure around it is retained.
A point substitution that collapses dispersion is a defect, and R1 measured
what that costs.

Reported: player TD CRPS, Brier and log score, calibration, bias, **each season
separately**, game-clustered bootstrap, and subgroups.

**A candidate that improves conversion in isolation and worsens composed TD
forecasts is `COMPOSITION_FAILED`, regardless of primitive performance.** RC1's
primitive-reversal finding and R1's composition failure are both binding.

## 8. Recovered oracle opportunity

Computed as the composed CRPS improvement of the best candidate over the
accepted control, divided by TD1's measured conversion-oracle CRPS reduction.

**Permitted wording:** "This model family recovered X% of the measured TD
conversion oracle opportunity."

**Forbidden:** "TD conversion is X% predictable." "Only X% of TDs can be
predicted." "The remaining amount is irreducible." **TD2 cannot establish an
information ceiling and will not claim one.**

## 9. Subgroups

WR, TE, RB, QB rushing; established vs low-history; high vs low opportunity;
red-zone, inside-10, inside-5. **No subgroup discovered post hoc may be
promoted or presented as a finding on its own** — a subgroup result is reported
with its sample size and as exploratory.

## 10. State classification rules — fixed now

Exactly one primary state, separately for receiving and rushing if the evidence
materially differs:

| state | condition |
|---|---|
| `RECOVERABLE_SIGNAL` | best candidate improves log loss by **≥ 1% relative** to the best pooled baseline, **AND** gains Murphy resolution over it, **AND** composed TD CRPS is not worse |
| `SIGNAL_WEAK` | log-loss gain **< 1%**, or a gain with **no** resolution gain (shrinkage rather than signal) |
| `COMPOSITION_FAILED` | primitive gain ≥ 1% with resolution, but composed TD CRPS is **worse** |
| `ESTIMATOR_DEFECT` | a defect in the estimator, not the information, explains the result |
| `DATA_BLOCKED` | the estimand cannot be constructed from authorized data |

## 11. Result-driven changes forbidden

No threshold, estimand, ladder rung, metric, subgroup or eligibility rule above
may change after a result is seen. If something proves unworkable it is
recorded as a defect and reported — the specification is not edited to match the
outcome.

**Seed 20260908, fixed now.**
