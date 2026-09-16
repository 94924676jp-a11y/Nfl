# The 2026 week-1 appearance rows are survivorship-filtered

Found 2026-09-16 while building the fifth arm -- R8 plus the 2026 week-1 rows
-- which is the arm that should have won on the merits. It does not work, and
the reason disqualifies two arms that were already registered.

## The symptom

Adding the observation that a player PLAYED in week 1 lowers his P(appear) for
week 2.

| player | week-1 observation | R8 | R8 + week-1 rows |
|---|---|---|---|
| Josh Allen | appeared, snap share 1.00 | 0.9625 | **0.8449** |
| James Cook | appeared, snap share 0.72 | 0.8381 | **0.6299** |
| Ray Davis | appeared, snap share 0.09 | 0.9716 | 0.8971 |
| Greg Dortch | **did not appear** | 0.6610 | 0.0233 |

Dortch moving down is the model working. A quarterback who took every snap
moving down is not, and it is not a rounding artifact -- Josh Allen loses 11.8
points and James Cook 20.8.

## The cause, measured

`appearance_r7.build_frame` builds each week from the panel **UNION the
point-in-time depth chart**, so a player who dressed and did not play, and a
player who was a healthy scratch, both get a row with `appeared = 0`.
`appearance_panel_2026.build` is derived from the snap-count file alone.

| frame | rows | appeared | did not appear | base rate |
|---|---|---|---|---|
| R7 frame, 2025 week 1 | **762** | 370 | 392 | **0.486** |
| 2026 week-1 panel | **422** | 391 | 31 | **0.927** |

R8 weights the current-season block by `w = n_cur / (n_cur + k)`, k = 1.2176,
and interacts the depth block with `(1 - w)`. At `n_cur = 1` that is w =
0.4509: a single game moves nearly half the weight off the depth listing and
onto current-season participation. Those coefficients were fitted against a
week-1 population that is 48.6% non-appearers. Serving them a population that
is 92.7% appearers changes what `n_cur = 1` MEANS, and the trade goes the wrong
way for a starter whose depth listing was carrying him.

This is a train/serve skew, not a football effect. The 2020-2025 seasons in the
R7 frame hold 700-760 rows per week 1; there are **zero 2026 rows** in it.

## What it disqualifies

The same 422 rows are what `appearance_panel_2026` supplies to the FROZEN
mechanism. So every arm that consumes them carries this:

- `V1_CANDIDATE_R9_W1P_GA` -- the published 8,000-draw board
- `V1_CANDIDATE_R9_W1P_GSP` -- the A2-only ablation arm
- `V1_CANDIDATE_R9_W1P_GSVP` -- the A1+A2 arm

A `GSP - GS` difference would be measuring the filter at least as much as the
panel. **It must not be reported as a panel effect, and no board built on these
arms is a clean candidate.**

`V1_CANDIDATE_R9_W1P_GS` and `V1_CANDIDATE_R9_W1P_GSV` do not touch the panel
and are unaffected.

## What the repair is, and what it is not

It is NOT reweighting, and it is not dropping the injection. It is building the
2026 week-1 rows the way every other week in the frame is built: the observed
panel UNION the point-in-time depth chart, with `appeared = 0` for a listed
player who took no offensive snap. The depth captures for 2026 week 1 exist;
the union construction is `appearance_r7.build_frame`'s and is not reimplemented
here.

Until that exists, the honest statement is that the current-season information
is available and the mechanism that could use it has not been given it in a
form it was fitted for.

## Why this was not caught earlier

The frozen mechanism's `extra_rows` path was checked for whether the injected
rows CHANGED anything -- Josh Allen 0.4188 to 0.8691 -- and they did, in the
direction that looked right. Nobody compared the injected population against
the training population. The check that catches it is one line: the base rate
of the rows you are injecting against the base rate of the rows the model was
fitted on. It is now a test.

V2 NOT YET EARNED.
