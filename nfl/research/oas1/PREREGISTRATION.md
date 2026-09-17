# OAS1 pre-declaration (Gate 5)

**Every value below is QUOTED FROM `nfl/research/oas1/preregistration.py`.**
That module is the source of truth; this file is a reading of it, and
`nfl/tests/test_oas1_gate345.py::test_F` asserts the two agree.

**Why that matters here.** This repository has already caught a threshold
loosening silently: the Contract 4 document claimed a precedent of eighteen of
twenty while `nfl/tools/draw_contract3.py` set `BATCH_AGREEMENT = 19`. Prose
and code disagreed and the prose was the softer number. A pre-registration
whose thresholds live only in prose does not constrain anything.

- `spec_version`: `oas1-preregistration-1`
- `DECLARED_AT`: 2026-09-17
- `DECLARED_BEFORE_ANY_WEEK2_FIT`: **True**

**No Week-2 OAS1 candidate has been fitted.** This document is committed first,
which is the whole point of gate 5.

## 1. Training data

| Item | Value |
|---|---|
| Training seasons | 2025, 2026 |
| Prior season (carryover source) | 2025 |
| Forecast season / week | 2026 week 2 |
| History-only seasons | 2024 |
| Season types fitted | REG |

2024 is captured and is **history only**: the declared carryover depth is one
prior season, so 2024 informs the baseline chain and is not a training season
for the candidate.

## 2. Target

| Item | Value |
|---|---|
| Target | `oas1_epa_target` |
| Source column | `epa` |
| Exemption | `nfl.ingest.allowlist.assert_oas1_epa_target` |
| Used as | REGRESSION TARGET ONLY; feature use refused |

## 3. Play classification

`pass if pass_attempt == 1 or sack == 1 or qb_scramble == 1; else rush if rush_attempt == 1; else excluded`

| Play | Class |
|---|---|
| Sack | **pass** |
| Scramble | **pass** |
| Designed QB run | rush |

## 4. Exclusions

| Item | Rule |
|---|---|
| Garbage time | search space none, A, B; reads a model-derived column: **False** |
| Penalties | excluded from V1, counted, and reversible |
| Kneels | excluded |
| Spikes | excluded |
| Overtime | included and flagged, so a sensitivity check can drop it |
| Playoffs | retained in the frame, excluded by filter |
| `no_play` | excluded |
| Special teams | excluded |
| Exclusions preserved | **True** |

Garbage-time rules, verbatim from `frame.GT_RULE_TEXT`:

| Rule | Definition |
|---|---|
| `none` | no garbage-time exclusion |
| `A` | exclude when |score_differential| > 21 and game_seconds_remaining < 300 |
| `B` | exclude when |score_differential| > 16 and game_seconds_remaining < 600 |

Win probability is **not** used as the filter, for two reasons: `wp` is
MODEL_DERIVED and refused for forecast use, and excluding plays *because* the
game was decided selects on an outcome downstream of the very team quality
being estimated.

## 5. Search spaces

| Parameter | Grid |
|---|---|
| Ridge penalty `lambda` | 12 log-spaced points, 0.1 to 10000 |
| Time decay `half_life` | 2, 4, 8, 16, inf |
| Offseason regression `rho` | 0.5, 0.7, 0.85, 1 |
| Prior carryover `kappa` | 0, 1, 5, 20, 100, 500 |
| `min_plays` | 0, 20, 50 |
| Garbage-time rule | none, A, B |

## 6. Forward chain

- Fold rule: for a forecast of season S week W, the fitting set is every play with ordinal < S*100 + W, and nothing else
- Inner lookback `INNER_K`: 8
- Inner metric: `mae`
- Ordinal guard is an assertion: **True**
- One-standard-error rule: **True**
- Tie-break order: max lambda, max kappa, min rho, max half_life, max min_plays

among configurations within one standard error of the best mean score, select the most shrunken, in TIE_BREAK_ORDER

## 7. Baselines

B0, B1, B2, B3, B4, B5 — decisive comparator **B5**.
Built before the candidate: **True**.
Identical row sets required: **True**.

| Baseline | Hyperparameters | Cold start |
|---|---|---|
| B0 league constant | none | trivially defined; no subject-level history needed |
| B1 prior-season unit prior | rho | a club absent from the prior season falls back to  |
| B2 rolling unit mean | n_games | spills into the prior season, then B1, then B0 |
| B3 EWMA unit mean | half_life | as B2 |
| B4 simple opponent-adjusted | none. Declared with `n_passes` and measured out of existence | a unit with no prior plays falls back to B1, then  |
| B5 shrunken opponent-adjusted -- THE DECISIVE COMPARATOR | kappa, rho | as B4 |

**B4 carries no hyperparameter, and a measurement removed the one it was
declared with.** Undamped Jacobi iteration oscillates with period 2 on a
design where each unit faces exactly one opponent: 0.0000 at 1, 3 and 5
passes, 0.9000 at 2 and 4. A tuner selecting `n_passes` there selects between
two arbitrary answers. B4 now iterates to `B4_TOL = 1e-06` with at most
`B4_MAX_ITER = 50` iterations and reports `converged`; on
non-convergence it returns the single-pass estimate and says so.

## 8. Scoring

- **Primary:** out-of-sample play-level MAE on oas1_epa_target against B5, clustered by game, in a forward chain, with the interval excluding zero
- Secondary: rmse, crps, calibration_slope, clustered_delta_by_game, clustered_delta_by_team
- Calibration slope band: **0.7 to 1.3**
- Cluster units: game, team — when the two disagree materially, report the wider
- Bootstrap replicates `R_BOOT`: 2000

## 9. Promotion

OAS1 is promotable ONLY IF all of: (a) it beats B5 on PRIMARY_SCORE with a game-clustered interval excluding zero; (b) it also beats B4, so the gain is not shrinkage alone; (c) its calibration slope lies in CALIBRATION_SLOPE_BAND; (d) sharpness is improved at MATCHED coverage, not sharpness alone; (e) design rank is recorded at every step and the claim is restricted to steps where the model was identified.

**If OAS1 loses:** if OAS1 does not beat B5 out of sample, OAS1 is recorded as a MEASURED NEGATIVE for early-season weeks and B5 is used for the early-season opponent layer. No retuning until OAS1 wins, no strata added, no gate weakened. Re-evaluate around week 6 when the schedule graph has connected.

State-space work is blocked until an identified mid-season OAS1 fit beats B5 out of sample.

## 10. Identification, and the Week-2 rule

| Quantity | Value |
|---|---|
| Structural deficiency (identified state) | 2 |
| 2026 Week-1 design columns | 66 |
| 2026 Week-1 rank | **32** |
| 2026 Week-1 deficiency | **34** |
| Graph components | 32, each of 2 nodes |

prior-season IDENTIFIED strengths plus a governed Week-1 update. NOT a 2026 Week-1 ridge presented as having learned separate offense and defense strengths: that design is rank 32 of 66 with 32 two-node graph components, so 32 dimensions carry no information from the data.

Minimum-sample rule: a unit with fewer than min_plays current-season plays is reported with n_plays_current_season and prior_weight_effective attached, and `identified` is False whenever design_rank < design_cols - STRUCTURAL_DEFICIENCY

## 11. Single-adjustment ownership

| Item | Value |
|---|---|
| Owner | `oas1` |
| Applied at | `team_volume` (the ONE layer that may apply it) |
| Adjustment names | opponent_pass_offense, opponent_rush_offense, opponent_pass_defense, opponent_rush_defense |
| May be applied once | **True** |
| Registry required before any downstream consumer | **True** |

## Sign convention

positive offensive strength = better offense; positive defensive strength = WORSE defence

## What this pre-registration does NOT claim

that opponent adjustment improves any forecast; that EPA is the right target; that the target is reproducible against future revisions of the source file; that a Week-2 estimate is a measurement of opponent quality.

**V2 NOT YET EARNED**

