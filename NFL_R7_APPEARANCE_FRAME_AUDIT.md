# R7 — APPEARANCE / DEPTH REPAIR

**Date** 2026-09-10 · **Branch** `claude/nfl-greenfield-architecture-stsxmk`
**Configuration** `V1_CANDIDATE_R7` · **promoted** `false` ·
**prospective_eligible** `false` · **governance** `REHEARSAL_ONLY`

Evidence: `nfl/research/r7/R7_EVIDENCE.json`.
Sealed run: `nfl/research/r7/sf_la_candidate/` (`f26af9a43f5adaf3`).
Freeze: `nfl/production/FREEZE_V1_R7.json`.

No sportsbook price was used as a label, a fit target or a model input anywhere
in this work. The market appears once, as a benchmark, and is labelled as one.

---

## 0. A correction to the R6 return, first

R6 reported that **`A.depth()` returns an empty dict, so `f_depth` is null on
every row.** That is wrong and the correction changes the diagnosis.

`A.depth()` returns **152,246 entries** when it is called the way production
calls it. The R6 measurement was taken without `stage_inputs()` having run, so
`stage_a.P1` still pointed at `nfl/research/p1`, where the `dc_*.csv` leaves do
not live. Staged, they are all present and hash-verified.

The real defect is worse, because an empty mapping would have been visible.

---

## 1. The depth-plumbing defect, traced end to end

```
raw capture            nfl_vintage/raw/depth_charts.<sha>.csv      501,069 rows
                       dt 2026-03-22 .. 2026-09-06, EPHEMERAL (gitignored)
        |
        v  capture_vintage.py, durability="reduce", strategy newest_dt_slice
durable vintage        nfl/vintage/depth_charts.<sha>.reduced.csv.gz
                       5 blobs, ONE dt each: 09-06, 09-07, 09-08, 09-09, 09-10
        |
        v  the only 2026 consumer before R7
selector               nfl/product/board.py:depth_rank(season, week, teams)
                       ... which uses NEITHER season NOR week
        |
        v  R6 tier fallback, wrapped in `except Exception: dr = {}`
role prior             nfl/production/nonqb/role_prior.assign_tiers

  and, on the historical side, entirely separately:

committed leaves       nfl/research/inputs/dc_2020..2024.csv.gz   hash-verified
        |
        v  stage_a.depth(y_range=range(2020, 2025))
mapping                152,246 entries
        |
        v  stage_a.build
row field              f_depth, non-null on 57,160 of 83,144 panel rows (68.75%)
        |
        X  <-- STOPS HERE
design matrix          49 columns. `f_depth` appears in NEITHER
                       stage_a.featurise NOR p3_features.featurise_p3.
```

**Five distinct losses. Each is named because each needs its own fix.**

**1. Computed, then discarded.** `f_depth` is written onto 68.75% of panel rows
(80.1–88.6% within 2020–2024) and then never featurised. Proof, not assertion:
`featurise_p3` returns a byte-identical 49-element row for `f_depth` = 1, 99 and
`None`, and the literal `f_depth` occurs **zero** times in either featuriser.
`assert_walk_matches_research` compares fourteen features and `f_depth` is not
one of them, so the equivalence check could never have caught it breaking.

**2. The 2025 hole, unreported.** `stage_a.depth` defaults to
`range(2020, 2025)` and `appearance_model.NEEDED` lists no `dc_2025.csv`.
Result: **0 of 13,813** 2025 panel rows carry depth, and nothing anywhere says
so. The docstring explains why 2025 was not adapted; no code path reports that
the consequence happened.

**3. The vendor schema break, unmapped.** 2020–2024 is
`season, week, club_code, depth_team, position, depth_position`. 2025+ is
`dt, team, gsis_id, pos_abb, pos_slot, pos_rank`. The captured 2026 vintage is
the *daily* schema. Nothing ever joined it to the key space `A.depth()` returns.

**4. The one 2026 consumer read it unlawfully, and failed open.**
`board.depth_rank(season, week, teams, blob)` accepts `season` and `week` and
**uses neither**: it takes the newest `dt` in the vintage regardless of which
week is being forecast, with no check that the capture predates the forecast
clock. R6's call site wrapped it in `except Exception: dr = {}`, so a total
failure to load depth was indistinguishable from no player having a rank.

**5. A guard that cannot fire.** Not depth, but found on the way and it belongs
in the same register. `appearance_model.fit` builds
`train = [r for r in rows if season(r) < season]` and
`late = [r for r in rows if season(r) >= season]`, then refuses if
`any(r in train for r in late)`. The two lists are **disjoint by construction**,
so the leakage guard has never made a single true comparison — and it costs
`O(|train| x |late|)` dict comparisons, which is why it is invisible in
production (the panel holds no forecast-season row, so `late` is empty) and
takes hours the moment it is asked to evaluate a historical season. This is the
`assert_batch_games_are_new` pattern again. **Reported, not repaired**: it is
inside the frozen mechanism and repairing it is not this mission.

### The repair

`nfl/production/nonqb/depth_vintage.py`. Point-in-time or refuse:

* `weekly(stage)` — 2020–2024 leaves, **naming any absent season** rather than
  skipping it. `DEPTH_WEEKLY_LEAF_MISSING`.
* `daily(text)` — the daily schema; an empty parse is `DEPTH_DAILY_EMPTY`,
  never an empty dict.
* `daily_point_in_time(by_team, team, before)` — the newest snapshot
  **strictly before** the clock. No clock is `DEPTH_PIT_NO_CLOCK`. Nothing
  earlier than the clock is `DEPTH_PIT_UNAVAILABLE`, a DEFERRED with the debt
  named. **Today's chart is never substituted for a historical game.**
* `captured(teams, observed_before)` — the 2026 vintage, same discipline,
  refusing for the whole slate if any team cannot be given a lawful chart.

**Proof it is point-in-time.** Over the 544 team-weeks of the 2025 regular
season, **every one resolves**, and the chosen snapshot sits **6.3 to 18.7 hours
before kickoff, median 10.8**. For SF@LA the chart chosen is
`2026-09-10T12:01:46Z`, 5.15 hours before `written_at` and 12.7 before kickoff.

**Proof depth now reaches the model.** `R7.featurise` returns different rows for
rank 1, rank 3 and unlisted, and the test asserting that the *frozen* featuriser
still ignores `f_depth` is kept deliberately: if it ever starts failing, the
control has moved and R7's premise needs restating.

**Rank was put on one scale, and the scales are NOT shown equivalent.** nflverse
`depth_team` ranks within `depth_position`, so a team fields three "WR1"s; ESPN
`pos_rank` ranks within `pos_abb` across slots, so a team fields one. Both are
converted to an ordinal within position. Measured appearance at rank 1 is
**0.707–0.812** under the weekly feed and **0.895–0.923** under the daily one.
That is consistent with a genuine vendor difference *or* with the daily chart
simply being fresher, and **the two feeds do not overlap in time, so nothing in
this repository can separate them.** Anything fitted across the break carries a
vendor indicator so the level shift is absorbed rather than averaged. Filed as
OUT-005.

---

## 2. The season boundary: it inverts, it does not decay

`f_consec_missed`, `f_weeks_since_appear` and `f_prev_appeared` all walk
backwards through the offseason without noticing it. At week 1, **1,278 of 4,624
rows carry a non-zero streak and every one of them is pure carry-over.**

Within a season the feature is strongly and monotonically informative:

| within-season streak | 0 | 1 | 2 | 3 |
|---|--:|--:|--:|--:|
| appearance rate | 0.7219 | 0.5038 | 0.2060 | 0.1777 |

Carried across the boundary at depth rank 1, **the sign flips**:

| week 1, depth rank 1 | streak 0 | streak 1–2 | streak 3+ |
|---|--:|--:|--:|
| n | 85 | 722 | 126 |
| appearance rate | **0.7765** | **0.9515** | 0.9048 |

A carried streak of one or two predicts a *higher* week-1 appearance rate than
no streak at all, by +17.5 points. The football reason is not subtle: resting a
starter in week 18 marks a team that had already clinched, not an injury.

**So neither of the two obvious answers is right.** A flat reset to zero throws
away a signal that is real. Carrying the value through unchanged inverts it. And
decay is not supported — the relationship reverses rather than attenuating.

The repair keeps both quantities and lets the fit give them different signs:
`cm_within` resets at the boundary, `cm_carried` fires only when the boundary
was crossed, and `crossed` and a week-1 indicator let the week-1 regime have its
own intercept. A test constructs a player who missed weeks 17 and 18 and asserts
`cm_within == 0`, `cm_carried == 2`, `crossed is True`, and that the two land in
different design columns.

---

## 3. Cold start: what is estimable, and what is refused

### The panel cannot measure it at all

`model.extend_with_zeros` adds a zero-opportunity row only for a player who
appeared in one of the team's previous `LOOKBACK_CANDIDATE = 4` games. So a
row with no prior history exists **only because the player played**.

Measured: **cold-start appearance rate in the panel is 1.0000, at every position
and every depth rank, n = 839.** Not a high probability — a degenerate estimator
with zero variance. Any model fitted through it learns that an unknown player is
a certainty, which is precisely the 0.998 the V1 mechanism assigns.

### The depth chart supplies the missing denominator

A depth chart lists a team's players whether or not they play. Unioning the
panel with the point-in-time listing adds **6,181 player-team-weeks the panel
does not hold at all** — including listed rank-1 players who missed the game.

On that frame, cold start becomes estimable **where the player is listed**:

| cell | n | appearance |
|---|--:|--:|
| WR rank 1, cold start | 35 | 0.7714 |
| WR rank 2, cold start | 77 | 0.5714 |
| WR rank 3, cold start | 38 | 0.3684 |
| RB rank 1, cold start | 25 | 0.6400 |
| RB rank 3, cold start | 56 | 0.3750 |
| TE rank 3, cold start | 53 | 0.4906 |

and stays degenerate where he is not:

| cell | n | appearance |
|---|--:|--:|
| RB, cold start, **unlisted** | 30 | **1.0000** |
| WR, cold start, **unlisted** | 69 | **1.0000** |
| TE, cold start, **unlisted** | 33 | **1.0000** |

### So that cell is refused, by name

`no_history_and_not_depth_listed`. Rows in it are **dropped from the fit** (245
of them) and players in it are **declined at prediction time**, with the reason
carried in the evidence. R7 emits no number there rather than a manufactured
one. On the SF@LA roster of 182 that is 137 declined and 45 scored; on the R5
active pool it is 72 declined and 29 scored, and every player the engine
actually reaches was scorable, so nothing fell through.

### The three states are kept apart

`KNOWN_HEALTHY` (seen before, and this week says something about him),
`NO_HISTORY` (never seen), `UNKNOWN_STATUS` (seen before, but no depth listing
and no injury row this week). Absence of prior missed games is not evidence of
availability, and the vocabulary is what stops it being read as such.

---

## 4. Historical calibration

Forward-chained: for each season S the model is fitted on frame rows from
seasons strictly before S and scored on S. 40,593 pooled rows.

### Where R7 is calibrated

| cell | n | predicted | observed | gap |
|---|--:|--:|--:|--:|
| KNOWN_HEALTHY | 33,963 | 0.7131 | 0.7120 | **+0.11 pp** |
| injury `Out` | 855 | 0.0100 | 0.0000 | +1.00 pp |
| injury `Doubtful` | 160 | 0.0219 | 0.0063 | +1.56 pp |
| injury `Questionable` | 1,312 | 0.6523 | 0.6387 | +1.36 pp |
| no injury row | 24,477 | 0.6546 | 0.6536 | +0.10 pp |
| within-season streak 0 | 26,977 | 0.8065 | 0.8108 | −0.43 pp |
| within-season streak 1 | 4,804 | 0.4165 | 0.4076 | +0.89 pp |
| 1–3 prior rows | 1,522 | 0.5249 | 0.5223 | +0.25 pp |
| 17+ prior rows | 32,362 | 0.6596 | 0.6451 | +1.45 pp |

### Where it is not, and this is the honest half

| cell | n | predicted | observed | gap |
|---|--:|--:|--:|--:|
| **NO_HISTORY (listed)** | 432 | 0.6107 | 0.4769 | **+13.39 pp** |
| **UNKNOWN_STATUS** | 6,198 | 0.2673 | 0.1833 | **+8.40 pp** |
| within-season streak 2 | 2,697 | 0.2974 | 0.1943 | +10.31 pp |
| within-season streak 3 | 2,000 | 0.2633 | 0.1725 | +9.08 pp |
| within-season streak 5+ | 3,005 | 0.2478 | 0.1381 | +10.97 pp |
| within-season streak 4 | 1,110 | 0.2790 | 0.3703 | **−9.13 pp** |
| WR unlisted | 2,904 | 0.3044 | 0.2197 | +8.47 pp |
| TE unlisted | 1,369 | 0.3021 | 0.2235 | +7.86 pp |
| QB rank 1 | 1,838 | 0.7931 | 0.8803 | −8.72 pp |

**R7 has reduced the inversion, not removed it.** It still over-predicts
appearance wherever information is thin, in the same direction as the original
defect — cold start 0.998 → 0.61 against a realised 0.48 is a large improvement
and is still 13 points too high. The residual sign flip at streak 4 is the
censoring that survives: a player both off the chart and absent from the panel
still produces no row. QB rank 1 is informational only; quarterbacks do not pass
through this layer (`qb_accounting.py:377`).

### By point-in-time depth rank

| rank | QB | RB | WR | TE |
|---|--:|--:|--:|--:|
| 1 | 0.880 | 0.825 | 0.813 | 0.906 |
| 2 | 0.310 | 0.851 | 0.888 | 0.900 |
| 3 | 0.179 | 0.755 | 0.898 | 0.730 |
| 4+ | 0.288 | 0.536 | 0.690 | 0.650 |
| unlisted | 0.085 | 0.202 | 0.220 | 0.224 |

Observed rates. Being **off** the chart is the single strongest signal in the
table and was previously unused anywhere.

---

## 5. The candidate

`V1_CANDIDATE_R7` inherits every R6 flag and adds exactly one,
`appearance_r7`. Its component manifest is
`A1, A3G, C0, C3, R2, SC1, R5, R6, R7`. `introduces_no_constant: true` — every
quantity is a fitted coefficient or a measured rate; there is no hand-set number
anywhere in `appearance_r7.py` or `depth_vintage.py`, and no player or team name.

The seam is `layers.appearance(appearance_spec=...)`, threaded through
`football_engine.run_game`. **The default is `'frozen'` and an unrecognised name
is a named FAIL, not a quiet fallback** — so V1, R5 and R6 produce exactly the
draws they produced before the parameter existed, and a typo cannot silently run
the control under the candidate's name.

The estimator is `stage_a.fit_logistic`, imported. What changed is the **frame**
and the **features**, which is the point: no coefficient change can fix a
training set in which long absence marks having played.

---

## 6. V1 / R5 / R6 / R7 against history

All four run on identical inputs, identical seed, identical written_at.

### Whole held-out season, identical rows

| season | V1 Brier | R7 Brier | Δ (V1−R7) | 95% team-week-blocked | V1 AUC | R7 AUC |
|---|--:|--:|--:|---|--:|--:|
| 2022 | 0.13701 | 0.11730 | +0.01971 | [+0.0144, +0.0251] | 0.8588 | 0.8911 |
| 2023 | 0.12806 | 0.10833 | +0.01973 | [+0.0142, +0.0252] | 0.8681 | 0.8971 |
| 2024 | 0.12503 | 0.10864 | +0.01638 | [+0.0107, +0.0221] | 0.8786 | 0.9033 |
| 2025 | 0.15114 | 0.13646 | +0.01468 | [+0.0094, +0.0197] | 0.8198 | 0.8428 |

Four for four, every interval excluding zero. **And that is not the result that
should decide anything**, because splitting it by week reverses it.

### The result that matters

| weeks | n | base | V1 Brier | R7 Brier | Δ | 95% blocked | V1 AUC | R7 AUC |
|---|--:|--:|--:|--:|--:|---|--:|--:|
| **1** | 2,568 | 0.576 | **0.24667** | **0.10966** | **+0.13702** | [+0.1273, +0.1464] | 0.7261 | **0.9376** |
| 2–4 | 7,709 | 0.581 | 0.18146 | 0.11510 | +0.06636 | [+0.0621, +0.0706] | 0.8055 | 0.9167 |
| 5–9 | 8,907 | 0.760 | 0.11213 | 0.11814 | **−0.00601** | [−0.0093, −0.0028] | 0.8826 | 0.8632 |
| 10–18 | 16,972 | 0.754 | 0.10975 | 0.11989 | **−0.01014** | [−0.0124, −0.0080] | 0.8886 | 0.8665 |

**At week 1 the frozen mechanism is barely distinguishable from the base rate.**
Predicting 0.576 for everyone scores 0.2443; V1 scores 0.2467. Its AUC is 0.726.
R7 scores 0.1097 at AUC 0.938 — a 56% reduction in Brier, on 2,568 rows, with a
blocked interval nowhere near zero.

From week 5 onward R7 is **worse**, by 0.006 to 0.010 Brier, intervals excluding
zero. The mechanism is not mysterious: by week 5 the frozen model's within-season
participation history (rate3, rate5, snap EWMA, vacated share, practice
progression, role volatility) carries more than a depth rank does, and R7 traded
those features away.

Two controls rule out the alternative explanation. Training strictly before week
10 and evaluating weeks 10–18 gives Δ = **−0.00567** [−0.0101, −0.0014] in 2025
(daily vendor) and **−0.01053** [−0.0148, −0.0062] in 2024 (weekly vendor). Same
sign, same size, both eras. **The reversal is about where in the season the
evaluation sits, not about which vendor supplied the chart.**

### Allocation on SF@LA

| quantity | V1 | R5 | R6 | **R7** | historical |
|---|--:|--:|--:|--:|--:|
| SF targets top-1 | 11.8% | 17.0% | 18.1% | **19.7%** | 29.3% |
| SF targets top-3 | 33.9% | 49.0% | 52.5% | **55.7%** | 65.5% |
| SF players targeted ≥0.5 | 16 | 12 | 12 | **11** | ~8 |
| LA targets top-1 | 15.9% | 22.4% | 24.3% | **21.8%** | 29.3% |
| LA targets top-3 | 30.8% | 44.4% | 46.9% | **50.8%** | 65.5% |
| SF carries top-1 | 39.8% | 52.6% | 67.6% | **74.1%** | 70.3% |
| LA carries top-1 | 36.4% | 60.1% | 60.2% | **59.3%** | 70.3% |

Mixed, and the mixture is informative. SF concentration keeps improving; **LA
top-1 targets falls back from 24.3% to 21.8%**, moving away from history. That
is not a concentration failure — it is redistribution. R7 raises Davante Adams
(`00-0031381`) from 3.14 to 4.73 targets because his V1 appearance probability
of 0.532 was the censoring artifact, and the mass comes partly out of Puka Nacua
(7.63 → 6.78). **SF carries top-1 now overshoots** 70.3% at 74.1%.

### Appearance probabilities that moved most

| player | V1 | R7 | Δ |
|---|--:|--:|--:|
| `00-0040177` | 0.999 | 0.381 | −0.618 |
| `00-0041052` | 0.999 | 0.419 | −0.580 |
| `00-0041510` | 0.999 | 0.469 | −0.530 |
| `00-0041035` | 0.998 | 0.484 | −0.514 |
| `00-0041399` | 0.998 | 0.484 | −0.514 |
| `00-0039075` (Nacua) | 0.947 | 0.764 | −0.183 |

The top five are all recent-draft-class players the frozen model was giving
near-certainty. Mean over the shared pool falls 0.798 → 0.638.

---

## 7. SF@LA projections

| player | market line | V1 | R5 | R6 | **R7** |
|---|--:|--:|--:|--:|--:|
| McCaffrey carries | 15.5 | 7.29 | 9.52 | 12.23 | **12.97** |
| McCaffrey receptions | 4.5 | 2.56 | 3.58 | 3.80 | **4.11** |
| Kittle receptions | 3.5 | 2.44 | 3.67 | 3.92 | **4.28** |
| Kittle receiving yards | 33.5 | 31.93 | 47.82 | 51.26 | **56.34** |
| Kyren Williams carries | 13.5 | 6.68 | 11.02 | 11.04 | **10.61** |
| Nacua receptions | 7.5 | 3.56 | 5.03 | 5.44 | **4.92** |
| Nacua receiving yards | 90.5 | 46.95 | 66.31 | 71.22 | **64.64** |
| Purdy pass attempts | 33.5 | 26.708 | 26.708 | 26.708 | **26.708** |
| Stafford pass attempts | 34.5 | 30.266 | 30.266 | 30.266 | **30.266** |

Median |gap| to the de-vigged market across 19 comparable prices:
**25.30 → 18.71 → 17.40 → 14.62 pp**. Mean gap −24.27 → −12.36 pp.

The market side is the sealed MKT1 snapshot carried over unchanged. **This is a
benchmark, not a target**, and R7 moves *away* from it on Nacua while moving
toward it elsewhere — which is what an untargeted repair looks like.

---

## 8. Invariants

**Team volume is bit-identical.** All ten team-metric draw vectors
(`team_off_snaps`, `team_dropbacks_part`, `team_targets`, `team_carries`,
`team_rz_carries` × SF, LA) agree to `0.0000000000` across V1, R5, R6 and R7.

**The QB path is untouched.** Pass attempts for all eight passers agree to
`0.000000` across all four. R7 is applied only to non-QB players; QBs do not
pass through the appearance layer at all.

**What is NOT invariant, stated plainly.** The *sum of modelled player means*
moves: SF carries 18.30 → 17.51, LA 18.35 → 17.90, targets by ≤0.07. That is
correct behaviour, not drift — appearance decides who is in the modelled pool
in each draw, so the modelled share of a fixed team budget moves and the balance
sits in the named `other` mass. All 14 accounting verdicts are unchanged between
V1 and R7 (10 PASS, 3 FAIL, 1 DEFERRED — the same pre-existing set).

**The control is bit-identical, and this is hashed rather than asserted.** The
R6 candidate was re-run on identical inputs, seed and `written_at` *after* the
`appearance_spec` seam was added, and its draw artifact hashes to
`8cc1787e1ceb351f94a65441109020fdaaa80de8cba3f763ca01a95252d536e6` — the same
value as the run sealed before the seam existed. 218 distribution means
compared, 0 differing. V1 and R5 travel the same code path with the same
default, so the same holds for them.

---

## 9. Suite

**61 modules · 667 test functions · 3,578 checks · 0 failing · 0 raised ·
SUITE PASS**, on `python3.12`.

New: `nfl/tests/test_r7_appearance_frame.py`, 67 checks. The load-bearing ones
fail if the control is removed: a clock before every snapshot must DEFER rather
than return the newest chart; a snapshot exactly at the clock must be refused;
no clock must FAIL rather than default; a missing weekly leaf must be named;
an unknown `appearance_spec` must FAIL rather than fall back; the degenerate
cell must be declined; the depth rank must change the design row.

---

## 10. Recommendation

**Do not promote. Do not adopt R7 as a blanket replacement either — the
evidence does not support that and says so in the same table that supports
using it.**

What the evidence does support, precisely:

1. **The three defects are real, located and repaired at their source.** The
   depth feature now reaches the model; the absence streak no longer inverts
   across the offseason; the degenerate cold-start cell is refused instead of
   scored at 1.0.
2. **R7 is decisively better in weeks 1–4** — Brier 0.2467 → 0.1097 at week 1,
   AUC 0.726 → 0.938 — and **measurably worse from week 5** by 0.006–0.010
   Brier. Both directions have blocked intervals excluding zero across four
   forward-chained seasons.
3. **SF@LA is week 1.** It is the regime where the frozen mechanism is barely
   better than the base rate.
4. **R7 has not finished the job.** It still over-predicts appearance by 13.4
   points on listed cold starts and 8.4 on unknown status, and the censoring
   residual is still visible at streak 4.

So: **shadow-evaluate R7 beside V1, R5 and R6 for the early weeks and let the
four-game refinement bar decide.** The result also points at the design that
would beat both, and that is a separate mission with its own pre-registration:
the two models are strong in complementary regimes, so the right end state
blends depth information with participation history rather than choosing between
them — most likely by giving the frozen feature set the depth columns it is
missing, on the frame R7 built.

What would change the recommendation to promotion: a pre-registered prospective
comparison over weeks 1–4 of the 2026 season on unseen games, with the week
regime declared in advance rather than discovered afterwards.
