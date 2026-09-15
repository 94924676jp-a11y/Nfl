"""What the V1 candidate configuration IS, in one readable table.

WHY THIS MODULE EXISTS. The owner's ruling is explicit: the canonical
entrypoint must be able to invoke the candidate configuration, it must stay
explicit and non-default, it must name every rehearsal-only component actually
active, and -- the load-bearing clause -- *"it must remain impossible for this
candidate mode to masquerade as the default/promoted production model."*

Impossible, not merely discouraged. So the mode is a DECLARED SET, not a pile
of boolean flags threaded through call sites. A component that is on has a row
here carrying its governance status and its pre-registration; a component with
no row cannot be switched on at all; and the artifact writes the resolved set
verbatim, so "which model produced this number" is answered by the artifact
rather than by reconstructing an invocation.

NOTHING HERE IS PROMOTED. Engineering integration is not prospective
validation. Every component below is REHEARSAL_ONLY and stays that way until
an owner artifact says otherwise -- which no code path can produce.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome            # noqa: E402

# The two configurations the entrypoint can run. PRODUCTION_BASELINE is the
# default and contains no candidate component.
PRODUCTION_BASELINE = 'PRODUCTION_BASELINE'
V1_CANDIDATE = 'V1_CANDIDATE'
V1_CANDIDATE_R5 = 'V1_CANDIDATE_R5'
V1_CANDIDATE_R6 = 'V1_CANDIDATE_R6'
V1_CANDIDATE_R7 = 'V1_CANDIDATE_R7'
V1_CANDIDATE_R8 = 'V1_CANDIDATE_R8'
V1_CANDIDATE_R9 = 'V1_CANDIDATE_R9'
V1_CANDIDATE_R10 = 'V1_CANDIDATE_R10'
V1_CANDIDATE_R11 = 'V1_CANDIDATE_R11'
V1_CANDIDATE_R12 = 'V1_CANDIDATE_R12'
V1_CANDIDATE_R13 = 'V1_CANDIDATE_R13'
#: R9 PLUS THE APPROXIMATED 2026 WEEK-1 PARTICIPATION NUMERATOR.
#: A SEPARATE IDENTITY ON PURPOSE. The accepted Stage-2 estimator is ewma_hl2
#: over TRUE pass_snaps. For 2026 week 2 that numerator does not exist --
#: pbp_participation was never captured and `offense_players` is absent from
#: the play-by-play -- so this arm feeds it a numerator APPROXIMATED from the
#: team dropback rate. Same estimator, DIFFERENT ESTIMAND. Running it under the
#: R9 name would be the accepted arm impersonated by an approximation, which is
#: the defect this registry exists to prevent.
V1_CANDIDATE_R9_W1P = 'V1_CANDIDATE_R9_W1P'
MODES = (PRODUCTION_BASELINE, V1_CANDIDATE, V1_CANDIDATE_R5,
         V1_CANDIDATE_R6, V1_CANDIDATE_R7, V1_CANDIDATE_R8,
         V1_CANDIDATE_R9, V1_CANDIDATE_R10, V1_CANDIDATE_R11,
         V1_CANDIDATE_R12, V1_CANDIDATE_R13, V1_CANDIDATE_R9_W1P)

# Every mode that is a CANDIDATE, derived so a new one cannot escape a guard
# by not being added to a hand-written list. See `assert_not_promoted`.
CANDIDATE_MODES = tuple(m for m in MODES if m != PRODUCTION_BASELINE)

# component -> what it does, what governs it, and what it changes.
# `engine_flag` is the argument football_engine.run_game receives.
COMPONENTS = {
    'R2': {
        'what': 'QB dropback level owned by D1 x QB3 and apportioned by '
                'largest remainder; QB V1 supplies conditional rates only',
        'replaces': 'the composition that divided one level by another',
        'predeclaration': 'nfl/research/r2/'
                          'predeclaration_qb_level_ownership_r2.md',
        'predeclaration_sha256':
            '3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c',
        'governance': 'REHEARSAL_ONLY -- engineering integration, not '
                      'prospective validation',
        'engine_flag': 'r2',
    },
    'C0': {
        'what': 'cold-start quarterbacks kept in the slate so allocated share '
                'reaches a modelled QB state',
        'replaces': 'a 2.3-6.9% dropback share leaving the system',
        'predeclaration': 'nfl/research/own3/predeclaration_own3.md',
        'predeclaration_sha256':
            'aedced9c82f74b5b406e4658ddf8b435fc1582fdfc0e7d759a5a7ff3b5f07c82',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'include_cold_start',
    },
    'C3': {
        'what': 'one passing event: the target budget comes from the throw '
                'process and the passer line is credited from the receiving '
                'event',
        'replaces': 'passing and receiving yards/TDs drawn independently',
        'predeclaration': 'nfl/research/xl1/predeclaration_xl1.md',
        'predeclaration_sha256':
            '60fe3fbc0f35933e7bd4b43c56fb0afb68d95de67b4f51699a878ceb488d94da',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'shared_pass',
    },
    'A3G': {
        'what': 'the two teams in a game share one coupled draw index; '
                'marginals unmoved by construction',
        'replaces': 'two independently drawn teams, and game totals whose '
                    'spread was the sum of independent marginals',
        'predeclaration': 'nfl/research/a3g/predeclaration_a3g.md',
        'predeclaration_sha256':
            'd3620883e52fd6d2da9b56403a219210e82e52d5a65bf73cbd23f1d13d4e78ea',
        'governance': 'REHEARSAL_ONLY -- its own pre-registered verdict did '
                      'NOT clear; integrated on corrected clauses recorded in '
                      'predeclaration_a3g_addendum_01.md',
        'engine_flag': 'game_coupling',
    },
    'SC1': {
        'what': 'the scramble/carry joint state is made coherent by permuting '
                'which draw index receives which carry value, so team carries '
                '>= QB scrambles in every draw',
        'replaces': 'two levels drawn on one index from independent '
                    'randomness, whose tails crossed into a negative '
                    'rush-play budget',
        'predeclaration': 'nfl/research/sc1/predeclaration_sc1.md',
        'predeclaration_sha256':
            'b62e48f23b5f3a16fb633e5286e575f23d7de3e07c8ebf923255d8d565e76729',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'rushing_a1',
    },
    'A1': {
        'what': 'single-owner rushing: one multinomial partitions the '
                'rush-play budget across kneel / designed QB / RB / WR / TE / '
                'fringe, so every carry has exactly one owner',
        'replaces': 'a QB rush draw that could exceed the carry pool it sits '
                    'inside',
        'predeclaration': 'nfl/research/own8/predeclaration_own8.md',
        'predeclaration_sha256':
            '90f6ecc37bcee427177f183be03374c13ec87fe1e14d667a4457c797748789db',
        'governance': 'REHEARSAL_ONLY',
        'engine_flag': 'rushing_a1',
    },
}

# The flag values the candidate mode resolves to. Kept beside the table so a
# reader can see the whole configuration without running anything.
V1_CANDIDATE_FLAGS = {
    'r2': True,
    'include_cold_start': True,
    'shared_pass': 'c3',
    'game_coupling': 'off_snaps',
    'rushing_a1': True,
}


# R5. THE ACTIVE-ROSTER POOL, AS A SEPARATE CONFIGURATION IDENTITY.
#
# V1_CANDIDATE is the immutable control and is unchanged, flag for flag. R5 is
# V1_CANDIDATE plus one repair, so any difference between the two runs is
# attributable to that repair and to nothing else.
#
# THE DEFECT, MEASURED. `p4c_params.class_point_forecast` returns an EWMA of a
# player's prior APPEARED class shares -- a share conditional on him playing --
# and the allocator uses it as a relative weight over whatever roster it is
# handed. The fitting panel holds 14.6 WR/TE/RB per team-game with C summing to
# 1.24. The prospective entrypoint hands it the full weekly roster: 22 and 23
# players for SF@LA, C summing to 2.25 and 2.04. The simplex divides by that
# sum, halving every real starter share.
#
# Of the 45 SF/LA WR/TE/RB roster rows, 29 are ACT, 10 DEV (practice squad),
# 3 RES and 3 CUT. Filtering to ACT restores the pool to 14 and 15 -- the size
# the estimator was fitted for -- without removing a single player who could
# take a snap.
#
# NO CONSTANT IS INTRODUCED AND NOTHING IS TUNED. The filter is a roster fact.
R5_FLAGS = dict(
    r2=True, include_cold_start=True, shared_pass='c3',
    game_coupling='off_snaps', rushing_a1=True,
    active_roster_only=True,
)

R5_REPAIR = {
    'component': 'R5',
    'what': 'restrict the allocation pool to players whose roster status is '
            'ACT. Originally non-QB only; the quarterback pool was exempt and '
            'is no longer, so this sentence was widened to match behaviour '
            'rather than leaving the two to drift apart',
    'replaces': 'an unfiltered weekly-roster pool that included practice '
                'squad, reserve and released players',
    'defect': 'P4C weights are conditional-on-appearing shares consumed as '
              'unconditional weights over an unfiltered roster, so the vector '
              'is not a partition and normalisation halves every starter',
    'evidence': 'historical pool 14.6/team-game with sum(C)=1.24; unfiltered '
                '2026 pool 22.5 with sum(C)=2.14; ACT-filtered 14.5 with '
                'sum(C)=1.46',
    'governance': 'REHEARSAL_ONLY',
    'introduces_no_constant': True,
}


# R6. THE ROLE-CONDITIONAL PRIOR, INHERITING R5.
#
# R6 = R5 + one thing: the P4C class weight becomes a player's own history
# shrunk toward his POINT-IN-TIME DEPTH TIER, instead of falling back to a
# positional mean that prices a team's second option and its ninth alike.
#
# Historical realised target share by tier, 2020-2025: WR1 22.7%, WR2 18.3%,
# WR3 13.3%, WR4+ 6.1% -- a 3.7:1 spread the positional mean collapses to 1:1.
# The participation prior it competes with runs at 1.39:1 where the realised
# snap ratio is 2.5:1, so it is too flat even as a snap quantity.
#
# NO CONSTANT IS CHOSEN. The shrinkage weight is n/(n+k) with k estimated from
# the panel as within-player over between-player variance: WR 0.87, TE 0.78,
# RB-targets 1.54, RB-carries 0.74. With a long history the weight goes to one
# and a player's own value is returned untouched.
R6_FLAGS = dict(R5_FLAGS)
R6_FLAGS['role_prior'] = True

R6_REPAIR = {
    'component': 'R6',
    'what': 'class weight = own history shrunk toward point-in-time depth tier',
    'replaces': 'a positional-mean fallback that is blind to role',
    'defect': 'the weight is role-blind where it has no history, and the '
              'participation prior it competes with is flat at 1.39:1 against '
              'a realised 2.5:1 in snaps and 3.7:1 in targets',
    'evidence': 'realised target share by point-in-time tier over 3,230 '
                'team-games: WR1 22.7 / WR2 18.3 / WR3 13.3 / WR4+ 6.1 pct',
    'shrinkage': 'n/(n+k), k estimated from within/between player variance',
    'governance': 'REHEARSAL_ONLY',
    'introduces_no_constant': True,
    'inherits': 'R5',
}


R7_FLAGS = dict(R6_FLAGS)
R7_FLAGS['appearance_r7'] = True

R7_REPAIR = {
    'component': 'R7',
    'what': 'the appearance mechanism is refitted on the panel UNIONED with the '
            'point-in-time depth listing, with depth rank as a feature, the '
            'absence streak reset at the season boundary, and the '
            'no-history-and-unlisted cell declined rather than scored',
    'replaces': 'a fit whose training frame drops a player after four missed '
                'games, so long absence is a marker of having played',
    'defect': 'appearance rate by consecutive games missed on the frozen panel '
              'is 0.825 / 0.406 / 0.201 / 0.165 and then 0.958 at four, where '
              '2,454 of 2,563 rows are appearances. The censoring point is '
              'model.LOOKBACK_CANDIDATE = 4 and it sits inside the range the '
              'featuriser encodes',
    'evidence': 'forward-chained, identical rows, 2022-2025: Brier '
                '0.13701->0.11730, 0.12806->0.10833, 0.12503->0.10864, '
                '0.15114->0.13646; team-week-blocked 95% intervals on the '
                'difference exclude zero in all four seasons',
    'declines': 'no prior frame row AND no depth listing -- appearance rate '
                '1.0000 with zero variance, which is a construction, not an '
                'estimate',
    'governance': 'REHEARSAL_ONLY',
    'introduces_no_constant': True,
    'inherits': 'R6',
}


# R8 REPLACES R7's MECHANISM RATHER THAN STACKING ON IT. Two appearance
# mechanisms in one configuration would be two answers to one question, so the
# R7 flag is removed rather than left set, and run_forecast refuses outright if
# both ever appear together.
R8_FLAGS = {k: v for k, v in R7_FLAGS.items() if k != 'appearance_r7'}
R8_FLAGS['appearance_r8'] = True

R8_REPAIR = {
    'component': 'R8',
    'what': 'one appearance model whose regime moves with the evidence: every '
            'current-season participation quantity enters weighted by '
            'w = n_cur / (n_cur + k), and the depth block is interacted with '
            '(1 - w), so depth carries the cold start and participation takes '
            'over as a player accumulates games',
    'replaces': 'choosing between two models by week number',
    'defect': 'R7 beat the frozen mechanism in weeks 1-4 and lost to it from '
              'week 5. A calendar switch would reproduce that table and learn '
              'nothing, and would hand the wrong model to a player who signs '
              'in week 9 with as little current-season evidence as one in '
              'week 1',
    'k': 'ESTIMATED, never chosen: within-player over between-player variance '
         'of player-season appearance rates. 4,073 player-seasons with at '
         'least four games give within 0.139520, between 0.114588, k = 1.2176',
    'evidence': 'forward-chained 2022-2025 on identical rows, Brier by regime '
                'V1 / R7 / R8: week 1 0.24667 / 0.10966 / 0.06321; weeks 2-4 '
                '0.18146 / 0.11510 / 0.10049; weeks 5-9 0.11213 / 0.11814 / '
                '0.10345; weeks 10-18 0.10975 / 0.11989 / 0.10611. R8 beats '
                'both in every regime and every team-week-blocked interval '
                'excludes zero',
    'no_week_number_in_the_design': True,
    'inherits_every_r7_refusal': (
        'point-in-time depth selection, no today-chart substitution, the '
        'three-state appearance vocabulary, the explicit season boundary, and '
        'the declined no_history_and_not_depth_listed cell'),
    'governance': 'REHEARSAL_ONLY',
    'introduces_no_constant': True,
    'inherits': 'R7',
}


# R9 REPLACES THE QUARTERBACK ROOM'S ALLOCATOR, AND NOTHING ELSE.
#
# R8's room is `qb3_lib.allocate`, which draws WHICH quarterback is the
# primary and then resamples that man's share from the cell's UNCONDITIONAL
# pool -- a pool in which 47.35% of the (rank 1, not-previous-primary)
# observations are exactly zero. The two steps disagree by construction:
# `P(share = 0 | he is the primary)` is 0.0000 by the definition of primary,
# and the pool it draws from says 0.4735. On tonight's board that put a
# 0.4120 probability of ZERO DROPBACKS on a healthy depth-chart QB1.
#
# The cohort that decides it is week-1 depth-chart QB1s, 2021-2024: 128
# quarterbacks, of whom ZERO recorded a zero-dropback game. Forward-chained,
# R8's mechanism assigns that population a mean 0.1982 and a maximum 0.456;
# R9's assigns a mean 0.0278 and a maximum 0.137. No floor, clip or minimum
# exists anywhere in the module -- the zero mass falls because the starter is
# DEFINED as the taker of dropback one, which makes P(db = 0 | started) an
# identity rather than an estimate.
#
# THE HONEST PART. This is EXPLORATORY. The season-boundary hypothesis was
# selected on this same historical panel before the module existed, so the
# forward chaining controls parameter leakage and says nothing about
# specification leakage. Three cells remain open and are recorded rather than
# smoothed: in-season rank-1 not-previous-primary is still under-assigned by
# 0.187, rank-2 zero mass is a trade rather than a strict improvement, and
# two quarterbacks at five-plus dropbacks on tonight's KC room sits at 9.8%
# against a realised season-opener rate of 3.12%.
R9_FLAGS = dict(R8_FLAGS)
R9_FLAGS['qb_allocator'] = 'qb_room_v2'

R9_REPAIR = {
    'component': 'R9',
    'what': 'the quarterback room allocates an INTEGER dropback count through '
            'an explicit starter/exit/replacement state, instead of drawing a '
            'share from a pool that contradicts the identity it drew',
    'replaces': 'qb3_lib.allocate, which stays frozen and is still the R8 '
                'configuration; this is a successor lineage, not an edit',
    'defect': 'the primary is drawn, then that player\'s share is resampled '
              'from the cell\'s unconditional pool, 47.35% of which is zero '
              'in the (rank 1, not previous primary) cell',
    'evidence': 'week-1 depth-chart QB1, 2021-2024, n=128, realised '
                'zero-dropback games 0/128. Forward-chained mean P(zero): R8 '
                '0.1982 (max 0.456, 39.8% at or above 0.25) vs R9 0.0278 '
                '(max 0.137, 0.0% at or above 0.25). Overall Brier 0.1305 -> '
                '0.1148',
    'structural_guarantee': 'the starter is defined as the taker of dropback '
                            '1, so P(dropbacks = 0 | started) = 0 is an '
                            'identity; tested against a poisoned parameter '
                            'set carrying the arithmetic form of the defect',
    'introduces_no_constant': True,
    'no_floor_clip_or_minimum': True,
    'governance': 'EXPLORATORY -- the hypothesis was selected on this panel, '
                  'so forward chaining controls parameter leakage only. A '
                  'confirmatory result needs untouched games.',
    'open_and_not_smoothed': [
        'in-season rank-1 not-previous-primary under-assigned by 0.187',
        'rank-2 zero mass is a trade, not a strict improvement',
        'two QBs at 5+ dropbacks on KC tonight is 9.8% vs a realised 3.12%',
        'a starter injured on the opening kickoff would be scored a '
        'non-starter; rare, definitional, and stated rather than papered over',
    ],
    'inherits': 'R8',
}


# R10 REPLACES THE APPEARANCE MECHANISM R8 INTRODUCED AND R9 INHERITED, AND
# NOTHING ELSE. The R9 quarterback room is carried over untouched.
#
# THE TWO DEFECTS, both in the appearance path, both changing the design
# matrix, and therefore ONE candidate rather than two: a run carrying one of
# them is not a control for the other.
#
#   1. `appearance_r8.featurise` encoded `f_weeks_since_appear` as
#      `min(v or 9, 9) / 9.0` -- the only numeric in the block with a value
#      and no missingness indicator, through a FALSY test. `None` (never
#      seen), `0` (appeared in the most recent game) and `9+` (gone all
#      season) all encode to 1.0000 while `1` encodes to 0.1111, so the
#      feature is not monotone in its own quantity. Measured on the union
#      frame: the stored quantity is 1-based, so the 0 collision is a latent
#      hazard; the collision that OCCURS is None against 9+, where 1,273 rows
#      carrying None appear at rate 1.0000 and 11 rows carrying 9-11 appear
#      at 0.5455 and the design row cannot tell them apart.
#
#   2. `depth_vintage.daily` ranked offence-wide while
#      `depth_vintage.weekly` grouped within position, so one column of one
#      design row held two different quantities. Appearance rate by bucket:
#      weekly era r1 0.8930 / r2 0.7018 / r3 0.5186, daily era 0.9136 /
#      0.9357 / 0.8805 -- flat at the top because those buckets are the three
#      alphabetically-first `pos_rank == 1` players, not roles. On the
#      within-position scale the same 2025 rows give 0.9139 / 0.7451 /
#      0.6425 / 0.3720, monotone.
#
# NEITHER MODULE IS EDITED IN PLACE. `depth_vintage` SUPPLIES the second
# scale beside the first and its default is unchanged value for value;
# `appearance_r8` gains a successor featuriser, fit and predict beside the
# frozen ones. R8's and R9's coefficients are byte-identical after the change.
R9_W1P_FLAGS = dict(R9_FLAGS)
R9_W1P_FLAGS['include_2026w1_participation'] = True

R9_W1P_REPAIR = {
    'component': 'R9_W1P',
    'what': 'include the 2026 week-1 participation rows derived in '
            'panel_2026w1 so the Stage-2 ewma sees a current-season game',
    'replaces': 'a PARTICIPATION_HISTORY_STALE refusal that produced no '
                'running back, receiver or tight end at all for a week-2 game',
    'defect': 'the accepted estimator weights the most recent games hardest '
              'and the panel stops at ordinal 202518, so week 2 of 2026 had '
              'no current-season history to weight',
    'approximation': (
        'pass_snaps is APPROXIMATED as offense_snaps * (team_dropbacks / '
        'team_offense_plays). Six of the seven fields the estimator needs are '
        'exact from held evidence; this one is not derivable because '
        'offense_players is absent from the play-by-play. The error is '
        'BOUNDED per row: lo = max(0, snaps - runs), hi = min(snaps, '
        'dropbacks). Measured on DET/BUF, mean share-bound width 0.307 -- '
        'tightest for every-down players (Amon-Ra St. Brown 0.098) and widest '
        'for rotational ones (Brock Wright 0.780).'),
    'known_bias': (
        'assumes a player pass/run snap split equal to his team, which '
        'over-credits blocking tight ends and early-down backs with pass '
        'participation and under-credits third-down backs and slot receivers'),
    'not_the_accepted_arm': (
        'ewma_hl2 over TRUE pass_snaps is the accepted estimator. This is the '
        'same estimator over a DIFFERENT ESTIMAND and must never be reported '
        'as, compared against, or promoted in place of the accepted arm '
        'without the exact numerator.'),
}

R10_FLAGS = {k: v for k, v in R9_FLAGS.items() if k != 'appearance_r8'}
R10_FLAGS['appearance_r10'] = True

R10_REPAIR = {
    'component': 'R10',
    'what': 'the appearance design row pairs f_weeks_since_appear with a '
            'missingness indicator and encodes it monotonically, and the '
            'depth rank is the WITHIN-POSITION ordinal on both sides of the '
            'fit instead of an offence-wide one in the daily era and a '
            'within-position one in the weekly era',
    'replaces': 'appearance_r8.featurise/fit/predict, which stay frozen and '
                'are still what R8 and R9 run; this is a successor lineage, '
                'not an edit',
    'defect': 'a value read through a falsy test and served without a '
              'missingness flag, and a depth ordinal contaminated by '
              'cross-position gsis_id tiebreaks',
    'evidence': 'AUTOPSY_DEN_KC section 4: the weeks-since feature carries '
                '39% of the 3.9266 logit gap between two backs and its '
                'direction is perverse -- giving the historyless back the '
                'other\'s full history DROPS him 0.9925 -> 0.8135. Depth '
                'cost, same board: 0.723664 at offence-wide ordinal 3 against '
                '0.977057 at ordinal 1',
    'refits': 'both repairs change the feature matrix, so R10 is fitted from '
              'scratch on the same forward-chained frame; the old '
              'coefficients are preserved under R8 and are not reused',
    'introduces_no_constant': True,
    'governance': 'EXPLORATORY -- both defects were found by inspecting a '
                  'sealed board in this repository, so any comparison on '
                  'these same seasons controls parameter leakage only. A '
                  'confirmatory result needs untouched games.',
    'wiring': 'the mechanism is registered and callable '
              '(appearance_r8.predict_r10); routing a board through it needs '
              'a line in nonqb/layers.py (FROZEN) and run_forecast, neither '
              'owned by this repair, so no sealed board runs R10 yet',
    'inherits': 'R9',
}


# R11 REPLACES THE RUSH COMPOSITION, AND NOTHING ELSE.
#
# IT INHERITS R9, NOT R10. R10 is a concurrent appearance repair on the same
# ancestor; the two are orthogonal and stacking an unrelated unvalidated
# mechanism underneath this one would make any difference between R9 and R11
# unattributable. R11 = R9 + one repair, so the only difference between the
# two runs is that repair.
#
# THE DEFECT, MEASURED. The product gate fires RUSH_ACCOUNTING_FAILURE on
# sealed board 96954efc523bd7d3 (2026_01_DEN_KC, V1_CANDIDATE_R9, 1,000 draws)
# at 149 of 1,000 Denver draws and 148 of 1,000 Kansas City draws, by up to
# 6.1219 and 9.6915 carries. DECOMPOSED against the same arrays, A1's
# multinomial running-back deal is sound and the impossibility is entirely in
# the quarterback's rushing opportunity:
#
#     RB carries only      DEN 2 draws positive, max +0.2619, 0 over the gate
#                          KC  2 draws positive, max +0.0854, 0 over the gate
#     RB + QB rush opp     DEN 206 positive, 149 over the gate, max +6.1219
#                          KC  237 positive, 148 over the gate, max +9.6915
#
# An earlier workstream read the fired gate as a defect in the RB deal and
# wrote a repair for it. A single undecomposed check is what aimed it there.
#
# THREE SEPARABLE CAUSES, ALL AT THE COMPOSITION, NONE IN A1's ESTIMATOR:
#
#   1. SC1 coupled the carry level against the SCRAMBLES. A designed
#      quarterback run is a team carry exactly as a scramble is, so the bound
#      was too weak and rush_opp > team_carries stayed reachable -- 1 of 1,000
#      KC draws on that board.
#   2. `rushing_a1.allocate` was called without `qb_designed_rush`, so A1 drew
#      its own `designed_qb` while the QB layer drew `rush_opp`. One football
#      quantity, two owners, two values: DEN 2.2960 vs 1.6270, KC 0.7090 vs
#      0.6150, disagreeing in 814 and 528 of 1,000 cells and differing per
#      draw by -10 to +15 carries.
#   3. run_forecast sealed D1's raw continuous level while the engine
#      partitioned the SC1-coupled integerised one, so the board published a
#      denominator the game never used and a breach could not be attributed
#      between a carry with two owners and a wrong vector.
#
# NO CONSTANT IS INTRODUCED AND NOTHING IS REFITTED. The estimator family, the
# category set, the shrinkage constant and the half-life are OWN-9's,
# untouched. The repair is an ORDER-OF-COMPOSITION change, assembled in one
# named function (`rushing_a1.compose_rush_ownership`) so the three steps
# cannot drift apart at a call site again.
#
# WHAT DOES MOVE, AND IT IS A MARGINAL. `rush_category.designed_qb` is no
# longer A1's own draw; it IS the QB layer's `rush_opp - scr`. That is the
# point -- one quantity, one value -- and because it changes a sampling
# distribution it is a NEW configuration identity rather than an edit to R9.
R11_FLAGS = dict(R9_FLAGS)
R11_FLAGS['rush_single_owner'] = True

R11_REPAIR = {
    'component': 'R11',
    'what': 'the rush composition becomes one construction: the carry level '
            'is permuted to hold the quarterbacks` WHOLE rush opportunity, '
            'the QB layer is the single owner of designed runs and A1 draws '
            'the other five categories from the exact conditional '
            'multinomial, and the level the board publishes is the level A1 '
            'partitioned',
    'replaces': 'three separately-defensible steps at the run_forecast call '
                'site whose composition left the constraint unenforceable. '
                'rushing_a1.allocate is unchanged and still what R9 runs; '
                'this is a successor lineage, not an edit',
    'defect': 'named rush owners were dealt more carries than the team`s own '
              'carry level in 149 of 1,000 DEN draws and 148 of 1,000 KC '
              'draws on sealed board 96954efc523bd7d3, by up to 6.1219 and '
              '9.6915 carries',
    'decomposition': 'RB carries alone exceed the gate tolerance in 0 of '
                     '1,000 draws on both teams (max +0.2619 DEN, +0.0854 '
                     'KC). The impossibility is entirely in the QB rush path, '
                     'and a single summed check could not say so.',
    'evidence': 'the two answers for designed QB runs disagreed in 814 of '
                '1,000 DEN cells and 528 of 1,000 KC cells, per draw by -10 '
                'to +15 carries',
    'structural_guarantee': 'rb_category + qb_rush_opportunity == published '
                            '- (kneel + wr + te + fringe), hence <= published, '
                            'in every draw for every input the composition '
                            'accepts. Asserted DECOMPOSED by '
                            'rushing_a1.assert_named_owner_containment and '
                            'demonstrated against a seeded one-carry breach '
                            'in nfl/tests/test_p3_rush_accounting.py',
    'introduces_no_constant': True,
    'no_clip_truncation_renormalisation_or_deleted_draw': True,
    'refits_nothing': True,
    'governance': 'REHEARSAL_ONLY -- engineering integration, not prospective '
                  'validation',
    'open_and_not_smoothed': [
        'raising SC1`s bound from scrambles to rush opportunity permutes more '
        'draws, so A3G`s game-level pairing survives in fewer cells than '
        'under R9. The carry marginal is unchanged element for element; the '
        'JOINT with the opposing club is not, and that is not measured here.',
        'the designed-QB marginal is now the QB layer`s draw. `qb2_lib` has '
        'its own open miscalibration on dropback share and this composition '
        'inherits whatever that layer carries.',
        'the published carry level becomes integral, which is what the '
        'partition consumed and is a change to what the board publishes.',
        'the repair was found by inspecting a sealed board in this '
        'repository, so it is engineering integration on development data '
        'and nothing here is a prospective result.',
    ],
    'inherits': 'R9',
    'does_not_inherit': 'R10 -- a concurrent, orthogonal appearance repair',
}


# R12 REPAIRS THE QUARTERBACK DROPBACK SHARE INSIDE QB V1, AND NOTHING ELSE.
#
# R9 is untouched and is still what R9 runs; R10 and R11 are concurrent,
# orthogonal repairs and are not inherited. This is a successor lineage, not
# an edit.
#
# THE DEFECT, MEASURED. `qb2_lib.simulate` builds a quarterback's share of his
# team's dropbacks by resampling his own prior shares against a positional
# pool holding EVERY quarterback-game with a dropback. On the 2020-2024 pool
# 690 of 3,376 rows -- 20.4% -- are backup appearances whose mean share is
# 0.1233, against 0.9683 for the 2,686 primary-passer rows. The own component
# and the shrinkage target are therefore estimates of DIFFERENT quantities and
# the rung weight trades between them as though they were the same one.
# Conditioned on being the primary passer the result sits too low; summed over
# the room it sits too high, which is the 2.17x over-allocation
# `qb_allocation.py` already records from the other end. Same missing
# normalisation, opposite sign.
#
# THE REPAIR. Both components are put on one conditioning basis: the own
# component is restricted to his prior games AS HIS TEAM'S PRIMARY PASSER, and
# the pool is stratified by `prior_primary` -- the passer's own role in his own
# most recent previous appearance. Both labels are facts about strictly
# earlier games, so no future information enters. No constant is introduced:
# the mixture weight is the module's existing `rung_weight`.
#
# EVIDENCE. Forward-chained over the 540 eligible 2025 starting-QB games in
# 272 games, block bootstrap over whole games, 2,000 resamples, the frame the
# defect was established on in nfl/research/v3/h1. Share signed bias
# -0.0778 [-0.0870, -0.0691] -> -0.0190 [-0.0278, -0.0109]. Randomized PIT
# chi-square on 9 df 32.481 (p = 1.6e-04) -> 8.667 (p = 0.469). End-to-end
# passing-yard CRPS 43.042 -> 41.744, paired difference -1.298
# [-2.198, -0.436].
#
# WHAT IT COSTS, RECORDED RATHER THAN SMOOTHED. Passing-yard signed bias moves
# from -5.922 [-12.669, +0.734], an interval containing zero, to
# +7.538 [+0.902, +14.167], an interval that does not. The incumbent's
# apparent accuracy on passing yards was two errors cancelling: a share drawn
# too low against a team-dropback layer drawn +1.637 too high, which H1
# attributes to league drift in a frozen 2020-2024 league mean. Repairing the
# share removes one of them and exposes the other, and the other lives in the
# team volume layer, not here.
#
# IT IS INERT UNDER R2. When `db_external` is supplied the share is never
# drawn at all, and every mode from V1_CANDIDATE onward sets r2, so on the
# engine path this component changes nothing. `qb_v1.forecast` refuses the
# pair outright rather than carrying a component label it did not use. The
# measured path is qb_v1 called WITHOUT `db_external` -- PRODUCTION_BASELINE,
# and the path nfl/research/v3/h1 scored.
R12_FLAGS = dict(R9_FLAGS)
R12_FLAGS['qb_share_spec'] = 'starter_conditioned'

R12_REPAIR = {
    'component': 'R12',
    'what': "the quarterback's share of team dropbacks is drawn from his own "
            'prior games in the primary-passer role, shrunk toward the pool '
            'stratum carrying the same lagged role, instead of toward a pool '
            'that mixes starters and backups',
    'replaces': "qb2_lib.simulate's unconditional share resample, which stays "
                'the default and is what every sealed artifact was produced '
                'under; verified identical on 1,296,000 draw cells',
    'defect': 'the own component and the shrinkage target estimate different '
              'quantities: 690 of 3,376 pool rows (20.4%) are backup '
              'appearances at a mean share of 0.1233 against 0.9683 for the '
              '2,686 primary rows',
    'evidence': '540 forward-chained 2025 starting-QB games over 272 games. '
                'Share bias -0.0778 [-0.0870, -0.0691] -> -0.0190 '
                '[-0.0278, -0.0109]; randomized PIT chi2 32.481 -> 8.667 on '
                '9 df; end-to-end passing-yard CRPS 43.042 -> 41.744, paired '
                'difference -1.298 [-2.198, -0.436], block bootstrap over '
                'whole games',
    'report': 'nfl/research/v4/p2/P2_QB_SHARE_REPAIR.md',
    'introduces_no_constant': True,
    'no_floor_clip_or_minimum': True,
    'refits_nothing': True,
    'inert_under_r2': True,
    'governance': 'EXPLORATORY -- three share specifications were compared on '
                  'this same 540-game 2025 frame before one was chosen, so '
                  'forward chaining controls parameter leakage only and not '
                  'specification leakage. 2025 is development data in this '
                  'project. A confirmatory result needs untouched games.',
    'open_and_not_smoothed': [
        'passing-yard bias moves from -5.922, whose interval contains zero, '
        'to +7.538, whose interval does not. The residual is the team '
        "dropback layer's +1.637 league drift, not the share.",
        'the share bias TOST against a predeclared +/-0.010 margin returns '
        'NOT_SHOWN_EQUIVALENT in BOTH arms, so the word calibrated is not '
        'used of either.',
        'on the 40 of 540 games where the lagged role is not the role he '
        'played, the repair is slightly WORSE: share CRPS 0.1077 -> 0.1184 '
        'and passing-yard CRPS 42.19 -> 46.84. It helps where the role '
        'signal is right and costs a little where it is not.',
        'the mid-PIT chi-square RISES, 944.6 -> 1074.9, because 78.89% of '
        'realised shares are exactly 1.0 and a mid-PIT is not uniform on an '
        'atom. The published 929.0 is largely that instrument. The '
        'randomized PIT is the instrument a discrete quantity needs and it '
        'is the one this repair is judged on.',
        'no 2025 weekly depth chart exists in nfl/research/inputs/, so the '
        'only pregame role signal available for the rerun is the lagged one. '
        'A real starter designation would strictly improve it and is not '
        'assumed here.',
    ],
    'inherits': 'R9',
    'does_not_inherit': 'R10 and R11 -- concurrent, orthogonal repairs',
}


# R13 REPAIRS THE PASSING-YARD CONSTRUCTION INSIDE QB V1, AND NOTHING ELSE.
#
# R9 is untouched and is still what R9 runs; R10, R11 and R12 are concurrent,
# orthogonal repairs and are not inherited. This is a successor lineage, not an
# edit.
#
# THE DEFECT, MEASURED. `qb2_lib.simulate` built passing yards as
# `PY = CMP * ypc_d`, where `ypc_d` is ONE game-level yards-per-completion
# ratio resampled whole from a pool of 3,787 realised QB game-lines and CMP is
# an independently drawn completion count. The donor ratio carries no record of
# the completion count that produced it and is not weighted by it, so a ratio
# estimated at n = 1 completion is applied at n = 16 with no shrinkage. That is
# SCALE NON-EXCHANGEABILITY. Measured over the sealed corpus: 680 of 520,000
# `qb/pyds` cells on QB-only team-sides exceed the all-time NFL single-game
# record of 554 yards, maximum 1,587, a rate of 1.308e-03 against a one-sided
# 95% bound of 7.907e-04 derived from zero such games in 3,787; 2,262 cells are
# negative, of which D19's -32 yards on 16 completions is -2.0 x 16 exactly,
# the -2.0 donated by a one-completion game. Negative yards per completion
# exists in real football ONLY at 1-2 completions; across the 3,385 games with
# five or more, the minimum is +3.462.
#
# THE REPAIR. The UNIT OF RESAMPLING changes from the game to the completion. A
# draw needing CMP completions draws donor games with probability proportional
# to their own completion count and consumes min(n_donor, completions still
# needed) from each until CMP are covered, so sum_k t_k == CMP and t_k <= n_k
# in every draw: no donor supplies yardage for more completions than it itself
# recorded. The mixture weight is the module's existing `rung_weight`, applied
# per completion block rather than per game -- the unit the weight is a
# reliability statement about. NOTHING IS CLIPPED, TRUNCATED OR REJECTED: the
# support of the generator is unchanged and only the probability law moves. No
# constant is introduced and nothing is refitted.
#
# EVIDENCE. 635 eligible 2025 QB-game rows over 272 games, forward-chained
# (pool 2020-2024), one seed, 1,000 draws, both arms on one slate. Rate above
# the record 5.260e-03 -> 5.102e-04, row-clustered 95% CI
# [4.32e-04, 5.89e-04], inside the derived bound. Maximum 2,898 -> 772 yards;
# minimum -238 -> -3; cells below -30 yards 970 -> 0; cells in D19's own state
# (16+ completions at or below -32 yards) 938 -> 0. Cells outside the realised
# ratio support at their own completion count 13,803 -> 112. On the 79
# quarterbacks who actually appear on the sealed boards, rate 5.873e-03 ->
# 3.798e-04 and out-of-support 2,395 -> 10.
#
# WHAT IT COSTS, RECORDED RATHER THAN SMOOTHED. Passing-yard CRPS 48.855 ->
# 49.103, paired difference +0.248 [-0.074, +0.524], game-clustered block
# bootstrap, 2,000 resamples -- the interval contains zero, so this cohort does
# NOT establish that either arm forecasts better. The centre moves -1.73 yards
# (-0.84%) and the between-row SD of predicted means 43.97 -> 42.42. Interval
# coverage moves toward nominal at 50% and 80% (0.531 -> 0.498, 0.827 -> 0.798)
# and slightly below it at 90% and 95% (0.934 -> 0.912, 0.967 -> 0.959). The
# implied-ratio variance at 1-4 completions falls further below the realised
# value than the incumbent's did; that band was already under-dispersed in both
# arms and the repair makes it worse.
#
# IT IS NOT INERT UNDER R2. The completion count is drawn in qb_v1 on every
# path, so this construction runs whether or not the dropback level arrives
# from D1 x QB3. R12 and R13 are independently selectable.
R13_FLAGS = dict(R9_FLAGS)
R13_FLAGS['qb_ypc_spec'] = 'completion_blocks'

R13_REPAIR = {
    'component': 'R13',
    'what': 'passing yards are built by resampling COMPLETIONS -- donor games '
            'drawn in proportion to their own completion count, each '
            'supplying at most as many completions as it recorded -- instead '
            'of multiplying one whole game-level yards-per-completion ratio '
            'by an independently drawn completion count',
    'replaces': "qb2_lib.simulate's `PY = CMP * ypc_d`, which stays the "
                'default and is what every sealed artifact was produced '
                'under; verified byte-identical on the 2025 cohort',
    'defect': 'scale non-exchangeability -- a ratio estimated at n = 1 '
              'completion applied at n = 16 with no shrinkage and no '
              'denominator weighting. 680 of 520,000 QB-only cells above the '
              '554-yard all-time record, maximum 1,587, rate 1.308e-03 '
              'against a derived bound of 7.907e-04; 2,262 negative cells',
    'evidence': '635 eligible 2025 QB-game rows over 272 games, forward '
                'chained. Rate above the record 5.260e-03 -> 5.102e-04 '
                '(row-clustered 95% CI [4.32e-04, 5.89e-04], inside the '
                'bound); maximum 2,898 -> 772; minimum -238 -> -3; cells '
                'below -30 yards 970 -> 0; out-of-support cells 13,803 -> 112',
    'report': 'nfl/research/v4/p8/P8_TAILS_AND_COUNTS.md',
    'introduces_no_constant': True,
    'no_clip_truncation_or_rejection': True,
    'refits_nothing': True,
    'inert_under_r2': False,
    'governance': 'EXPLORATORY -- four constructions were compared on the '
                  'same 2025 frame before one was chosen, and the sealed '
                  'corpus was inspected before the repair was designed, so '
                  'forward chaining controls parameter leakage only and not '
                  'specification leakage. A confirmatory result needs '
                  'untouched games.',
    'open_and_not_smoothed': [
        'passing-yard CRPS 48.855 -> 49.103, paired difference +0.248 '
        '[-0.074, +0.524], game-clustered block bootstrap. The interval '
        'contains zero. This cohort does not establish that either arm '
        'forecasts better and the repair is not offered as one that does.',
        'the centre moves -1.73 yards (-0.84%), because the completion-'
        'weighted mean ratio (10.955) is not the unweighted mean of ratios '
        '(11.135). That is a declared consequence of the denominator '
        'weighting, not a side effect.',
        'the implied-ratio variance at 1-4 completions falls from 27.4 to '
        '12.6 against a realised 148.5. Both arms are badly under-dispersed '
        'there and the repair makes it worse; the band is 7% of cells and '
        'no starting-quarterback forecast lives in it.',
        '324 cells still exceed 554 yards. 46 of them (14.2%) carry a '
        'completion count above 47, the realised maximum, so part of the '
        'residual is the completion layer and not this one.',
        'the randomised PIT chi-square on 9 df moves 19.09 -> 16.51 against a '
        '5% critical value of 16.92. Neither arm is shown calibrated and the '
        'word is not used of either; a failure to reject is not evidence of '
        'adequacy.',
    ],
    'inherits': 'R9',
    'does_not_inherit': 'R10, R11 and R12 -- concurrent, orthogonal repairs',
}


def resolve(mode: str) -> Outcome:
    """The flags and the component manifest for a named mode, or a refusal.

    An unknown mode is REFUSED rather than falling back to the baseline: a
    typo that silently produced the promoted model while the operator believed
    they were running the candidate is precisely the masquerade this module
    exists to make impossible -- and it would fail in the dangerous direction,
    since the baseline is the one allowed to publish.
    """
    if mode in (None, '', PRODUCTION_BASELINE):
        return Outcome.ok(
            'MODE_PRODUCTION_BASELINE',
            value={'mode': PRODUCTION_BASELINE, 'flags': {},
                   'components': [], 'candidate': False},
            detail='no candidate component is active')
    if mode == V1_CANDIDATE_R13:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R13',
            value={'mode': V1_CANDIDATE_R13, 'flags': dict(R13_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R13_REPAIR],
                   'candidate': True},
            detail='R9 plus the R13 completion-block passing-yard '
                   'construction, which resamples completions instead of '
                   'multiplying one game-level ratio by an independently '
                   'drawn completion count. NOT inert under r2.')

    if mode == V1_CANDIDATE_R12:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R12',
            value={'mode': V1_CANDIDATE_R12, 'flags': dict(R12_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R12_REPAIR],
                   'candidate': True},
            detail='R9 plus the R12 starter-conditioned dropback share, which '
                   'puts both halves of the share mixture on one conditioning '
                   'basis. INERT while r2 is set, because the share is then '
                   'not drawn at all')
    if mode == V1_CANDIDATE_R11:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R11',
            value={'mode': V1_CANDIDATE_R11, 'flags': dict(R11_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R11_REPAIR],
                   'candidate': True},
            detail='R9 plus the R11 rush composition, which gives the '
                   'quarterback`s rushing opportunity one owner and publishes '
                   'the carry level the partition actually consumed. It '
                   'inherits R9, NOT R10.')
    if mode == V1_CANDIDATE_R10:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R10',
            value={'mode': V1_CANDIDATE_R10, 'flags': dict(R10_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R10_REPAIR],
                   'candidate': True},
            detail='R9 with the appearance mechanism replaced: the '
                   'weeks-since-appearance feature carries a missingness '
                   'indicator and a monotone encoding, and the depth rank is '
                   'within-position on both sides of the fit')
    if mode == V1_CANDIDATE_R9_W1P:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P',
            value={'mode': V1_CANDIDATE_R9_W1P, 'flags': dict(R9_W1P_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R9_W1P_REPAIR],
                   'candidate': True},
            detail='R9 with the 2026 week-1 participation rows included. The '
                   'pass-snap numerator on those rows is APPROXIMATED from '
                   'the team dropback rate, not counted, so this is a '
                   'different estimand from the accepted arm and carries its '
                   'own identity')
    if mode == V1_CANDIDATE_R9:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9',
            value={'mode': V1_CANDIDATE_R9, 'flags': dict(R9_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR],
                   'candidate': True},
            detail='R8 plus the R9 quarterback room, which allocates integer '
                   'dropbacks through an explicit starter state instead of a '
                   'share drawn from a pool that contradicts it')
    if mode == V1_CANDIDATE_R8:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R8',
            value={'mode': V1_CANDIDATE_R8, 'flags': dict(R8_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR],
                   'candidate': True},
            detail='R6 plus the R8 reliability-weighted appearance model, '
                   'which supersedes R7 rather than stacking on it')
    if mode == V1_CANDIDATE_R7:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R7',
            value={'mode': V1_CANDIDATE_R7, 'flags': dict(R7_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R7_REPAIR],
                   'candidate': True},
            detail='R6 plus the R7 appearance-frame and depth repair')
    if mode == V1_CANDIDATE_R6:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R6',
            value={'mode': V1_CANDIDATE_R6, 'flags': dict(R6_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR],
                   'candidate': True},
            detail='R5 plus the R6 role-conditional class prior')
    if mode == V1_CANDIDATE_R5:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R5',
            value={'mode': V1_CANDIDATE_R5, 'flags': dict(R5_FLAGS),
                   'components': manifest() + [R5_REPAIR], 'candidate': True},
            detail='V1_CANDIDATE plus the R5 active-roster pool repair')
    if mode != V1_CANDIDATE:
        return Outcome.fail(
            'MODEL_CONFIGURATION_UNKNOWN',
            f'{mode!r} is not a declared model configuration. Declared: '
            f'{list(MODES)}. Refusing rather than defaulting -- a typo that '
            f'quietly ran the promoted baseline would be the masquerade this '
            f'refusal exists to prevent.',
            known=list(MODES))
    return Outcome.ok(
        'MODE_V1_CANDIDATE',
        value={'mode': V1_CANDIDATE, 'flags': dict(V1_CANDIDATE_FLAGS),
               'components': manifest(), 'candidate': True},
        detail=f'{len(COMPONENTS)} rehearsal-only component(s) active: '
               f'{", ".join(sorted(COMPONENTS))}')


def manifest() -> list:
    """Every active component, with what governs it. Written into the artifact
    verbatim so the run carries its own provenance."""
    return [{'component': k, **v} for k, v in sorted(COMPONENTS.items())]


def assert_not_promoted(mode: str, artifact: dict) -> Outcome:
    """A candidate artifact must say so, in every field that could be read as
    a promotion claim. Called by the sealer; tested with the guard stubbed."""
    # THE LIST IS DERIVED, NOT TYPED, AND THAT IS THE REPAIR.
    #
    # This guard used to enumerate candidate modes by hand. R9, R10 and R11
    # were registered and nobody added them, so an artifact in any of those
    # modes hit `not in (...)` and returned NOT_APPLICABLE -- the masquerade
    # check silently did not run on three live configurations, R9 among them,
    # which is the mode that produced the DEN@KC boards. A guard that has to
    # be remembered is a guard that gets forgotten; this one had already
    # deleted itself three times before anyone noticed.
    #
    # Appending the three names would have restored it and left the identical
    # trap for R13. `CANDIDATE_MODES` is derived from `MODES` instead, so a
    # newly registered candidate is checked the moment it exists and cannot
    # opt out by omission. PRODUCTION_BASELINE is excluded because it is not a
    # candidate; that exclusion is a property of the mode, not a list someone
    # maintains.
    if mode not in CANDIDATE_MODES:
        return Outcome.not_applicable('NOT_A_CANDIDATE_RUN',
                                      f'mode is {mode!r}')
    bad = []
    if artifact.get('model_configuration') not in CANDIDATE_MODES:
        bad.append('model_configuration does not name the candidate mode')
    if not artifact.get('candidate_components'):
        bad.append('candidate_components is empty on a candidate run')
    if artifact.get('promoted') is not False:
        bad.append('promoted is not explicitly False')
    if artifact.get('prospective_eligible') is not False:
        bad.append('prospective_eligible is not explicitly False')
    ev = str(artifact.get('eligibility_verdict', ''))
    if not any(m in ev for m in (V1_CANDIDATE, V1_CANDIDATE_R5,
                                 V1_CANDIDATE_R6)):
        bad.append('eligibility_verdict does not carry the candidate mode')
    if bad:
        return Outcome.fail(
            'CANDIDATE_RUN_COULD_MASQUERADE_AS_PROMOTED',
            'a V1 candidate artifact must be unmistakable: ' + '; '.join(bad),
            problems=bad)
    return Outcome.ok(
        'CANDIDATE_RUN_DECLARED', value=True,
        detail=f'{len(artifact["candidate_components"])} component(s) named; '
               f'promoted False; prospective_eligible False')
