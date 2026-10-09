# Accounting repair: integration evaluation, 2026-10-09

SHADOW ONLY. Nothing is promoted or wired into production. Branch `claude/showdown-accounting-repair`, evaluated at `9e207a4d`, python3.12.3, 2,000 worlds per slate. Machine-readable twin: `INTEGRATION_EVALUATION_2026-10-09.json`.

**Power.** two games, 79 player-games (44 with incumbent mean >= 1 DK), 4 DST-games. Development data, exploratory only; per-game values are the evidence, and no word like calibrated, unbiased or correct applies.

## Verdicts

| question | verdict | basis |
|---|---|---|
| a distributional_calibration | **DAMAGE_DETECTED** | historical dispersion benchmark (receivers); the outcome-based comparison has no power and detects nothing either way |
| b projection_means | **DAMAGE_DETECTED** | paired mean drift on identical raw worlds; skill-player means are not preserved |
| c lineup_selection | **NOT_MEASURABLE** | one game; lineup quality cannot be measured. The CHANGE is measured and is large |
| d valid_game_outcomes | **DAMAGE_DETECTED** | world-level club scores vs 2021-2025 regular-season final scores (pbp) |

DST: which arm is closer to history? **REPAIRED (both anchors share DST draws)**.

## Slates

- **TB_DAL_2026W5** evaluated. Scenario `nfl/dfs/salaries/showdown_tb_dal/OFFICIAL`. Reproduction: max |DK diff| 0.0 over 49 players, live data. Actuals: git show be87cb0d:nfl/postgame/showdown_tb_dal_2026W5/TB_DAL_2026W5_POSTGAME.json (player_actuals dk_A).
- **ATL_NO_2026W4** evaluated. Scenario `nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX (the production upload 8f4d9a77)`. Reproduction: max |DK diff| 0.0 over 30 players ONLY with NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json (cutoff 2026-10-05T23:47:26Z). Without it the runner refuses INCUMBENT_NOT_REPRODUCED (max |DK diff| 8.0): both kickers differ, because the live pbp capture 2b3e9f2c holds week 4, the game itself (docs/SHOWDOWN_BASELINE_REPRODUCTION.md F3). Actuals: nfl/postgame/showdown_atl_no_2026W4/ATL_NO_POSTGAME_ACTUAL.json (player_actuals dk_A; dk_B differs only for Daniel Carlson, 6 vs 5).
- **PIT_CLE_2026W4** skipped: nfl/dfs/salaries/SHOWDOWN_TONIGHT_{PROJ,STATE,DRAWS}.json is an earlier pipeline: the DRAWS carry no tag, projection_sha256 or state_sha256 (the runner refuses at its first check), the PROJ has no int_rate (the incumbent efficiency step cannot run), and showdown_draws.build on those inputs with the published seed 20261001 reproduces 0 of 45 players (worst |DK diff| 50.5). No PIT manifest exists for it, and the live pbp holds the game. The nfl/research/showdown_live/2026_04_PIT_CLE artifacts are post-kickoff rebuilds ("sealed after kickoff: DESCRIPTIVE ONLY") with no PROJ/STATE.
- **PHI_CHI** skipped: only DK contest standings exist (nfl/postgame/raw/showdown_history/196036243_PHI_CHI); no frozen pregame projection, state or draws anywhere in the repository.

## (a) Distributional calibration

Outcome-based: n = 79 player-games from 2 games (44 with incumbent mean >= 1 DK). Central-interval coverage rises under the repair and CRPS is worse in both games overall, better in both games for skill players and worse in both for DST (4 DST-games). With two game clusters none of this separates from noise; nothing here may be read as "calibrated". Against history: every skill player's DK distribution is wider in the repaired arm, and for receivers the repaired SD exceeds the historical within-player-season SD at matched mean -- itself an UPPER benchmark for a conditional single-game SD -- in most cases, where the incumbent sat below it. The repair also moves the receptions-yards and receptions-TD correlations most of the way to their historical values. Coherence improved; receiver dispersion now looks too wide.

Outcome-based, per player DK (FLEX). CRPS is the exact empirical CRPS from the 2,000 draws; PIT is the mid-PIT; coverage uses empirical central quantiles. Paired differences are repaired minus incumbent on the same players (negative = repaired better).

| slate | population | arm | n | mean CRPS | mean error | cov 50 | cov 80 | cov 90 | PIT mean | PIT deciles |
|---|---|---|---|---|---|---|---|---|---|---|
| TB_DAL_2026W5 | INC_MEAN_GE_1 | incumbent | 24 | 3.913 | +0.300 | 0.42 | 0.71 | 0.79 | 0.470 | 3 4 3 1 3 1 1 2 2 4 |
| TB_DAL_2026W5 | INC_MEAN_GE_1 | repaired, QB anchor | 24 | 3.975 | +0.330 | 0.50 | 0.79 | 0.79 | 0.491 | 2 3 4 2 2 2 0 3 3 3 |
| TB_DAL_2026W5 | INC_MEAN_GE_1 | repaired, receiver anchor | 24 | 3.966 | +0.510 | 0.50 | 0.79 | 0.79 | 0.483 | 2 4 3 2 3 1 0 4 2 3 |
| TB_DAL_2026W5 | SKILL_INC_MEAN_GE_1 | incumbent | 20 | 4.349 | +0.088 | 0.35 | 0.65 | 0.75 | 0.490 | 3 3 2 1 2 1 1 1 2 4 |
| TB_DAL_2026W5 | SKILL_INC_MEAN_GE_1 | repaired, QB anchor | 20 | 4.293 | -0.021 | 0.50 | 0.75 | 0.75 | 0.510 | 2 2 3 2 1 2 0 2 3 3 |
| TB_DAL_2026W5 | SKILL_INC_MEAN_GE_1 | repaired, receiver anchor | 20 | 4.282 | +0.196 | 0.50 | 0.75 | 0.75 | 0.501 | 2 3 2 2 2 1 0 3 2 3 |
| TB_DAL_2026W5 | DST_AND_K | incumbent | 4 | 1.735 | +1.361 | 0.75 | 1.00 | 1.00 | 0.374 | 0 1 1 0 1 0 0 1 0 0 |
| TB_DAL_2026W5 | DST_AND_K | repaired, QB anchor | 4 | 2.384 | +2.080 | 0.50 | 1.00 | 1.00 | 0.398 | 0 1 1 0 1 0 0 1 0 0 |
| TB_DAL_2026W5 | DST_AND_K | repaired, receiver anchor | 4 | 2.384 | +2.080 | 0.50 | 1.00 | 1.00 | 0.398 | 0 1 1 0 1 0 0 1 0 0 |
| TB_DAL_2026W5 | ALL_DRAWN | incumbent | 49 | 2.030 | +0.053 | 0.65 | 0.80 | 0.86 | 0.504 | 3 4 3 2 24 1 1 2 2 7 |
| TB_DAL_2026W5 | ALL_DRAWN | repaired, QB anchor | 49 | 2.062 | +0.067 | 0.69 | 0.84 | 0.86 | 0.516 | 2 3 4 3 21 4 0 3 3 6 |
| TB_DAL_2026W5 | ALL_DRAWN | repaired, receiver anchor | 49 | 2.058 | +0.157 | 0.69 | 0.84 | 0.86 | 0.512 | 2 4 3 3 22 3 0 4 2 6 |
| ATL_NO_2026W4 | INC_MEAN_GE_1 | incumbent | 20 | 3.563 | -0.557 | 0.60 | 0.80 | 0.85 | 0.501 | 2 0 2 5 4 0 1 2 1 3 |
| ATL_NO_2026W4 | INC_MEAN_GE_1 | repaired, QB anchor | 20 | 3.630 | -0.195 | 0.75 | 0.85 | 0.90 | 0.507 | 1 1 2 5 2 2 2 1 2 2 |
| ATL_NO_2026W4 | INC_MEAN_GE_1 | repaired, receiver anchor | 20 | 3.611 | -0.497 | 0.70 | 0.85 | 0.85 | 0.520 | 1 1 2 4 2 3 2 1 2 2 |
| ATL_NO_2026W4 | SKILL_INC_MEAN_GE_1 | incumbent | 16 | 3.758 | -1.487 | 0.56 | 0.81 | 0.88 | 0.540 | 1 0 2 4 3 0 0 2 1 3 |
| ATL_NO_2026W4 | SKILL_INC_MEAN_GE_1 | repaired, QB anchor | 16 | 3.750 | -1.210 | 0.75 | 0.88 | 0.94 | 0.550 | 0 1 2 3 2 2 1 1 2 2 |
| ATL_NO_2026W4 | SKILL_INC_MEAN_GE_1 | repaired, receiver anchor | 16 | 3.727 | -1.587 | 0.69 | 0.88 | 0.88 | 0.566 | 0 1 2 2 2 3 1 1 2 2 |
| ATL_NO_2026W4 | DST_AND_K | incumbent | 4 | 2.779 | +3.159 | 0.75 | 0.75 | 0.75 | 0.343 | 1 0 0 1 1 0 1 0 0 0 |
| ATL_NO_2026W4 | DST_AND_K | repaired, QB anchor | 4 | 3.147 | +3.863 | 0.75 | 0.75 | 0.75 | 0.334 | 1 0 0 2 0 0 1 0 0 0 |
| ATL_NO_2026W4 | DST_AND_K | repaired, receiver anchor | 4 | 3.147 | +3.863 | 0.75 | 0.75 | 0.75 | 0.334 | 1 0 0 2 0 0 1 0 0 0 |
| ATL_NO_2026W4 | ALL_DRAWN | incumbent | 30 | 2.580 | -0.490 | 0.63 | 0.77 | 0.83 | 0.495 | 3 0 2 6 10 0 1 2 1 5 |
| ATL_NO_2026W4 | ALL_DRAWN | repaired, QB anchor | 30 | 2.625 | -0.241 | 0.73 | 0.80 | 0.87 | 0.504 | 2 1 2 6 8 2 2 1 2 4 |
| ATL_NO_2026W4 | ALL_DRAWN | repaired, receiver anchor | 30 | 2.614 | -0.445 | 0.70 | 0.80 | 0.83 | 0.512 | 2 1 2 5 8 3 2 1 2 4 |
| POOLED | INC_MEAN_GE_1 | incumbent | 44 | 3.754 | -0.089 | 0.50 | 0.75 | 0.82 | 0.484 | 5 4 5 6 7 1 2 4 3 7 |
| POOLED | INC_MEAN_GE_1 | repaired, QB anchor | 44 | 3.818 | +0.091 | 0.61 | 0.82 | 0.84 | 0.498 | 3 4 6 7 4 4 2 4 5 5 |
| POOLED | INC_MEAN_GE_1 | repaired, receiver anchor | 44 | 3.804 | +0.052 | 0.59 | 0.82 | 0.82 | 0.500 | 3 5 5 6 5 4 2 5 4 5 |
| POOLED | SKILL_INC_MEAN_GE_1 | incumbent | 36 | 4.087 | -0.612 | 0.44 | 0.72 | 0.81 | 0.512 | 4 3 4 5 5 1 1 3 3 7 |
| POOLED | SKILL_INC_MEAN_GE_1 | repaired, QB anchor | 36 | 4.052 | -0.549 | 0.61 | 0.81 | 0.83 | 0.528 | 2 3 5 5 3 4 1 3 5 5 |
| POOLED | SKILL_INC_MEAN_GE_1 | repaired, receiver anchor | 36 | 4.035 | -0.596 | 0.58 | 0.81 | 0.81 | 0.530 | 2 4 4 4 4 4 1 4 4 5 |
| POOLED | DST_AND_K | incumbent | 8 | 2.257 | +2.260 | 0.75 | 0.88 | 0.88 | 0.358 | 1 1 1 1 2 0 1 1 0 0 |
| POOLED | DST_AND_K | repaired, QB anchor | 8 | 2.765 | +2.971 | 0.62 | 0.88 | 0.88 | 0.366 | 1 1 1 2 1 0 1 1 0 0 |
| POOLED | DST_AND_K | repaired, receiver anchor | 8 | 2.765 | +2.971 | 0.62 | 0.88 | 0.88 | 0.366 | 1 1 1 2 1 0 1 1 0 0 |
| POOLED | ALL_DRAWN | incumbent | 79 | 2.239 | -0.153 | 0.65 | 0.78 | 0.85 | 0.501 | 6 4 5 8 34 1 2 4 3 12 |
| POOLED | ALL_DRAWN | repaired, QB anchor | 79 | 2.276 | -0.050 | 0.71 | 0.82 | 0.86 | 0.511 | 4 4 6 9 29 6 2 4 5 10 |
| POOLED | ALL_DRAWN | repaired, receiver anchor | 79 | 2.269 | -0.072 | 0.70 | 0.82 | 0.85 | 0.512 | 4 5 5 8 30 6 2 5 4 10 |

Paired CRPS difference, repaired minus incumbent, mean per player:

| population | anchor | TB@DAL | ATL@NO | pooled |
|---|---|---|---|---|
| INC_MEAN_GE_1 | QB | +0.0618 | +0.0671 | +0.0642 |
| INC_MEAN_GE_1 | receiver | +0.0521 | +0.0483 | +0.0504 |
| SKILL_INC_MEAN_GE_1 | QB | -0.0556 | -0.0081 | -0.0345 |
| SKILL_INC_MEAN_GE_1 | receiver | -0.0672 | -0.0315 | -0.0514 |
| DST_AND_K | QB | +0.6488 | +0.3675 | +0.5082 |
| DST_AND_K | receiver | +0.6488 | +0.3675 | +0.5082 |
| ALL_DRAWN | QB | +0.0323 | +0.0455 | +0.0373 |
| ALL_DRAWN | receiver | +0.0277 | +0.0339 | +0.0300 |

Within one game a player-level bootstrap interval is anti-conservative (players share one game script); the JSON carries it with that caveat. With two game clusters a cluster bootstrap is meaningless and is not reported.

Mean error (simulated mean minus actual) and CRPS by position, pooled:

| pos | n | incumbent err | repaired QB err | incumbent CRPS | repaired QB CRPS |
|---|---|---|---|---|---|
| DST | 4 | +2.844 | +4.252 | 2.953 | 3.953 |
| K | 4 | +1.677 | +1.691 | 1.561 | 1.578 |
| QB | 10 | +1.441 | +1.411 | 0.982 | 0.985 |
| RB | 15 | -3.176 | -3.076 | 3.661 | 3.633 |
| TE | 19 | +1.027 | +1.019 | 0.771 | 0.731 |
| WR | 27 | -0.610 | -0.556 | 2.942 | 2.943 |

Against history (2021-2025 `nfl/warehouse/PLAYER_GAME.json`, DK current rules, player-seasons with >= 8 games). within-player-season SD across games includes week-to-week role and context changes that a single-game forecast conditions away, so it is an UPPER benchmark for a well-calibrated conditional SD, not a target.

| group | arm | n players | median SD / history SD | share above 1 | corr(rec, rec yds) minus history | corr(rec, rec TD) minus history |
|---|---|---|---|---|---|---|
| REC | incumbent | 20 | 0.916 | 0.25 | -0.313 | -0.303 |
| REC | repaired, QB anchor | 20 | 1.093 | 0.65 | -0.156 | -0.051 |
| REC | repaired, receiver anchor | 20 | 1.066 | 0.75 | -0.156 | -0.051 |
| RB | incumbent | 9 | 0.765 | 0.11 | -0.320 | -0.301 |
| RB | repaired, QB anchor | 9 | 0.848 | 0.11 | -0.199 | -0.068 |
| RB | repaired, receiver anchor | 9 | 0.849 | 0.11 | -0.199 | -0.068 |
| QB | incumbent | 4 | 0.908 | 0.00 |  |  |
| QB | repaired, QB anchor | 4 | 0.975 | 0.25 |  |  |
| QB | repaired, receiver anchor | 4 | 0.978 | 0.50 |  |  |

## (b) Projection means

Skill-player means move by up to about 2 DK per player, and which players move depends on the declared passing anchor: the projection does not close its own club passing game (QB yards vs the receivers' sum), so one side must move under either anchor. Rushing TDs the raw simulator had dropped into its unallocated bucket are now on player lines, raising RB/WR means. These are real changes to downstream projections that no outcome data here can adjudicate. The DST drift is the exception: see the DST section, where the incumbent is the defect.

| slate | anchor | players | abs drift > 2 paired SE | abs drift > 0.5 DK | by position: sum of drift (paired SE) |
|---|---|---|---|---|---|
| TB_DAL_2026W5 | repaired, QB anchor | 49 | 11 | 4 | DST +2.90 (0.07); K -0.03 (0.07); QB +0.03 (0.13); RB -0.27 (0.17); TE -0.80 (0.17); WR -1.11 (0.21) |
| TB_DAL_2026W5 | repaired, receiver anchor | 49 | 9 | 3 | DST +2.90 (0.07); K -0.03 (0.07); QB +1.30 (0.13); RB +0.18 (0.17); TE +0.15 (0.17); WR +0.59 (0.21) |
| ATL_NO_2026W4 | repaired, QB anchor | 30 | 11 | 5 | DST +2.73 (0.05); K +0.08 (0.06); QB -0.34 (0.14); RB +1.76 (0.14); TE +0.66 (0.16); WR +2.57 (0.21) |
| ATL_NO_2026W4 | repaired, receiver anchor | 30 | 6 | 3 | DST +2.73 (0.05); K +0.08 (0.06); QB -2.17 (0.13); RB +0.70 (0.13); TE +0.00 (0.16); WR -0.01 (0.20) |

Largest per-player drifts (repaired minus incumbent, paired SE):

- TB_DAL_2026W5, repaired, QB anchor: Cowboys|DAL +3.74 (0.07), Buccaneers|TB -0.83 (0.03), Emeka Egbuka|TB -0.83 (0.11), Cade Otton|TB -0.55 (0.09), Ted Hurst III|TB -0.41 (0.07), Chris Godwin Jr.|TB -0.37 (0.07)
- TB_DAL_2026W5, repaired, receiver anchor: Cowboys|DAL +3.74 (0.07), Jalon Daniels|TB +1.43 (0.09), Buccaneers|TB -0.83 (0.03), Cade Otton|TB +0.26 (0.10), Chris Godwin Jr.|TB +0.25 (0.08), KaVontae Turpin|DAL +0.23 (0.05)
- ATL_NO_2026W4, repaired, QB anchor: Drake London|ATL +2.09 (0.13), Saints|NO +1.98 (0.04), Bijan Robinson|ATL +1.19 (0.09), Falcons|ATL +0.75 (0.03), Kyle Pitts Sr.|ATL +0.54 (0.08), Jahan Dotson|ATL +0.41 (0.08)
- ATL_NO_2026W4, repaired, receiver anchor: Michael Penix Jr.|ATL -2.02 (0.07), Saints|NO +1.98 (0.04), Falcons|ATL +0.75 (0.03), Alvin Kamara|NO +0.36 (0.11), Bijan Robinson|ATL +0.20 (0.09), Tyler Shough|NO -0.15 (0.11)

## DST: which arm is the defect

Historical DK DST scores are integers in 100% of 2,718 club-games; the incumbent's DST draws are non-integers in 92-98% of worlds because a multiplicative anchor (TB@DAL: DAL x0.5085, TB x1.1867, from the original report) rescales DK points after scoring. Conditioned on each arm's own points-allowed draws, the repaired DST distribution matches the history-resampled one (KS 0.015-0.048) where the incumbent does not (0.09-0.37); that part is close to true by construction, since the simulator's DST tuples are resampled history, and the club-adjusted benchmark below is league-conditional plus a club residual, so the repaired arm's gap to it is just that residual. The non-circular content is the size of the club residual: measured on each club's own 2025 + 2026 pre-lock games it is TB +0.15, DAL -0.95, ATL +0.65, NO +0.58 DK (SE about 1), while the incumbent (= the DST projection) departs from the league-conditional expectation by TB +0.39, DAL -3.74, ATL -0.69, NO -1.86 DK. The clubs' own history does not support departures that large (DAL, NO) or of that sign (ATL, NO). So the incumbent DST step is the defect. The repaired arm still uses league-average tuples and drops the club-specific rates the DST projection carries; the right fix is club-adjusted COMPONENT draws, scored once, not a rescale of DK. The four realised DST scores (1, 7, 4, -3) favour the incumbent's lower numbers; n = 4, hindsight only.

History 2021-2025 REG, all clubs: mean DK DST 6.52 (SD 5.78), integer share 100%, n = 2718. Scoring: sack 1, INT 2, fumble recovery 2, safety 2, def/ST TD 6, blocked kick 2, points-allowed bands 0:+10, 1-6:+7, 7-13:+4, 14-20:+1, 21-27:0, 28-34:-1, 35+:-4 (points allowed = opponent final score; excluding opponent TDs scored against the offence moves the mean by +0.11).

| DST | projection | incumbent mean (SD) | repaired mean (SD) | incumbent non-integer | KS vs history-resampled inc / rep | club-adjusted benchmark (SE) | gap inc / rep | actual (hindsight) |
|---|---|---|---|---|---|---|---|---|
| Buccaneers|TB (TB_DAL_2026W5) | 4.31 | 4.31 (5.55) | 3.47 (4.74) | 92% | 0.091 / 0.048 | 4.07 (1.28) | 0.24 / 0.60 | 7.0 |
| Cowboys|DAL (TB_DAL_2026W5) | 3.91 | 3.91 (3.00) | 7.64 (6.02) | 97% | 0.371 / 0.019 | 6.69 (0.97) | 2.79 / 0.95 | 1.0 |
| Falcons|ATL (ATL_NO_2026W4) | 5.61 | 5.61 (5.02) | 6.37 (5.92) | 95% | 0.121 / 0.015 | 6.96 (1.24) | 1.34 / 0.59 | 4.0 |
| Saints|NO (ATL_NO_2026W4) | 6.55 | 6.55 (4.47) | 8.53 (5.99) | 98% | 0.186 / 0.034 | 8.99 (1.25) | 2.44 / 0.46 | -3.0 |

Benchmark definition: league E[DST DK | opponent-points band] over the repaired arm's own points-allowed draws, plus the club's unshrunk residual (own 2025+2026-prelock mean DK minus league-conditional mean at its own points allowed). Declared for this evaluation; no coefficient fitted; SE is roughly the residual SE.

## (c) Lineup selection (TB@DAL)

Harness validated: the incumbent draws rebuild R1 byte for byte. On repaired worlds only a small share of R1 lineups survive; DAL DST exposure is the largest single change. A diagnostic build with the incumbent DST draws restored still replaces most R1 lineups, so the skill-world changes alone move the portfolio; no seed-only overlap baseline was measured, so the replacement share cannot be judged against selection noise. Each portfolio scores better on its own worlds, as an optimiser must. Realised totals are one game, hindsight only.

Control: rebuilding on the incumbent draws reproduces R1 byte for byte: True (7 files).

| contest | lineups | R1 lineups kept by the repaired build | kept by the diagnostic build (incumbent DST) | DAL DST exposure R1 -> repaired -> diagnostic |
|---|---|---|---|---|
| 196438543 | 150 | 10 (7%) | 11 | 0.047 -> 0.347 -> 0.04 |
| 196438555 | 20 | 4 (20%) | 9 | 0.050 -> 0.350 -> 0.0 |
| 196438556 | 20 | 4 (20%) | 9 | 0.050 -> 0.350 -> 0.0 |
| ALL | 190 | 21 (11%) | 31 | 0.047 -> 0.347 -> 0.032 |

Cross-evaluation, all 190 entries: expected best lineup per world (mean lineup mean), scored on each world set; realised = one game, hindsight:

| portfolio | on incumbent worlds | on repaired QB-anchor worlds | on repaired receiver-anchor worlds | realised best / mean |
|---|---|---|---|---|
| R1_incumbent | 128.33 (89.09) | 130.36 (88.31) | 132.47 (90.11) | 130.00 / 78.69 |
| REBUILT_on_repaired_qb_anchor | 127.29 (87.05) | 131.41 (87.70) | 133.48 (89.24) | 131.20 / 76.85 |
| DIAGNOSTIC_rebuilt_on_repaired_with_incumbent_DST | 127.87 (88.44) | 130.71 (87.69) | 132.80 (89.36) | 133.59 / 79.96 |

Largest player exposure changes, all contests (R1 -> repaired): Cowboys|DAL 0.047 -> 0.347, Emeka Egbuka|TB 0.442 -> 0.311, Chris Godwin Jr.|TB 0.295 -> 0.200, Buccaneers|TB 0.221 -> 0.147, George Pickens|DAL 0.279 -> 0.332, Brandon Aubrey|DAL 0.442 -> 0.395.

Build log, last line: control: `DONE PASS SHOWDOWN_PORTFOLIO_BUILT 5387 candidates; NFL Showdown $100K mini-MAX [150 Entry M 150/150 cov 0.998; NFL Showdown $10K Quarter Jukebox [Just  20/20 cov 0.718; NFL Showdown $4K Dime Package [Just $0.1 20/20 cov 0.718 603s`; repaired: `DONE PASS SHOWDOWN_PORTFOLIO_BUILT 5648 candidates; NFL Showdown $100K mini-MAX [150 Entry M 150/150 cov 0.993; NFL Showdown $10K Quarter Jukebox [Just  20/20 cov 0.594; NFL Showdown $4K Dime Package [Just $0.1 20/20 cov 0.594 255s`; hybrid: `DONE PASS SHOWDOWN_PORTFOLIO_BUILT 5543 candidates; NFL Showdown $100K mini-MAX [150 Entry M 150/150 cov 0.993; NFL Showdown $10K Quarter Jukebox [Just  20/20 cov 0.607; NFL Showdown $4K Dime Package [Just $0.1 20/20 cov 0.607 226s`

## (d) Valid game outcomes

Impossible scores are eliminated: the incumbent's club scores are non-integers in ~98% of club-worlds and fall strictly between 0 and 2 in 0.6-1.6%; the repaired arm has none, and its points equal the event sums exactly (max gap 0.0) on both slates. But the repair introduces ties at 1.8% and 3.7% of worlds against 0.29% of historical final scores (overtime is not represented), still under-produces 3- and 7-point margins (8-11% vs 22.4%), and raises total-points dispersion relative to the drawn total. Ties do not score in DK, so the DFS cost is small; as a game-outcome model it is a defect.

| source | worlds | club score non-integer | club score in (0, 2) | club score 0 | ties | margin 3 or 7 | total mean | total SD | total p5 / p95 | points == event sum (max gap) |
|---|---|---|---|---|---|---|---|---|---|---|
| history 2021-2025 REG | 1359 games | 0.000 | 0.0000 | 0.0107 | 0.0029 | 0.224 | 45.02 | 13.65 | 24 / 69 | |
| TB_DAL_2026W5 incumbent | 2000 | 0.987 | 0.0063 | 0.0135 | 0.0000 | 0.000 | 49.86 | 13.91 | 28.4 / 73.7 | n/a (continuous draw) |
| TB_DAL_2026W5 repaired, QB anchor | 2000 | 0.000 | 0.0000 | 0.0158 | 0.0180 | 0.083 | 50.54 | 14.71 | 28.0 / 76.0 | 0.0 |
| TB_DAL_2026W5 actual | 1 game | | | | | | 40 | | | |
| ATL_NO_2026W4 incumbent | 2000 | 0.980 | 0.0155 | 0.0203 | 0.0000 | 0.000 | 40.58 | 13.85 | 19.0 / 64.0 | n/a (continuous draw) |
| ATL_NO_2026W4 repaired, QB anchor | 2000 | 0.000 | 0.0000 | 0.0288 | 0.0370 | 0.110 | 41.24 | 14.34 | 19.0 / 65.0 | 0.0 |
| ATL_NO_2026W4 actual | 1 game | | | | | | 69 | | | |

History is unconditional (all games); a single slate's conditional distribution should be narrower, so a totals SD above the historical 13.65 is wider than history, not merely different. Both arms exceed it; the repaired arm by more. The receiver-anchor arm has the same club points as the QB-anchor arm.

## Defects found in the repair itself

- **ECW-D1** no overtime: event-sum club points tie in 1.8% (TB@DAL) and 3.7% (ATL@NO) of worlds vs 0.29% of 2021-2025 final scores. (game-outcome validity; small DFS cost)
- **ECW-D2** defensive/return TD and safety points (0.65-0.89 per club-game) are added ON TOP of a drawn remainder the kicker only partly consumes; club points rise by +0.10 to +0.59 per club vs the drawn total, and total SD rises by 0.5-0.8. (mean and dispersion of club scoring; feeds DST points allowed)
- **ECW-D3** margins of 3 or 7 occur in 8.3% / 11.0% of worlds vs 22.4% in history: the FG count is a rounded share of a continuous remainder, not a drive outcome. (game-outcome shape)
- **ECW-D4** receiver DK distributions widen (every skill player, median SD ratio 1.11-1.13) and exceed the historical within-player SD benchmark for most receivers. Probably partly unmasking, not created: the incumbent's near-zero catch-TD correlation offset the raw simulator's wide yards-per-catch (CV, TB@DAL receivers with >2 catches: 0.82 incumbent, 0.72 repaired, 0.53 median in 2021-2025 history). (calibration risk; blocks promotion until measured on more slates)
- **ECW-D5** DST tuples are drawn in the band of the CONTINUOUS points allowed and scored on the event-sum points; the band differs in 372-498 of 2,000 worlds per DST. (named by the module; measured here)
- **ECW-D6** DST uses league-average conditional tuples, discarding the club-specific event rates in the DST projection. (DST mean; needs club-adjusted components)
- **ECW-D7** the club passing anchor is a free choice that moves skill means by up to ~2 DK (London +2.09 under QB anchor, Penix -2.02 under receiver anchor), because the projection itself does not close the passing game. (owner decision)
- **ECW-D8** the shadow runner does not record whether a point-in-time manifest was active. ATL@NO reproduces only under NFL_PIT_MANIFEST (without it the kickers differ by up to 8 DK and the runner refuses); the repaired arm's kicker inputs come from whatever data is live. (provenance; fail-closed today via the reproduction check)

## Promotion requirements still unmet

- End-to-end regression via nfl/tests/run_suite.py of every module that consumes worlds (showdown_portfolio, world_accounting_check, postgame graders, classic_slate_run) with the arm wired in -- NOT RUN here; only nfl/tests/test_event_consistent_worlds.py was run (74 passed).
- Classic integration via nfl/tools/classic_slate_run.py -- NOT ATTEMPTED; the arm is Showdown-only.
- Owner decision on the club passing anchor (QB vs receiver side), and on whether DST means should follow the DST projection or the simulator events.
- Club-adjusted DST component draws (replace the multiplicative DK anchor in BOTH arms) and a re-measurement against history.
- Overtime (or an explicit tie-break) in event-sum club points, and a re-check of 3/7 margin frequencies.
- Resolve the double-count of defensive/return TD and safety points against the drawn remainder (ECW-D2).
- Receiver dispersion re-measured on more slates and against a conditional (not within-season) benchmark (ECW-D4).
- A forward-chained, pre-registered evaluation on new slates with point-in-time manifests; two development games cannot establish an improvement.
- Runner records the active PIT manifest seal in its report (ECW-D8).
- A seed-only lineup-overlap baseline, so a lineup-replacement share can be read against selection noise.

## Reproduce

- atl_repaired: `NFL_PIT_MANIFEST=nfl/warehouse/pit_manifests/PIT_MANIFEST.ATL_NO_2026W4.1294f0dc638d95c9.json python3.12 nfl/research/accounting_repair/run_event_consistent_shadow.py nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX nfl/research/accounting_repair/ATL_NO_2026W4`
- history: `EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/hist.py <dir>/hist.json`
- measurements: `EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/evaluate.py <dir>/MEASUREMENTS.json`
- dispersion: `EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/dispersion.py <dir>/DISPERSION.json`
- portfolios: `python3.12 nfl/research/accounting_repair/integration_eval/build_portfolio.py <DRAWS.json> <out_dir>   (incumbent / repaired / hybrid DRAWS)`
- lineups: `EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/lineups.py <repaired_pf> <control_pf> <dir>/LINEUPS.json <hybrid_pf>`
- compose: `EVAL_WORK=<dir> python3.12 nfl/research/accounting_repair/integration_eval/compose.py`
- all with: `PYTHONPATH=<numpy/pandas site>; never -I`
