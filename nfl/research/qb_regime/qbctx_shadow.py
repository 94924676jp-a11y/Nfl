"""QBCTX shadow candidate: team volume, pass rate, QB rushing and teammate shares CONDITIONED ON THE
KNOWN PREGAME STARTER, by hierarchical partial pooling. SHADOW RESEARCH ONLY -- nothing in production
reads this module and it changes no production behaviour.

Root cause it answers: docs/QB_REGIME_ROOT_CAUSE_2026-10-08.md (proj_v1.team_volume has no QB
argument; QB rushing uses a generic cohort prior; starts and relief are pooled).

=====================================================================================================
PREDECLARATION -- written 2026-10-09 BEFORE any evaluation number was computed. Not to be edited after
results exist; any later change is appended below as a dated AMENDMENT and the original text stays.
=====================================================================================================

P1. STARTER RULE. The starter of a team-game is the passer with the most dropbacks (nflverse
    qb_dropback == 1, attributed by the `id` column, regular season, two-point tries excluded). Ties
    break on pass attempts, then on player id (deterministic). A team-game whose leader had < 60% of
    the club's dropbacks is flagged SPLIT. In the evaluation the starter so identified is treated as
    the KNOWN PREGAME STARTER (identity oracle, as in the brief); volume is not an oracle.

P2. QUANTITIES. (a) team dropbacks [primary volume quantity; pass attempts excluding sacks are
    reported as a secondary quantity with no acceptance bar]; (b) team pass rate =
    dropbacks / (dropbacks + designed runs); (c) starter QB rush attempts = his designed runs +
    his scrambles (kneels excluded); (d) teammate target shares -- REPORT ONLY, no bar.

P3. ARMS. INCUMBENT = the same quantities with no QB argument, mirroring proj_v1.team_volume (current
    season club mean blended with the prior-season club mean at TEAM_VOLUME_PRIOR_GAMES pseudo-games,
    read from proj_v1's own source) and proj_v1._combine for QB carries (QB's pooled carry share over
    every game he appeared in, starts and relief together, blended with his own prior-season pooled
    share or a generic all-QB cohort share, prior weight capped at PRIOR_WEIGHT_CAP). CANDIDATE = the
    incumbent club baseline PLUS a QB-specific deviation estimated from that QB's prior games (starts
    at weight 1; relief appearances as separate, down-weighted evidence), shrunk toward a population
    prior by empirical Bayes; QB rushing = his per-dropback rush rate from all prior games, all clubs,
    shrunk toward a position prior estimated from data. The declared treatment is the QB term; the
    club baseline is identical in both arms.

P4. POINT IN TIME. A forecast for a game dated D reads only games dated strictly before D. Asserted
    in code (PointInTimeViolation). Population priors for evaluation season S are fitted on seasons
    < S only (forward chained): S=2024 fits on <=2023, S=2025 on <=2024, the 2026 prospective run on
    <=2025.

P5. EVALUATION SEASONS 2024 and 2025, regular season, every team-game (two rows per game, one per
    club). Subsets:
      QB-CHANGE = the starter differs from the club's dominant starter of its prior window, where the
                  prior window is the club's last 8 games (crossing seasons) and the dominant starter
                  is the QB with the most dropbacks in that window;
      STABLE    = the starter equals that dominant starter.
    The PRIMARY analysis includes every team-game (SPLIT included: excluding them would condition on
    an outcome). A SENSITIVITY analysis excludes SPLIT team-games. Both are reported.

P6. METRICS per arm, subset and quantity: n, MAE, RMSE, mean error (bias, defined forecast minus
    actual). Paired cluster bootstrap of the MAE difference (candidate minus incumbent): resample
    team-season clusters with replacement within the subset, B = 4000, seed 20261009, 95% percentile
    interval.

P7. ACCEPTANCE, applied separately to each of (a) dropbacks, (b) pass rate, (c) QB rush attempts:
      PASS iff  [QB-CHANGE: MAE difference 95% CI upper bound < 0]
           AND  [STABLE:    MAE difference 95% CI upper bound <= +0.02 x incumbent STABLE MAE].
    The OVERALL candidate passes only if all three quantities pass. Pass attempts (secondary) and
    teammate shares (d) carry no bar. The bar is not loosened after results exist; a failure is
    reported as a failure.

P8. PROSPECTIVE 2026 weeks 1-5 are DESCRIPTIVE ONLY (n is tiny, and nothing is tuned to TB@DAL or to
    any 2026 game). Week 5 2026 forecasts are produced for the 16 Sunday-early clubs with the
    starters listed in WEEK5_QB_REGIME_BOARD.json.
=====================================================================================================
"""
