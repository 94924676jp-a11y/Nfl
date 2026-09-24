# QB allocation: one withdrawn hypothesis, one real reporting defect

**Date:** 2026-09-24
**Data:** run `2fc4e9599f0889f1` (8,000 draws, ATL @ GB) and the preserved
play-by-play corpus for 2024, 2025 and 2026 to date. All offline.
**Status:** SUPERSEDED on the QB-rate question (see below); the
conditionality section stands. Two team-games is not a rate. Nothing here is a
finding about the model's systematic behaviour, and nothing here authorises a
change to the engine.

## What prompted it

Cooper Rush's mean DK points are 9.23 against Jordan Love's 15.25. A starting
NFL quarterback projecting under ten points looked like the systematic
underprojection already on the queue as MR-3.

## Hypothesis 1: the model over-hedges which QB starts. WITHDRAWN as stated.

ATL's QB room carries four non-zero play probabilities summing to 1.232 and
GB's carries two summing to 1.211, so the room is not constrained to one
starter. In the draws, **two or more QBs throw in 21.8% of ATL worlds and
21.1% of GB worlds**. My first reaction was that this must be several times
the real rate.

It is not. Measured from our own play-by-play, counting a team-game as
multi-passer when two or more distinct `passer_player_id` values record a
non-two-point pass attempt:

| season | team-games | >=2 passers |
|---|---|---|
| 2024 | 570 | 21.6% |
| 2025 | 570 | 20.4% |
| 2026 to date | 32 | 15.6% |
| **pooled** | **1,172** | **20.8%** |

Against *any* passer the model is almost exactly right, and the "several
times too high" reading was wrong. Recorded because being wrong quickly is
cheaper than defending it.

## Both hypotheses are SUPERSEDED. The project already measured this.

`nfl/production/qb_v1.py:KNOWN_LIMITATIONS['multi_qb_over_prediction']` holds
the same question answered on **n = 699 team-games**, with the mechanism
named rather than left open:

> prior-only dropback shares are not normalised within a team-game

That is exactly the sum-above-one I set out to investigate. Measured 2024:
multi-QB team-games draw **62.51 team dropbacks against a realised 36.61**,
+25.90, while single-QB team-games draw 34.45 against 36.80, -2.35. Pass-yards
bias is +79.89 on multi-QB team-games against -13.81 on single-QB, and 90%
coverage is 0.794 against 0.961. The recorded policy is *"reported on every
run, never smoothed away"*, which is why `qb_known_limitations` shows FAIL on
every run including this one.

My evidence was two team-games from one game. Everything below this line about
the rate is kept only because the withdrawal is more useful than the deletion;
none of it adds to the existing measurement, and the ticket I opened has been
withdrawn rather than left to invite a re-measurement on worse data.

**One line is worth carrying forward.** The recorded cause says *"no pregame
information in this project resolves it"*. Official game-day inactives are
pregame information that resolves part of it: a quarterback on the inactive
list cannot be the one who starts and is later pulled. That does not fix the
within-team normalisation, which is the real mechanism and applies equally to
two healthy quarterbacks, but it does make tonight's post-inactive rerun the
one lever this project currently holds on the measured bias.

## Superseded detail: the comparison is not like for like

The model's `qb` layer holds quarterbacks only, while `passer_player_id`
includes trick-play throws by receivers and backs. Restricting the historical
count to passers whose roster position is QB needs a position map, and ours
comes from 2026 roster captures, so a 2024 passer absent from a 2026 roster is
dropped. 1,490 passer rows have no position. That biases the restricted rate
downward, so it is reported as a bracket rather than a point:

| treatment of the 1,490 unknown-position passers | team-games | >=2 QB passers |
|---|---|---|
| counted as NON-QB (lower bound) | 1,142 | **13.3%** |
| counted as QB (upper bound) | 1,172 | **16.9%** |

The model's 21.8% and 21.1% sit **above the upper bound**. So there is a
plausible over-hedge of roughly 1.3x to 1.6x -- not the 4x I first assumed,
and not established. Two team-games from one game is a single cluster, which
under this project's own rules is not a rate at all.

**What would establish it:** the model run across many team-games, with
clustering by game and by date, against a position map built from
contemporaneous rosters rather than 2026 ones. That is a pre-registration, not
a patch. Logged as a research ticket, not a fix.

## The real defect is in reporting, and it is not exploratory

The headline table mixes two different quantities and labels them the same.

| QB | tm | P(plays) | DK mean | DK mean given he plays | ratio |
|---|---|---|---|---|---|
| Jordan Love | GB | 0.957 | 15.25 | 15.95 | 1.05x |
| Cooper Rush | ATL | 0.657 | 9.23 | 14.04 | **1.52x** |
| Michael Penix Jr. | ATL | 0.326 | 4.63 | 14.21 | **3.07x** |
| Tyrod Taylor | GB | 0.255 | 1.59 | 6.20 | 3.90x |
| Tua Tagovailoa | ATL | 0.191 | 1.10 | 5.77 | 5.24x |
| Jack Strand | ATL | 0.058 | 0.38 | 6.51 | 17.28x |

Jordan Love's 15.25 is very nearly a conditional number, because he plays in
96% of worlds. Cooper Rush's 9.23 is not: a third of its mass comes from
worlds where he never takes a snap. **Reading the two side by side as though
they measure the same thing is the error**, and it is the reader's error
only because the table invites it.

Cooper Rush is not underprojected. Conditional on playing he is 14.04, a
normal starter's line, and the gap to 9.23 is entirely the starting
uncertainty. The unconditional mean is the right number for a question that
integrates over who starts, and the wrong number for "how good is he if he
plays". Both get asked, and the artifact currently answers only one while
looking like it answers both.

Penix at 4.63 unconditional and 14.21 conditional is the same trap at three
times the severity, and it is the one most likely to mislead: he is the
highest conditional QB projection on the slate and sixth on the unconditional
table.

**The fix is a reporting-layer change and alters no projection.** Any player
table must carry `P(plays)` next to the mean, and should present the
conditional mean beside the unconditional one wherever `P(plays)` is below
some declared threshold. This is the same family as the two methodology fixes
already pending elsewhere in the project: the number is not wrong, the
presentation lets a reader take it for a different number.

## A falsifiable expectation for tonight, recorded before the evidence

When official inactives arrive and the pinned rerun happens:

* If ATL's list rules out Penix and/or Tua, Cooper Rush's `P(plays)` should
  rise toward 1.0 and his unconditional DK mean should move up toward roughly
  14, his current conditional value.
* If his `P(plays)` does **not** move after the inactives are ingested, the
  availability evidence is not reaching the QB allocation. That would be a
  wiring defect, not a modelling one, and it would be visible immediately.
* GB's side should barely move: Love is already at 0.957, so his ceiling for
  movement is about 5%.

This is written down now so it cannot be reinterpreted afterwards. A
prediction recorded after seeing the outcome is not a prediction.
