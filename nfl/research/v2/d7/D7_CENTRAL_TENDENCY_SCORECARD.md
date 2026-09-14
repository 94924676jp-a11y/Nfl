# D7 — CENTRAL-TENDENCY SCORECARD

**Diagnostic only. Not a promotion test.** Nothing here tunes, promotes, adjusts
or selects anything. No estimator was changed, no board was rebuilt, no price
was touched, nothing was committed.

| | |
|---|---|
| Frame | 9 completed games, 2026 week 1, 18 team-games, 203 players, 925 forecast rows |
| Scorer | `nfl/research/same_day_retrospective.py` at `same-day-retrospective/2.0.0` — the **repaired** module (`51b364a`). `resolve_realised`, `score_seal`, `role_tiers` and `_cluster_se` are imported, never reimplemented |
| Outcome | `nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz`, sha `1415dd98…f9bd`, finality proven per game from the bytes |
| Seal rule | latest seal with `written_at < kickoff`, per game |
| Selection | `COMPLETE_INCLUDING_ZERO_BY_COMPLETION` — 415 OBSERVED + 510 ZERO_BY_COMPLETION |
| Excluded | **2026_01_DEN_KC has not been played and enters nothing.** Five further week-1 games are absent from the authoritative outcome blob and were skipped by name |
| Artifacts | `D7_ROWS_2026W1.csv` (925 rows, 53 columns) · `D7_SUMMARY_2026W1.json` · `D7_ROWS_ALL_SEALS_2026W1.csv` (2,939 rows, every pregame seal) · `D7_BOUNDARY_OUTCOME_2021_2024.json` · `d7_central_tendency.py` · `d7_boundary_outcome.py` |

**Reproduction of the known results, before anything new.** The repaired
figures reproduce exactly: pooled bias **−0.0655**, coverage **0.8368 /
0.9503 / 0.9730**, `rushing/carries` **−1.7775** on **5 game clusters** with
game-clustered z **−3.391**, `receiving/targets` **−0.0744**,
`qb/pyds` **−1.7179**. Convention: CRVE for a mean with the G/(G−1)
finite-cluster correction, as written in `same_day_retrospective._cluster_se`
and reused by import. **My measurement agrees with the briefing and adds
nothing to that dispute.**

---

## 0. Two conventions that change how every number below reads

**(a) A cluster-robust z is not a standard normal deviate at G = 5.** Every
cell carries `p_two_sided_t_G_minus_1` beside its z, computed in-artifact. The
two references disagree by more than an order of magnitude on the headline:

| figure | G | z | p (normal) | p (t, G−1) |
|---|--:|--:|--:|--:|
| `rushing/carries` bias | 5 | −3.391 | 0.0007 | **0.0275** |
| BACKUP `qb/pyds` bias | 9 | +3.016 | 0.0026 | **0.0167** |
| STARTER `qb/cmp` bias | 9 | −3.053 | 0.0023 | **0.0157** |

Neither is a licence for an adequacy word. No equivalence margin was
predeclared and no TOST was run, so nothing here is unbiased, stable, closed or
correct — including the cells whose z is near zero.

**(b) A cluster-robust SE collapses when every cluster says the same thing.**
Two cells and three participation bins show |z| > 10 on fewer than 10 clusters.
That is not precision: it is a near-deterministic gap (players projected volume
who all recorded exactly zero) driving the between-cluster spread toward zero.
Those cells carry a `se_collapsed` field and **the bias is the number to read,
never the z**.

**(c) Units are not pooled.** The pooled `mae` 6.0244 and `rmse` 18.6507
average passing yards with interceptions. Every such cell is stamped
`unit_mixed: true` and is not an error magnitude. The primary table is
(position × stat).

---

## 1. The headline: the engine's near-zero pooled bias is two large errors cancelling

The pooled bias is −0.0655 (z = −0.094). It is not a small error; it is a small
**residue**. The model is above the outcome on **635 of 925 rows** and below on
**243** (47 exact). Splitting participation from conditional volume shows why.

For a count or a sum over events, `E[Y] = P(opportunity > 0) · E[Y | opportunity > 0]`
**exactly** — a player with zero opportunity contributes zero. The identity is
verified in-artifact, not assumed: `mu_equals_p_times_c_max_abs_gap` is
**6.9e-05** across all 925 rows (4-dp rounding of the published means). The
bias then splits without residual:

`bias = (P_model − P_actual)·C_model + P_actual·(C_model − C_actual)`

`decomposition_residual` is 0.0 in every cell.

| stat | G | bias | **from participation** | **from conditional volume** |
|---|--:|--:|--:|--:|
| `qb/db` | 9 | +0.1947 | **+3.5595** | **−3.3648** |
| `qb/att` | 9 | +0.1909 | +3.1559 | −2.9650 |
| `qb/cmp` | 9 | −0.0953 | +2.0281 | −2.1234 |
| `qb/pyds` | 9 | −1.7179 | **+22.7033** | **−24.4212** |
| `receiving/targets` | 5 | −0.0744 | −0.2082 | +0.1338 |
| `receiving/receptions` | 5 | −0.0652 | −0.1423 | +0.0771 |
| `receiving/receiving_yards` | 5 | +0.8521 | −1.6165 | +2.4686 |
| `rushing/carries` | 5 | **−1.7775** | +0.1466 | **−1.9241** |

Read it as three different engines.

- **QB.** The model puts participation probability **0.4549** on the average
  quarterback row against a realised **0.2817**, and then projects **131.1**
  passing yards per participating quarterback against a realised **217.8**.
  Each error is worth roughly 23 yards of bias and they point opposite ways.
  A pooled QB bias of −1.72 conceals a ±23-yard structural error.
- **Receiving.** Small in both terms and opposite in sign; nothing here
  survives clustering.
- **Rushing.** Participation is nearly right (+0.1466). **The entire carries
  bias is conditional volume** (−1.9241): 8.12 carries projected per
  participating rusher against 11.05 realised. This localises the only bias
  that survives clustering, and it is *not* an availability problem.

`C_actual` conditions on the outcome and is a decomposition term, not a
forecast score. The outcome-free half of the comparison is `P_model` against
`P_actual`, which uses every forecast row in the stratum.

---

## 2. Primary table — position × stat

Cluster counts alongside every figure. `PM` = mean forecast participation
probability, `PA` = realised participation rate, both on the layer's own
opportunity metric (`qb/db`, `receiving/targets`, `rushing/carries`), never on
the stat being scored.

| pos | stat | n | **G** | players | proj mean | proj median | actual | bias | z(G) | p t(G−1) | MAE | RMSE | PM | PA | cov50 |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| QB | qb/att | 71 | 9 | 71 | 8.290 | 7.500 | 8.099 | +0.191 | 0.33 | 0.750 | 4.442 | 7.184 | 0.455 | 0.282 | 0.859 |
| QB | qb/cmp | 71 | 9 | 71 | 5.327 | 4.648 | 5.423 | −0.095 | −0.29 | 0.780 | 2.935 | 4.560 | 0.455 | 0.282 | 0.873 |
| QB | qb/db | 71 | 9 | 71 | 9.350 | 8.521 | 9.155 | +0.195 | 0.32 | 0.760 | 5.032 | 8.108 | 0.455 | 0.282 | 0.873 |
| QB | qb/int | 71 | 9 | 71 | 0.177 | 0.000 | 0.141 | +0.036 | 1.06 | 0.321 | 0.214 | 0.395 | 0.455 | 0.282 | 0.944 |
| QB | qb/ptd | 71 | 9 | 71 | 0.359 | 0.169 | 0.394 | −0.035 | −0.47 | 0.648 | 0.343 | 0.641 | 0.455 | 0.282 | 0.930 |
| QB | qb/pyds | 71 | 9 | 71 | 59.634 | 50.028 | 61.352 | −1.718 | −0.33 | 0.747 | 34.955 | 59.906 | 0.455 | 0.282 | 0.873 |
| QB | qb/sacks | 71 | 9 | 71 | 0.600 | 0.366 | 0.549 | +0.050 | 0.63 | 0.545 | 0.493 | 0.914 | 0.455 | 0.282 | 0.916 |
| RB | receiving/receiving_yards | 32 | **5** | 32 | 11.177 | 6.031 | 12.594 | −1.417 | −1.01 | 0.371 | 9.087 | 13.748 | 0.503 | 0.594 | 0.656 |
| RB | receiving/receptions | 32 | **5** | 32 | 1.414 | 0.938 | 1.906 | **−0.492** | **−2.57** | **0.062** | 1.143 | 1.737 | 0.503 | 0.594 | 0.781 |
| RB | receiving/targets | 32 | **5** | 32 | 1.802 | 1.312 | 2.344 | −0.542 | −1.91 | 0.129 | 1.402 | 2.072 | 0.503 | 0.594 | 0.750 |
| RB | rushing/carries | 32 | **5** | 32 | 5.473 | 4.891 | 7.250 | **−1.778** | **−3.39** | **0.028** | 3.196 | 4.672 | 0.674 | 0.656 | 0.563 |
| TE | receiving/receiving_yards | 40 | **5** | 40 | 15.435 | 9.175 | 11.800 | +3.635 | 1.42 | 0.229 | 12.113 | 17.784 | 0.522 | 0.550 | 0.725 |
| TE | receiving/receptions | 40 | **5** | 40 | 1.429 | 0.950 | 1.225 | +0.204 | 1.32 | 0.258 | 0.985 | 1.368 | 0.522 | 0.550 | 0.825 |
| TE | receiving/targets | 40 | **5** | 40 | 2.032 | 1.450 | 1.875 | +0.157 | 0.46 | 0.669 | 1.268 | 1.919 | 0.522 | 0.550 | 0.850 |
| WR | receiving/receiving_yards | 60 | **5** | 60 | 24.140 | 15.625 | 23.933 | +0.207 | 0.07 | 0.948 | 15.397 | 24.762 | 0.579 | 0.617 | 0.800 |
| WR | receiving/receptions | 60 | **5** | 60 | 1.850 | 1.383 | 1.867 | −0.017 | −0.07 | 0.947 | 1.174 | 1.592 | 0.579 | 0.617 | 0.800 |
| WR | receiving/targets | 60 | **5** | 60 | 2.887 | 2.275 | 2.867 | +0.021 | 0.06 | 0.954 | 1.530 | 2.060 | 0.579 | 0.617 | 0.817 |

**A structural fact about this frame that no prior artifact states.** The QB
layer rests on **9** game clusters and the receiving and rushing layers on
**5**: only ATL_PIT, BAL_IND, NO_DET, SF_LA and TB_CIN carry non-QB layers at
all; BUF_HOU, CHI_CAR, CLE_JAX and NYJ_TEN are quarterback-only boards. This is
the same class of defect `CORRECTIONS.json` records in
`MODEL_HEALTH_2026-09-13.json` (7-game receiving against 8-game QB), still
present at 9 against 5, and it means **no QB figure and non-QB figure in this
artifact are computed on the same games.**

Where the engine systematically mis-projects, by position:

- **RB is under-projected on every opportunity stat it has** — carries −1.78,
  targets −0.54, receptions −0.49. Direction is consistent across four stats.
- **TE is over-projected on receiving yards** (+3.63) and mildly on receptions;
  neither survives clustering at G = 5.
- **WR is flat at the position level** (+0.02 targets) — and Section 3 shows
  that flatness is itself two offsetting errors.
- **QB is flat at the position level** and structurally wrong underneath it.

---

## 3. Starter / backup — the largest effect in the artifact

`depth_chart` comes from the board's own pregame claim. **A player with no
depth-chart entry is a third class, not a missing value**: 19 players (18 QBs,
1 receiver) were carried into the forecast pool with no depth-chart row at all.

| class | stat | n | **G** | proj | actual | bias | z(G) | p t(G−1) | PM | PA |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| STARTER | qb/db | 18 | 9 | 28.361 | 34.333 | **−5.973** | −2.30 | 0.050 | 0.817 | 0.944 |
| STARTER | qb/cmp | 18 | 9 | 16.201 | 20.611 | −4.410 | −3.05 | 0.016 | 0.817 | 0.944 |
| STARTER | qb/pyds | 18 | 9 | 180.928 | 233.333 | **−52.406** | −2.24 | 0.056 | 0.817 | 0.944 |
| BACKUP | qb/db | 35 | 9 | 3.525 | 0.914 | **+2.610** | 2.51 | 0.037 | 0.338 | 0.086 |
| BACKUP | qb/cmp | 35 | 9 | 1.997 | 0.400 | +1.597 | 3.03 | 0.016 | 0.338 | 0.086 |
| BACKUP | qb/pyds | 35 | 9 | 22.568 | 4.457 | **+18.111** | 3.02 | 0.017 | 0.338 | 0.086 |
| NOT_ON_DEPTH_CHART | qb/db | 18 | 8 | 1.665 | **0.000** | +1.665 | 3.18 | 0.015 | 0.320 | 0.000 |
| NOT_ON_DEPTH_CHART | qb/pyds | 18 | 8 | 10.415 | **0.000** | +10.415 | 3.27 | 0.014 | 0.320 | 0.000 |
| STARTER | receiving/targets | 32 | **5** | 4.845 | 5.906 | −1.061 | −1.61 | 0.182 | 0.848 | 0.938 |
| BACKUP | receiving/targets | 99 | **5** | 1.586 | 1.343 | +0.242 | 1.52 | 0.204 | 0.449 | 0.485 |
| BACKUP | receiving/receiving_yards | 99 | **5** | 12.082 | 9.263 | +2.819 | 5.05 | 0.007 | 0.449 | 0.485 |
| STARTER | rushing/carries | 11 | **5** | 10.898 | 14.273 | −3.375 | −1.71 | 0.163 | 0.876 | 0.909 |
| BACKUP | rushing/carries | 21 | **5** | 2.630 | 3.571 | −0.941 | −0.99 | 0.381 | 0.569 | 0.524 |

By depth-chart rank, the quarterback gradient is monotone and unambiguous:

| rank | n | G | projected dropbacks | realised | bias | p t(G−1) |
|---|--:|--:|--:|--:|--:|--:|
| QB1 | 18 | 9 | 28.361 | 34.333 | −5.973 | 0.050 |
| QB2 | 18 | 9 | 4.893 | 0.333 | **+4.560** | **0.010** |
| QB3 | 12 | 7 | 2.372 | 2.167 | +0.205 | 0.938 |
| QB4 | 5 | 4 | 1.365 | 0.000 | +1.365 | 0.051 |
| none | 18 | 8 | 1.665 | 0.000 | +1.665 | 0.015 |

**The engine moves dropback mass off the starter and spreads it down the room.**
Measured directly on the club's own board, grouped by `(game_id, posteam)`:

| | model | realised (2026 wk 1) | historical wk 1 (2021–24) | historical wks 2+ |
|---|--:|--:|--:|--:|
| mean top-passer share | **0.7767** | **0.9898** | 0.9289 | 0.9223 |
| mean QBs with ≥5 dropbacks | 1.333 | 1.000 | 1.039 | 1.078 |
| share of team-games with 2+ QBs ≥5 | **0.333** | **0.000** | 0.039 | 0.078 |

The model's room is bimodal: 12 of 18 team-games get a top share of 0.87–0.91
(close to the historical 0.93), and **6 get 0.51–0.57** — ATL 0.570, IND 0.507,
BUF 0.546, CLE 0.537, NYJ 0.562, TEN 0.557. Those six are the split-room
configuration, and they are the whole of the QB defect. This is the same
pathology recorded for KC in `DEN_KC_LIVE_RUN_RECORD.json`
(P(Mahomes zero dropbacks) = 0.412), now measured against outcomes on six
further clubs.

**Participation calibration, quarterbacks, one row per player-game** (not per
stat, so a quarterback does not enter seven times):

| forecast p bin | n | G | mean forecast p | realised rate | gap |
|---|--:|--:|--:|--:|--:|
| [0.05, 0.25) | 20 | 7 | 0.234 | 0.100 | +0.134 |
| [0.25, 0.5) | 18 | 7 | 0.278 | **0.000** | **+0.278** |
| [0.5, 0.75) | 20 | 5 | 0.571 | 0.300 | **+0.271** |
| [0.75, 0.95) | 12 | 8 | 0.933 | 1.000 | −0.067 |

The z in the middle two bins exceeds 12 and is flagged `se_collapsed`; read the
gaps, not the z. Receiving and rushing participation are far better calibrated
(largest bin gap −0.100 and +0.205 respectively).

---

## 4. Season boundary vs non-boundary — **the contrast is not identified**

**Every club in this frame is at a season boundary.**
`previous_primary_detail(2026, 1)` returns `is_season_opener = True` for **32 of
32** clubs, and `season_boundary_census` is `{1: 925}`. The non-boundary arm is
**empty**. There is no comparison to make, and no statistic in this artifact
can separate a boundary effect from the engine's ordinary behaviour.

This is the stratum the brief calls most important, and it is the one the data
cannot supply. Stating it plainly is the finding. What *would* supply it: a
sealed, forward-valid board for a week ≥ 2 game scored against a completed
outcome. One week-2 slate produces the first non-empty cell.

**What can lawfully be said meanwhile, from the outcome side only.** Using
`pbp_2021`–`pbp_2024`, regular season, unit `(game_id, posteam)`, 2,174
team-games:

| | week 1 | weeks 2+ |
|---|--:|--:|
| team-games | 128 (64 game clusters) | 2,046 (1,023 game clusters) |
| mean top-passer share | **0.9289** | **0.9223** |
| median | 0.9474 | 0.9487 |
| 10th percentile | 0.8371 | 0.8333 |
| team-games with 2+ passers ≥5 dropbacks | **3.91%** | 7.77%|

Difference week 1 − rest: **+0.0067**, game-clustered SE 0.0062, z 1.07. If
anything the real world is *slightly more* concentrated on one passer in week 1,
and split rooms are *half* as common. **This contains no forecast and cannot
identify the engine's boundary sensitivity.** What it does is remove one
available explanation: the engine's 0.777 top-passer share and its 33% rate of
two-quarterback rooms are not tracking a real week-1 phenomenon, because no such
phenomenon appears in four seasons of week-1 outcomes.

**Within-boundary split on prior history** (coordinator's instruction).
`n_own` is rebuilt with the identical filter `p4c_params.class_point_forecast`
uses — `ord < 202601`, position in class, non-null share, `appeared` — over the
83,144-row P4C panel (ordinals 202001–202518), so it is the count the forecast
consumed. `role_prior.weight` returns the tier mean exactly when `n_own == 0`
(`role_prior.py:190-191`), which is why this is the variable to split on.

| history | stat | n | G | proj | actual | bias | z(G) | p t(G−1) | PM | PA |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| NONE | qb/db | 23 | 9 | 1.498 | 0.174 | +1.325 | 2.52 | **0.036** | 0.279 | 0.043 |
| NONE | qb/pyds | 23 | 9 | 9.621 | 0.565 | +9.056 | 2.89 | **0.020** | 0.279 | 0.043 |
| NONE | receiving/targets | 26 | **5** | 1.307 | 0.654 | +0.653 | 2.11 | 0.102 | 0.448 | 0.308 |
| NONE | rushing/carries | **5** | 4 | 2.302 | 3.200 | −0.898 | −0.36 | 0.740 | 0.663 | 0.400 |
| THIN 1–4 | qb/db | **4** | 4 | 2.984 | 0.000 | +2.984 | 3.38 | 0.043 | 0.418 | 0.000 |
| THIN 1–4 | qb/pyds | **4** | 4 | 18.459 | 0.000 | +18.460 | 3.52 | 0.039 | 0.418 | 0.000 |
| THIN 1–4 | receiving/targets | **5** | 4 | 0.391 | 0.000 | +0.391 | 2.27 | 0.108 | 0.170 | 0.000 |
| ESTABLISHED 5+ | qb/db | 44 | 9 | 14.033 | 14.682 | −0.649 | −0.69 | 0.508 | 0.550 | 0.432 |
| ESTABLISHED 5+ | receiving/targets | 101 | **5** | 2.735 | 3.020 | −0.285 | −0.97 | 0.385 | 0.586 | 0.693 |
| ESTABLISHED 5+ | rushing/carries | 25 | **5** | 6.431 | 8.640 | −2.210 | −2.81 | **0.049** | 0.699 | 0.760 |

**This is the single coherent story in the artifact.** Opportunity mass flows
from established starters to no-history and thin-history players, in all three
layers at once:

- no-history and thin-history rows are **over**-projected everywhere they have
  a measurable sample (QB +1.32 dropbacks, receiving +0.65 targets);
- established starters are **under**-projected everywhere (QB1 −5.97 dropbacks,
  starting receivers −1.13 targets, RB1 −3.37 carries).

**Against D4's two mechanisms, explicitly:**

- **D4 mechanism 2 (R7/R8 appearance features invert across the boundary; low-history
  players get too-high appearance) is corroborated in direction.** No-history
  quarterbacks carry forecast participation 0.279 against a realised 0.043;
  no-history receivers 0.448 against 0.308. `rushing/carries` at NONE goes the
  other way (−0.90) but rests on **5 rows over 4 clusters** and supports nothing.
- **D4 mechanism 1 (depth-rank-1 skill players with no trailing history are
  understated) can be neither confirmed nor contradicted here.** That population
  in the forward-valid frame is **one player-game**:
  `(NONE, STARTER, receiving/targets)`, n = 1, G = 1, bias +1.084 — the wrong
  sign for D4's prediction and far too thin to mean anything. D4's 47-of-47
  replay result stands on its own data; this frame has no power against it.
  Cell marked `thin`.

**Before attributing anything to a layer, the value must reach the football.**
I checked the sites D4 named. `layers.py:358` and `football_engine.py:1018`
both apply `(A > 0)` — but `A` is already a 0/1 Bernoulli draw produced at
`layers.py:222` by `rng.binomial(1, clip(p, 0, 1))`, so on this path the cast
is idempotent and the appearance **probability does reach the simulation**,
through the draw. What does not reach allocation is any continuous
participation *share*. Every participation figure in this artifact is measured
from the **published opportunity draws** (`qb/db`, `receiving/targets`,
`rushing/carries`, addressed by `row_ids`), i.e. from the engine's own output,
so it is a property of what reached the board by construction and does not
depend on that question.

---

## 5. Injury state, where lawful

Two pregame byte-stored sources only. `weekly_rosters.status` is **not** used;
it is post-hoc and `PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE` is open.

- Official game-day inactive lists, ingested per game, 0.84–1.00 h before
  kickoff, 9 of 9 games present.
- The delivered week-1 injury report, `nfl/vintage/injuries.0bc645a4b9aa6255.csv.gz`,
  sha `0bc645a4…1208`, published **2026-09-11T21:02:00Z** — 42.7 h before the
  1 PM seals.

Absence from either source is recorded as `NOT_ON_REPORT`, never as a health
claim.

| state | rows | players | **G** | PM | PA | participation gap |
|---|--:|--:|--:|--:|--:|--:|
| NOT_ON_REPORT | 781 | 175 | 9 | 0.547 | 0.506 | +0.041 |
| OFFICIAL_INACTIVE | 144 | 28 | 7 | **0.247** | **0.000** | **+0.247** |

**28 players who were on an official inactive list and took zero snaps carried a
mean forecast participation probability of 0.247, and 101 of their 144 rows
carry a strictly positive projection.** The concentration is in the QB layer
(PM 0.320, 26.4 projected passing yards each, z +2.43, p t(5) = 0.060 on 6
clusters) far more than in receiving (PM 0.086).

**How much of that is timing, and how much is not.** 87 of the 144 inactive rows
come from games whose last *pregame* seal is `PRE_INACTIVES` — for ATL_PIT,
BAL_IND, CHI_CAR and CLE_JAX no board was re-sealed after the list arrived, so
the forecast in force at kickoff never saw it. That part is operational.
**The part that is not:** ATL's QB1 (`00-0036212`, Tua Tagovailoa) was listed
**Out** on the injury report published 42.7 hours before the seal, and the
sealed board still projected him **19.7 dropbacks and 131.2 passing yards** with
P(participate) = 0.624. CHI's QB2 (`00-0038416`, Tyson Bagent, *Questionable*)
was projected 2.2 dropbacks. A two-day-old official "Out" did not reach the
forecast.

**The injury-report strata themselves are unusable here and are marked so.** All
eight board players carrying a status were *also* officially inactive, so the
report adds no independent signal in this frame, and each cell is n ≤ 2 on 1–2
game clusters: `OUT/qb/db` n = 2 G = 1, `QUESTIONABLE/qb/db` n = 1 G = 1,
`DOUBTFUL/receiving/targets` n = 2 G = 1. **No claim rests on any of them.**

**What the inactive list does when it is applied.** In the 4 games carrying both
a pregame PRE and a pregame POST seal, every inactive player's projection goes
to exactly 0.000 in the POST board (1 QB, 6 receiver, 2 rusher player-metrics)
and **no player is added to or removed from the pool** — `n_pre_only_rows` = 0,
`n_post_only_rows` = 0. Allocate-then-zero, as the V2 plan describes.

---

## 6. Information set: PRE vs POST inactives, paired within game

Between-game stage comparison is confounded here — the QB-only games are not
the same games as those carrying a receiving layer — so only the 4 games with
both a pregame PRE and a pregame POST seal enter, matched on
`(game_id, gsis_id, metric)`.

| stat | n | **G** | bias PRE | bias POST | paired Δ | MAE PRE → POST |
|---|--:|--:|--:|--:|--:|---|
| qb/db | 30 | **4** | −0.537 | −0.537 | +0.000 | 5.207 → 5.192 |
| qb/pyds | 30 | **4** | −3.508 | −3.263 | +0.245 | 35.009 → 34.810 |
| receiving/targets | 54 | **2** | −0.433 | −0.434 | −0.001 | 1.806 → 1.691 |
| rushing/carries | 14 | **2** | −1.323 | −1.323 | −0.000 | 3.159 → 2.510 |

**4 game clusters, and 2 for the non-QB rows. This cannot support a claim** and
is recorded so the direction is on file. The blind spot is stated in the
artifact: the matched set is the survivors, and here the survivorship is total
(0 added, 0 removed), so what the table shows is that the list moved the
*surviving* players almost not at all — which is what allocate-then-zero
predicts, since the removed mass is redistributed by the simplex rather than
by re-deciding anyone's role.

---

## 7. Interval coverage, carried for context

| | 50% | 80% | 90% |
|---|--:|--:|--:|
| pooled (925 rows, 9 clusters) | 0.8368 | 0.9503 | 0.9730 |
| `rushing/carries` (32 rows, 5 clusters) | **0.5625** | 0.8125 | 0.9375 |
| `receiving/receiving_yards` (132, 5) | 0.7424 | 0.9242 | 0.9621 |
| `qb/pyds` (71, 9) | 0.8732 | 0.9437 | 0.9718 |

Intervals are wide relative to nominal almost everywhere — the mass at zero for
the many low-participation rows sits inside every interval — and `rushing/carries`
is the single stat whose 50% interval is *below* nominal. Coverage and
discrimination are different properties and neither is evidence about the other.
`pit_mean` and the PIT quartiles are carried by the upstream scorer and are
**not interpretable** (`SHARED_CONSTANT_RANDOMISATION`); they are not used here.

---

## 8. Every figure too thin to support a claim, listed

`D7_SUMMARY_2026W1.json` carries a `thin` field on **85** cells — every cell
whose `n_game_clusters` is below 5 — and a `se_collapsed` field on 2 more.
The table below is not that list; it is the subset that bears on a finding
stated above, so that none of those is quoted without its sample beside it.
**Any cell in the JSON carrying `thin` supports nothing, whether or not it
appears here.**

| cell | n | G | why it cannot be used |
|---|--:|--:|---|
| `(NONE, STARTER, receiving/targets)` | **1** | **1** | D4 mechanism 1's whole population in this frame |
| `(THIN_1_4, *)` all stats | 2–5 | 2–4 | fewer rows than clusters would need |
| `(NONE, rushing/carries)` | 5 | 4 | the one cell contradicting D4 mechanism 2 |
| `DEPTH_RUSHER, rushing/carries` | 3 | 3 | all three projected exactly 0.000 |
| `OUT / DOUBTFUL / QUESTIONABLE` × any stat | 1–2 | 1–2 | and fully nested inside OFFICIAL_INACTIVE |
| depth rank 7, `receiving/targets` | 2 | 2 | — |
| depth rank 4, `rushing/carries` | 2 | 2 | — |
| `(PRE_INACTIVES, rushing/carries)` | 11 | **2** | flagged `se_collapsed`, z = −19.8 |
| `(NONE, NOT_ON_DEPTH_CHART, qb/db)` | 10 | 7 | flagged `se_collapsed`, z = +25.4 |
| paired PRE/POST, non-QB rows | 54 / 14 | **2** | 2 games |
| every receiving and rushing cell | — | **5** | 5 games is the ceiling for the whole non-QB layer |
| QB participation bins [0.25,0.5) and [0.5,0.75) | 18 / 20 | 7 / 5 | `se_collapsed`; gaps usable, z not |

---

## 9. What may not be concluded from any of this

1. **This is not a promotion test.** Nothing here may be used to tune, promote,
   adjust or select any layer, threshold or constant.
2. One week is not a sample. The largest cell rests on 9 game clusters and
   every non-QB cell on 5.
3. No equivalence margin was predeclared and no TOST was run, so no cell
   supports *unbiased*, *stable*, *closed* or *correct* — including those whose
   z is near zero.
4. **The season-boundary contrast is not identified**: the non-boundary arm is
   empty, and the 2021–2024 outcome-side comparison is not a substitute for it.
5. `conditional_actual_among_participants` conditions on the outcome; it is a
   decomposition term, not a forecast score.
6. Coverage and discrimination are different properties; neither is evidence
   about the other. PIT is not interpretable and is unused.
7. QB and non-QB figures are computed on different games (9 clusters against 5)
   and must not be compared with each other.
8. A forecast that was wrong in week 1 is not thereby a defect, and one that was
   right is not thereby correct.

## 10. What would move this forward, in order

1. **One sealed week-2 board scored against a completed outcome** creates the
   first non-boundary cell and turns Section 4 from a refusal into a
   measurement. Nothing else in this document is blocked by anything as cheap.
2. **Non-QB layers on all 9 games**, so QB and non-QB stop resting on different
   populations.
3. Re-seal after the official inactive list for every game, not 5 of 9 — and
   separately, find why a 42-hour-old official *Out* did not reach a forecast.

---

*Reproduce:*

```
python3.12 nfl/research/v2/d7/d7_central_tendency.py \
  --games 2026_01_ARI_LAC,2026_01_ATL_PIT,2026_01_BAL_IND,2026_01_BUF_HOU,\
2026_01_CHI_CAR,2026_01_CLE_JAX,2026_01_DAL_NYG,2026_01_GB_MIN,2026_01_MIA_LV,\
2026_01_NO_DET,2026_01_NYJ_TEN,2026_01_SF_LA,2026_01_TB_CIN,2026_01_WAS_PHI \
  --outcome-blob nfl/research/postgame/pbp_2026.1415dd98ba7f701a.csv.gz \
  --seal last --out-csv <csv> --out-json <json>

python3.12 nfl/research/v2/d7/d7_boundary_outcome.py
```

`2026_01_DEN_KC` is not in the list and is in no frame.
