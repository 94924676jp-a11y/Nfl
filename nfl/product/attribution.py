"""Attribute a low (or high) central projection to a dominant MECHANISM.

WHAT THIS IS FOR

A board row reads "Mahomes 144.02 passing yards" and a reader's first question
is *why so low*. The engine's own answer is buried in a 1000-column draw
matrix: 41.3% of the simulated worlds give him zero, and in the rest he throws
for 245. "Low" is therefore not a statement about his passing; it is a
statement about how often the model thinks he is the quarterback.

This module turns that from a story into arithmetic. It reads a SEALED run --
artifact, manifest and draws, nothing else -- and splits the gap between the
unconditional projection and the conditional one into named mechanisms whose
contributions sum to the gap exactly.

WHAT THIS IS NOT

It changes no estimator, no parameter and no draw. It has no floors, no
adjustments and nothing fitted. Every constant in it is either an arithmetic
identity (a majority is > 1/2) or a declared reporting threshold stated with
its derivation. A diagnostic that quietly corrected the thing it was measuring
would destroy the measurement.

THE ALGEBRA, AND WHY THE PARTS SUM

For a metric Y over m draws, with p0 = P(Y = 0):

    U = E[Y]                      the board's unconditional projection
    C = E[Y | Y > 0]              the conditional projection
    U = (1 - p0) * C              identity, by definition of a conditional mean
    G = C - U = p0 * C            the gap

So `C / U = 1 / (1 - p0)` ALWAYS. That ratio is an identity and carries no
information about mechanism whatever -- it is worth saying plainly because the
first hand-worked case in this project quoted "1.70 = exactly 1/(1-0.413)" as
if it confirmed something. What the identity *does* establish is the thing
this module is built on: the ENTIRE unconditional/conditional gap is carried
by the zero mass. Attributing the gap is therefore exactly attributing p0.

And the per-draw form makes summation automatic:

    G = (1/m) * SUM_j (C - Y_j)           because the non-zero draws cancel:
                                          SUM_{Y_j>0} (C - Y_j) = 0 exactly
      = (1/m) * SUM_{j : Y_j = 0} C

Every zero draw contributes exactly C/m to the gap. Label the zero draws and
the mechanism contributions sum to G by construction, with no interaction term
to argue about and no residual to absorb.

THE CHANNEL MAP: WHICH MECHANISMS CAN EVEN FIRE

A mechanism that has no layer cannot produce a zero, and pretending otherwise
is how a residual acquires a confident name. V1's channels, per modelled
layer, read off the spec_version strings the sealed artifact carries:

    qb          'qb-v1-aggregate-then-allocate-1'
                eligibility: roster status (R5) + official-inactive exclusion
                appearance/participation: **ABSENT**. football_engine.py:501
                  builds the appearance population from RECEIVING_POS =
                  ('WR','TE','RB'). No quarterback has an appearance draw, so
                  no quarterback zero can be a participation event.
                role allocation: qb_allocation.allocate, a RIVALROUS room --
                  the primary's empirical share pool is modal at exactly 1.0.
    receiving   'nfl-nonqb-receiving-1'        appearance -> participation ->
                  p4c simplex. NON-rivalrous room: many players hold shares.
    rushing     'nfl-nonqb-rushing-1'          the SAME appearance indicator,
                  a different p4c simplex over the A1 running-back budget.

Two consequences do real work below. A quarterback's zero cannot be
PARTICIPATION. A running back is modelled in TWO rooms whose allocations are
conditionally independent given that one shared appearance indicator, which is
what makes his participation mass identifiable at all.

THE ORDER OF THE CASCADE IS LOAD-BEARING, SO IT IS ARGUED

Participation is resolved BEFORE role displacement. A player who is not on the
field necessarily has his room reallocated to a team-mate, so "a team-mate
holds the role" is ENTAILED by absence and is not evidence against it. Running
the displacement predicate first would relabel almost every absent running
back as ROLE_STATE. Measured on 2026_01_DEN_KC: P(a team-mate holds a carry
majority | RB1 has zero carries) = 0.973, while the identified participation
mass is 0.145 of a 0.150 zero mass. Displacement-first gets that case exactly
backwards.

WHAT IS HONESTLY NOT IDENTIFIED

For a player modelled in ONE room only, PARTICIPATION and PLAYER_ALLOCATION
are not separable from the sealed draws, because the appearance indicator is
not stored -- only its products are. Two identification strategies were tried
and BOTH FAIL; they are named here so nobody pays for them twice.

  (1) Volume-limit. "Thinness vanishes as team volume rises, availability does
      not, so p0 in the top volume tercile estimates P(not available)."
      REFUTED on this board: p0 is near volume-invariant because the allocator
      draws a SHARE, and a share does not improve with the size of the budget.
      WR6 p0 by team-target tercile: 0.667 / 0.670 / 0.662.
  (2) Binomial thinness bound. "P(zero | present) <= (1 - share)^volume, so
      P(not available) >= p0 - that."
      REFUTED: the p4c/A1 share draw can be exactly zero (the named share
      floor binds), so zeros do not come from multinomial sampling. It gives
      RB2 a bound of >= 0.168 where the identified value is 0.009.

So a single-room player's remaining mass is reported as UNKNOWN with
`unresolved_between = ('PARTICIPATION', 'PLAYER_ALLOCATION')` and a bound. The
fix is instrumentation, not estimation: storing the appearance indicator in
the sealed draw set (one bit per player per draw) closes the cell outright.

MECHANISMS WITH NO LAYER AT ALL

GAME_STATE and INJURY_LIMITATION are represented and always resolve to
NOT_MODELLED_IN_V1, with contribution None -- never 0.0. A measured zero and
an absent layer are different facts and this module refuses to render them the
same colour. Residual never lands there; it lands in OTHER_RESIDUAL, named.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product.distributions import Forecast                     # noqa: E402
from sportsplatform.governance.outcome import (Cause, Outcome,      # noqa: E402
                                               State)

SPEC_VERSION = 'nfl-low-projection-attribution-1'

# --------------------------------------------------------------- vocabulary
MECHANISMS = (
    'ELIGIBILITY',          # never had support: not in the pool before the draw
    'PARTICIPATION',        # an established player does not take the field
    'ROLE_STATE',           # he is on the field; someone else holds the role
    'TEAM_VOLUME',          # his team ran no plays of this kind in that world
    'PLAYER_ALLOCATION',    # he was in the room and the allocator gave him none
    'OTHER_RESIDUAL',       # named leftover; never silently folded elsewhere
    'EFFICIENCY',           # a LEVEL mechanism: yards per opportunity
    'GAME_STATE',           # no layer in V1
    'INJURY_LIMITATION',    # no layer in V1
    'UNKNOWN',              # honestly unresolved
)

# Mechanisms that describe the ZERO MASS (the unconditional/conditional gap).
ZERO_MECHANISMS = ('ELIGIBILITY', 'TEAM_VOLUME', 'PARTICIPATION', 'ROLE_STATE',
                   'PLAYER_ALLOCATION', 'OTHER_RESIDUAL', 'UNKNOWN')

# Mechanisms that describe the LEVEL of the conditional projection.
LEVEL_MECHANISMS = ('TEAM_VOLUME', 'PLAYER_ALLOCATION', 'EFFICIENCY',
                    'OTHER_RESIDUAL')

NOT_MODELLED = {
    'GAME_STATE': (
        'V1 has no game-state conditioning at any layer, so no draw in this '
        'artifact can be moved by score, clock or win probability. '
        'nfl/research/live/OPEN_DEFECTS.json D09, repaired: false.'),
    'INJURY_LIMITATION': (
        'V1 models whether a player appears, never how much he is limited '
        'once he does, and has no in-game injury transition either -- '
        'OPEN_DEFECTS D17 records a starter injured early and replaced, which '
        'the engine cannot represent. There is no layer whose output could '
        'carry this, so it cannot be attributed a share of anything.'),
}

# --------------------------------------------------------- declared numbers
#
# MATERIAL_RATIO. The gate the deliverable is defined on: a gap is material
# when the conditional projection exceeds the unconditional one by a tenth.
# It is a REPORTING threshold, not a model parameter; it moves no number. It
# is stated as a ratio rather than an absolute because the gap identity is
# multiplicative: C/U = 1/(1-p0), so 1.10 is exactly p0 >= 1/11 = 0.0909 for
# every metric on the board, in every unit, with no per-metric constant.
MATERIAL_RATIO = 1.10
MATERIAL_P0 = 1.0 - 1.0 / MATERIAL_RATIO          # 0.090909...

# MAJORITY. Not a tuned threshold: strictly more than half is the arithmetic
# definition of exclusivity, because at most one member of a room can hold it.
# The verdicts below are invariant for any threshold in (0.5, 0.6] on the
# 2026_01_DEN_KC board, which is reported rather than assumed.
MAJORITY = 0.5

# DOMINANCE. A mechanism is called dominant when it holds more of the zero
# mass than every other mechanism combined -- again a majority, for the same
# reason: at most one mechanism can satisfy it, so "dominant" never needs a
# tie-break rule. Below that, the verdict is UNKNOWN with the ranking shown.
DOMINANCE = 0.5

# SENSITIVITY_TOLERANCE. The dual-layer estimator is re-run within terciles of
# team volume to check it is not reading team-volume co-movement as a shared
# appearance indicator. The tolerance is the width at which the two answers
# would change a reported share by one percentage point of a typical zero
# mass; above it the estimate is withdrawn to UNKNOWN rather than defended.
SENSITIVITY_TOLERANCE = 0.02

# ------------------------------------------------------------ the layer map
#
# Keyed on the spec_version the SEALED artifact carries, so a board built by a
# different engine version is refused by name instead of silently attributed
# with the wrong channel set.
LAYER_CHANNELS = {
    'qb-v1-aggregate-then-allocate-1': {
        'layer': 'qb',
        'opportunity': 'db',
        'team_volume': 'team_dropbacks_part',
        'participation_channel': False,
        'rivalrous_room': True,
        'note': ('appearance runs on RECEIVING_POS only '
                 '(football_engine.py:501), so a quarterback carries no '
                 'appearance draw and no quarterback zero can be a '
                 'participation event'),
    },
    'nfl-nonqb-receiving-1': {
        'layer': 'receiving',
        'opportunity': 'targets',
        'team_volume': 'team_targets',
        'participation_channel': True,
        'rivalrous_room': False,
        'note': 'appearance_r8 -> participation -> p4c simplex over targets',
    },
    'nfl-nonqb-rushing-1': {
        'layer': 'rushing',
        'opportunity': 'carries',
        'team_volume': 'team_carries',
        'participation_channel': True,
        'rivalrous_room': False,
        'note': ('the SAME appearance indicator as receiving, then a p4c '
                 'simplex over the A1 running-back budget'),
    },
}


# The denominator the EFFICIENCY factor is read against, per metric. A yards
# metric divides by the attempts that produced it, never by the room's
# allocation quantity -- 245.34 passing yards over 34.41 ATTEMPTS is 7.13 per
# attempt, which is the number a reader can judge; over dropbacks it is 6.31,
# which mixes sacks into an efficiency it did not cause. A metric that IS its
# own opportunity has no efficiency factor and says so rather than reporting
# a vacuous 1.0.
LEVEL_DENOMINATOR = {
    'qb/pyds': 'att', 'qb/cmp': 'att', 'qb/ptd': 'att', 'qb/int': 'att',
    'qb/ryds': 'rush_opp', 'qb/rtd': 'rush_opp',
    'qb/att': 'db', 'qb/sacks': 'db', 'qb/scr': 'db',
    'qb/db': None, 'qb/rush_opp': None,
    'receiving/receiving_yards': 'targets',
    'receiving/receptions': 'targets',
    'receiving/receiving_td': 'targets',
    'receiving/targets': None,
    'rushing/rushing_td': 'carries',
    'rushing/carries': None,
}


# ------------------------------------------------- the label this set lacks
#
# D4 (2026-09-14) found a SECOND week-1 boundary pathology, live on tonight's
# board: `role_prior.assign_tiers` (nfl/production/nonqb/role_prior.py:147-176)
# ranks a room by PRIOR-SEASON trailing snap share and then appends everyone
# with no history AFTER every veteran who has any (`start = len(known)`,
# line 170). Replayed on week 1 of 2021-2024, 47 of 47 depth-chart rank-1
# skill players with no trailing history were placed below tier 1, 29 of them
# into tier 4 or worse; the tiers they received imply a 0.0604 target share
# against a realised 0.1031. `role_prior.weight` returns the tier mean EXACTLY
# at n_own = 0, so for such a player the tier IS the whole forecast. R8_FLAGS
# inherits role_prior=True (candidate_mode.py:190), so it is active here.
#
# IT DOES NOT FIT ANY LABEL IN `MECHANISMS`, AND IT MUST NOT BE MADE TO.
# The separation from ROLE_STATE is structural, not a matter of taste:
#
#   ROLE_STATE         which player holds a RIVALROUS role, and it varies
#                      PER DRAW. It has a per-draw indicator, so it is
#                      identified inside one run. Mahomes: 412 of 1000 draws.
#   ROLE_PRIOR         the player's allocation CENTRE in a NON-rivalrous room,
#                      set by a prior-season ranking rather than his current
#                      role. It is CONSTANT ACROSS EVERY DRAW of the run.
#   PLAYER_ALLOCATION  the realised split, per draw, GIVEN that centre.
#
# The consequence is the important part: because ROLE_PRIOR does not vary
# across draws, NO across-draw statistic can separate it from
# PLAYER_ALLOCATION. It is a bias in the location of an allocation, not an
# event inside one. Separating them needs a DIFFERENT KIND of evidence -- an
# external statement of the player's current role, compared against the
# ordering the model actually delivered. `board.json` carries `depth_chart`,
# which is exactly such a statement, so a SCREEN is computable (see
# `role_prior_screen`). Confirmation is not: it needs the trailing-history
# input and the assigned tier, and the sealed run records neither.
#
# Recording `tier` and `basis` from `assign_tiers` on the board would turn the
# screen into an identification. That is instrumentation, not estimation, and
# it is the cheapest fix available.
#
# A NOTE ON THE SHARED ROOT, WHICH IS NOT THE SAME AS A SHARED MECHANISM.
# Mahomes and this defect have one upstream cause in common -- a week-1 board
# reaching across the season boundary for a prior. That is an INPUT
# CONTAMINATION feeding two different channels. Naming the contamination is
# useful; collapsing the two channels into one label would not be, because
# they have different signatures, different detectability and different fixes.
TAXONOMY_GAP = {
    'missing_label': 'ROLE_PRIOR',
    'definition': ('the player\'s allocation centre in a non-rivalrous room '
                   'is set by a role/tier prior estimated from a different '
                   'information generation than the game belongs to'),
    'why_not_ROLE_STATE': ('ROLE_STATE is a per-draw contest for a rivalrous '
                           'role and carries a per-draw indicator; this is '
                           'constant across every draw of the run'),
    'why_not_PLAYER_ALLOCATION': ('PLAYER_ALLOCATION is the realised split '
                                  'given a centre; this is a displacement OF '
                                  'the centre, with a different remedy'),
    'separable_by': ('an external statement of current role (depth_chart) '
                     'against the ordering the draws deliver -- a screen'),
    'not_separable_by': ('any across-draw statistic, because the mechanism '
                         'does not vary across draws'),
    'to_make_it_identifiable': ('record role_prior.assign_tiers `tier` and '
                                '`basis` per player on the sealed board'),
    'shared_upstream_cause_with_ROLE_STATE': 'SEASON_BOUNDARY_PRIOR',
    'source': 'D4, 2026-09-14; nfl/production/nonqb/role_prior.py:147-176',
}

# The appearance layer's own boundary problem, carried onto every
# PARTICIPATION mass this module reports. It changes no number here; it says
# what the number is a measurement OF.
PARTICIPATION_CAVEAT = (
    'This is the mass the MODEL assigns to the player not taking the field. '
    'Whether that mass is right is a separate question and D4 (2026-09-14) '
    'reports it is not, on a week-1 board: R7/R8 carried appearance features '
    'INVERT across the season boundary -- prev_appeared == 0 gives an '
    'in-season appearance rate of 0.2778 (n=19,499) against 0.5079 crossed '
    '(n=1,134), and f_rate_ewma < 0.3 gives 0.3543 in-season against 0.7036 '
    'crossed. R8 carries these on one slope and the existing repair moves an '
    'intercept only, which cannot correct a slope whose sign flips. So a '
    'week-1 PARTICIPATION mass is correctly ATTRIBUTED and its LEVEL is '
    'suspect. This module states that and changes nothing.')


class AttributionRefused(RuntimeError):
    """Named. An attribution that cannot be computed says so."""


# ====================================================================== gap
def gap(y) -> dict:
    """U, p0, C, G for one metric's draws, with the identity checked.

    The identity is CHECKED rather than assumed because everything downstream
    is a partition of it. If U != (1-p0)*C to floating tolerance the draws are
    not what they claim to be and the right answer is a refusal.
    """
    y = np.asarray(y, float).reshape(-1)
    m = y.size
    if m == 0:
        raise AttributionRefused('DRAWS_EMPTY: a zero-width draw vector')
    z = (y == 0)
    n0 = int(z.sum())
    p0 = n0 / m
    u = float(y.mean())
    if n0 == m:
        return {'n_draws': m, 'n_zero': n0, 'p0': 1.0, 'unconditional': 0.0,
                'conditional': None, 'gap': None, 'gap_ratio': None,
                'degenerate': 'ALL_DRAWS_ZERO'}
    c = float(y[~z].mean())
    g = c - u
    recon = (1.0 - p0) * c
    if abs(recon - u) > 1e-9 * max(1.0, abs(u)):
        raise AttributionRefused(
            f'GAP_IDENTITY_VIOLATED: (1-p0)*C = {recon!r} against E[Y] = {u!r}')
    return {'n_draws': m, 'n_zero': n0, 'p0': p0, 'unconditional': u,
            'conditional': c, 'gap': g,
            'gap_ratio': (c / u) if u > 0 else None,
            'per_zero_draw_contribution': c / m,
            'identity': 'C - U = p0 * C, checked to 1e-9 relative'}


def is_material(gp) -> bool:
    """The declared reporting gate. Nothing else in this module uses it."""
    r = gp.get('gap_ratio')
    return r is not None and r >= MATERIAL_RATIO


# ================================================== dual-layer identification
def participation_mass(p_a, p_b, p_joint) -> dict:
    """P(the shared appearance indicator is off), from two rooms.

    Model, which is the engine's own construction rather than an assumption
    imposed on it (layers.participation multiplies ONE appearance indicator
    into both rooms; the two p4c allocations then draw on separate streams):

        Y_a = 0  iff  A = 0  or  (A = 1 and thin_a)
        Y_b = 0  iff  A = 0  or  (A = 1 and thin_b)
        thin_a independent of thin_b given A = 1

    With a = P(A=0), u = P(thin_a | A=1), v = P(thin_b | A=1):

        p_a = a + (1-a)u ,  p_b = a + (1-a)v ,  p_j = a + (1-a)uv

    Eliminating u and v gives one closed form and no free parameter:

        a = (p_j - p_a * p_b) / (1 + p_j - p_a - p_b)

    Nothing is fitted; this is the unique solution of three equations in three
    unknowns. It is FALSIFIABLE and the falsifications are checked: `a` must
    lie in [0, min(p_a, p_b)], and the denominator must be positive.
    """
    den = 1.0 + p_joint - p_a - p_b
    if den <= 1e-9:
        return {'state': 'UNIDENTIFIED',
                'reason': ('the two zero sets very nearly exhaust the draw '
                           f'space (denominator {den:.6f}); the system is '
                           'degenerate'),
                'estimate': None}
    a = (p_joint - p_a * p_b) / den
    hi = min(p_a, p_b)
    clamped = float(min(max(a, 0.0), hi))
    if a < -1e-9 or a > hi + 1e-9:
        return {'state': 'REFUTED', 'raw': float(a), 'clamped': clamped,
                'upper_bound': float(hi),
                'reason': (f'estimate {a:.6f} lies outside [0, {hi:.6f}]; the '
                           'conditional-independence model does not hold for '
                           'these two rooms and no participation mass is '
                           'claimed from it'),
                'estimate': None}
    return {'state': 'IDENTIFIED', 'estimate': clamped, 'raw': float(a),
            'clamped': clamped, 'upper_bound': float(hi),
            'p_a': float(p_a), 'p_b': float(p_b), 'p_joint': float(p_joint),
            'independent_joint': float(p_a * p_b),
            'excess_over_independence': float(p_joint - p_a * p_b)}


def participation_sensitivity(ya, yb, strat, n_strata=3) -> dict:
    """Re-run the estimator inside strata of `strat` (team volume).

    The one confound that could masquerade as a shared appearance indicator is
    team-volume co-movement: a low-play world thins both rooms at once. If the
    estimate is the same inside volume strata as it is pooled, that confound
    is not driving it. This is a CONTROL that is run, not a caveat that is
    written.
    """
    ya = np.asarray(ya, float).reshape(-1)
    yb = np.asarray(yb, float).reshape(-1)
    s = np.asarray(strat, float).reshape(-1)
    qs = np.quantile(s, [(i + 1) / n_strata for i in range(n_strata - 1)])
    band = np.digitize(s, qs)
    vals, clamped_n = [], 0
    for k in range(n_strata):
        sel = band == k
        if sel.sum() < 30:
            continue
        r = participation_mass(float((ya[sel] == 0).mean()),
                               float((yb[sel] == 0).mean()),
                               float(((ya[sel] == 0) & (yb[sel] == 0)).mean()))
        # A STRATUM ESTIMATE THAT LANDS JUST OUTSIDE [0, min(p_a,p_b)] IS NOT
        # A REFUTATION, IT IS A THIRD OF THE DRAWS. The bound is part of the
        # estimator's own definition, so a stratum value is taken at the bound
        # rather than discarded -- discarding them silently shrank this
        # control to a single stratum on the KC RB2 row, and a control with
        # one stratum is not a control.
        if 'clamped' in r:
            vals.append(r['clamped'])
            if r['state'] == 'REFUTED':
                clamped_n += 1
    pooled = participation_mass(float((ya == 0).mean()), float((yb == 0).mean()),
                                float(((ya == 0) & (yb == 0)).mean()))
    # A VERDICT NEEDS AT LEAST TWO STRATA. One stratum cannot disagree with
    # itself, so calling it PASS or FAIL would be reporting an opinion as a
    # measurement. It is NOT_RUN, and the caller withdraws to UNKNOWN.
    if len(vals) < 2 or pooled['state'] != 'IDENTIFIED':
        return {'state': 'NOT_RUN', 'n_strata_used': len(vals),
                'reason': ('fewer than two strata produced an estimate'
                           if len(vals) < 2 else
                           f"pooled estimate is {pooled['state']}"),
                'pooled': pooled.get('estimate'),
                'stratified': [float(v) for v in vals]}
    strat_mean = float(np.mean(vals))
    dev = abs(strat_mean - pooled['estimate'])
    return {'state': 'PASS' if dev <= SENSITIVITY_TOLERANCE else 'FAIL',
            'pooled': pooled['estimate'], 'stratified_mean': strat_mean,
            'stratified': [float(v) for v in vals],
            'n_strata_used': len(vals), 'n_strata_clamped': clamped_n,
            'absolute_deviation': dev, 'tolerance': SENSITIVITY_TOLERANCE}


# ============================================================ room geometry
def room_geometry(opportunity, row) -> dict:
    """How the room this player sits in allocates its opportunity.

    `opportunity` is (n_room, m). `row` is his index within it. Everything
    here is a statement about the ROOM, computed on the shared draw index.
    """
    o = np.asarray(opportunity, float)
    tot = o.sum(axis=0)
    with np.errstate(invalid='ignore', divide='ignore'):
        share = np.where(tot > 0, o / np.maximum(tot, 1e-12), 0.0)
    mine = o[row]
    present = mine > 0
    others = np.delete(share, row, axis=0)
    other_lead = others.max(axis=0) if others.size else np.zeros(o.shape[1])
    occ = (o > 0).sum(axis=0)
    return {
        'room_size': int(o.shape[0]),
        'share_given_present': (float(share[row][present].mean())
                                if present.any() else None),
        'mean_leader_share': float(share.max(axis=0).mean()),
        'mean_occupancy': float(occ.mean()),
        'p_other_holds_majority': float((other_lead > MAJORITY).mean()),
        'p_other_holds_majority_given_zero': (
            float((other_lead[~present] > MAJORITY).mean())
            if (~present).any() else None),
        'displaced': (other_lead > MAJORITY) & (~present),
        'team_total': tot,
    }


# ================================================================== cascade
def attribute_zero_mass(y, opportunity, row, team_volume, *,
                        channels, sibling=None, eligibility=None) -> dict:
    """Split p0 into mechanisms whose masses sum to p0 EXACTLY.

    `y`            (m,)          the reported metric's draws
    `opportunity`  (n_room, m)   the room's allocation quantity
    `row`          int           this player's row within the room
    `team_volume`  (m,)          his team's own volume for this layer
    `channels`     dict          from LAYER_CHANNELS, which mechanisms exist
    `sibling`      (m,) or None  the same player's opportunity in his OTHER
                                 room, which is what makes PARTICIPATION
                                 identifiable
    `eligibility`  dict or None  a row-level verdict that pre-empts everything

    Assignment is per-draw wherever a per-draw predicate is decisive, and a
    mass split where identification does not reach the individual draw. The
    difference is reported per mechanism as `basis`, because a reader is
    entitled to know which of the two he is looking at.
    """
    y = np.asarray(y, float).reshape(-1)
    m = y.size
    zero = (y == 0)
    n0 = int(zero.sum())
    parts, basis, notes = {}, {}, {}

    if eligibility:
        return {'p0': n0 / m, 'mass': {'ELIGIBILITY': n0 / m},
                'basis': {'ELIGIBILITY': 'ROW_LEVEL_VERDICT'},
                'notes': {'ELIGIBILITY': eligibility.get('reason', '')},
                'unresolved_between': (), 'closes': True}

    remaining = zero.copy()

    # 1. TEAM_VOLUME -- his side ran no plays of this kind in that world.
    tv = np.asarray(team_volume, float).reshape(-1)
    hit = remaining & (tv <= 0)
    parts['TEAM_VOLUME'] = int(hit.sum()) / m
    basis['TEAM_VOLUME'] = 'PER_DRAW'
    notes['TEAM_VOLUME'] = (
        f'team volume was zero in {int(hit.sum())} of {n0} zero draw(s); '
        f'its mean over all draws is {tv.mean():.3f}')
    remaining &= ~hit

    # 2. EFFICIENCY -- he was in the room and had opportunity in that world,
    #    and the metric still came out zero. That is a conversion event, not
    #    an allocation or an availability one, and it is the whole story for
    #    a touchdown market: a back with carries who did not score.
    own_opp = np.asarray(opportunity, float)[row]
    hit = remaining & (own_opp > 0)
    parts['EFFICIENCY'] = int(hit.sum()) / m
    basis['EFFICIENCY'] = 'PER_DRAW'
    notes['EFFICIENCY'] = (
        f'he held opportunity in {int(hit.sum())} of {n0} zero draw(s) and '
        f'the metric was still zero, so the zero is conversion, not access')
    remaining &= ~hit

    geo = room_geometry(opportunity, row)

    # 3. PARTICIPATION -- resolved BEFORE displacement; see the module note.
    part_state = 'NOT_MODELLED_FOR_THIS_LAYER'
    part_detail = channels.get('note', '')
    if channels.get('participation_channel'):
        if sibling is None:
            part_state = 'UNIDENTIFIED_SINGLE_ROOM'
            part_detail = (
                'this player is modelled in one room only. The appearance '
                'indicator is not stored in the sealed draw set, so his '
                'participation mass cannot be separated from allocation '
                'thinness. Storing that one bit per player per draw would '
                'close this cell outright.')
        else:
            sib = np.asarray(sibling, float).reshape(-1)
            own = np.asarray(opportunity, float)[row]
            est = participation_mass(float((own == 0).mean()),
                                     float((sib == 0).mean()),
                                     float(((own == 0) & (sib == 0)).mean()))
            sens = participation_sensitivity(own, sib, tv)
            if est['state'] == 'IDENTIFIED' and sens['state'] == 'PASS':
                a = min(est['estimate'], remaining.sum() / m)
                # Remove that mass from the remaining zero draws. WHICH
                # individual draws it is does NOT follow from the estimator,
                # so the removal is by count, taken from the draws where BOTH
                # rooms are zero -- the only draws where A = 0 is possible.
                # The assigned mass is then the INTEGER count actually
                # removed, so every part is a multiple of 1/m and the
                # partition closes exactly instead of to rounding.
                both = remaining & (own == 0) & (sib == 0)
                take = min(int(round(a * m)), int(both.sum()))
                idx = np.flatnonzero(both)[:take]
                remaining[idx] = False
                parts['PARTICIPATION'] = take / m
                basis['PARTICIPATION'] = 'MASS_SPLIT_DUAL_ROOM_ESTIMATOR'
                notes['PARTICIPATION'] = (
                    f"a = (p_j - p_a*p_b)/(1 + p_j - p_a - p_b) = "
                    f"{est['estimate']:.4f} from p_a={est['p_a']:.4f}, "
                    f"p_b={est['p_b']:.4f}, p_joint={est['p_joint']:.4f} "
                    f"(independence would give {est['independent_joint']:.4f}); "
                    f"volume-stratified control {sens['state']}; assigned as "
                    f"{take} of {m} draws")
                part_state = 'IDENTIFIED'
                part_detail = json.dumps({'estimate': est, 'control': {
                    k: v for k, v in sens.items() if k != 'stratified'}})
            else:
                if est['state'] != 'IDENTIFIED':
                    part_state = est['state']
                elif sens['state'] == 'NOT_RUN':
                    part_state = 'CONTROL_NOT_RUN'
                else:
                    part_state = 'WITHDRAWN_ON_SENSITIVITY'
                part_detail = est.get('reason') or json.dumps(sens)

    # 4. ROLE_STATE -- he is in the room and a named team-mate holds it.
    #    Requires the room to be rivalrous FOR HIM: when he is present he
    #    holds a majority himself. Otherwise there is no single role to lose.
    # RIVALROUSNESS IS A PROPERTY OF THE ALLOCATOR, NOT OF THE PLAYER, and
    # reading it off the player's own share was wrong. `qb_allocation` samples
    # the primary's share from an empirical pool whose modal value is exactly
    # 1.0 -- the room has ONE primary passer and the engine has no
    # representation of two quarterbacks splitting a game by design. The p4c
    # simplex is the opposite: it exists to spread a budget over many players.
    # Keying on the player instead sent every BACKUP quarterback's zeros to
    # PLAYER_ALLOCATION, because a backup's share given he plays is small --
    # which describes his role, not the mechanism of his zero. On this board a
    # team-mate held a dropback majority in 100% of EVERY quarterback's zero
    # draws, backups included.
    sgp = geo['share_given_present']
    rivalrous = bool(channels.get('rivalrous_room'))
    hit = remaining & geo['displaced'] if rivalrous else np.zeros(m, bool)
    parts['ROLE_STATE'] = int(hit.sum()) / m
    basis['ROLE_STATE'] = 'PER_DRAW'
    notes['ROLE_STATE'] = (
        f"share given present {sgp if sgp is None else round(sgp, 4)}; "
        f"the ALLOCATOR is {'rivalrous' if rivalrous else 'NOT rivalrous'}; "
        f"a team-mate held a majority in {int(hit.sum())} of the "
        f"{int(remaining.sum())} zero draw(s) still unassigned at this step")
    remaining &= ~hit

    # 5. What is left.
    left = float(remaining.sum()) / m
    unresolved = ()
    if left > 0:
        if part_state in ('UNIDENTIFIED_SINGLE_ROOM', 'WITHDRAWN_ON_SENSITIVITY',
                          'CONTROL_NOT_RUN', 'REFUTED', 'UNIDENTIFIED'):
            parts['UNKNOWN'] = left
            basis['UNKNOWN'] = 'PER_DRAW_BUT_MECHANISM_UNRESOLVED'
            notes['UNKNOWN'] = (
                'these zero draws are not ELIGIBILITY, not TEAM_VOLUME and '
                'not ROLE_STATE, each ruled out by measurement. They are '
                'PARTICIPATION or PLAYER_ALLOCATION and the sealed artifact '
                'cannot say which: ' + part_detail)
            unresolved = ('PARTICIPATION', 'PLAYER_ALLOCATION')
        else:
            parts['PLAYER_ALLOCATION'] = left
            basis['PLAYER_ALLOCATION'] = 'PER_DRAW'
            notes['PLAYER_ALLOCATION'] = (
                'he was on the field and in a room with no single holder, and '
                'the allocator gave him none of it')

    parts.setdefault('OTHER_RESIDUAL', 0.0)
    basis.setdefault('OTHER_RESIDUAL', 'PER_DRAW')
    total = sum(parts.values())
    if abs(total - n0 / m) > 1e-9:
        parts['OTHER_RESIDUAL'] = parts.get('OTHER_RESIDUAL', 0.0) \
            + (n0 / m - total)
        notes['OTHER_RESIDUAL'] = ('closing term; it exists so the parts sum '
                                   'to p0 exactly and is never a mechanism '
                                   'claim')
    return {'p0': n0 / m, 'mass': parts, 'basis': basis, 'notes': notes,
            'room': {k: v for k, v in geo.items()
                     if k not in ('displaced', 'team_total')},
            'participation_state': part_state,
            'unresolved_between': unresolved,
            'closes': abs(sum(parts.values()) - n0 / m) <= 1e-9}


def dominant(mass, p0) -> dict:
    """The mechanism holding a strict majority of the zero mass, or UNKNOWN."""
    if p0 <= 0:
        return {'mechanism': None, 'share': None,
                'reason': 'no zero mass to attribute'}
    ranked = sorted(((v / p0, k) for k, v in mass.items() if v > 0),
                    reverse=True)
    if not ranked:
        return {'mechanism': 'OTHER_RESIDUAL', 'share': 0.0,
                'reason': 'zero mass present but nothing assigned'}
    share, mech = ranked[0]
    if mech == 'UNKNOWN' or share <= DOMINANCE:
        return {'mechanism': 'UNKNOWN', 'share': float(share),
                'leading_candidate': mech,
                'ranking': [(k, round(float(s), 4)) for s, k in ranked],
                'reason': ('no mechanism holds a strict majority of the zero '
                           'mass' if mech != 'UNKNOWN' else
                           'the leading cell is itself unresolved')}
    return {'mechanism': mech, 'share': float(share),
            'ranking': [(k, round(float(s), 4)) for s, k in ranked]}


# ============================================== the ROLE_PRIOR screen (D4)
def role_prior_screen(rows) -> dict:
    """Does the model's ordering of a room disagree with the depth chart?

    `rows` is [{'gsis_id', 'depth_chart', 'share_given_present', 'conditional',
    'unconditional'}] for ONE room, where a room is (team, position) -- the
    same grouping key `role_prior.assign_tiers` uses, so the screen looks at
    the object the mechanism acts on rather than at a room of our own making.

    WHAT THIS IS. A screen, not an identification. A disagreement between the
    chart and the draws is CONSISTENT with the tier defect and is also
    consistent with a p4c weight that legitimately disagrees with a club's
    published ordering. The sealed run carries neither the trailing-history
    input nor the assigned tier, so it cannot tell those apart, and this
    function does not pretend to.

    THE SWAP-EQUIVALENT DELTA is an arithmetic restatement of the board and
    nothing else: it is what each of an inverted pair would project if their
    room shares were exchanged. No estimator is re-run, no weight is changed,
    and the number is never applied to anything. It exists so that "the model
    ranks him below his chart" comes with a magnitude in the metric's own
    units instead of being a direction.
    """
    got = [r for r in rows if r.get('share_given_present') is not None]
    if len(got) < 2:
        return {'state': 'ROOM_TOO_SMALL', 'n': len(got)}
    def chart_rank(r):
        d = ''.join(c for c in str(r.get('depth_chart') or '') if c.isdigit())
        return int(d) if d else 99
    by_share = sorted(got, key=lambda r: -r['share_given_present'])
    model_rank = {r['gsis_id']: i + 1 for i, r in enumerate(by_share)}
    out, inversions = [], 0
    for r in sorted(got, key=chart_rank):
        cr, mr = chart_rank(r), model_rank[r['gsis_id']]
        disp = mr - cr
        rec = {'gsis_id': r['gsis_id'], 'depth_chart': r.get('depth_chart'),
               'chart_rank': cr, 'model_rank': mr, 'displacement': disp,
               'share_given_present': r['share_given_present'],
               'unconditional': r.get('unconditional'),
               'conditional': r.get('conditional')}
        if disp > 0:
            inversions += 1
            # The man who actually occupies his chart slot in the model.
            occupant = by_share[cr - 1] if cr - 1 < len(by_share) else None
            if occupant and r['share_given_present'] > 0:
                ratio = (occupant['share_given_present']
                         / r['share_given_present'])
                rec['swap_equivalent'] = {
                    'occupant_of_his_chart_slot': occupant['gsis_id'],
                    'share_ratio': ratio,
                    'unconditional_if_swapped': (
                        (r.get('unconditional') or 0.0) * ratio),
                    'delta': ((r.get('unconditional') or 0.0) * (ratio - 1.0)),
                    'basis': ('arithmetic restatement of this board only; no '
                              'estimator re-run, nothing applied')}
        out.append(rec)
    severe = [r for r in out if r['chart_rank'] == 1 and r['displacement'] > 0]
    return {'state': 'OK', 'n': len(got), 'n_inversions': inversions,
            'n_rank1_displaced': len(severe),
            'severity': ('SEVERE_SIGNATURE_PRESENT' if severe else
                         ('MILD_ADJACENT_INVERSIONS' if inversions else
                          'CHART_AND_MODEL_AGREE')),
            'members': out,
            'what_it_cannot_say': (
                'whether an inversion is the assign_tiers defect or a p4c '
                'weight legitimately disagreeing with the chart. The sealed '
                'run records neither the trailing-history input nor the '
                'assigned tier, so that is UNATTRIBUTABLE FROM THE ARTIFACT.')}


# ======================================================== conditional level
def level_factors(y, opportunity_row, team_volume, mask,
                  denominator=None, denominator_name=None) -> dict:
    """Factorise the CONDITIONAL level exactly, with the interaction named.

        C = E[Y | Y>0]  =  Tbar * sbar * ebar * K

    with K = C / (Tbar*sbar*ebar) carried explicitly rather than dropped, so
    that in logs the parts sum to log C with no approximation. This is the
    half of the diagnostic that answers "and is the conditional projection
    itself low", which is a different question from why there are zeros.
    """
    y = np.asarray(y, float).reshape(-1)[mask]
    o = np.asarray(opportunity_row, float).reshape(-1)[mask]
    t = np.asarray(team_volume, float).reshape(-1)[mask]
    if y.size == 0:
        return {'state': 'NO_CONDITIONAL_SAMPLE'}
    c = float(y.mean())
    tbar = float(t.mean())
    ok = t > 0
    sbar = float((o[ok] / t[ok]).mean()) if ok.any() else None
    if denominator is None:
        ebar, dbar = None, None
    else:
        dnm = np.asarray(denominator, float).reshape(-1)[mask]
        dbar = float(dnm.mean())
        ebar = float(y.sum() / dnm.sum()) if dnm.sum() > 0 else None
    out = {'state': 'OK', 'conditional': c, 'team_volume': tbar,
           'share_of_team_volume': sbar, 'per_unit': ebar,
           'unit': denominator_name,
           'unit_mean': dbar,
           'opportunities': float(o.mean()),
           'n_conditional_draws': int(y.size)}
    if denominator is None:
        out['efficiency_factor'] = (
            'NOT_APPLICABLE: this metric IS its own opportunity, so there is '
            'no conversion step to attribute')
    if sbar and ebar and tbar and dbar:
        prod = tbar * sbar * ebar * (dbar / max(float(o.mean()), 1e-12))
        out['interaction_K'] = c / prod if prod else None
        out['check'] = ('log C = log T + log s + log(unit/opportunity) + '
                        'log e + log K, exact by construction of K')
    return out


# ================================================================== reading
def _board_meta(directory) -> dict:
    p = pathlib.Path(directory) / 'board.json'
    if not p.exists():
        return {}
    b = json.loads(p.read_text())
    return {q['gsis_id']: q for q in b.get('players', [])}


def attribute_run(directory) -> Outcome:
    """Attribute every metric of every player on ONE sealed run.

    Reads the sealed artifact, its manifest and its draws. Writes nothing,
    fetches nothing, and touches no estimator.
    """
    d = pathlib.Path(directory)
    try:
        fc = Forecast(d)
    except Exception as exc:                                   # noqa: BLE001
        return Outcome.blocked(
            'SEALED_RUN_UNREADABLE', f'{d}: {exc}', cause=Cause.DATA)
    man = fc.manifest or {}
    layers = man.get('layers') or {}
    if not layers:
        return Outcome.blocked(
            'DRAW_MANIFEST_ABSENT',
            f'{d} carries no player_draws_manifest layers, so rows cannot be '
            f'addressed by gsis_id and a positional read is forbidden',
            cause=Cause.DATA)

    # Refuse an engine version this map does not describe, rather than
    # attributing it with the wrong channel set.
    unknown = {k: (v.get('spec_version')) for k, v in layers.items()
               if k != 'team_volume'
               and v.get('spec_version') not in LAYER_CHANNELS}
    if unknown:
        return Outcome.blocked(
            'LAYER_SPEC_UNKNOWN',
            f'{unknown} is not in LAYER_CHANNELS. Which mechanisms can fire '
            f'is a fact about the engine version, so an unmapped version is '
            f'refused rather than guessed.',
            cause=Cause.GOVERNANCE, unknown=unknown)

    meta = _board_meta(d)
    art = fc.artifact
    teams = art.get('team_ids') or []
    # Row addressing: gsis_id -> row, from the manifest's own row_ids.
    rows = {lay: {g: i for i, g in enumerate(v.get('row_ids') or [])}
            for lay, v in layers.items()}

    def team_of(pid):
        return (meta.get(pid) or {}).get('team')

    # Room membership: same team, same layer, taken from the manifest rows.
    def room(lay, team):
        return [g for g in (layers[lay].get('row_ids') or [])
                if team_of(g) == team]

    # A row-level eligibility verdict, from the artifact's own governance.
    board = json.loads((d / 'board.json').read_text()) if \
        (d / 'board.json').exists() else {}
    deferred_teams = []
    for lg in (board.get('layer_governance') or []):
        for w in (lg.get('warnings') or []):
            if 'APPEARANCE_TEAM_DEFERRED' in w:
                deferred_teams = [t for t in teams if f'{t} is ' in w]

    modelled = set(art.get('player_ids') or [])
    with_rows = set(art.get('distributions') or {})
    absent = sorted(modelled - with_rows)

    out, n_material = {}, 0
    for pid, block in fc.players().items():
        pmeta = meta.get(pid, {})
        team = pmeta.get('team')
        per_player = {'team': team, 'position': pmeta.get('position'),
                      'depth_chart': pmeta.get('depth_chart'),
                      'layers': sorted(block), 'metrics': {}}
        # The sibling room, which is what makes participation identifiable.
        sib_vec = {}
        for lay in block:
            ch = LAYER_CHANNELS[layers[lay]['spec_version']]
            v = fc.vector(lay, ch['opportunity'], pid)
            if v is not None:
                sib_vec[lay] = v
        for lay, keys in block.items():
            ch = LAYER_CHANNELS[layers[lay]['spec_version']]
            opp_key = ch['opportunity']
            mates = room(lay, team)
            arr = fc.arrays.get(f'{lay}__{opp_key}')
            if arr is None or not mates or pid not in rows[lay]:
                continue
            ridx = [rows[lay][g] for g in mates]
            opp = np.asarray(arr, float)[ridx]
            row = mates.index(pid)
            tvv = fc.team_vector(ch['team_volume'], team)
            if tvv is None:
                tvv = opp.sum(axis=0)
            sib = None
            for other, vec in sib_vec.items():
                if other != lay:
                    sib = vec
                    break
            for key in keys:
                y = fc.vector(lay, key, pid)
                if y is None:
                    continue
                try:
                    gp = gap(y)
                except AttributionRefused as exc:
                    per_player['metrics'][f'{lay}/{key}'] = {
                        'state': 'REFUSED', 'detail': str(exc)}
                    continue
                rec = {'gap': gp, 'material': is_material(gp)}
                if gp.get('conditional') is not None:
                    az = attribute_zero_mass(
                        y, opp, row, tvv, channels=ch, sibling=sib,
                        eligibility=None)
                    rec['zero_mass'] = az
                    rec['dominant'] = dominant(az['mass'], az['p0'])
                    rec['contribution_to_gap'] = {
                        k: v * gp['conditional']
                        for k, v in az['mass'].items()}
                    dn = LEVEL_DENOMINATOR.get(f'{lay}/{key}', 'UNMAPPED')
                    if dn == 'UNMAPPED':
                        rec['level'] = {
                            'state': 'NO_DENOMINATOR_DECLARED',
                            'detail': (f'{lay}/{key} is not in '
                                       f'LEVEL_DENOMINATOR, so no efficiency '
                                       f'factor is claimed for it')}
                    else:
                        dvec = (fc.vector(lay, dn, pid)
                                if dn is not None else None)
                        rec['level'] = level_factors(
                            y, opp[row], tvv, np.asarray(y, float) > 0,
                            denominator=dvec, denominator_name=dn)
                if rec['material']:
                    n_material += 1
                per_player['metrics'][f'{lay}/{key}'] = rec
        out[pid] = per_player

    # ----------------------------------------------------- ROLE_PRIOR screen
    # Rooms are (team, position) because that is `assign_tiers`'s own grouping
    # key, and the opportunity metric is the one the allocator splits.
    screens = {}
    for lay, spec in ((l, v.get('spec_version')) for l, v in layers.items()
                      if l != 'team_volume'):
        ch = LAYER_CHANNELS[spec]
        if ch['rivalrous_room']:
            continue                       # the QB room is ROLE_STATE's, not this
        opp_key = ch['opportunity']
        arr = fc.arrays.get(f'{lay}__{opp_key}')
        if arr is None:
            continue
        groups = {}
        for g in (layers[lay].get('row_ids') or []):
            q = meta.get(g) or {}
            groups.setdefault((q.get('team'), q.get('position')), []).append(g)
        for key, mates in sorted(groups.items(), key=lambda kv: str(kv[0])):
            ridx = [rows[lay][g] for g in mates if g in rows[lay]]
            if len(ridx) < 2:
                continue
            sub = np.asarray(arr, float)[ridx]
            tot = sub.sum(axis=0)
            recs = []
            for k, g in enumerate([g for g in mates if g in rows[lay]]):
                geo = room_geometry(sub, k)
                y = fc.vector(lay, opp_key, g)
                gp = gap(y) if y is not None else {}
                recs.append({'gsis_id': g,
                             'depth_chart': (meta.get(g) or {}).get(
                                 'depth_chart'),
                             'share_given_present': geo['share_given_present'],
                             'unconditional': gp.get('unconditional'),
                             'conditional': gp.get('conditional')})
            screens[f'{key[0]}|{key[1]}|{lay}/{opp_key}'] = \
                role_prior_screen(recs)

    return Outcome.ok(
        'ATTRIBUTION_OK',
        value={'game_id': art.get('game_id'),
               'run_dir': str(d),
               'run_id': man.get('run_id'),
               'draw_content_digest': fc.content_digest,
               'n_draws': fc.n_draws,
               'spec_version': SPEC_VERSION,
               'material_ratio': MATERIAL_RATIO,
               'deferred_teams': deferred_teams,
               'structurally_absent': {
                   'mechanism': 'ELIGIBILITY',
                   'n_in_modelled_pool': len(modelled),
                   'n_with_a_distribution': len(with_rows),
                   'n_absent': len(absent),
                   'gap_arithmetic': ('NONE. These rows carry no draws, so '
                                      'there is no unconditional and no '
                                      'conditional projection to compare and '
                                      'no gap to split. ELIGIBILITY is the '
                                      'whole verdict and its magnitude is '
                                      'not a number on this scale.'),
                   'limitation': ('the sealed run records the COUNT and an '
                                  'aggregate reason but not a per-row cause, '
                                  'so this module cannot say which of the '
                                  f'{len(absent)} was dropped for roster '
                                  'status, for team deferral, or for never '
                                  'being a skill position. Attribution at row '
                                  'level needs the run to record it.'),
                   'ids': absent},
               'not_modelled': dict(NOT_MODELLED),
               'taxonomy_gap': dict(TAXONOMY_GAP),
               'participation_caveat': PARTICIPATION_CAVEAT,
               'role_prior_screen': screens,
               'players': out},
        n_players=len(out), n_material_metrics=n_material,
        game_id=art.get('game_id'), spec_version=SPEC_VERSION)


if __name__ == '__main__':                                       # pragma: no cover
    o = attribute_run(sys.argv[1])
    print(o)
    if o.state is State.PASS:
        print(json.dumps(o.evidence, indent=1, default=str))
