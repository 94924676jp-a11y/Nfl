# Pre-registration — RC1, receiving conversion oracle decomposition

Written 2026-09-08, **before any evaluation result was computed or inspected**.
Start HEAD `3615bfe`.

Everything below is fixed now. The data/provenance audit in §2 was performed
first and is reported here because the directive requires auditing semantics
before construction; it inspects INPUTS, never evaluation results.

## 1. The question

Once target opportunity is determined, how much receiving-yard uncertainty comes
from **target volume**, from **catch conversion**, and from **yards per
reception**?

This is an **oracle decomposition and recoverability study**. It is not a search
for the best receiving model.

## 2. Data and provenance audit — done first, results fixed here

Source: nflverse `play_by_play_{season}.csv.gz`, 2020–2025, `season_type == REG`.
Licence CC BY 4.0. No FTN. No PFR-restricted field. No market, DFS, or 2026 data.

**Target definition, inherited unchanged** from `nfl/research/p1/build_panel.py`
lines 88–95: `receiver_player_id` set **AND** `pass_attempt == 1`. Two-point
attempts excluded, matching the participation join.

**The sack trap, measured rather than assumed.** Every sack in every season
carries `pass_attempt == 1` — 1,135 / 1,244 / 1,297 / 1,410 / 1,314 / 1,287 for
2020–2025, all of them. A target defined on `pass_attempt` alone would put every
sack into the receiving denominator. What actually keeps them out is that **no
sack carries a `receiver_player_id`: 0 in every season**. This is tested, not
trusted.

**Field audit, 2020–2025 (measured):**

| | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| targets | 17,309 | 18,058 | 17,306 | 17,483 | 17,013 | 16,609 |
| receptions | 11,756 | 12,121 | 11,605 | 11,808 | 11,629 | 11,217 |
| incompletions | 5,553 | 5,937 | 5,701 | 5,675 | 5,384 | 5,392 |
| targets with null `air_yards` | 1 | 1 | 0 | 0 | 0 | 0 |
| receptions with null `receiving_yards` | 0 | 0 | 0 | 0 | 0 | 0 |
| receptions with null `yards_after_catch` | 1 | 1 | 0 | 0 | 0 | 1 |
| `air_yards + yac == receiving_yards` holds | 11,750 | 12,119 | 11,598 | 11,801 | 11,625 | 11,214 |
| identity violations | 5 | 1 | 7 | 7 | 4 | 2 |
| receptions involving a lateral | 8 | 14 | 14 | 8 | 20 | 18 |
| incompletions with non-null `yards_after_catch` | 0 | 0 | 0 | 0 | 0 | 0 |
| incompletions with non-zero `receiving_yards` | 0 | 0 | 0 | 0 | 0 | 0 |

Readings that follow, and that constrain the design:

- **`receiving_yards` and `yards_after_catch` are NULL on incompletions, never
  zero.** A null is recorded as a missing observation and never summed as 0.
  Folding it in would bias any per-target rate downward by exactly the missing
  count.
- **The air-yards / YAC identity holds on 99.94% of receptions.** The
  violations are fumble plays where the receiver fumbled after the catch and
  `receiving_yards` is adjusted. `receiving_yards` is therefore treated as
  authoritative for caught-ball yardage; the AY/YAC split is reported only as a
  secondary descriptive and never used to reconstruct the total.
- **Laterals: 8–20 receptions per season.** Yardage gained by a lateral
  recipient is not attributed through `receiver_player_id`. Recorded as an
  information gap; too small to change a decomposition and not silently ignored.

**`ngs_air_yards` REMAINS QUARANTINED and is not used.** The project recorded it
as all-null; measured here it is more specific than that — `pbp_participation`
carries it on **36.31%** of 2022 plays and **0.00%** of 2023 and 2025 plays. It
dies after 2022. This is a **different field** from pbp's own `air_yards`, which
is populated on essentially every target (see table). Only the latter is used,
and only descriptively.

**Identity check against the accepted panel, already run:** the primitives built
here reproduce `panel_enriched.targets` for **all 25,765** player-games that have
a target, with **0 mismatches** and a total of **103,559 targets** on both sides.

## 3. Frozen design

**Evaluation seasons:** 2022, 2023, 2024, 2025. Fitted on strictly prior seasons
only, walk-forward. 2020–2021 are history only.

**Eligible positions:** WR, TE, RB.

**Frame:** appeared player-games. A player who appeared and drew zero targets has
receiving yards of exactly 0 and **stays in the frame** — that is a real outcome a
receiving-yards forecast faces, and dropping it would condition on the thing being
forecast.

**Minimum history:** at least one prior appeared game (`q_n_prior_app >= 1`),
matching Stage 2's accepted `eligible`.

**Chronology:** every feature is built from **strictly earlier ordinals** using
the `bisect` prefix cut. 1,318 player-ordinal pairs in this frame carry two rows
from mid-week team changes, so "everything appended so far" would let the second
read the first.

**Estimand:** `Y` = receiving yards in a player-game.

**Primitives, defined exactly:**

- `T` = targets (definition above)
- `R` = receptions = targets with `complete_pass == 1`
- `C` = catch conversion = `R / T`, undefined when `T = 0`
- `V` = yards per reception = `Y / R`, undefined when `R = 0`
- `Y` = `sum(receiving_yards)` over that player-game's receptions

**The mechanical identity:** `Y = T × C × V`, with `Y = 0` whenever `T = 0` or
`R = 0`. When `R = 0` the product is zero regardless of `V`, so `V` may take any
value there without affecting the identity.

## 4. Baseline simulator

Chronology-safe, prior-only, **draw-based** — not a point estimate. Per
player-game, `M = 2000` draws:

1. `T` drawn by resampling the player's prior appeared-game target counts,
   shrunk toward the position's prior-season pooled distribution when history is
   short.
2. `R | T` drawn Binomial(`T`, `Ĉ`), `Ĉ` the prior-only shrunk catch rate.
3. `V` drawn by resampling prior-only per-reception yardage, pooled to position
   when the player's own history is short.
4. `Y = Σ` of `R` resampled per-reception yardages.

**Resampling, not a parametric family.** Per-reception yardage is heavy-tailed
and right-skewed; a Gaussian would be rejected by the empirical residuals and
would destroy exactly the tail this study is about. Fixed now so no distribution
is chosen after seeing a fit.

## 5. Oracle substitutions

Realised values substituted in, holding everything else at its drawn value:

| Arm | Perfect |
|---|---|
| A | target count `T` |
| B | catch conversion `C` given targets |
| C | yards per reception `V` given receptions |
| D | B + C (all conversion) |
| E | A + B + C (**mechanical identity check — must reproduce `Y` exactly**) |

**Attribution:** exact **Shapley** over the 2³ = 8 subsets of {T, C, V}, on the
CRPS-reduction scale. Order-invariant by construction, so interaction is not
assigned by substitution order.

**Substitution is draw-preserving.** A component's draws are replaced by a
distribution centred on the oracle value with the arm's own dispersion retained
where dispersion exists. R1 established this the hard way: replacing a draw
matrix with a point estimate destroyed dispersion of CV 0.914 and manufactured
+0.0542 of apparent harm. Asserted by test.

## 6. Scoring

**CRPS (primary), MAE, RMSE, Pearson r, and interval coverage** at 50 / 80 / 90 /
95%. Reported together. **No single score is reported alone**, and CRPS does not
substitute for coverage.

**Bootstrap:** 1,000 resamples, **clustered by `game_id`**. Player-games in the
same game share opponent, game script and weather, so an unclustered interval
would be too narrow. Fixed now.

## 7. Recoverability ladder — small and closed

Exactly these four, no more, no feature search, no hyperparameter tuning:

1. `L0` pooled positional empirical distribution
2. `L1` chronology-safe player shrinkage toward the positional pool
3. `L2` EWMA recency, half-life 2 over prior appeared games
4. `L3` `L1` and `L2` combined

**No hyperparameter is searched.** Half-life 2 is inherited from the accepted
Stage 2 model, not chosen here.

## 8. Composition test — mandatory

Any conversion candidate that improves its own primitive is then substituted
into the receiving-yard simulation with the **target machinery held fixed**, and
judged on downstream receiving-yard CRPS. R1 already demonstrated a better
isolated primitive worsening the composed simulator. A primitive-level win that
does not survive composition is **not** a win and is reported as such.

## 9. Subgroups, defined now

- position: WR / TE / RB
- target volume: **prior-only** mean targets over prior appeared games, split at
  the pooled median computed on TRAINING seasons only
- history: `<4`, `4-9`, `10-24`, `25+` prior appeared games (Stage 2's cohorts)
- role change: prior-only participation step, `up` / `stable` / `down` at
  ±0.10, the P study's definition — computed from strictly prior games, never
  the current one

## 10. Prohibitions

- **No promotion language.** Not "unbiased", "stable", "closed", "correct",
  "successful" or "validated" without a predeclared equivalence margin and a
  two-one-sided test. None is predeclared, so none of those words may appear
  about a result.
- 2022–2025 are **heavily mined**. Every result here is **exploratory /
  diagnostic**, never confirmatory, and must be labelled so in every artifact.
- **A large oracle share does not imply modelability.** Oracle opportunity and
  recoverable predictive signal are reported as separate quantities and never
  conflated.
- Nothing is promoted. P4C, ABC_MPR, Stage 2 `ewma_hl2` and G0A are untouched.
  NFL-1 stays unauthorized.
- No FTN. No PFR-restricted fields. No market, DFS, props, or 2026 data.

## 11. Result-driven changes are forbidden

No threshold, eligibility rule, seed, metric or subgroup definition in this file
may be changed after a result is seen. If something here proves unworkable, the
defect is recorded as a defect and the failure is reported — the specification is
not edited to match the outcome.

**Seed:** 20260908, fixed now.
