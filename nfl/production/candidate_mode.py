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
V1_CANDIDATE_R9_W1P_G = 'V1_CANDIDATE_R9_W1P_G'
V1_CANDIDATE_R9_W1P_GA = 'V1_CANDIDATE_R9_W1P_GA'
V1_CANDIDATE_R9_W1P_GS = 'V1_CANDIDATE_R9_W1P_GS'
V1_CANDIDATE_R9_W1P_GSV = 'V1_CANDIDATE_R9_W1P_GSV'
V1_CANDIDATE_R9_W1P_GSP = 'V1_CANDIDATE_R9_W1P_GSP'
V1_CANDIDATE_R9_W1P_GSVP = 'V1_CANDIDATE_R9_W1P_GSVP'
V1_CANDIDATE_R9_W1P_GSVU = 'V1_CANDIDATE_R9_W1P_GSVU'
V1_CANDIDATE_R9_W1P_GSVUQ = 'V1_CANDIDATE_R9_W1P_GSVUQ'
V1_CANDIDATE_R9_W1P_GSVUC = 'V1_CANDIDATE_R9_W1P_GSVUC'
V1_CANDIDATE_R9_W1P_GSVUCY = 'V1_CANDIDATE_R9_W1P_GSVUCY'
MODES = (PRODUCTION_BASELINE, V1_CANDIDATE, V1_CANDIDATE_R5,
         V1_CANDIDATE_R6, V1_CANDIDATE_R7, V1_CANDIDATE_R8,
         V1_CANDIDATE_R9, V1_CANDIDATE_R10, V1_CANDIDATE_R11,
         V1_CANDIDATE_R12, V1_CANDIDATE_R13, V1_CANDIDATE_R9_W1P,
         V1_CANDIDATE_R9_W1P_G, V1_CANDIDATE_R9_W1P_GA,
         V1_CANDIDATE_R9_W1P_GS, V1_CANDIDATE_R9_W1P_GSV,
         V1_CANDIDATE_R9_W1P_GSP, V1_CANDIDATE_R9_W1P_GSVP,
         V1_CANDIDATE_R9_W1P_GSVU, V1_CANDIDATE_R9_W1P_GSVUQ,
         V1_CANDIDATE_R9_W1P_GSVUC, V1_CANDIDATE_R9_W1P_GSVUCY)

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
# CARRY CONSERVATION IS R11's REPAIR AND IT ALREADY EXISTS.
# Measured on the R9_W1P board 1119ae644642392c, per draw and never noise:
#   team_carries vs summed rush categories -- DET 29.17 vs 28.31, BUF 30.08
#   vs 27.55, agreeing in 0 of 1000 draws on either club.
# R9 leaves three things undone that R11 composes in one call: SC1 bounds the
# carry level by SCRAMBLES while the named owners include the quarterback's
# DESIGNED runs; `allocate` runs without `qb_designed_rush`, so A1 draws a
# second answer to a quantity the QB layer already drew; and the sealed level
# is D1's raw CONTINUOUS draw rather than the integerised vector the partition
# consumed. Nothing is clipped, renormalised or deleted by including it.
R9_W1P_FLAGS['rush_single_owner'] = True
# TARGET CONSERVATION IS THE RECEIVING ANALOGUE, AND ONLY CAUSE THREE OF IT.
# `football_engine` already computes the partitioned level and names it
# `published_team_targets` with `published_level_is: 'targeted'`, and checks
# `sum_i targets_i + other == targeted` per team per draw exactly. What was
# missing is that `run_forecast` sealed D1's separately drawn CONTINUOUS
# `team_targets` beside it -- a denominator the game never used. Measured:
# receivers exceed the published level in 51.18% of 139,800 sealed C3 draws
# and agree in 0. The allocation is sound; the published label was wrong, so
# this publishes the level that was partitioned rather than renormalising a
# partition that is already correct.
R9_W1P_FLAGS['publish_partitioned_team_targets'] = True

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

R9_W1P_G_FLAGS = dict(R9_W1P_FLAGS)
R9_W1P_G_FLAGS['allocate_gadget_rush'] = True

R9_W1P_G_REPAIR = {
    'component': 'R9_W1P_G',
    'what': 'the kneel, wr and te rush categories are dealt to NAMED players '
            'on the same board, on the same draw index, instead of reaching '
            'the board as a team-level number with nobody on it',
    'replaces': 'three categories of team rushing mass with no player. '
                'Measured on the sealed DET-BUF board: BUF kneel 1.560 + wr '
                '0.478 + te 0.058 and DET 0.641 + 0.584 + 0.040 carries per '
                'draw belonging to no one',
    'defect': 'a board that hides kneels overstates every quarterback rushing '
              'line on a team that is ahead, because a kneel is an official '
              'rush attempt that loses a yard or two; and a gadget carry with '
              'no owner is a receiver rushing line that silently reads zero',
    'evidence': (
        'pre-cutoff: 2212 kneels, 100.0% taken by a quarterback and 83.2% by '
        'the game\'s own primary passer; 2685 wr carries whose busiest '
        'receiver takes a median 100% and mean 91.7% of a team-game; 203 te '
        'carries at 99.0%. nfl/production/nonqb/GADGET_RUSH_FIT.json.'),
    'coefficients': (
        'ONE per category. Weights are own prior carries + alpha, with alpha '
        'fitted by forward-scored log-loss of the actual owner: wr 0.75 '
        '(loss 1.2612, n=2685), te 0.10 (loss 0.7411, n=203). Both interior '
        'to the grid. The first criterion tried -- matching the mean '
        'top-share -- is WITHDRAWN: it is monotone in alpha and returned the '
        'grid boundary, where a player with no prior carry can never take '
        'one.'),
    'not_allocated': (
        'fringe and the unmodelled-back pool stay unnamed. Of 132 pre-cutoff '
        'fringe carries, 28 are defensive backs, 26 punters, 12 linebackers, '
        '1 a kicker and 65 belong to 11 rushers with no position in any '
        'source held -- none recoverable from panel_p3. Where an owner exists '
        'he is on no offensive board. This is the correct answer, not a gap.'),
    'known_limitation': (
        'the allocation is slightly LESS concentrated than the real thing -- '
        'simulated mean top-share 0.873 against an observed 0.917 for wr. '
        'Reported rather than closed, because moving alpha to close it is the '
        'moment-matching this component explicitly withdrew.'),
    'opportunity_only_not_yards': (
        'THIS ALLOCATES THE CARRY, NOT THE YARD. A kneel, a jet sweep and a '
        'tight-end run now have a named owner and still contribute nothing to '
        'his rushing yards, because the conversion draws on the RB pool over '
        'the rushing layer and these carries are not in it. Measured '
        'pre-cutoff: a kneel is -1.0922 yards (n=2212, sd 0.57, p50 -1.0), a '
        'wr carry +5.5423 (n=2685, sd 7.72, p50 4.0, p90 14.0) and a te carry '
        '+2.7044 (n=203). On this board that is about -1.64 rushing yards '
        'missing from Josh Allen and +1.55 from Amon-Ra St. Brown. Small, and '
        'NOT closed here: the wr distribution is a different animal from the '
        'RB pool -- mean 5.54 against 4.29, with a far heavier tail -- so '
        'converting these carries needs its own stratum, which is a further '
        'closure change and therefore a further candidate, not an edit to '
        'this one.'),
    'governance': 'REHEARSAL_ONLY -- a closure change with its own identity, '
                  'never an edit to R9_W1P',
    'engine_flag': 'allocate_gadget_rush',
}

R9_W1P_GA_FLAGS = dict(R9_W1P_G_FLAGS)
# THE PANEL IS DEFINED AGAINST THE FROZEN MECHANISM, SO GA NAMES THAT ONE.
# `appearance_panel_2026` injects observed 2026 rows into the frozen walk;
# R8 is a different mechanism with its own frame builder and the injection is
# not defined for it. Setting both raised APPEARANCE_SPEC_AMBIGUOUS, which is
# the guard working -- two answers to "which model ran" is exactly what it
# exists to stop. R8 is therefore dropped HERE, explicitly, rather than
# letting one silently win.
#
# THE COST IS STATED: GA differs from G in TWO ways, the panel and the
# mechanism, so a G-to-GA delta is not a clean read of the panel alone. The
# isolated panel effect is measured separately, frozen-with against
# frozen-without, and reported beside it.
R9_W1P_GA_FLAGS.pop('appearance_r8', None)
R9_W1P_GA_FLAGS['appearance_panel_2026'] = True
R9_W1P_GA_FLAGS['availability_feed'] = True

R9_W1P_GA_REPAIR = {
    'component': 'R9_W1P_GA',
    'what': 'the appearance mechanism runs on a panel that reaches the '
            'forecast season, and current-state availability evidence is '
            'joined to participant eligibility',
    'replaces': 'a panel ending at 2025 week 18, so a league-wide rest week '
                'was every player\'s most recent game; and an injury path '
                'that consumed only the official weekly CSV, of which every '
                '2026 capture carries week 1 only',
    'defect': (
        'Josh Allen scored P(appear) 0.4188 and James Cook 0.7138 against a '
        '0.6936 training base rate, while Ty Johnson was given 4.1 carries '
        'on a week the feed lists him OUT. n_with_an_injuries_row was 0 for '
        'every player on the board.'),
    'evidence': (
        '769 official 2026 injury rows across eight captures, ALL week 1, so '
        'no week-2 official evidence exists. 428 ESPN captures hold current '
        'state; the newest lawful at the cutoff is stamped 2026-09-15T13:06Z '
        'and was never offered to the parser, and would have been dropped by '
        'it anyway for carrying no season/week column. '
        'nfl/production/AVAILABILITY_AUDIT_DET_BUF.json.'),
    'coefficients': 'NONE. The appearance coefficients are unchanged -- same '
                    'coef_sha256, same featuriser. The panel it walks is '
                    'longer and the eligibility set is smaller.',
    'availability_authority': (
        'OFFICIAL_GAMEDAY_INACTIVE > OFFICIAL_TEAM_OR_LEAGUE > '
        'SECONDARY_ATTRIBUTED_REPORT. The secondary feed never outranks an '
        'official declaration.'),
    'probabilistic_states_not_acted_on': (
        'Doubtful and Questionable are preserved and do NOT move a player out '
        'of the pool. No calibrated transition exists for them at this '
        'cutoff, so no coefficient is fabricated in either direction.'),
    'confounded_comparison': (
        'GA drops appearance_r8 because the panel injection is defined only '
        'for the frozen mechanism, so a G-to-GA delta mixes a panel change '
        'with a mechanism change. The isolated panel effect is measured '
        'frozen-with against frozen-without and reported separately: Josh '
        'Allen +0.4503, James Cook +0.2147, Gibbs +0.0047.'),
    'known_limitation': (
        'a kicker has no offensive snap share, and the appearance panel holds '
        '47 kicker rows against 21,219 receivers. His appearance is recorded '
        'and his share is left MISSING rather than filled with a '
        'special-teams share on an offensive scale -- which read 0.45 for '
        'Tyler Bass and drove him to 0.6850 on a 3-for-3 kicking game. Both '
        'kickers now sit at 0.7781 on history alone; that is thin support, '
        'and it is reported rather than dressed up.'),
    'governance': 'REHEARSAL_ONLY -- an eligibility and panel change with its '
                  'own identity, never an edit to R9_W1P_G',
    'engine_flag': 'appearance_panel_2026',
}

# ================================================================== SC2
#
# THE ABLATION LINEAGE. Four arms that differ in ONE declared thing each, and
# in nothing else -- which is the whole point, because the last comparison this
# project ran (G at 1,000 draws against GA at 8,000) differed in the draw
# count, the appearance mechanism, the availability evidence AND whether C3's
# second half completed, and could therefore identify none of them.
#
# Every arm here carries SC2, because without it C3's passer credit refuses on
# roughly 4 draws in 10,000 and the run seals a HALF-APPLIED C3 -- targets
# dealt from the throw process, passer line uncredited. That is not a property
# of any arm; it is a property of the draw count, and it made a 1,000-draw
# board and an 8,000-draw board on the same arm look like different candidate
# declarations.
SC2_REPAIR = {
    'component': 'SC2',
    'what': 'the intercepted throws are reserved out of the pool the '
            'receiving conversion converts, and the catch rate is taken '
            'conditional on not having been intercepted',
    'replaces': 'a chain in which C3 built the targeted-throw budget from the '
                'quarterbacks\' attempts, RC1 converted every one of those '
                'throws to a possible catch, and nothing had removed the ones '
                'the interception draw had already spent',
    'defect': 'credit_passing_line refuses a draw in which the receiving '
              'event caught more balls than the quarterbacks had '
              'non-intercepted attempts to throw. The refusal is correct. '
              'What was wrong is that the engine recorded the halt and did '
              'not return, so the board sealed a half-applied C3 and said '
              'nothing -- 60 sealed boards across the week-1 slate and every '
              'arm from V1_CANDIDATE to R9_W1P_GA carry an unexplained '
              '`not reached: [C3]`',
    'evidence': 'reproduced on 2026_02_DET_BUF, same checkout, same seed, '
                'same written_at, changing only the draw count and the '
                'candidate: G and GA both PASS at 400 draws; G FAILs on 1 '
                'draw and GA on 3 at 8,000. Arm-independent, draw-count '
                'dependent. nfl/research/sc2/SC2_SECTION3_RESULT.md',
    'coefficients': 'ONE, and it is MEASURED: the league interception share '
                    'of targets, 0.023766, on 2,718 REG team-games 2021-2025. '
                    'It is what makes E[receptions] unchanged -- '
                    'c/(1-pi) against a pool short by pi -- so the level does '
                    'not move and only the joint state does. '
                    'nfl/research/sc2/SC2_SECTION3_MEASUREMENT.json',
    'withdrawn_alternative': 'SC2-B, a feasibility-constrained permutation of '
                             'the interception draw index in SC1\'s style, is '
                             'WITHDRAWN on the rule written before the number '
                             'was seen. SC1\'s defence was that the model was '
                             'badly under-coupled, +0.0299 against a '
                             'historical +0.1802. Here the model is at '
                             '+0.1973 against +0.2159, so permuting would '
                             'destroy a dependence it already has about right',
    'known_limitation': 'targets are treated as exchangeable with respect to '
                        'being intercepted. A deep contested throw is '
                        'likelier to be picked than a checkdown, and this '
                        'layer forecasts no air yards, so it holds no '
                        'quantity that could express the difference. Recorded '
                        'rather than approximated with a coefficient nothing '
                        'here can estimate',
    'governance': 'REHEARSAL_ONLY -- a closure change with its own identity, '
                  'never an edit to R9_W1P_G or R9_W1P_GA',
    'engine_flag': 'reserve_interceptions',
}

#: GS -- the ablation BASELINE. G plus SC2 and nothing else: R8 appearance,
#: the old availability path, C3 completing.
R9_W1P_GS_FLAGS = dict(R9_W1P_G_FLAGS)
R9_W1P_GS_FLAGS['reserve_interceptions'] = True

#: GSV -- A1 only. The repaired current-state availability evidence, on the
#: SAME R8 appearance mechanism the baseline runs.
R9_W1P_GSV_FLAGS = dict(R9_W1P_GS_FLAGS)
R9_W1P_GSV_FLAGS['availability_feed'] = True

#: GSP -- A2 only. The 2026 week-1 appearance panel, on the OLD availability
#: path. R8 is dropped because the panel injection is defined against the
#: frozen mechanism and setting both is APPEARANCE_SPEC_AMBIGUOUS.
R9_W1P_GSP_FLAGS = dict(R9_W1P_GS_FLAGS)
R9_W1P_GSP_FLAGS.pop('appearance_r8', None)
R9_W1P_GSP_FLAGS['appearance_panel_2026'] = True

#: GSVP -- A1 + A2 together, for the interaction.
R9_W1P_GSVP_FLAGS = dict(R9_W1P_GSP_FLAGS)
R9_W1P_GSVP_FLAGS['availability_feed'] = True

def _sc2_base():
    """The component list every ablation arm shares, in one place.

    Written as a function rather than a module constant so that a caller who
    mutates the list it receives cannot reach back into the next arm's
    declaration. Two arms whose component lists are the same object is one
    `.append` away from an artifact that names a component the run never had.
    """
    return manifest() + [R5_REPAIR, R6_REPAIR, R8_REPAIR, R9_REPAIR,
                         R9_W1P_REPAIR, R9_W1P_G_REPAIR, SC2_REPAIR]


def _avail_only():
    """A1 on its own: the eligibility half of GA, without the panel half."""
    return {k: v for k, v in R9_W1P_GA_REPAIR.items()
            if k not in ('coefficients', 'confounded_comparison',
                         'known_limitation')} | {
        'component': 'A1_AVAILABILITY',
        'what': 'current-state availability evidence is joined to participant '
                'eligibility. The appearance mechanism is NOT touched',
        'isolates': 'the Ty Johnson effect -- a player the feed lists OUT '
                    'leaves the allocation, and the A1 category multinomial '
                    'and the P4C simplex deal his share among the players who '
                    'are in it',
        'engine_flag': 'availability_feed'}


#: STOP. Every arm that consumes `appearance_panel_2026` carries this, and it
#: disqualifies the arm from being a clean candidate until the week-1 rows are
#: rebuilt on the union construction. Measured, not suspected:
#: nfl/research/sc2/W1_PANEL_SURVIVORSHIP.md
W1_PANEL_SURVIVORSHIP = {
    'defect': 'the 2026 week-1 rows come from the snap-count file alone, so a '
              'player who dressed and did not play, or was a healthy scratch, '
              'has NO row. The frame every other week is built from is the '
              'panel UNION the point-in-time depth chart, where he has one '
              'with appeared = 0',
    'measured': 'R7 frame 2025 week 1: 762 rows, 370 appeared, base rate '
                '0.486. The 2026 week-1 panel: 422 rows, 391 appeared, base '
                'rate 0.927',
    'consequence': 'R8 moves w = n_cur/(n_cur+k) = 0.4509 of the weight off '
                   'the depth listing at n_cur = 1. Those coefficients were '
                   'fitted against a 48.6% non-appearer population. Adding '
                   'the observation that a player PLAYED lowers him -- Josh '
                   'Allen 0.9625 to 0.8449 on a 100% snap share, James Cook '
                   '0.8381 to 0.6299 on 0.72',
    'status': 'OPEN. This is a train/serve skew, not a football effect, and a '
              'GSP-minus-GS difference would measure the filter at least as '
              'much as the panel',
    'repair': 'build the 2026 week-1 rows as the observed panel UNION the '
              'point-in-time depth chart, appeared = 0 for a listed player '
              'who took no offensive snap. NOT reweighting, and not dropping '
              'the injection',
}


def _panel_only():
    """A2 on its own, and it is NOT only the panel -- see `also_changes`."""
    return {
        'survivorship': dict(W1_PANEL_SURVIVORSHIP),
        'component': 'A2_PANEL',
        'what': 'the appearance mechanism walks a panel that reaches the '
                'forecast season instead of stopping at 2025 week 18, which '
                'was a league-wide rest week',
        'also_changes': 'THE MECHANISM. The panel injection is defined only '
                        'for the frozen logistic, so this arm drops R8. '
                        'GSP-minus-GS is panel AND mechanism together and '
                        'must never be reported as the panel effect alone',
        'challenger_not_replacement': 'R8 carries forward-chained Brier '
                                      'evidence by regime and this arm does '
                                      'not. Out-of-sample score decides, not '
                                      'feature novelty',
        'known_limitation': 'a kicker has no offensive snap share and the '
                            'panel holds 47 kicker rows against 21,219 '
                            'receivers; his share is left MISSING rather '
                            'than filled with a special-teams number on an '
                            'offensive scale',
        'engine_flag': 'appearance_panel_2026'}


#: GSVU -- THE REAL CHALLENGER. GSV plus the 2026 week-1 rows built on the
#: SAME population construction R8 was fitted on. It differs from GSV in one
#: declared flag, and it is the only arm in which the current season reaches
#: the validated mechanism.
R9_W1P_GSVU_FLAGS = dict(R9_W1P_GSV_FLAGS)
R9_W1P_GSVU_FLAGS['appearance_w1_union'] = True

W1_UNION_REPAIR = {
    'component': 'W1U',
    'what': 'R8`s history walk reaches the forecast season: the 2026 week-1 '
            'rows are appended to its frame, built as the observed panel '
            'UNION the point-in-time depth chart with appeared = 0 for a '
            'listed player who took no offensive snap',
    'replaces': 'a frame ending at 2025 week 18, a league-wide rest week, so '
                'a week-2 forecast asked R8 what a player did most recently '
                'and was answered with a game half the league sat out',
    'not_the_panel_arm': 'the FROZEN mechanism`s injection used the panel '
                         'ALONE, which is the snap-count file, and its week-1 '
                         'base rate is 0.9265 against a fitted 0.5390. '
                         'Serving that skew read a 100%-snap starter as '
                         'evidence to LOWER him: Josh Allen 0.9625 to 0.8449, '
                         'James Cook 0.8381 to 0.6299',
    'evidence': 'union construction: 553 rows, 378 from the panel and 175 '
                'added by the depth chart, base rate 0.6275, all 30 teams '
                'charted point-in-time at their own week-1 kickoff. The '
                'fitted seasons run 0.4856 (2025) to 0.7476 (2020), pooled '
                '0.5390 over 4,176 rows, so the served population is inside '
                'the range the model was fitted on rather than 0.39 above it',
    'coefficients': 'NONE. appearance_r8.fit trains on s < season, so a 2026 '
                    'row cannot enter a 2026 fit and coef_sha256 is '
                    'identical with and without the injection',
    'mechanism_unchanged': 'R8 keeps the forward-chained Brier record that '
                           'the frozen challenger does not have. This adds '
                           'information to it; it does not replace it',
    'known_limitation': '`appeared = 0` means "listed and took no offensive '
                        'snap". It cannot distinguish a healthy scratch from '
                        'a dressed player who never got on the field -- and '
                        'neither could the training frame, which is the point',
    'governance': 'REHEARSAL_ONLY -- a frame change with its own identity, '
                  'never an edit to R9_W1P_GSV',
    'engine_flag': 'appearance_w1_union',
}

#: GSVUQ -- QBSEM. GSVU plus the cell-conditional relief rate. One flag.
R9_W1P_GSVUQ_FLAGS = dict(R9_W1P_GSVU_FLAGS)
R9_W1P_GSVUQ_FLAGS['qb_cell_relief'] = True

QBSEM_REPAIR = {
    'component': 'QBSEM',
    'what': 'the probability that a NON-STARTING quarterback takes any '
            'dropback is estimated per starter-state cell from the QB room`s '
            'own frame, instead of a rank-pooled weight that answers a '
            'different question',
    'replaces': '`p_reliever_by_rank`, which answers "given the role changed '
                'hands, WHO took it", used for both that and "did it change '
                'hands at all"',
    'defect': 'the board published QB lines on a different conditioning event '
              'from every other position. A rank-1 quarterback who did not '
              'start was returned to the field in about 93% of those worlds',
    'evidence': 'the room`s own depth-chart frame, 6,673 rows over 2,717 '
                'team-games. Cell (1,1,0): n=2,290, P(starter) 0.9284, '
                'P(db=0) 0.0694, and 164 non-starting rows of which 5 '
                'relieved -- 0.0305 raw, 0.0333 Jeffreys, against a pooled '
                'rank-1 weight of 0.3030. '
                'nfl/research/qbsem/predeclaration_qbsem.md',
    'coefficients': 'NONE ADDED. A cell rate under the module`s existing '
                    'Jeffreys Beta(1/2,1/2), the same prior and the same '
                    'cells `p_start` already uses',
    'unchanged': 'the starter-selection model, the reliever-identity model, '
                 'the exit hazard, the post-exit pool and the integer split. '
                 'Only the event "this non-starter returns at all" changes',
    'sparse_cells': 'a cell needs 30 non-starting rows to use its own rate; '
                    'below that the pooled rank weight is used and the '
                    'fallback is COUNTED per player, never silent',
    'known_limitation': 'the historical cell rate is estimated on a frame '
                        'that includes quarterbacks who were inactive, while '
                        'at serve time the eligibility gate has already '
                        'removed hard-OUT quarterbacks from the room. Applied '
                        'to a gate survivor this double-counts absence. The '
                        'exposure on this board is nil -- no 2026 week-2 '
                        'official report exists, so the gate removed no '
                        'quarterback -- and it is recorded rather than '
                        'repaired, because repairing it is a scope change',
    'governance': 'REHEARSAL_ONLY -- a mechanism change with its own '
                  'identity, never an edit to qb_room_v2 or to GSVU',
    'engine_flag': 'qb_cell_relief',
}

#: GSVUC -- CS1. GSVU plus current-season incumbency state. One flag.
R9_W1P_GSVUC_FLAGS = dict(R9_W1P_GSVU_FLAGS)
R9_W1P_GSVUC_FLAGS['current_season_state'] = True

#: QY1 -- the passing yards dealt as a PARTITION of the catches, not as a
#: share of their sum.
QY1_REPAIR = {
    'component': 'QY1',
    'what': 'a quarterback`s passing yards in a draw are the SUM OF A BLOCK '
            'of that team`s completion yardages, drawn by partitioning the '
            'multiset of per-catch yards into blocks of the credited '
            'completion counts',
    'replaces': 'nothing is deleted. `credit_passing_line` keeps its '
                'continuous-share path verbatim and takes the partition only '
                'when a candidate supplies the atoms, so every sealed arm '
                'reproduces bit for bit',
    'defect': '`pyds_q = cmp_q / team_cmp * team_pyds` makes passing yards a '
              'CONTINUOUS share of an integer team total. Measured: '
              '`qb/pyds` non-integer in 5,594 of 32,000 sealed cells '
              '(17.48%), the fractional parts being exactly the k/n '
              'completion-share denominators. A yard is not divisible',
    'why_not_a_hypergeometric': 'the atoms are SIGNED -- the frozen 2026 '
                                'receiving pools carry 2,043 negative '
                                'per-catch yardages out of 69,981, minimum '
                                '-13, and the repository holds 2,261 lawful '
                                'negative sealed `qb/pyds` cells. A '
                                'multivariate hypergeometric distributes '
                                'non-negative counts from an urn and would '
                                'have to be rescued by a clip, and a clip '
                                'breaks the HARD '
                                'qb_cross_layer_reconciliation, which '
                                'asserts team passing yards EQUALS player '
                                'receiving yards over exactly those negative '
                                'values',
    'holds_by_construction': 'the blocks partition the multiset, so the '
                             'per-passer yards sum to the team total exactly '
                             'and not within a tolerance; a block of '
                             'integers sums to an integer; an EMPTY block '
                             'sums to 0, so "no completion, no yards" needs '
                             'no np.where; and no step anywhere compares a '
                             'value against zero, so a negative total deals '
                             'like any other',
    'upstream': 'RC1 already drew these atoms and summed them away. '
                '`layers.receiving_conversion` now RETURNS them alongside '
                'its existing values -- byte-identical `receptions` and '
                '`receiving_yards` against HEAD, no added RNG call -- and '
                'that additivity is asserted against the pre-change source '
                'in nfl/tests/test_qb_yard_atoms.py, not asserted in prose',
    'separate_rng_stream': 'the permutation draws from its own generator '
                           '(0xC302) so the completion and touchdown '
                           'allocations are bit-identical to the incumbent '
                           'for the same seed. An arm comparison then '
                           'isolates the yardage change instead of measuring '
                           'a shifted random stream',
    'not_claimed': 'that integer yards FORECAST better. This repairs the '
                   'SUPPORT of a quantity whose realised values are '
                   'integers. Whether it improves a proper score is an '
                   'out-of-sample question and no acceptance gate in '
                   'nfl/research/qb_yards/predeclaration_signed_deal.md '
                   'makes that claim',
    'consequence_recorded_in_advance': '`qb/pyds` moves from the continuous '
                                       'class into Contract 4`s discrete '
                                       'class. Declared before the arm ran, '
                                       'not discovered after it',
    'governance': 'REHEARSAL_ONLY -- a mechanism change with its own '
                  'identity, never an edit to GSVUC or to any frozen arm',
    'engine_flag': 'qb_yard_atoms',
}

#: GSVUCY -- QY1. GSVUC plus the signed integer partition of passing yards.
#: One flag, one mechanism, one new identity.
R9_W1P_GSVUCY_FLAGS = dict(R9_W1P_GSVUC_FLAGS)
R9_W1P_GSVUCY_FLAGS['qb_yard_atoms'] = True

CS1_REPAIR = {
    'component': 'CS1',
    'what': 'the previous-primary passer and the season-boundary flag are '
            'read from CURRENT-SEASON evidence captured before the forecast '
            'instant, instead of from a panel that stops at the end of last '
            'season',
    'replaces': 'nothing. The panel is unchanged and is never rewritten; '
                'current-season rows are APPENDED in memory and only when a '
                'caller asks',
    'defect': 'panel_p3.csv.gz holds 2020-2025 with a maximum ordinal of '
              '202518 and ZERO rows for 2026, so a 2026 WEEK 2 forecast gave '
              'all 32 clubs a 2025 week-18 previous primary and classed all '
              '32 a season opener. Measured against 2026 week-1 play-by-play, '
              '7 of the 20 checkable clubs carried the WRONG previous primary',
    'evidence': '2026 week-1 play-by-play, 10 games over 20 clubs, retrieved '
                '2026-09-14T00:25:56Z; and week-1 snap counts over 30 clubs, '
                'retrieved 2026-09-14T18:33:36Z. Both strictly before the '
                '2026-09-16T15:45:14Z forecast instant. '
                'nfl/research/sbs/predeclaration_sbs.md',
    'coefficients': 'NONE ADDED. The repair changes which bytes answer an '
                    'existing question. There is no rate and no threshold',
    'proxy': 'a club with no play-by-play falls back to the QB with the most '
             'offensive snaps. The two agreed 20 of 20 on the week-1 overlap '
             'with 0 identity-bridge failures, and n = 20 is NOT a validated '
             'rate: no historical snap capture exists to check it against',
    'missing_clubs': 'a club with neither source keeps the frozen panel answer '
                     'and is NAMED, never inferred. For 2026 week 2 that is '
                     'exactly DEN and KC',
    'clock': 'enforced in code. A capture whose retrieval instant is not '
             'STRICTLY before the forecast instant is dropped and the drop is '
             'counted',
    'not_claimed': 'no better forecast. The model is fed the state that is '
                   'true rather than one nine months stale; whether that '
                   'forecasts better is an out-of-sample question this board '
                   'cannot answer',
    'governance': 'REHEARSAL_ONLY -- a new identity, never an edit to GSVU',
    'engine_flag': 'current_season_state',
}

ABLATION_NOTE = {
    'arms': {'R9_W1P_GS': 'baseline: R8 appearance, old availability, C3',
             'R9_W1P_GSV': 'A1 only: repaired current availability',
             'R9_W1P_GSP': 'A2 only: 2026 week-1 appearance panel',
             'R9_W1P_GSVP': 'A1 + A2'},
    'held_fixed': 'draw count, seed, written_at, game, code version, and SC2',
    'what_it_cannot_separate': (
        'A2 changes the appearance MECHANISM as well as the panel, because '
        'the panel injection is defined only for the frozen model and R8 is a '
        'different frame builder. So GSP-minus-GS is panel AND mechanism '
        'together, and it is labelled that way rather than called the panel '
        'effect.'),
    'appearance_mechanism_status': (
        'R8 carries forward-chained Brier evidence and the panel arm does '
        'not. The panel arm is a CHALLENGER. Which survives is decided by '
        'out-of-sample score, not by which has the newer features.'),
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
    # ---- the four matched ablation arms ----------------------------
    if mode == V1_CANDIDATE_R9_W1P_GS:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GS',
            value={'mode': V1_CANDIDATE_R9_W1P_GS,
                   'flags': dict(R9_W1P_GS_FLAGS),
                   'components': _sc2_base(),
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='the ablation BASELINE: R9_W1P_G plus SC2, so C3 completes '
                   'at any draw count. R8 appearance, old availability path')
    if mode == V1_CANDIDATE_R9_W1P_GSVUC:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSVUC',
            value={'mode': V1_CANDIDATE_R9_W1P_GSVUC,
                   'flags': dict(R9_W1P_GSVUC_FLAGS),
                   'components': _sc2_base() + [_avail_only(),
                                                dict(W1_UNION_REPAIR),
                                                dict(CS1_REPAIR)],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='CS1: GSVU with current-season incumbency state, so a '
                   'week-2 game is not treated as a season opener')
    if mode == V1_CANDIDATE_R9_W1P_GSVUCY:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSVUCY',
            value={'mode': V1_CANDIDATE_R9_W1P_GSVUCY,
                   'flags': dict(R9_W1P_GSVUCY_FLAGS),
                   'components': _sc2_base() + [_avail_only(),
                                                dict(W1_UNION_REPAIR),
                                                dict(CS1_REPAIR),
                                                dict(QY1_REPAIR)],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='QY1: GSVUC with the team passing yards PARTITIONED among '
                   'the passers as the catches they are, so a passing-yard '
                   'total is an integer by construction instead of a share '
                   'of one')
    if mode == V1_CANDIDATE_R9_W1P_GSVUQ:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSVUQ',
            value={'mode': V1_CANDIDATE_R9_W1P_GSVUQ,
                   'flags': dict(R9_W1P_GSVUQ_FLAGS),
                   'components': _sc2_base() + [_avail_only(),
                                                dict(W1_UNION_REPAIR),
                                                dict(QBSEM_REPAIR)],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='QBSEM: GSVU with the non-starter relief rate conditioned '
                   'on the starter-state cell, so QB publication semantics '
                   'match every other position')
    if mode == V1_CANDIDATE_R9_W1P_GSVU:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSVU',
            value={'mode': V1_CANDIDATE_R9_W1P_GSVU,
                   'flags': dict(R9_W1P_GSVU_FLAGS),
                   'components': _sc2_base() + [_avail_only(),
                                                dict(W1_UNION_REPAIR)],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='THE CHALLENGER: GSV plus the 2026 week-1 rows on the '
                   'population construction R8 was fitted on. One flag from '
                   'GSV, same coefficients, validated mechanism')
    if mode == V1_CANDIDATE_R9_W1P_GSV:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSV',
            value={'mode': V1_CANDIDATE_R9_W1P_GSV,
                   'flags': dict(R9_W1P_GSV_FLAGS),
                   'components': _sc2_base() + [_avail_only()],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='A1 ONLY: the baseline with current-state availability '
                   'evidence joined to eligibility. The appearance mechanism '
                   'is unchanged, so this is the Ty Johnson effect alone')
    if mode == V1_CANDIDATE_R9_W1P_GSP:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSP',
            value={'mode': V1_CANDIDATE_R9_W1P_GSP,
                   'flags': dict(R9_W1P_GSP_FLAGS),
                   'components': _sc2_base() + [_panel_only()],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='A2 ONLY: the baseline with the 2026 week-1 appearance '
                   'panel and the old availability path. Panel AND mechanism '
                   'move together here and the note says so')
    if mode == V1_CANDIDATE_R9_W1P_GSVP:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GSVP',
            value={'mode': V1_CANDIDATE_R9_W1P_GSVP,
                   'flags': dict(R9_W1P_GSVP_FLAGS),
                   'components': _sc2_base() + [_avail_only(), _panel_only()],
                   'ablation': dict(ABLATION_NOTE),
                   'candidate': True},
            detail='A1 + A2: both, for the interaction term')
    if mode == V1_CANDIDATE_R9_W1P_GA:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_GA',
            value={'mode': V1_CANDIDATE_R9_W1P_GA,
                   'flags': dict(R9_W1P_GA_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R9_W1P_REPAIR, R9_W1P_G_REPAIR,
                                               R9_W1P_GA_REPAIR],
                   'candidate': True},
            detail='R9_W1P_G with the appearance panel extended to 2026 week '
                   '1 and current-state availability joined to eligibility. '
                   'Same appearance coefficients; a longer panel and a '
                   'smaller eligible set')
    if mode == V1_CANDIDATE_R9_W1P_G:
        return Outcome.ok(
            'MODE_V1_CANDIDATE_R9_W1P_G',
            value={'mode': V1_CANDIDATE_R9_W1P_G,
                   'flags': dict(R9_W1P_G_FLAGS),
                   'components': manifest() + [R5_REPAIR, R6_REPAIR,
                                               R8_REPAIR, R9_REPAIR,
                                               R9_W1P_REPAIR,
                                               R9_W1P_G_REPAIR],
                   'candidate': True},
            detail='R9_W1P with the kneel, wr and te rush categories dealt '
                   'to named players. It changes what the board CLOSES over, '
                   'so it takes its own identity rather than editing the arm '
                   'it descends from')
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
