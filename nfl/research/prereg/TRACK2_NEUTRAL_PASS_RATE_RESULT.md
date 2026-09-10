# TRACK 2 — NEUTRAL PASS-RATE TRAIT: **H2 REJECTED**

**Date** 2026-09-10 · research only · nothing in the production or capture path
was touched · no candidate created.

Pre-registration: `nfl/research/prereg/PREREG_TRACKS_1_2_3.md` §Track 2.

---

## The hypothesis, as registered

> A point-in-time, shrunk neutral-situation pass-rate trait improves prospective
> prediction of the team pass/run split beyond the existing `coach_prior`,
> without changing the total-play distribution.

## The answer

**It does not.** Pooled over four forward-chained held-out seasons the trait
adds **0.00001** MAE against a base MAE of **0.07994** — three orders of
magnitude below the error it was meant to reduce — and the incremental
coefficient **flips sign** from season to season.

---

## What was built

`play_by_play_{2020..2025}` from the nflverse release, 295,000 offensive plays.
**Neutral was declared before the data was inspected**: early down (1st or 2nd),
first three quarters, outside the last two minutes of the half, score within one
possession (|differential| ≤ 8). Those are in-game states of a **past** game;
the resulting trait is attached to the team and consumed only for a **later**
game.

3,385 team-games carry neutral plays, median **24** per team-game. Neutral pass
rate: mean **0.4916**, sd **0.1144** — close to W5's 0.5167 / 0.1074 under its
own slightly different definition.

**The estimand is the SPLIT, never the level.** `team_off_snaps` is the
denominator on both sides and is never predicted, because W5 measured plays per
game at ICC **0.000** and drives per team-game at split-half **0.001**. A gain on
total plays would be measuring something this project has already refused. Split
mean 0.5714, sd 0.1011 over 3,229 team-games.

**Shrinkage is estimated, not chosen.** `k` = within-team over between-team
variance of the neutral rate, re-estimated at each forecast cut from strictly
earlier seasons: **3.27 – 3.90 games**. Both mapping slopes are OLS fits on
strictly prior seasons only.

---

## Forward-chained result

Fitted on seasons strictly earlier than the evaluation season.

| season | n | k | b | b₂ | league_mean MAE | **coach_prior MAE** | neutral_only MAE | **coach+neutral MAE** |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 2022 | 542 | 3.73 | 0.596 | **+0.034** | 0.08541 | 0.08334 | 0.08225 | 0.08332 |
| 2023 | 544 | 3.27 | 0.611 | **+0.062** | 0.07846 | 0.07681 | 0.07841 | 0.07706 |
| 2024 | 544 | 3.69 | 0.527 | **−0.048** | 0.08113 | 0.08106 | 0.08223 | 0.08095 |
| 2025 | 543 | 3.90 | 0.446 | **−0.095** | 0.07900 | 0.07857 | 0.07945 | 0.07841 |
| **pooled** | 2,173 | — | — | — | **0.08100** | **0.07995** | 0.08059 | **0.07994** |

Pooled bias: league_mean +0.00628, coach_prior +0.00223, neutral_only +0.00622,
coach+neutral +0.00229.

**`b` is positive and stable (0.45 – 0.61): the neutral rate genuinely carries
information about the split.** **`b₂` is not: +0.034, +0.062, −0.048, −0.095.**
The slope of the `coach_prior` *residual* on the neutral deviation collapses
toward zero and changes sign season to season. A coefficient that flips sign is
not a trait; it is noise fitted to a sample.

The reading is that the neutral rate is **real but redundant**: `coach_prior`
already contains what it knows. W5's 0.532 split-half measured the trait's
**repeatability**, which is a different property from **incremental value over
what production already uses**, and the two were never the same claim.

---

## Stratification — no subgroup pays

| stratum | n | coach_prior MAE | + neutral | delta |
|---|--:|--:|--:|--:|
| all | 2,173 | 0.07994 | 0.07993 | +0.00001 |
| early season, weeks 1–4 | 512 | 0.08106 | 0.08099 | +0.00008 |
| mid season, weeks 5–9 | 578 | 0.08090 | 0.08086 | +0.00004 |
| late season, weeks 10+ | 1,083 | 0.07890 | 0.07893 | **−0.00004** |
| **coach changed from last season** | 525 | 0.08126 | 0.08123 | +0.00003 |
| coach continuous | 1,648 | 0.07952 | 0.07952 | +0.00001 |
| lowest quintile of neutral rate | 435 | 0.08063 | 0.08066 | **−0.00003** |
| highest quintile of neutral rate | 435 | 0.07429 | 0.07425 | +0.00005 |

Every delta is within ±0.00008. The coach-change stratum is where the trait
should have been most useful — a new play-caller is exactly the case
`GAP-PLAYCALLER` says `coach_prior` lags — and it pays **+0.00003** there.

---

## What this does and does not settle

**Settled.** A shrunk neutral pass-rate prior does not improve the team pass/run
split beyond `coach_prior` on unseen seasons, in aggregate or in any stratum
tested. It does not warrant a candidate configuration.

**Not settled, and not claimed.** Whether a neutral tendency has value as the
**policy baseline inside a game-state simulation** —
`neutral tendency + simulated state response → play-call probability` — is a
different question with a different estimand, and this result does not answer
it. What it does do is remove the cheapest reason to expect Track 1 to pay: if
the trait carries no incremental information about the *unconditional* split,
the case for Track 1 now rests entirely on the *conditional* response, which is
where its pre-registration already put it.

**One thing this strengthens.** `coach_prior` beats the league mean by only
0.00105 MAE (1.3%). The whole family of team-level split predictors is
operating in a narrow band, which is consistent with P4B's original finding that
team volume is close to unforecastable and is worth remembering before funding
further work at this node.

---

## Registry

Recorded in `nfl/NFL_FEATURE_REGISTRY.md` under REJECTED, beside the W5
reliability measurement, so the next reader sees that a reliable trait was
tested for incremental value and did not pay.
