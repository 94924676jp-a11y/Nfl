"""Gate 5: the OAS1 pre-declaration, as LITERALS A TEST READS FROM CODE.

WHY THIS IS A PYTHON MODULE AND NOT ONLY A MARKDOWN FILE

The repository has already caught a threshold loosening silently: a Contract 4
document claimed a precedent of eighteen of twenty while
`nfl/tools/draw_contract3.py` set `BATCH_AGREEMENT = 19`. Prose and code
disagreed and the prose was the softer number. That is the template for how a
pre-registration stops constraining anything.

So every threshold, grid and rule below is a literal in code. The companion
markdown quotes this module; a test asserts the two agree; and the fitting
code imports these names rather than restating their values.

NOTHING IN THIS MODULE MAY BE EDITED AFTER A WEEK-2 CANDIDATE IS FITTED. A
changed threshold is a new pre-registration with a new identity, and the old
one is preserved.
"""
from __future__ import annotations

import numpy as np

SPEC_VERSION = 'oas1-preregistration-1'
DECLARED_AT = '2026-09-17'
DECLARED_BEFORE_ANY_WEEK2_FIT = True

# ---------------------------------------------------------------- 1. DATA
TRAINING_SEASONS = (2025, 2026)
PRIOR_SEASON = 2025
FORECAST_SEASON = 2026
FORECAST_WEEK = 2
#: 2024 is captured and is HISTORY ONLY for the baseline chain. It is not a
#: training season for the Week-2 candidate, because the declared carryover
#: depth is one prior season.
HISTORY_ONLY_SEASONS = (2024,)
SEASON_TYPES_FITTED = ('REG',)

# ---------------------------------------------------------------- 2. TARGET
TARGET = 'oas1_epa_target'
TARGET_SOURCE_COLUMN = 'epa'
TARGET_EXEMPTION = 'nfl.ingest.allowlist.assert_oas1_epa_target'
TARGET_USED_AS = 'REGRESSION TARGET ONLY; feature use refused'

# ------------------------------------------------- 3. PLAY CLASSIFICATION
#: A sack and a scramble are PASS plays. Declared, and asserted in
#: `test_oas1_frame`.
PLAY_CLASS_RULE = ('pass if pass_attempt == 1 or sack == 1 or '
                   'qb_scramble == 1; else rush if rush_attempt == 1; else '
                   'excluded')
SACKS_IN_CLASS = 'pass'
SCRAMBLES_IN_CLASS = 'pass'
DESIGNED_QB_RUNS_IN_CLASS = 'rush'

# ------------------------------------------------------------ 4. EXCLUSIONS
GARBAGE_TIME_RULES = ('none', 'A', 'B')
GARBAGE_TIME_SEARCH_SPACE = ('none', 'A', 'B')
GARBAGE_TIME_USES_MODEL_DERIVED_COLUMN = False
PENALTY_HANDLING = 'excluded from V1, counted, and reversible'
KNEEL_HANDLING = 'excluded'
SPIKE_HANDLING = 'excluded'
OVERTIME_HANDLING = 'included and flagged, so a sensitivity check can drop it'
PLAYOFF_HANDLING = 'retained in the frame, excluded by filter'
NO_PLAY_HANDLING = 'excluded'
SPECIAL_TEAMS_HANDLING = 'excluded'
EXCLUSIONS_PRESERVED = True

# ------------------------------------------------------- 5. SEARCH SPACES
LAMBDA_GRID = tuple(float(x) for x in np.logspace(-1, 4, 12))
HALF_LIFE_GRID = (2.0, 4.0, 8.0, 16.0, float('inf'))
RHO_GRID = (0.5, 0.7, 0.85, 1.0)
KAPPA_GRID = (0.0, 1.0, 5.0, 20.0, 100.0, 500.0)
MIN_PLAYS_GRID = (0, 20, 50)

# ------------------------------------------------------- 6. FORWARD CHAIN
FOLD_RULE = ('for a forecast of season S week W, the fitting set is every '
             'play with ordinal < S*100 + W, and nothing else')
INNER_K = 8
INNER_METRIC = 'mae'
ORDINAL_GUARD_IS_AN_ASSERTION = True
ONE_SE_RULE = True
TIE_BREAK_ORDER = ('max lambda', 'max kappa', 'min rho', 'max half_life',
                   'max min_plays')
TIE_BREAK = ('among configurations within one standard error of the best '
             'mean score, select the most shrunken, in TIE_BREAK_ORDER')

# --------------------------------------------------------- 7. BASELINE SET
BASELINES = ('B0', 'B1', 'B2', 'B3', 'B4', 'B5')
DECISIVE_COMPARATOR = 'B5'
BASELINES_BUILT_BEFORE_CANDIDATE = True
IDENTICAL_ROWSETS_REQUIRED = True

# ------------------------------------------------------------- 8. SCORING
PRIMARY_SCORE = ('out-of-sample play-level MAE on oas1_epa_target against '
                 'B5, clustered by game, in a forward chain, with the '
                 'interval excluding zero')
SECONDARY_SCORES = ('rmse', 'crps', 'calibration_slope',
                    'clustered_delta_by_game', 'clustered_delta_by_team')
CALIBRATION_SLOPE_BAND = (0.7, 1.3)
CLUSTER_UNITS = ('game', 'team')
CLUSTER_REPORTING_RULE = 'when the two disagree materially, report the wider'
R_BOOT = 2000

# ----------------------------------------------------------- 9. PROMOTION
PROMOTION_CRITERION = (
    'OAS1 is promotable ONLY IF all of: (a) it beats B5 on PRIMARY_SCORE with '
    'a game-clustered interval excluding zero; (b) it also beats B4, so the '
    'gain is not shrinkage alone; (c) its calibration slope lies in '
    'CALIBRATION_SLOPE_BAND; (d) sharpness is improved at MATCHED coverage, '
    'not sharpness alone; (e) design rank is recorded at every step and the '
    'claim is restricted to steps where the model was identified.')
NEGATIVE_RESULT_ACTION = (
    'if OAS1 does not beat B5 out of sample, OAS1 is recorded as a MEASURED '
    'NEGATIVE for early-season weeks and B5 is used for the early-season '
    'opponent layer. No retuning until OAS1 wins, no strata added, no gate '
    'weakened. Re-evaluate around week 6 when the schedule graph has '
    'connected.')
STATE_SPACE_BLOCKED_UNTIL = (
    'an identified mid-season OAS1 fit beats B5 out of sample')

# -------------------------------------------- 10. IDENTIFICATION AND WEEK 2
STRUCTURAL_DEFICIENCY = 2
WEEK1_DESIGN_COLS = 66
WEEK1_RANK = 32
WEEK1_DEFICIENCY = 34
WEEK1_COMPONENTS = 32
WEEK1_COMPONENT_SIZE = 2
WEEK2_CONSTRUCTION = (
    'prior-season IDENTIFIED strengths plus a governed Week-1 update. NOT a '
    '2026 Week-1 ridge presented as having learned separate offense and '
    'defense strengths: that design is rank 32 of 66 with 32 two-node graph '
    'components, so 32 dimensions carry no information from the data.')
MIN_SAMPLE_RULES = (
    'a unit with fewer than min_plays current-season plays is reported with '
    'n_plays_current_season and prior_weight_effective attached, and '
    '`identified` is False whenever design_rank < design_cols - '
    'STRUCTURAL_DEFICIENCY')

# --------------------------------------------- 11. SINGLE-ADJUSTMENT OWNER
ADJUSTMENT_OWNER = 'oas1'
ADJUSTMENT_APPLIED_AT = 'team_volume'
ADJUSTMENT_NAMES = ('opponent_pass_offense', 'opponent_rush_offense',
                    'opponent_pass_defense', 'opponent_rush_defense')
ADJUSTMENT_MAY_BE_APPLIED_ONCE = True
ADJUSTMENT_REGISTRY_REQUIRED_BEFORE_DOWNSTREAM = True

# -------------------------------------------------------------- SIGN
SIGN_CONVENTION = ('positive offensive strength = better offense; positive '
                   'defensive strength = WORSE defence')

#: What this pre-registration does NOT claim, recorded so a later reader does
#: not infer it.
NOT_CLAIMED = (
    'that opponent adjustment improves any forecast; that EPA is the right '
    'target; that the target is reproducible against future revisions of the '
    'source file; that a Week-2 estimate is a measurement of opponent '
    'quality.')
