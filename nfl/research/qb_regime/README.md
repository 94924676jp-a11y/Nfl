# QBCTX shadow candidate: conditioning on the starting QB (2026-10-09)

**Status: SHADOW RESEARCH. Nothing in production reads this.** No production module changed.
Branch `claude/qbctx-shadow-research`. The predeclaration was committed on its own as `dd440398`,
before any result existed.

## What was asked

The root cause is in `docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md`. `proj_v1.team_volume` takes no QB
argument, QB rushing falls back to a generic cohort prior, and starts are pooled with relief
appearances.

The brief was to forecast four things for a team-game whose starter is known before kickoff:

- team dropbacks;
- pass rate;
- the starter's rush attempts;
- teammate target shares.

The method is hierarchical partial pooling with empirical-Bayes shrinkage, compared against an
incumbent that has no QB argument. The evaluation is forward-chained on 2024 and 2025 under a
predeclared bar. Separately, 2026 is described (not evaluated) and Week 5 forecasts are produced.

## What was done

- `qbctx_shadow.py` holds the model, the evaluation and the outputs. Its docstring carries the
  predeclaration (P1-P8) and amendment A1. Run it with
  `PYTHONPATH=<numpy/pandas> python3.12 nfl/research/qb_regime/qbctx_shadow.py`, about 70 s.
- `QBCTX_SHADOW_EVAL.json` holds:
  - every metric and CI, the verdict and n per subset;
  - the fitted priors for each forecast season;
  - the provenance of every constant;
  - the fingerprint (module and input sha256);
  - the 2026 descriptive run.
- `QBCTX_W5_2026_FORECASTS.json` has, for each of the 16 Sunday-early clubs, incumbent and
  candidate forecasts with 80% intervals, the evidence used and the teammate shares.
- `nfl/tests/test_qbctx_shadow.py` covers:
  - the starter rule;
  - named errors on empty input;
  - the incumbent mirroring proj_v1;
  - recovery of known variances on synthetic data;
  - that the bootstrap is paired and seeded;
  - the TB 2026 regime facts;
  - the point-in-time guard: it rejects a seeded violation, and when bypassed the leaked future
    changes the forecast;
  - artifact self-consistency: the stored verdict recomputes from the stored CIs.

  Harness result: `python3.12 nfl/tests/run_suite.py --modules test_qbctx_shadow` gives
  **10 functions, 39 checks, 0 failing, SUITE PASS** (an explicit-module run, not a full-suite result).

## Model (as run)

**Starter.** The passer with the most dropbacks. Ties break on pass attempts, then on player id.
A game is flagged SPLIT when the leader had less than 60% of the dropbacks. In 2024-25 that was 22 of
1,088 team-games.

**Incumbent.** Club baseline:
- the current-season club mean, blended with the prior-season mean at `TEAM_VOLUME_PRIOR_GAMES` = 4
  pseudo-games;
- that constant is read from the proj_v1 source;
- the market response is not applied.

QB rush attempts:
- carry share is computed with the `_combine` rule;
- the prior is his own prior-season carry share, or the cohort share; its weight is capped at
  `PRIOR_WEIGHT_CAP` = 2;
- the current-season share pools starts and relief together;
- the share is multiplied by the club's carries.

The full list of what is approximated is in `INCUMBENT_APPROXIMATION` in the artifact: no recency
decay, no tier ladder, no roster renormalisation, no market response.

**Candidate.** The same club baseline, plus a QB term:
- the QB term is `(S_START - c) x E[Delta_q | his prior games]`;
- `c` is the QB's share of the baseline's composition;
- `Delta_q` is his contrast against the other QBs in that composition.

Each prior club-game counts as evidence with exposure `a = f - c`, where `f` is his dropback share
in that game:
- a start under another QB's baseline has `a` close to 1;
- a regular starter's start has `a` close to 0, so it carries no information;
- a relief cameo has a small `a`;
- a game he missed has `a = -c`.

The between-QB variance `tau2` and the game noise `s2` are fitted by profile maximum likelihood on
prior seasons only. The prior mean is 0; that is the owner's ruling against a universal backup-QB
penalty.

QB rushing is his per-dropback rush rate over all prior games for all clubs:
- relief appearances are weighted by an estimated inverse-variance ratio;
- the rate is shrunk toward a position prior that is estimated from the data;
- the rate is multiplied by the candidate dropbacks and by `S_START`.

**Amendment A1, disclosed.** The first implementation used a plain mean residual. Fitting its priors
showed that a regular starter's residual against his own baseline is close to 0 by construction, so
`tau2` was about 1 against `s2` of about 67. In that version one start moved the forecast by only
1-2% of what it showed. I replaced it with the exposure model above. This was done after the priors
were fitted and before any evaluation metric existed. P1-P8 and the bar are unchanged, and the
original text is kept in the docstring.

## Predeclared bar (P7)

For each of dropbacks, pass rate and QB rush attempts, the candidate PASSES only if both hold:
- on QB-CHANGE games, the 95% CI of the MAE difference (candidate minus incumbent) is entirely below 0;
- on STABLE games, the upper bound of that CI is at most +2% of the incumbent's STABLE MAE.

The overall result is a pass only if all three quantities pass. The bootstrap is paired, resamples
team-season clusters, and uses B = 4000 with seed 20261009.

QB-CHANGE means the starter is not the dominant starter (by dropbacks) of the club's prior 8 games.

## Result: the candidate FAILS overall (1 of 3 quantities pass)

Primary analysis: all 2024-25 regular-season team-games. Bias is forecast minus actual. Pass rate is
in percentage points.

| Subset | Quantity | n (team-season clusters) | Incumbent MAE | Candidate MAE | MAE diff [95% CI] | RMSE inc / cand | Bias inc / cand |
|---|---|---|---|---|---|---|---|
| QB_CHANGE | dropbacks | 303 (53) | 6.912 | 6.696 | -0.216 [-0.394, -0.040] | 8.525 / 8.335 | +0.656 / +0.511 |
| QB_CHANGE | pass_rate (pp) | 303 (53) | 8.434 | 8.245 | -0.189 [-0.480, +0.065] | 10.241 / 10.035 | +0.940 / +0.610 |
| QB_CHANGE | qb_rush | 303 (53) | 1.750 | 1.670 | -0.079 [-0.201, +0.037] | 2.399 / 2.192 | -0.594 / +0.216 |
| QB_CHANGE | pass_att (secondary) | 303 (53) | 6.477 | 6.122 | -0.355 [-0.588, -0.119] | 7.917 / 7.627 | +0.474 / +0.264 |
| STABLE | dropbacks | 785 (64) | 6.395 | 6.407 | +0.011 [-0.021, +0.043] | 8.149 / 8.149 | +0.258 / +0.308 |
| STABLE | pass_rate (pp) | 785 (64) | 8.076 | 8.089 | +0.014 [-0.029, +0.056] | 10.146 / 10.143 | +0.188 / +0.234 |
| STABLE | qb_rush | 785 (64) | 1.525 | 1.545 | +0.021 [-0.013, +0.054] | 2.017 / 2.037 | +0.061 / +0.109 |
| STABLE | pass_att (secondary) | 785 (64) | 6.082 | 6.087 | +0.006 [-0.035, +0.043] | 7.680 / 7.672 | +0.210 / +0.284 |

| Quantity | QB-change improves (CI upper bound < 0) | Stable non-inferior (upper bound <= margin) | Verdict |
|---|---|---|---|
| dropbacks | yes (-0.040) | yes (0.043 <= 0.128) | **PASS** |
| pass rate | no (+0.065 pp) | yes (0.056 <= 0.162 pp) | **FAIL** |
| QB rush attempts | no (+0.037) | **no** (0.054 > 0.030) | **FAIL** |
| **Overall** | | | **FAIL** |

The sensitivity analysis excludes SPLIT games (n = 288 QB-change and 778 stable) and gives the same
verdicts. For QB rush on QB-change games the upper bound there is +0.007, still not below 0.

**What the table supports:**
- The QB term gives a small, real improvement in team dropbacks on QB-change games: -0.22 MAE, about
  3%.
- It also improves pass attempts (secondary): -0.35, CI excludes 0.
- It costs nothing measurable on stable games for volume.

**What it does not support:**
- On QB rushing the candidate shrinks RMSE and bias on QB-change games: RMSE 2.40 to 2.19, bias
  -0.59 to +0.22. Its MAE gain does not clear the bar, though.
- On stable games the candidate's QB rushing is slightly worse (+0.021 MAE). Its upper bound exceeds
  the predeclared +2% margin.

**Per season, descriptive:**
- Dropbacks on QB-change games improved in both 2024 and 2025 (-0.21 and -0.22).
- Neither season's CI excludes 0 on its own.

**Teammate target shares (report only, outcome-conditioned player set):**
- On QB-change games the change is -0.011 pp MAE, CI [-0.039, +0.013] pp.
- That is effectively no change. The between-player variance is small: `tau2` = 3.3e-4 against a
  per-game `s2` of 3.4e-3, so one shared game gets a shrink of about 0.1.

## 2026 weeks 1-5: descriptive only, nothing tuned

On QB-change team-games (n = 34) the candidate was worse than the incumbent:
- dropbacks: MAE 6.50 against 6.08;
- pass attempts: 5.84 against 5.19;
- QB rush: about equal, 1.54 against 1.54.

On stable games (n = 96) volume was about equal. QB rush was worse for the candidate: 1.70 against 1.52.

n is far too small for any inference. Nothing is tuned to these games.

**TB with Jalon Daniels.** He has one prior start (week 4) and one relief appearance (week 3).

| Game | Quantity | Actual | Incumbent | Candidate |
|---|---|---|---|---|
| W4 GB@TB (first start) | dropbacks | 36 | 38.9 | 39.0 |
| | pass attempts | 27 | 32.9 | 33.0 |
| | pass rate | 0.590 | 0.639 | 0.641 |
| | QB rush | 8 | 2.25 | 3.41 |
| W5 TB@DAL | dropbacks | 31 | 38.5 | 38.3 |
| | pass attempts | 25 | 32.1 | 31.2 |
| | pass rate | 0.492 | 0.633 | 0.628 |
| | QB rush | 5* | 3.65 | 5.92 |

\*In W5 he had 5 scrambles and 2 kneel-downs. Kneels are excluded by definition P2. The brief's 7
counted them.

**How the candidate used the week-4 start for week 5:**
- Rush rate: the raw rate of 0.222 per dropback was shrunk halfway (shrink 0.53) toward the position
  prior of 0.089, giving 0.159.
- Volume contrast: the raw -2.15 dropbacks was shrunk to -0.28 (shrink 0.13). His start gave 36
  dropbacks against a 38.9 baseline, so the data says one start of this size barely moves team
  volume.

**What that means for TB:**
- The candidate fixes most of the rushing gap.
- It does **not** explain TB's W5 volume and pass rate (31 dropbacks, 49% pass rate). That was not
  predictable from his week-4 game. One start informs; it did not dominate, as the owner ruled.

## Week 5 2026 forecasts: shadow, Sunday-early slate

The intervals are 80% empirical out-of-sample error quantiles for the same arm and subset, taken from
2024-25. Starter ids were resolved from the 2026 weekly roster.

| Club | Starter | Subset (dominant prior-8) | Dropbacks inc / cand [cand 80%] | Pass att inc / cand | Pass rate inc / cand | QB rush inc / cand [cand 80%] |
|---|---|---|---|---|---|---|
| CHI | Tyson Bagent | QB_CHANGE (C.Williams) | 37.6 / 37.6 [26.7, 48.5] | 33.2 / 34.2 | 0.548 / 0.530 | 1.56 / 3.76 [1.2, 6.2] |
| CIN | Joe Burrow | STABLE (J.Burrow) | 41.6 / 42.0 [31.2, 52.1] | 38.4 / 38.8 | 0.675 / 0.676 | 2.23 / 2.29 [0.0, 4.8] |
| CLE | Deshaun Watson | STABLE (D.Watson) | 36.3 / 35.6 [24.9, 45.8] | 30.9 / 29.1 | 0.626 / 0.623 | 5.44 / 4.54 [2.2, 7.1] |
| GB | Jordan Love | STABLE (J.Love) | 36.5 / 36.7 [25.9, 46.8] | 33.6 / 33.9 | 0.627 / 0.630 | 1.15 / 1.98 [0.0, 4.5] |
| HOU | C.J. Stroud | STABLE (C.Stroud) | 39.8 / 39.6 [28.9, 49.8] | 35.5 / 35.3 | 0.634 / 0.632 | 2.42 / 2.57 [0.2, 5.1] |
| IND | Daniel Jones | STABLE (D.Jones) | 35.6 / 35.7 [25.0, 45.9] | 32.5 / 32.6 | 0.585 / 0.585 | 3.21 / 4.93 [2.6, 7.5] |
| LV | Kirk Cousins | STABLE (K.Cousins) | 36.2 / 36.4 [25.7, 46.6] | 32.7 / 33.7 | 0.606 / 0.608 | 0.95 / 1.09 [0.0, 3.6] |
| MIA | Malik Willis | STABLE (M.Willis) | 31.5 / 29.3 [18.6, 39.5] | 26.9 / 23.5 | 0.584 / 0.558 | 4.16 / 6.04 [3.7, 8.6] |
| MIN | Kyler Murray | STABLE (K.Murray) | 33.2 / 32.5 [21.7, 42.6] | 28.0 / 27.1 | 0.585 / 0.571 | 3.24 / 4.15 [1.8, 6.7] |
| NE | Drake Maye | STABLE (D.Maye) | 36.5 / 36.5 [25.8, 46.7] | 30.1 / 30.1 | 0.599 / 0.600 | 4.67 / 4.59 [2.2, 7.1] |
| NO | Tyler Shough | STABLE (T.Shough) | 44.3 / 44.6 [33.9, 54.8] | 39.6 / 39.8 | 0.658 / 0.660 | 3.69 / 4.01 [1.6, 6.6] |
| NYG | Jameis Winston | QB_CHANGE (J.Dart) | 34.1 / 35.7 [24.8, 46.6] | 29.4 / 31.6 | 0.556 / 0.569 | 1.59 / 2.29 [0.0, 4.7] |
| NYJ | Geno Smith | QB_CHANGE (B.Cook) | 34.9 / 35.6 [24.7, 46.6] | 28.9 / 29.5 | 0.607 / 0.620 | 2.66 / 2.34 [0.0, 4.8] |
| PIT | Aaron Rodgers | STABLE (Aa.Rodgers) | 38.6 / 38.6 [27.9, 48.8] | 35.3 / 35.4 | 0.648 / 0.649 | 0.68 / 1.12 [0.0, 3.7] |
| TEN | Cam Ward | STABLE (C.Ward) | 35.9 / 35.9 [25.1, 46.0] | 31.6 / 31.5 | 0.639 / 0.639 | 2.79 / 2.10 [0.0, 4.6] |
| WAS | Jayden Daniels | QB_CHANGE (M.Mariota) | 36.1 / 37.2 [26.3, 48.2] | 30.7 / 30.7 | 0.593 / 0.597 | 6.49 / 7.86 [5.3, 10.3] |

**MIN is STABLE under the predeclared rule, but the board flags a regime change.** Murray has 84
dropbacks in MIN's last 8 games, against 69 for McCarthy and 47 for Wentz.
`WEEK5_QB_REGIME_BOARD.json` names Wentz as the dominant passer, so the board and this rule disagree.
That disagreement is not resolved here.

**NYJ is QB_CHANGE although Geno Smith started all four 2026 games.** Brady Cook's late-2025 games
still give Cook the most dropbacks in the 8-game window. Both are consequences of the brief's
predeclared rule, and I report them rather than change it.

## Constants and their provenance

All are in `CONSTANTS_PROVENANCE` in the artifact.

**Read from production source:**
- `TEAM_VOLUME_PRIOR_GAMES` = 4.0, from proj_v1;
- `PRIOR_WEIGHT_CAP` = 2.0, from proj_v1.

**Specified by the brief:**
- `SPLIT_THRESHOLD` = 0.60;
- `DOMINANT_WINDOW` = 8. It only defines the subsets;
- evaluation seasons 2024 and 2025;
- 95% CI;
- the +2% non-inferiority margin.

**Documented priors:**
- `MU0` = 0, the owner's ruling against a universal backup penalty. The empirical mean of r/a where
  |a| > 0.5 is about -1 dropback; it is reported and not used;
- `TEAMMATE_WINDOW` = 8;
- the relief rush weight is capped at 1;
- `INTERVAL_LEVEL` = 0.80, a reporting choice.

**Predeclared:** B = 4000, seed 20261009.

**Derived:** exposure `a = f - c`. The blend weights reproduce proj_v1's blend exactly; this is
tested.

**Estimated on prior seasons only.** Values are given for forecast seasons 2024 / 2025 / 2026.

| Quantity | tau2 | s2 |
|---|---|---|
| Dropbacks | 7.83 / 7.90 / 9.94 | 65.9 / 66.5 / 65.7 |
| Pass attempts | 15.4 / 12.9 / 14.4 | — |
| Pass rate | 0.0010 / 0.0018 / 0.0016 | about 0.0101 |

For dropbacks, the likelihood-ratio statistic against tau2 = 0 is 5.0 / 9.6 / 21.2.

| Parameter | Value |
|---|---|
| Rush position prior p0 | 0.087 / 0.089 / 0.089 per dropback |
| Rush tau2 | 0.0043 / 0.0042 / 0.0038 |
| Rush s2 | 0.125 per dropback |
| Relief rush weight | 0.040 / 0.049 / 0.046 |
| S_START | 0.969 |
| Cohort carry share | 0.112 |
| Teammate tau2 | 3.3e-4 / 3.0e-4 / 3.9e-4 |
| Teammate s2 | 3.4e-3 |

## Limitations

- **Starter identity is an oracle.** It is the dropback leader, applied as if known before the game.
  A starter injured early can make the backup the "starter". The SPLIT sensitivity analysis covers
  this.
- **The incumbent is an approximation of proj_v1, not proj_v1 itself.** In particular my cohort carry
  share of 0.112 is more generous than the production ARCHETYPE value of 0.068. That makes my
  incumbent's QB rushing stronger than production's: TB W5 is 3.65 here against 3.39 in production.
- **The QB contrast is relative to whoever else was in the composition.** It is not a portable QB
  effect, and it confounds game script in relief and missed-game rows.
- **Teammate shares use an "active" proxy** (at least one target or carry) and are evaluated on an
  outcome-conditioned player set.
- **No opponent, coaching, mobility features or market are used.** The owner's correction plan names
  these as further pooling levels.
- **Treat the result as development evidence.** 2024-25 was forward-chained, and the bar was
  predeclared before any result. Even so, amendment A1 was made after inspecting the fitted priors.

## Still open, and what needs the owner

- Whether a 1-of-3 pass is worth taking forward as a dropbacks-only shadow arm. The pass-attempts
  result points the same way. Promoting anything to production is the owner's decision.
- The CLAUDE.md status line reads "NFL-0, no predictive model; NFL-1 not authorised". This module
  forecasts, so it may sit in tension with that line. It was built as a SHADOW research candidate
  under the correction plan in the root-cause doc (steps 1-4). The owner should confirm that this is
  within scope.
- The disagreement between the QB-change rule and the regime board for MIN.
- Pre-existing failures noticed while running the meta-tests. Neither is caused by this change:
  - `test_discovery_boundary` counts 45 discovery primitives against a baseline of 42; no hit is in
    these files;
  - `test_suite_harness_tally` flags `test_designations_from_injuries.py`.
