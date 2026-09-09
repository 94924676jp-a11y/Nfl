# QB3 finding — the QB dropback allocation

Pre-registration sha256
`be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e`, committed
before any estimator was built, run or scored.

**EXPLORATORY.** 2022–2024 are development seasons. Nothing is promoted and
`PATH_C_STATE` is not edited.

## Result

Walk-forward, 3,851 QB-games over 3 evaluation folds. CRPS of the predicted
share distribution against the realised share, lower is better.

| arm | pooled CRPS | closure violation rate |
|---|---|---|
| **QB3 allocation** | **0.0945** | **0.0000** |
| B0 — last game's primary gets 1.0 | 0.1135 | 0.0288 |
| B1 — depth-chart QB1 gets 1.0 | 0.1347 | 0.0080 |
| B2 — **current production**: every rostered QB gets 1.0 | 0.5842 | **0.9853** |

Against the predeclared rule (CRPS improves **and** the team-game clustered
interval excludes zero **and** the direction is consistent):

| contrast | ΔCRPS | clustered CI95 | folds better | rule |
|---|---|---|---|---|
| QB3 − B0 | −0.0190 | [−0.0257, −0.0126] | 3 of 3 | **MET** |
| QB3 − B1 | −0.0402 | [−0.0484, −0.0322] | 3 of 3 | **MET** |
| QB3 − B2 | −0.4897 | [−0.4991, −0.4807] | 3 of 3 | **MET** |

**B2 is the status quo**, and scoring it is the point: current production is
6.2× worse than QB3 on this estimand, and its shares fail to sum to one in
**98.5%** of team-games.

**The predeclared rule asked for 3 of 4 seasons and only 3 folds could run.**
The committed depth-chart leaves stop at 2024; nflverse moved to daily snapshots
with a different schema for 2025 and `stage_a.depth()` declines to half-adapt
it. The 2025 fold is reported as `NO_DEPTH_CHART_LEAF_FOR_SEASON`, not averaged
in as a `nan` — an earlier version of the runner did exactly that and emitted
`nan` closure rates. "3 of 4" is not claimed anywhere.

## Behaviour, which is the actual deliverable

The owner asked for a quantity that behaves correctly for normal starters,
committees, injury uncertainty, midgame replacement and multi-QB packages while
preserving same-draw team accounting. Emitted distributions, 4,000 draws:

| case | mean | P(=1) | P(=0) | p10 | p90 |
|---|---|---|---|---|---|
| rank 1, was last primary (settled starter) | 0.894 | 0.703 | **0.071** | 0.606 | 1.000 |
| rank 2, not last primary (backup) | 0.076 | 0.003 | 0.757 | 0.000 | 0.282 |
| rank 1, NOT last primary (change week) | 0.461 | 0.202 | 0.444 | 0.000 | 1.000 |
| rank 2, WAS last primary (committee) | 0.516 | 0.240 | 0.405 | 0.000 | 1.000 |

Closure is exact in every case: max |Σ − 1| ≤ 2.2e-16.

The settled starter's **P(share = 0) = 0.071** is the event a point forecast
assigns probability zero to, and it happens in 11.9% of games measured over the
whole panel. That single number is most of why B0 loses.

## Calibration of the zero event

Descriptive only. **No equivalence margin was predeclared and no test was run,
so this is not called calibrated.**

| predicted P(share=0) | n | observed |
|---|---|---|
| 0.0–0.1 | 446 | 0.065 |
| 0.4–0.5 | 153 | 0.562 |
| 0.7–0.8 | 557 | 0.844 |

The bucket that matters most — the settled starter — reads 0.065 observed
against ~0.07 predicted. The 0.5–0.7 buckets over-predict but hold n = 13 and
n = 10.

## Week 1 is structurally different, and this is the top follow-up

| | CRPS | depth-QB1 also last game's primary |
|---|---|---|
| week 1 | 0.0934 | **0.469** |
| weeks 2–4 | 0.0639 | 0.965 |
| weeks 5+ | 0.1017 | 0.887 |

In week 1 the "previous game" is the prior season's **week 18**, when starters
commonly rest, so the incumbency feature disagrees with the depth chart on more
than half of teams. The live 2026 week-1 slate shows the same thing: 17 of 32
(0.531).

Week-1 CRPS is *not* worse, because the layer responds by emitting honestly
uncertain distributions and CRPS rewards that. But the uncertainty is partly an
artifact of the feature definition rather than football.

**The obvious repair — define the incumbent as the last game the team's QB1
actually started, or use a season-level incumbent — was NOT implemented.**
Changing a feature after seeing results is tuning, and the pre-registration
fixed `was_prev_primary` as "last game's primary". It is recorded here as the
first candidate for a QB3b pre-registration.

## Effect in production

Applied to the real 2026 week-1 slate, 32 teams × 200 draws, using the captured
depth chart (`2026-09-08T11:56:57Z`, which precedes the earliest week-1 game):

| | before | after |
|---|---|---|
| QB-summed ÷ team dropbacks | **2.170** | **0.947** |
| cells where a team's QBs out-drop their team | 5,930 of 6,400 | **0 of 6,400** |
| QB share of team carries | 0.284 | 0.127 (historical 0.157) |
| cells QB rush opportunity > team carries | 121 | 22 of 6,400 |

The composition applied is the one `W2_QB_PASSING.md` §7.1 already specifies —
`QB dropbacks = team dropbacks × QB dropback share` — so this is the
architecture being implemented, not a frozen model being replaced. QB V1
forecasts the line conditional on being the primary passer; the allocation
supplies the conditioning it never had. Every count scales by one factor, so
rate-type outputs are unchanged.

## What is NOT fixed, and it is the next link

**QB rushing opportunity is still not carved out of the team carry budget.** The
P4C `carries` class allocates RB shares and its OTHER mass is drawn
independently of the QB layer's rush opportunity, so in the tail the two overlap:
22 of 6,400 cells still have the quarterbacks out-rushing their team's carries,
and `qb_rush_contained_in_other` still fails. Scaling rush opportunity by the
dropback factor got the slate mean from 0.284 to 0.127 against a historical
0.157 — closer, but by a different route than the truth.

The fix is an architecture question rather than an estimator one: whether the QB
rush opportunity should be **carved out of team carries before** the RB
allocation runs, so the RB simplex is over the remaining budget. That changes
the carries layer and it is not something to half-implement at the end of a
session.

## Governance

Not promoted. `PATH_C_STATE` untouched. Enters the engine as a REHEARSAL_ONLY
candidate — the same runtime role every other non-QB layer already holds — and
nothing in the engine is publication-eligible while NFL-1 is unauthorised. No
2026 outcome was consumed; the layer's only 2026 inputs are the captured depth
chart and prior-season history.
