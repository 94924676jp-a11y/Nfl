# MKT1 pre-registration — written before SF@LA kickoff

Written 2026-09-10, before the 2026-09-11T00:35:00Z kickoff, against sealed
forecast `e3e2bc8a1f043abf` (draw digest `7f322318d10c55e1…`). **V1 is
unchanged and stays unchanged.** No sportsbook price is a label, a target or a
fit input.

## Hypothesis under test

`PLAYER_OPPORTUNITY_ALLOCATION_TOO_DIFFUSE` — V1 spreads receiving and rushing
opportunity across too many rostered players, so every individual projection is
too low while the team totals are approximately right.

## The competing explanation this must be separated from

`TEAM_VOLUME_TOO_LOW` — the team-level play, dropback, target and carry
forecasts are themselves low, and the player projections inherit it. These
predict **different things about tonight**, and the point of writing this before
the game is that the discriminating quantities are fixed now.

## Predeclared thresholds

Every interval below is the sealed model's own, read from the stored draws.

### A. Team totals — the control

| team | metric | model mean | model p10–p90 |
|---|---|--:|---|
| SF | dropbacks | 36.01 | 26.2 – 47.4 |
| SF | targets | 36.19 | 26.1 – 47.3 |
| SF | carries | 26.59 | 18.1 – 36.7 |
| LA | dropbacks | 33.89 | 24.1 – 44.5 |
| LA | targets | 29.78 | 20.8 – 38.3 |
| LA | carries | 28.35 | 17.8 – 38.6 |

**Supports allocation:** actual team totals land INSIDE these intervals.
**Supports team volume instead:** actual team totals land ABOVE p90.

### B. Top-player share of his own team's pool — the treatment

| player | metric | model mean share | model p10–p90 |
|---|---|--:|---|
| Puka Nacua | targets | 16.0% | 4.3% – 27.3% |
| Deebo Samuel Sr. | targets | 11.9% | 2.6% – 21.2% |
| Kyren Williams | carries | 36.2% | 21.1% – 52.0% |
| Christian McCaffrey | carries | 39.9% | 26.7% – 54.3% |

**Supports:** the realised share lands ABOVE p90 for the lead back and the lead
receiver on at least one team.
**Weakens:** realised shares land inside the model interval — the market was
simply wrong and V1 was fine.

### C. Breadth — the mechanism

| team | model mean distinct players with ≥1 target | model p10–p90 |
|---|--:|---|
| SF | 10.97 | 9 – 13 |
| LA | 11.88 | 9 – 14 |

A real NFL team typically targets seven to nine players in a game.

**Supports:** the realised count lands at or BELOW p10.
**Weakens:** the realised count lands inside the interval.

## Decision rule, fixed in advance

Tonight can produce **a hypothesis, not a finding.** The evaluation ledger's
bar is unchanged: the same directional miss in **at least four distinct
games**. One game with every prediction confirmed raises no refinement
candidate and licenses no change to V1.

Confirmation requires **A inside AND (B above p90 OR C at/below p10)**. Any
other combination is recorded as-is and the hypothesis is left open or
withdrawn, not rescued.

## Uncontrolled factor, declared now

The external snapshot establishes that this game is at the **Melbourne Cricket
Ground, Australia**, kicking off 10:35 local. V1 has no venue, travel or
neutral-site feature of any kind. A single international morning game is a poor
place to read team volume, and that weakens any inference from tonight about
part A specifically. Written down before the result so it cannot be reached for
afterwards if part A is inconvenient.

## What is explicitly not being done

No estimator, prior, parameter or threshold is changed. No price is compared to
a model probability for any purpose other than sizing a disagreement. The
market is evidence that two estimates differ; it is not the truth against which
either is scored. Truth is tonight's play-by-play, and it is scored through the
permanent postgame evaluator against a forecast sealed before the game.
