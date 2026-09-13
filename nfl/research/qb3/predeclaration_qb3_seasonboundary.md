# QB3-SB pre-registration — the week-1 season-boundary candidate

Written 2026-09-13, **after** the week-1 incumbent audit (`QB3_WEEK1_INCUMBENT_AUDIT.json`,
commit `c6b401a`) and **before any estimator for this candidate is built, run or scored**.

This document does not authorise a change to production. R8 is untouched by it.
Nothing here may be applied to a live board without a further owner decision.

## 0. The baseline is preserved, not edited

The frozen contract `predeclaration_qb3.md`, sha256
`be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e`, remains the
**baseline** and is not modified by this work. `qb3_lib.cell_of` and
`qb3_lib.allocate` are not edited. The candidate is a **new** estimator
evaluated against that baseline, exactly as QB3 itself was evaluated against
B0/B1/B2.

## 1. The demonstrated failure this addresses

Measured, walk-forward, clustered by team (audit artifact, §summaries):

| stratum | n clean | actual P(chart QB1 is primary) | predicted share | bias | 95% CI |
|---|---|---|---|---|---|
| week 1, AGREE | 50 | 1.0000 | 0.8902 | −0.1098 | [−0.1144, −0.1054] |
| week 1, DISAGREE | 20 | 1.0000 | 0.5580 | −0.4420 | [−0.4711, −0.4128] |
| week 1, NO_PREV | 41 | 1.0000 | 0.6389 | −0.3611 | [−0.3846, −0.3347] |
| weeks 2+, DISAGREE | 160 | 0.2500 | 0.5437 | **+0.2918** | [0.2264, 0.3413] |

The sign reverses between week 1 and mid-season in the same cell. The mechanism
is specific: §3B's "last game's primary passer, strictly earlier ordinal"
resolves, at a season boundary, to **week 18** — the game a playoff-bound club
is most likely to rest its starter in. 40.1% of team-seasons end with a
final-game primary who is not that season's modal primary. Tonight's Dallas
room is the cleanest illustration in the 2026 data: Joe Milton III out-dropped
Dak Prescott **13 to 11** in week 18, so Prescott — rank 1 on the chart — fails
`was_prev_primary` and is modelled at 42.1% behind Milton's 52.2%.

## 2. Candidate definition

**QB3-SB.** Identical to QB3 in every respect except the cell definition:

    cell = (rank, was_prev_primary, is_season_opener)

where `rank ∈ {1, 2, 3+}` and `was_prev_primary ∈ {yes, no}` are unchanged from
§4 of the baseline, and `is_season_opener` is the boundary condition in §3.
Pooling of rank 2 with rank 3+ when `was_prev_primary` is yes is retained.

The mechanism of §5 — draw the primary's identity from cell probabilities
normalised across the charted room, resample his share from his cell's
empirical pool, allocate the remainder by cell weight — is **unchanged**.
Closure by construction is unchanged.

**What this candidate may not do**, stated now so a later result cannot be
reinterpreted:

- it may not clip, floor, bound or manually rebalance any share;
- it may not assign the depth-chart QB1 a share of 1.0 by rule, silently or
  otherwise. His share must remain **resampled from an empirical pool**, and
  that pool must retain whatever zero and partial mass the data contains;
- it may not introduce a fitted constant. Every rate stays an empirical cell
  frequency and every share stays a resampled pool, per the baseline's
  discipline;
- it may not consume injury designations, market data, or any forecast-season
  outcome.

## 3. The exact week-1 boundary condition

`is_season_opener` is true for a team-game **iff the strictly-earlier ordinal
that supplies `was_prev_primary` belongs to a different season than the game
being forecast**. It is defined on the ORDINAL GAP, not on `week == 1`, because
the two differ: a team whose week-1 game is postponed, or whose first game of a
season is not week 1, must still be treated as crossing the boundary. The
predicate is computed from the same `bisect` prefix cut the baseline already
uses, so no new data source enters.

Stated as code, to remove ambiguity:

    prev_ord = oo[bisect_left(oo, o) - 1]        # as in qb3_lib.build_frame
    is_season_opener = (prev_ord // 100) != (o // 100)

A team with no strictly-earlier ordinal at all (an expansion club, or the first
season in the panel) has no `was_prev_primary` and is **excluded** from both
arms rather than defaulted, and the exclusion count is reported.

## 4. Training and evaluation partitions

Walk-forward, identical in shape to baseline §7. For evaluation season *Y*,
every rate is estimated on seasons `< Y` only, and `was_prev_primary` uses a
strictly-earlier ordinal prefix cut.

- **Evaluation seasons: 2022, 2023, 2024** (the depth-chart leaves committed to
  this repository stop at 2024; 2021 is retained for fitting only, since a 2021
  evaluation would train on 2020 alone).
- Both arms see exactly the same rows, the same cut, and the same seed.
- The `is_season_opener` stratum is small by construction — roughly 32
  team-games per season — and that is stated here, before scoring, as the
  principal limitation of the design rather than discovered afterwards.

## 5. Primary metric

**CRPS of the predicted `s_dropbacks` distribution against the realised share**,
per QB-game, pooled — the baseline's own primary metric, so the comparison is
like for like. Reported alongside:

- Brier score on `is_primary`;
- mean absolute share error;
- **calibration of the chart QB1's share**: predicted mean against realised
  mean, with bias and its interval, reported separately for
  `is_season_opener` true and false;
- team-closure violation rate (must remain exactly zero; closure is the
  accounting property the layer exists for and a candidate that breaks it is
  rejected outright regardless of CRPS).

Uncertainty: **team-game clustered bootstrap**, as in the baseline. Cluster
counts are reported with every interval, and no interval is quoted without one.

## 6. Secondary downstream metrics

The share is an input to the QB layer, so the candidate is also scored on what
it does downstream, on the same walk-forward folds:

- `qb/att` (attempts), `qb/cmp` (completions), `qb/pyds` (passing yards):
  calibration slope and intercept, bias, MAE, and interval coverage at 50/80/90/95.

These are **secondary and cannot rescue a failed primary**. A candidate that
improves passing-yards calibration while worsening share CRPS is rejected: the
estimand is the share, and improving a downstream quantity by degrading the
thing that produces it is how a model gets tuned toward an answer.

## 7. Replacement and injury handling

Declared now, because it decides which rows count:

- a team-game in which **more than one charted quarterback took a dropback** is
  flagged `replacement_game`. This names what is measured — a box score cannot
  distinguish injury from benching from blowout relief — and does not claim an
  injury occurred;
- every metric is reported **three times**: all rows, `clean` rows, and
  `replacement` rows. No headline number is computed on `clean` alone;
- replacement games are **not excluded** from the primary comparison. Excluding
  them would flatter both arms by removing the hardest cases;
- neither arm receives any injury designation as an input. The candidate is
  pregame-only, exactly as the baseline is.

## 8. Acceptance and rejection criteria, fixed before any result

QB3-SB is preferred over the QB3 baseline only if **all** of:

1. pooled CRPS improves; **and**
2. the team-game clustered 95% interval on the CRPS difference excludes zero;
   **and**
3. the direction is consistent in **all 3** evaluation seasons (the baseline
   required 3 of 4; with only three folds available, unanimity is the
   equivalent bar and is stated now rather than relaxed later); **and**
4. the team-closure violation rate is exactly zero; **and**
5. the `is_season_opener = false` stratum is **not degraded** — its CRPS
   difference interval must not exclude zero in the worse direction. A candidate
   that fixes week 1 by damaging the other seventeen weeks is rejected.

If CRPS does not improve but the week-1 share bias does, the return says
**the boundary term improves week-1 calibration without improving the
distribution, and is not adopted on that basis alone.**

If the week-1 strata are too small to separate the arms, the return says
**the design cannot distinguish them at this sample size**, and names the
sample that would.

## 9. Confirmation limitations — stated plainly

**This cannot be a confirmatory result, and no amount of procedure here makes
it one.**

The defect was found by inspecting 2020–2024. Those seasons selected the
finding, the stratification, and the choice of boundary condition. A
pre-registration written after that inspection does not restore independence,
and freezing the data now does not make it a holdout.

Therefore every result produced under this document is **EXPLORATORY** and must
be labelled so in every artifact and summary. Specifically:

- the week-1 strata are ~20 clean DISAGREE team-games across 16 team clusters
  and ~41 clean NO_PREV across 27. These are small;
- the depth-chart leaves stop at 2024, so no 2025 evaluation fold exists;
- a genuinely confirmatory comparison requires week-1 games not used here —
  which, for a once-a-year event, means **waiting for future seasons**. That is
  the honest cost and it is recorded rather than engineered around.

## 10. Prospective role for 2026

2026 is **not** a fitting season and nothing in 2026 is used to estimate any
rate in either arm.

If QB3-SB meets §8 on the exploratory folds, the proposed role is
**prospective shadow only**: both arms are computed and recorded per week-1
team-game, neither is published, and the comparison accumulates toward a
genuinely out-of-sample record. Promotion into R8 requires a separate owner
decision on evidence that does not exist yet and will not exist this season —
week 1 happens once.

Until then the baseline QB3 remains the production layer, and every QB market
on a week-1 board stays contaminated and inadmissible, which is the state the
4:25 slate and tonight's DAL_NYG board already record.

## 11. Governance

New component. `PATH_C_STATE` is not edited. R8 parameters are not edited. Q9 is
not touched. The baseline contract file is not modified. This document is
registered before any QB3-SB estimator exists, and its sha256 is to be cited by
any module that implements it.
