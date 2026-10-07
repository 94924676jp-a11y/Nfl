# SC-COH-1 clean comparison: pre-registration

Status: SHADOW_ONLY. Written 2026-10-07, before any 2025 game was scored by this harness.
Harness: `nfl/research/coherence/sc_coh_1_clean_eval.py`.
Frozen inputs (everything from 2024 or earlier): `nfl/research/coherence/SC_COH_1_CLEAN_FROZEN.json`,
sha256 `e0e4243e40b4c81f95481d3458d8e89235165fbc76178d97a20e5c97901f41c6`.
Fitted-quantity hash inside it: `fits_sha256 = 19c7928d87c47aaa1926a4b1a759f752d71067f2de1129e91e17674834c86646`.
Library hash: `607100ec74e81357680a9e2ee47cd41ef465ff240cf6a73c64644df3cea229a7`.

The harness refuses to score unless this file and the frozen file match, byte for byte, the hashes recorded in
`nfl/research/coherence/SC_COH_1_CLEAN_PREREG_LOCK.json` (`SC_COH_1_CLEAN_PREREG_CHANGED`,
`SC_COH_1_CLEAN_FROZEN_CHANGED`).

## 1. Why this exists, and what it replaces as evidence

The first SC-COH-1 pass (`SC_COH_1_MEASUREMENT.json`) counts only as development evidence:

1. its candidate picked analogue games by the nearest sportsbook `total_line` / `spread_line`
   (`sc_coh_1_candidate.py:43,104-111,323`). Market information may never enter the proprietary forecast, so that
   candidate cannot go to production;
2. its pool was players with `offense_snaps > 0` in the evaluated game itself (`sc_coh_1_measure.py:22,226-236`),
   which uses the outcome;
3. the incumbent's inputs (SHARED_STATE 2000-2026, EFFICIENCY 2021-2026, VARIANCE_COMPONENTS, USAGE, DST_MODEL)
   include 2025, and the incumbent was run on market lines rather than production's FOOTBALL_ONLY setting.

None of the old files is changed. The new output carries a `SUPERSEDES_AS_EVIDENCE` note that reclassifies them.

## 2. Units

- **club-game**: team points, team offensive TDs, team passing yards, team rushing yards, DST DK points.
- **player-club-game**: every player in the club's pregame pool (section 3). A pool player who did not play is
  scored against an actual of 0. He is part of the forecast problem and is not dropped.
- **game**: a 12-part vector: home points, away points, then DK points for the home QB, RB1, WR1, WR2, TE1 and the
  same five roles for the away side.

DK points are "DK core" for every forecaster and for the actuals: 0.04 per passing yard, 4 per passing TD, 0.1 per
rushing or receiving yard, 6 per rushing or receiving TD, 1 per reception. There are no yardage bonuses, no
interception penalty and no fumble penalty, because the simulator's raw stage draws neither interceptions nor
fumbles, and both are left out on every side rather than compared against a zero.

## 3. Eligibility: the point-in-time pool

- **Pool, SEASON_TO_DATE (primary)**: skill players (crosswalk position QB, RB, FB, WR or TE) who had at least one
  target, carry or pass attempt for this club in an earlier week of the same season.
- **Pool, LAST_GAME (secondary)**: the same, limited to the club's most recent earlier game.
- **Shares**: season-to-date (weeks before W) targets, carries and pass attempts, renormalised over the pool.
  This is the same step as `showdown_draws._shares`. QBs get no target share, and pass-attempt shares go to QBs
  only. TD shares are opportunity shares (`validate_correlations` precedent): target share for receiving TDs,
  carry share for rushing TDs (RB and QB only).
- **Roles**: QB = the pool QB with the most earlier pass attempts. WR1, WR2 and TE1 are ranked by earlier
  targets, and RB1 by earlier carries. Ties are broken by player id.
- No snap count, and no row from the evaluated game, enters the pool. Official active zero-snap players and
  game-day inactives are **NOT_IDENTIFIABLE_FROM_CURRENT_DATA**. The request for 2024-2025 nflverse weekly rosters
  and inactives is already in `docs/AGENT_OUTBOX.md` (2026-10-07). Nothing is substituted for them.
- **Scored set**: every pool player. Players who played but were not in the pool cannot be forecast by either
  forecaster. Their count and their DK points are reported as `out_of_pool_account`.
- **Game eligibility**: 2025 regular season, week 2 or later. Both clubs must have a pool with an earlier passer, a
  target and a carry. Both clubs must have a football centre and a volume centre. A game is never chosen by its
  outcome.

## 4. Training cutoff

Everything fitted uses seasons up to and including 2024. Pregame inputs for a 2025 week-W game may use 2025 weeks
before W. Those are known before kickoff, and nothing is fitted on them. The frozen values:

| Input | Procedure (production's, re-run) | Data | Frozen value |
|---|---|---|---|
| Total and margin residuals around the football centre | `football_points.build` loop | TEAM_GAME 2001-2024, 6,195 games | total SD 14.0291, margin SD 13.8508, home field +2.3011, points-allowed SD 9.9242 |
| Plays / pass-share response | `shared_state.build` OLS, clustered by game | TEAM_GAME 2021-2024, 2,174 club-games | plays 57.624 + 0.2067 per own point - 0.0350 per margin point, SD 8.180; pass share 0.5580 + 0.000895 per own point - 0.004015 per margin point, SD 0.0931 |
| Scoring inversion | `shared_state.build` | same | 6.3569 points per offensive TD, remainder 7.3977, SD 4.4771 |
| Club YPA / YPC distribution | `game.fit_efficiency` | PLAYER_GAME 2021-2024 | 2,168 / 2,168 club-games, mean 6.7018 / 4.4383 |
| Yards-share concentration | `variance_components._estimate` | PLAYER_GAME 2021-2024 | receiving 15.921, rushing 12.8961 |
| Opportunity-share concentration | `variance_components.share_dispersion` | same | targets 142.12, carries 12.858 |
| Teammate-backs concentration | `usage._teammate_decomposition` | PLAYER_GAME + ROLE_HISTORY 2021-2024 | 18.467 |
| DST points-allowed bands | `dst.build` | TEAM_GAME + pbp 2021-2024 | band sizes 180 / 415 / 617 / 523 / 439 |
| INT rate (efficiency step) | INT per attempt | pbp 2021-2024 | 0.023059 |
| Candidate library | 2021-2024 play-by-play games | 1,087 games | k = 33, centre SDs 5.7939 / 5.4383 |
| Candidate share concentration | method of moments, point-in-time pools | 2024 weeks 2-18 | targets 19.264, carries 5.2446 |

The harness recomputes all of these before scoring and refuses if they differ (`SC_COH_1_CLEAN_FITS_NOT_REPRODUCED`).

## 5. Football-only conditioning, for both forecasters

- **Scoring centre**: `football_points.expected_points` and `centre_for_game`, production's FOOTBALL_ONLY function.
  It blends the club's points per game in weeks before W with last season's per-game average, weighted as 4
  pseudo-games. It runs on a TEAM_GAME table loaded through a field whitelist (game, club, opponent, season,
  week, home flag, points, points allowed, volumes, offensive TD, margin, sacks, turnovers). `total_line`,
  `club_spread`, `implied_total`, `moneyline` and `spread_line_raw` are dropped before anything reads them.
- **Play-by-play** is read through a column whitelist. The committed files carry `total_line`, `spread_line` and
  `vegas_wp`, and the harness never loads them.
- Every source passes `guard_no_market`, which refuses any column or key containing line, odds, moneyline,
  implied, spread, vegas, vig, juice, price, sportsbook, book, market, wager or bet.
- **Incumbent**: `nfl/sim/game.py:simulate_game_centred(model, spec, volume_centre, n_sims, seed, n_calib=n_sims)`,
  which is production's Showdown call. Its game total and margin centres are the football centre, and its residuals
  are the 2001-2024 football residuals. Its volume centre follows the `proj_v1.team_volume` FOOTBALL_ONLY branch:
  pass attempts, rush attempts and targets per game for weeks before W, plus 4 pseudo-games of last season. Its
  Model is built from the section-4 refits.
- **Live transform order replayed**: S0 raw simulator, then S1 `classic_slate_run.efficiency_worlds`, then S2
  `classic_slate_run.anchor_means` on the DST draws. The efficiency rows are each player's pooled yards per
  opportunity (weeks before W plus 2024, any club). The INT rate is the frozen 0.023059. The DST anchor target uses
  the `dst_model.project` form: event rates for weeks before W, blended with 2024 at 4 pseudo-games and weighted by
  DK points, plus `dst_model.pa_expectation` around the opponent's football centre with the 2024-or-earlier
  points-allowed residuals.
- **Candidate (clean)**: the analogue-game play library. Neighbours are found by Euclidean distance on the football
  centre (total, home margin), each divided by its library SD. The library centres are computed point-in-time for
  every library game. k = round(sqrt(1,087)) = 33, a declared prior. The allocation and identities are those of
  `sc_coh_1_candidate._club_world` and `verify`, unchanged.
- **Ways the replay differs from the live path** (declared up front):
  - shares are not proj_v1 projections;
  - TD shares are opportunity shares;
  - the efficiency rows and the DST target are recomputed rather than taken from proj_v1;
  - kickers are not simulated, and only the kicker remainder is counted;
  - the football_sanity gate and role_state are not run;
  - the SHARED_STATE refit drops production's filter that requires a market line to exist.

## 6. Development and confirmation split

- **Development**: 2025 weeks 2-9. Used only to debug the pipeline. No model, metric, margin or design choice is
  made on it. It may be re-run, and each run is numbered. During development the harness cuts the 2025 data to
  weeks 9 and earlier right after loading.
- **Confirmation**: 2025 weeks 10-18. It is read **once**, by the code of the last development run, at the
  registered settings (400 worlds, both pool modes, all games). A second read, a code change since development, or
  any setting off the registration is refused (`SC_COH_1_CLEAN_CONFIRMATION_ALREADY_READ`,
  `..._CODE_CHANGED_SINCE_DEVELOPMENT`, `..._CONFIRMATION_NOT_AS_REGISTERED`).
- After the lock, the only harness changes allowed are bug fixes. Each one is recorded in `DEVIATIONS` and written
  into the output.

Why this split: the season has to be split forward in time. Weeks 2-9 have the thinnest point-in-time inputs, so
they suit debugging. Weeks 10-18 give the confirmation slightly more than half of the games.

## 7. Missing-input policy

- A club-game without an earlier passer, target or carry, or with no earlier game at all, is excluded, with its
  reason listed.
- A game with no football centre or volume centre is excluded and listed.
- If the incumbent refuses a game (for example `VOLUME_CENTRE_NOT_RECONCILED`), that game is excluded from **both**
  forecasters and listed.
- A missing role (no TE1, for instance) takes that game out of the joint vector and that role's Brier event only.
  It is never read as zero.
- An absent actual stat line for a pool player is the outcome 0. That is a forecast miss, not missing data.

## 8. Metric panel

All scores are computed from draws: 400 worlds per game per forecaster. Lower is better for every score.

- **Marginal CRPS** on every unit variable.
  - Club-game: team points, offensive TDs, passing yards, rushing yards, DST DK.
  - Player-club-game: DK core, receptions, targets and receiving yards (RB, WR, TE); carries, rushing yards and
    scrimmage TDs (all positions); passing yards and passing TDs (QB).
  - Estimator: mean |X - y| - 0.5 mean |X - X'| over all M² pairs.
- **Count log score**, only where both forecasters' draws and the actual are whole numbers. p̂ = max(count, 0.5) / M,
  a half-draw floor. The number of floored events is reported. A comparison is reported only if both supports
  qualify.
- **Randomised PIT**: u = F(y-) + V(F(y) - F(y-)), with V uniform on (0, 1) and seed 20261010. The output is a
  10-bin histogram per forecaster, plus the sum of absolute bin deviations from uniform. This is descriptive, not a
  test.
- **Coverage**: central 50 / 80 / 90% intervals taken from draw quantiles (`inverted_cdf`), inclusive. For discrete
  outcomes coverage at or above nominal is expected by construction.
- **Energy score** and **variogram score** (p = 0.5, all pairs i < j, weight 1) on the 12-part game vector. Each
  part is divided by its fixed 2024 SD: team points 9.8443, QB 10.1805, RB1 8.9255, WR1 9.483, WR2 7.9435,
  TE1 6.9684.
- **Brier scores**, thresholds frozen at the 2024 90th percentile (event = actual ≥ threshold):
  - team points ≥ 36.0
  - offensive TDs ≥ 4.0
  - QB DK ≥ 27.374
  - RB1 DK ≥ 25.2
  - WR1 DK ≥ 24.88
  - WR2 DK ≥ 19.7
  - TE1 DK ≥ 17.29
- **Fixed normalisation scales** (2024 SDs over the 2024 scoring set, for any scaled summary):
  - player DK 7.9194, receptions 2.2473, targets 3.1349, receiving yards 28.5177, carries 4.3871, rushing yards
    21.9319, scrimmage TDs 0.4391, passing yards 125.2647, passing TDs 1.1324
  - team points 9.8443, offensive TDs 1.4046, passing yards 70.6316, rushing yards 51.8296, DST DK 5.4806
- **Structure (coherence) statistics** against 2025 history, the first pass's 15 statistics. Equivalence margins
  were set from 2024 or earlier: for each statistic, the largest change between consecutive seasons in 2021-2024
  history, using the same point-in-time pools.

| Statistic | Margin | | Statistic | Margin |
|---|---|---|---|---|
| team DK vs team points | 0.0712 | | WR1 vs WR2 | 0.1159 |
| team DK vs offensive TD | 0.0313 | | QB vs RB1 | 0.1038 |
| yards per extra TD | 1.8105 yd | | RB1 vs own DST | 0.1391 |
| pass yards vs pass TD | 0.0402 | | RB1 vs opposing QB | 0.0510 |
| QB vs WR1 | 0.1699 | | QB vs opposing QB | 0.1009 |
| QB vs WR2 | 0.0598 | | QB vs opposing DST | 0.1485 |
| QB vs TE1 | 0.0608 | | team DK vs opponent team DK | 0.0644 |
| | | | team points vs opponent points | 0.2107 |

A statistic is labelled `WITHIN_PREDECLARED_EQUIVALENCE_MARGIN_TOST` only if the 90% interval of (forecaster minus
history) lies strictly inside ± the margin under **both** blocking schemes. Every other case is
`NOT_SHOWN_EQUIVALENT`. At about 120-140 games most intervals will be wider than these margins, so most labels will
be NOT_SHOWN_EQUIVALENT. That is a fact about the sample size, not evidence of a gap. Nothing else may be called
matched.

## 9. Uncertainty

- **Game-blocked bootstrap**: resample games, keeping both clubs and all players of a game together.
- **Week-blocked bootstrap**: resample weeks, keeping every game in a week together.
- 2,000 resamples, seed 20261009. Means are ratio-of-sums, and every comparison is paired, so both forecasters are
  scored on identical unit sets (`SC_COH_1_CLEAN_UNPAIRED` otherwise).
- Intervals are 95% percentile intervals for the difference and the ratio (candidate over incumbent), plus 90%
  intervals for the equivalence test.
- Simulation seeds are 20261008 plus the game's index, in game_id order within the phase. Both forecasters get the
  same seed.

## 10. Decision rule (confirmation, primary pool SEASON_TO_DATE, CANDIDATE_RAW vs INCUMBENT_PROD)

| Endpoint | Test | Passes if the ratio's upper 95% bound, under BOTH blocks, is |
|---|---|---|
| P1 energy score (game vector) | superiority | < 1.00 |
| P2 variogram score (game vector) | superiority | < 1.00 |
| P3 team-points CRPS | non-inferiority | < 1.02 |
| P4 player DK CRPS | non-inferiority | < 1.02 |

The rule is conjunctive: all four must pass. So the joint claim needs no multiplicity adjustment.

The 1.02 non-inferiority margin (at most 2% worse) is a **declared value judgement**, and the owner may override
it. Every other comparison is secondary and descriptive.

Passing gives the shadow label `ALL_FOUR_PASSED`. It promotes nothing.

## 11. Stop rules

1. Any accounting-identity violation in the candidate's raw stage raises `SC_COH_1_IDENTITY_VIOLATED` and stops
   the run.
2. Empty or partial input at any stage stops the run with a named error. A zero is never reported as a result.
3. After confirmation has been read, nothing in either phase is scored again.
4. Whatever the result, STATUS stays SHADOW_ONLY. No production file is changed, and nothing is promoted.
5. A model change after confirmation needs a new registration, a new holdout and a new name.

## 12. Inventory of every scored variant

| Forecaster | Stage | Role |
|---|---|---|
| INCUMBENT_PROD | S2: simulator, then efficiency_worlds, then DST anchor | primary incumbent |
| INCUMBENT_RAW | S0: simulator only | secondary |
| CANDIDATE_RAW | S0: analogue library | primary candidate |
| CANDIDATE_POST | S2: library, then efficiency_worlds, then DST anchor | secondary |

Each forecaster runs with each of the two pool modes, SEASON_TO_DATE (primary) and LAST_GAME (secondary), in each
of the two phases. That gives 4 × 2 × 2 = 16 scored arms.

Paired comparisons:
- CANDIDATE_RAW vs INCUMBENT_PROD (primary)
- CANDIDATE_RAW vs INCUMBENT_RAW
- CANDIDATE_POST vs INCUMBENT_PROD

Earlier trials on the same 2025 season, listed so they are counted:
- first-pass incumbent (market lines, snap pool)
- first-pass candidate (market analogues, snap pool)
- first-pass k sensitivity at k/2 and 2k

They are not re-run here. No k sensitivity is run in this registration.

## 13. Conservation counts

Conservation is counted after **every** stage (S0, S1, S2), for each forecaster, per player-world and per
club-world:

- receiving yards with zero receptions
- receiving TD with zero receptions
- receiving TDs > receptions
- receptions > targets
- rushing TD with zero carries
- rushing TDs > carries
- rushing yards with zero carries
- passing yards with zero attempts
- team offensive TDs ≠ passing TD + rushing TD. Declared: no other offensive TD type; non-scrimmage TDs belong to
  the DST.
- QB passing yards ≠ sum of receiving yards (> 0.5 yd). Declared exception: laterals, which only history can show.
- QB passing TDs ≠ sum of receiving TDs
- points < 6 × offensive TDs
- kicker remainder negative even if every XP is good (points < 7 × TD). This can happen in real games through
  missed XPs and two-point tries, so the history count is reported alongside.
- non-integer points
- DST DK ≠ tier(opponent points) + its components
- opposing QB interceptions > DST takeaways (S1 and later, once interceptions exist)

DST sacks against opponent sack events are NOT_IDENTIFIABLE_IN_DRAWS: no offence stat line in either simulator
carries sacks. The same counters run on the actual games as the baseline.
