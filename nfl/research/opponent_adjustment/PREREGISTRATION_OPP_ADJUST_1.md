# PREREGISTRATION — OPP-ADJUST-1 (opponent adjustment, research only)

- spec_version: `opp-adjust-1-prereg-v1`
- Declared at: **2026-10-09T19:31Z** (UTC), before any outcome-based quantity was computed.
- Authority: owner ruling 2026-10-09, RESEARCH ONLY. Supersedes the exclusion "item 9"
  (`nfl/sim/football_points.py` docstring; `docs/FOOTBALL_INTELLIGENCE_AUDIT_2026-10-08.md` G15)
  **for investigation only**. Production behaviour is not changed by anything in this study.
  Nothing is written under `/home/user/nfl`.
- Status: EXPLORATORY-vs-CONFIRMATORY note in section 9.

## 0. What the author had seen before writing this

Disclosed so a reader can judge independence:

1. The incumbent formula (`football_points.expected_points`, `proj_v1.TEAM_VOLUME_PRIOR_GAMES = 4.0`).
2. Two raw TEAM_GAME rows (one 2024 week 1 row, one 2026 week 5 row with null outcomes).
3. The one-paragraph summary of `nfl/research/W6_DEFENSE_MATCHUP.md`: on 2024 data, defensive
   *outcome* rates are weakly reliable (pass EPA allowed 17-game reliability 0.094; sack rate no
   resolvable between-team component), pressure rate generated 0.693, takeaways 0.499. **2024 is a
   test season here**, so those numbers were NOT used to set any constant; this is why shrinkage
   strength is estimated from training seasons only (section 3).
4. No result relating any opponent variable to any target in any season.

## 1. Question

Does opponent information add predictive value **beyond the club's own baseline**, and does the
improvement persist on seasons not used to fit it?

## 2. Data (read-only)

| Item | Source | Fields admitted |
|---|---|---|
| Club-game targets and incumbent | `nfl/warehouse/TEAM_GAME.json` | club, opponent, game_id, season, week, is_home, points, pass_attempts, rush_attempts, starting_qb_id |
| Opponent variables | `nfl/research/postgame/pbp_{2021..2025}.*.csv.gz`, `pbp_2026.2b3e9f2c6f92123f.csv.gz` | game_id, season, season_type, week, posteam, defteam, play_type, pass, rush, sack, qb_hit, qb_kneel, qb_spike, two_point_attempt, yards_gained, epa |
| Player fantasy targets | `nfl/warehouse/PLAYER_GAME.json` | player_id, club, opponent, game_id, season, week, dk_points_current_rules |
| Position labels | `nfl/warehouse/ROLE_HISTORY.json` | player_id, position (modal label) |

**Forbidden and never read as inputs:** spread_line, total_line, vegas_wp, vegas_home_wp, wp-derived
market columns, club_spread, implied_total, opponent_implied_total, moneyline, spread_line_raw,
total_line (TEAM_GAME). pbp is loaded with an explicit `usecols` allowlist; the script asserts no
forbidden column is in the loaded frame.

Regular season only. Seasons 2021-2025; 2026 **weeks 1-4 only** (an assertion refuses any 2026
week >= 5 row anywhere in the frame). Player fantasy uses 2021-2025 only (PLAYER_GAME 2026 holds
weeks 1-3 only, so no 2026 player fold).

Known caveat: nflverse `epa` comes from an EP model fitted by nflverse on multi-season history; the
EP model's own training may include seasons later than g. It does not contain game g's outcome
for game g's feature (features use only earlier games), but it is a mild, disclosed look-ahead in
the *scale* of EPA.

## 3. Variables (all point-in-time, all shrunk)

Play admission: `play_type in {pass, run}`, `qb_kneel == 0`, `qb_spike == 0`,
`two_point_attempt == 0`, `epa` not missing. A play is a **dropback** if `pass == 1` (includes sacks
and scrambles), otherwise a **rush**.

Per defence d and game, numerators and denominators:

| Id | Variable | Numerator | Denominator |
|---|---|---|---|
| D1 | def EPA/play allowed | sum epa (all admitted plays vs d) | plays |
| D2 | def EPA/dropback allowed | sum epa (dropbacks) | dropbacks |
| D3 | def EPA/rush allowed | sum epa (rushes) | rushes |
| D4 | pressure rate generated | count(sack==1 or qb_hit==1) | dropbacks |
| D5 | explosive rate allowed | count(dropback & yards>=20, or rush & yards>=10) | plays |
| D6 | opponent OFFENCE points centre | opponent points scored (TEAM_GAME) | games |
| D7 | opponent points allowed | points allowed by opponent (TEAM_GAME) | games |
| D8 | own pass-protection x opp pressure (matchup, EXPLORATORY) | own pressure allowed (same def as D4, offence side) | dropbacks |

**Point-in-time rule.** For club c playing opponent d in game g = (season S, week W): use only
games with (season, week) strictly before (S, W): current-season games of d in weeks < W, plus
season S-1. Same-week earlier games (e.g. Thursday before Sunday) are excluded — conservative.

**Formula** (identical for every variable):

    value = (N_cur + w_p * N_prv + k * m * mu) / (D_cur + w_p * D_prv + k * m)  -  mu

- `w_p = PRIOR_GAMES / G_prv` with `PRIOR_GAMES = 4.0` (the incumbent's declared prior-season
  weight, `proj_v1.TEAM_VOLUME_PRIOR_GAMES`; no new carry-over coefficient), `G_prv` = games d
  played in S-1. So the whole prior season counts as 4 games, as in the incumbent.
- `mu` = league-wide rate over the same point-in-time pool (all clubs, season S weeks < W plus
  season S-1); `m` = league mean denominator per club-game in that pool. No data -> value 0.
- 2021 has no 2020 pbp in the repository, so for D1-D5, D8 in 2021 the prior term is empty
  (D6, D7 use 2020 TEAM_GAME points, which exist).
- **k (games-equivalent shrinkage) is estimated, per variable and per fold, from that fold's
  training seasons only**, by split-half method of moments over team-seasons: per-game rates
  r_tg; tau^2 = mean over training seasons of the across-team covariance of the odd-game and
  even-game half-season rates (each half = ratio of sums), corrected to single-season scale
  (tau^2 is the covariance itself); sigma^2_game = pooled within-team-season variance of per-game
  rates; **k = sigma^2_game / tau^2**, clipped to [1, 200]. If tau^2 <= 0 the variable is declared
  NO_RESOLVABLE_SIGNAL for that fold, set identically to 0, and its coefficient is not estimated.
  Justification: the only prior evidence the author holds (W6) was measured on a test season and
  shows reliabilities ranging over an order of magnitude across these variables, so any single
  a-priori k would be a silent constant; a training-only estimator is an empirical estimate and
  does not touch held-out seasons. Sensitivity (EXPLORATORY, no verdict): k fixed at 4 and at 17.

## 4. Targets

Club level (PRIMARY): club pass attempts, club rush attempts, club points (TEAM_GAME definitions).

Position-group fantasy (SECONDARY): sum of `dk_points_current_rules` over the club's players with
an opportunity row at QB / RB / WR / TE in the club-game.

Player fantasy (SECONDARY, if time permits): player `dk_points_current_rules` in games where the
player has an opportunity row (conditional-on-appearing; declared, not hidden), by position.

## 5. Arms

- **INC-RAW**: the engine's own-offence centre, unchanged: current-season per-game mean through
  W-1 weighted by its games, plus prior-season per-game mean weighted by 4 pseudo-games
  (`football_points.expected_points` logic, applied to each target). For pass/rush attempts 2020
  is a sentinel, so 2021 is CURRENT_ONLY. Rows with no history (incumbent undefined) are dropped
  from all arms. For position groups/players: same blend of that unit's own DK points per game.
- **INC-R** (the comparison incumbent): OLS on training rows `y = a + b*INC-RAW + h*is_home`.
  Recalibrating the incumbent the same way as the candidate isolates the opponent term from a
  mere refit gain. INC-RAW vs INC-R is reported too.
- **CAND-FULL** (the single primary candidate, same for every target): INC-R plus
  `beta_2*D2 + beta_3*D3 + beta_4*D4 + beta_5*D5 + beta_6*D6 + beta_7*D7`, OLS on training rows
  only. (D1 is omitted from the primary as near-collinear with D2+D3.) Fitted separately per
  target and, for fantasy, per position.
- EXPLORATORY (no verdict): INC-R + each single D_j; CAND-OL = CAND-FULL + own pressure-allowed +
  (own pressure-allowed x D4); k sensitivity.

Predictive distribution for CRPS: empirical, `prediction + {training residuals of that arm}`
(no parametric assumption); CRPS computed exactly for that ensemble.

## 6. Evaluation design

- Forward-chained folds: **F1** train 2021-2023 -> test 2024; **F2** train 2021-2024 -> test 2025.
  SUPPLEMENTARY (no verdict): **F3** train 2021-2025 -> test 2026 weeks 1-4 (club level only;
  these weeks have already been seen by the project).
- Unit: club-game (two per game).
- Subsets (labels only, never features): **STABLE** = the club's starting QB (TEAM_GAME
  `starting_qb_id`, realised starter) equals the starter in each of the club's previous 3 games
  (crossing seasons; 2020 starters used for early 2021); **QB_CHANGE** = differs from at least
  one; UNLABELLED if fewer than 3 prior games (in pooled analysis only).
- Uncertainty: paired cluster bootstrap of the score difference (CAND-FULL minus INC-R),
  B = 2000, seed 20261009, three cluster schemes: (i) season-week blocks, (ii) game_id,
  (iii) club. **Acceptance uses the widest interval of the three.** Percentile intervals.
- Multiplicity: three primary club targets -> Bonferroni, A1 uses the 98.33% interval
  (alpha 0.05/3). Fantasy position groups: four positions -> 98.75% for A1 (secondary).
- Calibration: OLS slope and intercept of actual on predicted, held-out pooled, with bootstrap
  CI (week blocks), by target and (fantasy) by position.

## 7. Acceptance bars (per target; PASS requires all four)

- **A1 (improvement):** pooled held-out (2024+2025) dCRPS = CRPS(CAND-FULL) - CRPS(INC-R): upper
  bound of the Bonferroni interval (widest cluster scheme) < 0.
- **A2 (persistence):** dCRPS point estimate < 0 in 2024 and in 2025 separately, and pooled
  dMAE point estimate < 0.
- **A3 (non-inferiority by subset):** in STABLE and in QB_CHANGE (pooled held-out), 95% upper
  bound (widest scheme) of dMAE < +0.02 x INC-R MAE in that subset. Subset with n < 100
  club-games -> NOT_EVALUABLE.
- **A4 (calibration):** held-out pooled calibration slope of actual on CAND-FULL in [0.80, 1.20]
  and |mean(actual - pred)| <= 0.05 x mean(actual).

Fantasy position groups: the same four bars per position (A3 within each position).
A verdict of PASS is a research verdict only; it does not promote anything.

## 8. What voids the study

- Any feature for game g found to use a game with (season, week) >= g's (a truncation self-test
  recomputes features for a random sample of 60 club-games from data truncated before g and must
  match exactly).
- Any forbidden market column present in a loaded frame; any 2026 week >= 5 row.
- Held-out coverage < 95% of regular-season club-games with targets and features defined.
- This file changed after test-season results were seen without a new version and stated reason.

## 9. Status of the evidence

2024 and 2025 have been used elsewhere in the project (W6 measured 2024; QB studies used 2024-25).
They are untouched **for this question and these variables**, which makes F1/F2 a valid
forward-chained out-of-sample test of these specific prespecified models, but not a sealed
holdout of the project. Promotion would additionally require: a prospective 2026 test on weeks
not yet played (week 5 onward), declared before those games, and an owner decision.
