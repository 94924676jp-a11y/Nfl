# The week-1 union, and the appearance decision

Two things happened here and only one of them is the thing I said it was. The
correction comes first.

## 1. A withdrawal

I reported that R8 + 2026 week-1 rows moving Josh Allen DOWN (0.9625 to 0.8449
on a 100% snap share) was **perverse**, and attributed it to the panel's
survivorship filter. **The direction is correct and my reasoning was wrong.**

The survivorship filter is real -- the panel alone runs a 0.9265 week-1 base
rate against a fitted 0.5390 -- and rebuilding on the union construction moves
it to 0.6275, inside the 0.4856-0.7476 range of the seasons R8 was fitted on.
But it does **not** change these players' numbers, and it could not have:
R8's prospective row is built from the player's OWN history, so another
player's row never enters his feature vector. Union and panel agree to four
decimals on 26 of 30 DET-BUF players. The four that move are the three
chart-added rows the panel did not contain at all.

So the population argument explains a train/serve mismatch in the abstract and
explains **none** of the Allen/Cook movement. The movement has a different
cause and the measurement below is what establishes it.

## 2. The construction

`appearance_panel_2026.as_union_frame_rows` builds the week the way every
other week in the R7/R8 frame is built: the observed panel UNION the
point-in-time depth chart, `appeared = 0` for a listed player who took no
offensive snap. The chart is selected at each team's own week-1 kickoff from
the captured 2026 vintage, which spans 2026-09-06T11:29Z to 2026-09-15T12:39Z
and therefore predates every week-1 game.

| | rows | appeared | base rate |
|---|---|---|---|
| panel alone (snap counts) | 422 | 391 | **0.9265** |
| **union (panel + chart)** | **553** | **347** | **0.6275** |
| R7 frame, all week 1 | 4,176 | 2,251 | **0.5390** |

378 from the panel, 175 added by the chart, all 30 teams charted, none without
a lawful chart. Per fitted season, week 1: 2020 **0.7476**, 2021 0.5285, 2022
0.4862, 2023 0.5312, 2024 0.5214, 2025 0.4856. The union's 0.6275 sits inside
that range; the panel's 0.9265 sits 0.19 above its top.

## 3. The decision, on real outcomes

The question is not "does the number move" but **"does giving R8 the current
season's week-1 row make it better?"** That is answerable on the fitted frame
with no 2026 data at all: a training week-2 row ALREADY carries the week-1
row, which is the GSVU analogue, and deleting it -- zeroing `n_cur` and the
current-season quantities -- reproduces the stale frame GSV runs on. Same
rows, same fit, same coefficients, one input removed, scored against what
actually happened. Bootstrap blocked by team, 2,000 resamples.

| season | n | base | Brier WITH | Brier STALE | stale − with | 95% CI |
|---|---|---|---|---|---|---|
| 2022 | 748 | 0.5000 | **0.07745** | 0.08980 | +0.01235 | [+0.00315, +0.02134] |
| 2023 | 705 | 0.5362 | **0.07737** | 0.09517 | +0.01780 | [+0.00871, +0.02747] |
| 2024 | 693 | 0.5368 | **0.07343** | 0.09664 | +0.02321 | [+0.01217, +0.03566] |
| 2025 | 759 | 0.4875 | **0.08375** | 0.10449 | +0.02074 | [+0.00870, +0.03228] |

Log loss agrees in every season: 0.25447/0.30607, 0.25303/0.33242,
0.24382/0.32947, 0.27243/0.34139.

**Four seasons, four wins, every team-blocked interval excluding zero.**

### And the calibration that settles the Allen question

In the fitted frame, a week-2 player who played week 1 at a snap share of 0.60
or more:

| season | n | mean predicted | realised |
|---|---|---|---|
| 2024 | 135 | 0.9563 | **0.9556** |
| 2025 | 136 | 0.9349 | **0.9779** |

So R8 puts such players at 0.93-0.96 and they appear 0.96-0.98 of the time.
**0.8449 is not where R8 puts a healthy full-snap starter.** Josh Allen's
`app_ewma` reads **0.8330** against **0.9983** for a matched 2025 week-2
quarterback, and the arithmetic says why: with a half-life of three games,
`(1 - 0.7937) / (1 - 0.7937)` weighting puts weight 0.7937 on the game before
last, and Allen's is **2025 week 18 -- the league-wide rest week**. One new
game pushes it back a slot; it does not remove it.

That is a THIRD defect, distinct from both the stale frame and the
survivorship filter, and it is **OPEN**: the frame treats a league-wide rest
week as a genuine non-appearance, and the exponential weighting keeps it alive
for several games. It is recorded here and not repaired, because repairing it
means deciding what a rest week IS in the frame, which is a mechanism change
with its own identity.

## 4. What this licenses

**R8 remains the appearance mechanism.** It was never in question against the
frozen challenger -- weeks 2-4 Brier 0.10049 against 0.18146 on 7,709 rows --
and the panel arms that ran the frozen mechanism stay disqualified.

**R8 SHOULD receive the 2026 week-1 rows**, built on the union construction.
That is `V1_CANDIDATE_R9_W1P_GSVU`, one declared flag from GSV, same
coefficients (`appearance_r8.fit` trains on `s < season`, so a 2026 row cannot
enter a 2026 fit and `coef_sha256` is identical with and without).

**What it does not license:** calling the resulting DET-BUF numbers good. The
rest-week contamination above is unrepaired and it is pulling Allen and Cook
down by an amount this file does not estimate.

V2 NOT YET EARNED.
