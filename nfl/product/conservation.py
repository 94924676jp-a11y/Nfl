"""Team-level conservation of OPPORTUNITY MASS, per draw and per team.

WHAT THIS IS, AND WHY IT IS NOT `draw_coherence`
================================================
`nfl.production.draw_coherence` asks, of one cell: is this state IMPOSSIBLE?
It answers in violating-cell counts, and it gates. That is per-cell
impossibility and it is a different object from the one here.

This file asks a conservation question instead: a team had some quantity of
opportunity in a draw -- dropbacks, throws, carries -- and the model dealt it
out to named owners. **Did the pieces add up, and if they did not, how much
mass is unaccounted for and WHO is supposed to own it?**

The two differ in three ways that matter:

* A CONTAINMENT CHECK PASSES ON LOST MASS. `sum(targets) <= sum(attempts)` is
  satisfied by a team that deals ZERO targets. Every one of the 35 throws has
  gone somewhere unnamed and the inequality is perfectly happy. Only a
  conservation view sees the hole, because only a conservation view asks what
  the rest of the mass was.
* A VIOLATION COUNT DISCARDS THE SIZE. 464 cells over a bound and 464 cells
  over it by 9.96 carries read identically in a tally. The residual's
  magnitude is the whole finding.
* THE OWNER IS THE POINT. Unowned mass is NOT automatically a defect. A
  throwaway is an attempt that is not a target, and the C3 target budget deals
  a named `other` pool to receivers outside the modelled set. Neither is
  stored in the artifact. The job of this file is to make that mass VISIBLE
  AND NAMED -- its size, and whose it is -- never to flag it and never, ever,
  to close the gap by adjusting anything.

DIAGNOSTICS ONLY. NOTHING HERE REPAIRS.
=======================================
There is no clip, no renormalisation, no survivor reallocation, no "assign the
remainder to fringe" anywhere in this module, and there must never be. An
invariant asserts; it does not repair. If a residual here is large, the answer
is a finding, not a correction. This module also does not re-gate anything
`draw_coherence` already gates: where a HARD check there covers the same
identity, this file names it and defers to it by name rather than restating it
as a second, weaker verdict.

THE THREE TRAPS, EACH OF WHICH HAS ALREADY FIRED ONCE
=====================================================
1. **THE STORED TEAM TOTAL IS NOT THE ALLOCATION DENOMINATOR.** Under C3 the
   target budget is the QUARTERBACKS' ATTEMPTS
   (`football_engine.py` C3 block; `shared_pass.targeted_throws`), and
   `team_volume/team_targets` is a SEPARATE, UNUSED D1 draw that the engine
   marks `d1_team_targets_unused: True` and `run_forecast` seals anyway under
   a name that says it is the team's targets. WS09 J-12 falsified it against
   the dealt targets at r = 0.79-0.84, exact in 0.00% of draws. Measured live
   on DEN@KC: stored 28.70 against a C3 budget of 35.41, a gap of -6.70 on the
   mean and up to 19.01 against the dealt count on a single draw.
   A dashboard that used the stored total as the denominator would report a
   false violation on every board. So this file NEVER uses it as one. It
   measures the gap instead, under `stored_team_targets_is_not_the_denominator`,
   so the trap is a visible number rather than a comment someone has to read.
   `team_volume/team_carries` carries the same defect one layer along (J-13:
   the SC1-coupled vector the engine partitioned is not the vector that is
   sealed), and that is recorded on the carry checks rather than papered over.
2. **A TEAM CAN HAVE NO MODELLED LAYER AT ALL.** On DEN@KC the appearance
   layer ran on KC only -- DEN is `APPEARANCE_TEAM_DEFERRED` -- so DEN has no
   receiving and no rushing rows. That is NOT_APPLICABLE with the reason
   named. It is NOT zero mass, it is NOT a closure failure, and it must never
   be summed into a slate total as though the team had dealt nothing. Every
   per-team record here carries its own applicability, and an absent layer
   produces a stated absence rather than a zero.
3. **A RESIDUAL REPORTED AS A MEAN IS A RESIDUAL HIDDEN.** The rush residual
   on KC has mean +0.1555, which is 0.62% of a 25.24-carry level and reads as
   a rounding crumb. Its standard deviation is 3.99, it runs from -9.96 to
   +28.08, and it is NEGATIVE -- over-allocated, carries dealt twice -- in 464
   of 1000 draws. The mean is the average of a quantity that changes sign in
   nearly half the draws, and summarising it by that mean is how the finding
   disappears. So every residual here reports its distribution, and any
   residual whose sign changes across draws is flagged `sign_changes`, which
   is a FACT about the sample and not a threshold anybody chose.

WHAT A RESIDUAL'S OWNER MEANS, AND WHY `owner_stored` IS A FIELD
===============================================================
Each residual names the components the contract says hold it. Some of those
components are not in the sealed artifact at all:

  * the untargeted-throw pool (throwaways, spikes) -- drawn in
    `shared_pass.targeted_throws`, never sealed;
  * the `other` receiver pool -- the share held by players outside the
    modelled set, dealt by `shared_pass.deal_targets`, never sealed;
  * A1's `kneel`, `wr`, `te` and `fringe` carry categories -- partitioned in
    `rushing_a1.allocate`, never sealed.

Where the owner is unstored, the residual can be MEASURED but not
ATTRIBUTED, and `owner_stored=False` says exactly that. It is the difference
between "1.91 targets went to throwaways and unmodelled receivers in some
unknown split" and "1.91 targets are missing", and reporting the second when
the truth is the first is a manufactured defect.

ROWS ARE RESOLVED BY IDENTITY, NEVER POSITIONALLY
=================================================
Row identity lives in `manifest['layers'][layer]['row_ids']`, joined to team
through `board.json['players'][].team`. `team_volume` has `row_axis == 'team'`
and its row ids ARE team codes. Nothing in this file indexes one layer's rows
with another layer's positions.

REGIME IS DECLARED, NOT INFERRED
================================
Three of the closures below hold only under C3, and the dropback closure only
under R2. Which components were live is read from the artifact's
`candidate_components_applied` -- a DECLARATION the run wrote about itself --
and never guessed from the numbers. Inferring "C3 must have been on, look how
well the yards agree" would be asserting the conclusion from the evidence
meant to test it.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause, Outcome,     # noqa: E402
                                               State)

SPEC_VERSION = 'nfl-team-conservation-1'

# Integer accumulation slack in float64 over a whole room. NOT a modelling
# tolerance: no closure below is given room chosen to let a board pass.
TOL = 1e-6
# Yardage summed over a receiver room. The measured worst residual in the
# repository on the C3 identity is 0.0.
YARD_TOL = 1e-4

# --- classes --------------------------------------------------------------
# CLOSURE      an EXACT identity the model contract says holds by
#              construction. A deviation is a defect in the construction, and
#              it is reported as a failure of this dashboard.
# RESIDUAL     real mass whose owner is named. It is MEASURED and never
#              judged: a non-zero residual here is information, not a fault.
# CONTAINMENT  an inequality that is a genuine impossibility when breached,
#              but which `draw_coherence` already owns as a gate. Restated
#              here only to carry the SIZE and the sign, and explicitly
#              non-gating so that two files cannot disagree about one rule.
# ABSENT       the contract is named in prose or in a design document but no
#              quantity in the sealed artifact can express it. Recorded so
#              the gap is a row in the table rather than a silence.
CLOSURE = 'CLOSURE'
RESIDUAL = 'RESIDUAL'
CONTAINMENT = 'CONTAINMENT'
ABSENT = 'ABSENT_CONTRACT'

CONTRACTS = {
    # ------------------------------------------------ dropbacks / QB room
    'team_dropback_partition': {
        'class': CLOSURE, 'view': 'dropbacks', 'unit': 'team-draw',
        'layers': ('qb',), 'regime': None, 'tol': TOL,
        'asserts': 'sum over the QB room of db == sum over the QB room of '
                   '(att + sacks + scr), per team per draw',
        'contract': 'qb_accounting.PER_DRAW_IDENTITIES.dropback_identity -- a '
                    'dropback ends in exactly one of the three. The per-cell '
                    'form is HARD in draw_coherence.qb_dropback_partition; '
                    'this is the room-level sum, which is what a team volume '
                    'is built from.',
        'residual_owner': None, 'owner_stored': True},
    'qb_room_closes_on_team_dropbacks': {
        'class': CLOSURE, 'view': 'dropbacks', 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'), 'regime': 'R2', 'tol': TOL,
        'asserts': 'sum over the QB room of db == max(rint(team_volume/'
                   'team_dropbacks_part), 0), per team per draw, EXACTLY',
        'contract': 'R2. qb_accounting.apportion_dropbacks splits an INTEGER '
                    'team budget by largest remainder, so the room closes on '
                    'the rounded level by construction in every draw. The '
                    'rounding is the level owner\'s and is measured '
                    'separately below rather than folded in here.',
        'residual_owner': None, 'owner_stored': True},
    'team_dropback_level_rounding_residual': {
        'class': RESIDUAL, 'view': 'dropbacks', 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'), 'regime': 'R2', 'tol': None,
        'asserts': 'measures sum(db) - team_volume/team_dropbacks_part, the '
                   'CONTINUOUS level, per team per draw. Bounded by 0.5 in '
                   'absolute value by the rint above.',
        'contract': 'D1 emits a continuous dropback level; R2 needs an '
                    'integer budget. The gap is the integerisation and '
                    'nothing else.',
        'residual_owner': 'R2 level rounding (rint of D1\'s continuous level)',
        'owner_stored': True},

    # ------------------------------------------------------------ targets
    'target_opportunity_closes': {
        'class': RESIDUAL, 'view': 'targets', 'unit': 'team-draw',
        'layers': ('qb', 'receiving'), 'regime': 'C3', 'tol': None,
        'asserts': 'measures rint(sum QB att) - sum over the receiver room of '
                   'targets, per team per draw. Under C3 the exact identity '
                   'is sum_i targets_i + other + untargeted == rint(sum att); '
                   'two of its three right-hand terms are not in the '
                   'artifact, so what is evaluable here is the residual that '
                   'holds both.',
        'contract': 'C3. shared_pass.targeted_throws draws a NAMED untargeted '
                    'pool (throwaways and spikes) from the throw budget; '
                    'shared_pass.deal_targets partitions the remainder '
                    'between the modelled receivers and a NAMED `other` pool. '
                    'football_engine asserts sum_i targets_i + other == '
                    'targeted exactly, per team per draw.',
        'residual_owner': 'untargeted throws (shared_pass.targeted_throws) '
                          'PLUS the `other` pool of unmodelled receivers '
                          '(shared_pass.deal_targets)',
        'owner_stored': False,
        'not_a_defect': 'A positive residual here is EXPECTED and lawful. A '
                        'throwaway is an attempt that is not a target. The '
                        'residual is reported so its size is visible; it is '
                        'not a violation and must not be presented as one.'},
    'stored_team_targets_is_not_the_denominator': {
        'class': RESIDUAL, 'view': 'targets', 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'), 'regime': 'C3', 'tol': None,
        'asserts': 'measures team_volume/team_targets - rint(sum QB att). '
                   'Reported so the trap is a number, never used as a '
                   'denominator. WHAT THE NUMBER MEANS DEPENDS ON THE ARM, '
                   'and reading it as one thing is how the pin below went '
                   'stale: see `two_regimes`.',
        'two_regimes': 'BEFORE `publish_partitioned_team_targets` (R9_W1P) '
                       'the stored vector is D1`s separately drawn CONTINUOUS '
                       'level, which nothing partitions, so this gap is the '
                       'distance between two unrelated numbers and exact '
                       'agreement has probability ~0. FROM R9_W1P the board '
                       'publishes the level the partition consumed, so the '
                       'gap is identically `-untargeted` -- it can only be '
                       'non-positive, and it is ZERO exactly when no throw in '
                       'that draw was a throwaway or a spike. Measured on '
                       'five sealed boards: gap <= 0 in 1.0000 of cells, and '
                       'P(gap = 0) matches E[(1-u)^throws] with u = 0.042320 '
                       'to within 0.02. nfl/research/sc2/'
                       'STORED_TARGET_AGREEMENT_982.md',
        'contract': 'WS09 J-12, FALSIFIED FOR THE ARMS THAT PREDATE THE '
                    'REPAIR: there the stored vector is a separate unused D1 '
                    'draw, football_engine records `d1_team_targets_unused: '
                    'True`, and run_forecast seals the unused vector under a '
                    'name that says it is the team`s targets. From R9_W1P '
                    'that is no longer what is sealed, and the agreement '
                    'this check now reports is the repair working rather '
                    'than a defect appearing.',
        'residual_owner': 'D1 team_volume, a second owner of one football '
                          'quantity; the number is stored but the game did '
                          'not use it',
        'owner_stored': True,
        'not_a_defect': 'This row is a WARNING ABOUT THE ARTIFACT, not a '
                        'measurement of the forecast. A large gap here says '
                        'the sealed field is misnamed, which is already '
                        'known; it says nothing about whether targets closed.'},
    'targets_within_throw_budget': {
        'class': CONTAINMENT, 'view': 'targets', 'unit': 'team-draw',
        'layers': ('qb', 'receiving'), 'regime': 'C3', 'tol': TOL,
        'asserts': 'sum of receiver targets <= rint(sum QB att), per team per '
                   'draw',
        'contract': 'every target is a pass the team threw in that draw.',
        'gated_elsewhere': 'draw_coherence.team_targets_within_team_attempts '
                           '(HARD). Carried here for the SIZE and sign only; '
                           'this module does not re-gate it.',
        'residual_owner': None, 'owner_stored': True},

    # ------------------------- the passing line, counted from both sides
    'receptions_close_on_completions': {
        'class': CLOSURE, 'view': 'passing_line', 'unit': 'team-draw',
        'layers': ('qb', 'receiving'), 'regime': 'C3', 'tol': TOL,
        'asserts': 'sum of receiver receptions == sum of QB cmp, per team per '
                   'draw',
        'contract': 'C3. One completed pass counted from two sides. The '
                    'passer line is CREDITED FROM the receiving event, so a '
                    'difference is arithmetic, not a disagreement about '
                    'football.',
        'gated_elsewhere': 'draw_coherence.team_passing_line_closes_on_'
                           'receiving (HARD)',
        'residual_owner': None, 'owner_stored': True},
    'receiving_yards_close_on_passing_yards': {
        'class': CLOSURE, 'view': 'passing_line', 'unit': 'team-draw',
        'layers': ('qb', 'receiving'), 'regime': 'C3', 'tol': YARD_TOL,
        'asserts': 'sum of receiving_yards == sum of QB pyds, per team per '
                   'draw',
        'contract': 'C3, same shared event. Lawfully negative on either side '
                    '-- a catch for a loss is ordinary football -- so this is '
                    'an EQUALITY and never a floor.',
        'gated_elsewhere': 'draw_coherence.team_passing_line_closes_on_'
                           'receiving (HARD)',
        'residual_owner': None, 'owner_stored': True},
    'receiving_td_closes_on_passing_td': {
        'class': CLOSURE, 'view': 'touchdowns', 'unit': 'team-draw',
        'layers': ('qb', 'receiving'), 'regime': 'C3', 'tol': TOL,
        'asserts': 'sum of receiving_td == sum of QB ptd, per team per draw',
        'contract': 'C3, same shared event: a passing touchdown IS a '
                    'receiving touchdown. This is the ONLY touchdown '
                    'conservation the sealed artifact can express.',
        'gated_elsewhere': 'draw_coherence.team_passing_line_closes_on_'
                           'receiving (HARD)',
        'residual_owner': None, 'owner_stored': True},

    # ---------------------------------------------- rushing opportunity
    'qb_designed_rush_non_negative': {
        'class': CONTAINMENT, 'view': 'rushing', 'unit': 'team-draw',
        'layers': ('qb',), 'regime': None, 'tol': TOL,
        'asserts': 'sum of QB scr <= sum of QB rush_opp, per team per draw, '
                   'so that the designed-rush component recovered as '
                   'rush_opp - scr is not negative',
        'contract': 'qb_accounting.PER_DRAW_IDENTITIES.'
                    'rush_opportunity_composition -- rush_opp is COMPOSED as '
                    'scr + drush and never drawn whole. `drush` is not '
                    'sealed, so the designed component is recovered as '
                    'rush_opp - scr; this asserts that recovery is coherent. '
                    'Recovering a quantity by subtraction and then using it '
                    'as an owner in the rush partition is only legitimate if '
                    'the subtraction cannot go negative, which is what this '
                    'measures.',
        'gated_elsewhere': 'qb_accounting.PER_DRAW_IDENTITIES.'
                           'scrambles_within_opportunities (per cell) and '
                           'draw_coherence has no team-level form. Carried '
                           'here because the team sum is what the rush '
                           'partition below consumes.',
        'residual_owner': None, 'owner_stored': True},
    'rush_opportunity_closes': {
        'class': RESIDUAL, 'view': 'rushing', 'unit': 'team-draw',
        'layers': ('qb', 'rushing', 'team_volume'), 'regime': 'A1',
        'tol': None,
        'asserts': 'measures team_volume/team_carries - (RB carries + QB '
                   'scrambles + QB designed rushes), per team per draw. The '
                   'four named owners are RB / QB-scramble / QB-designed / '
                   'OTHER, and OTHER is this residual.',
        'contract': 'A1\'s frozen ownership graph: team_carries = scrambles + '
                    'rush_play_budget, and rush_play_budget = kneel + '
                    'designed_qb + rb + wr + te + fringe. Every carry lands '
                    'in exactly one category by construction.',
        'residual_owner': 'A1 categories kneel + wr + te + fringe, none of '
                          'which is sealed; PLUS the J-13 defect that the '
                          'SC1-coupled carry vector the engine partitioned is '
                          'not the vector run_forecast seals, so a residual '
                          'here cannot be attributed between an unsealed '
                          'category and the wrong denominator',
        'owner_stored': False,
        'not_a_defect': 'WR and TE carries and kneels are real football and '
                        'are not modelled as rows, so a POSITIVE residual is '
                        'expected. A NEGATIVE residual is a carry dealt '
                        'twice, and its attribution is blocked by J-13.'},
    'qb_rush_opportunity_within_team_carries': {
        'class': CONTAINMENT, 'view': 'rushing', 'unit': 'team-draw',
        'layers': ('qb', 'team_volume'), 'regime': None, 'tol': TOL,
        'asserts': 'sum of QB rush_opp <= team_volume/team_carries, per team '
                   'per draw',
        'contract': 'a quarterback rush IS one of the team\'s rush attempts.',
        'gated_elsewhere': 'draw_coherence.team_qb_rush_opportunity_within_'
                           'team_carries (DIAGNOSTIC, gates nothing until the '
                           'stored-vector defect is closed). This is the OPEN '
                           'ITEM the dashboard exists to surface: it is '
                           'present on control boards, was not caused by any '
                           'recent repair, and nobody owns it. Carried here '
                           'with its SIZE so it is a standing row rather than '
                           'a line in a test log.',
        'residual_owner': None, 'owner_stored': True},

    # -------------------------------------------- contracts with no data
    'team_rushing_td_closes': {
        'class': ABSENT, 'view': 'touchdowns', 'unit': 'team-draw',
        'layers': ('qb', 'rushing'), 'regime': None, 'tol': None,
        'asserts': 'WOULD assert sum of QB rtd + sum of RB rushing_td == a '
                   'team rushing-touchdown total',
        'contract': 'no team rushing-touchdown quantity is drawn, allocated '
                    'or sealed anywhere in the artifact. There is no '
                    'right-hand side, so the identity cannot be written.',
        'why_absent': 'team_volume carries team_carries, '
                      'team_dropbacks_part, team_off_snaps, team_rz_carries '
                      'and team_targets, and no touchdown quantity of any '
                      'kind. WR and TE rushing touchdowns are unmodelled as '
                      'well, so even the left-hand side is partial.',
        'residual_owner': None, 'owner_stored': False},
    'team_touchdowns_close': {
        'class': ABSENT, 'view': 'touchdowns', 'unit': 'team-draw',
        'layers': ('qb', 'receiving', 'rushing'), 'regime': None, 'tol': None,
        'asserts': 'WOULD assert the team\'s offensive touchdowns equal the '
                   'sum of its passing, rushing and receiving touchdown '
                   'credits without double counting',
        'contract': 'a passing TD and a receiving TD are ONE score, so a team '
                    'total needs ptd + rushing credits counted once. No team '
                    'touchdown total exists to close against, and no score '
                    'or drive layer is modelled.',
        'why_absent': 'V1 forecasts no team scoring distribution. The only '
                      'touchdown conservation the artifact can express is '
                      'receiving_td_closes_on_passing_td above.',
        'residual_owner': None, 'owner_stored': False},
    'team_target_pool_membership': {
        'class': ABSENT, 'view': 'targets', 'unit': 'team-draw',
        'layers': ('receiving',), 'regime': 'C3', 'tol': None,
        'asserts': 'WOULD split target_opportunity_closes into its two named '
                   'owners: untargeted throws, and the `other` unmodelled-'
                   'receiver pool',
        'contract': 'shared_pass draws both as NAMED pools, and '
                    'football_engine checks their identity exactly at run '
                    'time -- then seals neither.',
        'why_absent': 'neither the untargeted vector nor the `other` vector '
                      'is written to player_draws.npz, so a sealed board can '
                      'measure their SUM and can never split it. Sealing '
                      'either one would make this check writable.',
        'residual_owner': None, 'owner_stored': False},
    'team_carry_category_membership': {
        'class': ABSENT, 'view': 'rushing', 'unit': 'team-draw',
        'layers': ('rushing',), 'regime': 'A1', 'tol': None,
        'asserts': 'WOULD split rush_opportunity_closes into A1\'s kneel, wr, '
                   'te and fringe categories',
        'contract': 'rushing_a1.allocate partitions the rush-play budget '
                    'across six named categories with one multinomial per '
                    'draw, so every carry has exactly one owner.',
        'why_absent': 'only the `rb` category reaches the artifact, as '
                      'rushing/carries rows. kneel, wr, te and fringe are '
                      'computed and discarded. Sealing the category matrix '
                      'would make the whole rush partition auditable from a '
                      'sealed board.',
        'residual_owner': None, 'owner_stored': False},
}

CLOSURES = tuple(sorted(k for k, v in CONTRACTS.items()
                        if v['class'] == CLOSURE))
RESIDUALS = tuple(sorted(k for k, v in CONTRACTS.items()
                         if v['class'] == RESIDUAL))
CONTAINMENTS = tuple(sorted(k for k, v in CONTRACTS.items()
                            if v['class'] == CONTAINMENT))
ABSENT_CONTRACTS = tuple(sorted(k for k, v in CONTRACTS.items()
                                if v['class'] == ABSENT))
VIEWS = tuple(sorted({v['view'] for v in CONTRACTS.values()}))

# Components whose presence a check depends on, as the artifact declares them.
REGIMES = tuple(sorted({v['regime'] for v in CONTRACTS.values()
                        if v['regime']}))

# Arrays that must NEVER be used as an allocation denominator, and why. Held
# as data so a caller can assert it rather than remember it.
NOT_A_DENOMINATOR = {
    'team_volume/team_targets': (
        'WS09 J-12. A separate, unused D1 draw of the same football quantity. '
        'Under C3 the denominator is rint(sum of QB attempts). Measured live '
        'on DEN@KC: stored 28.70 against a C3 budget of 35.41.'),
    'team_volume/team_carries': (
        'WS09 J-13. run_forecast seals D1\'s raw vector while the engine '
        'partitioned the SC1-coupled one. Usable as a LEVEL to measure '
        'against -- it is the only carry level sealed -- but a residual '
        'computed from it cannot be attributed.'),
}


# ---------------------------------------------------------------- helpers
def _get(arrays, key):
    v = arrays.get(key)
    return None if v is None else np.asarray(v, dtype=float)


def _dist(x) -> dict:
    """A residual's DISTRIBUTION, never just its mean.

    `sign_changes` is a fact about the sample -- both a negative and a
    positive cell occur -- and not a threshold. It is the flag that says the
    mean cannot stand in for this quantity.
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    n = int(x.size)
    neg = int((x < -TOL).sum())
    pos = int((x > TOL).sum())
    return {
        'cells': n,
        'mean': float(x.mean()), 'sd': float(x.std()),
        'min': float(x.min()), 'max': float(x.max()),
        'p05': float(np.percentile(x, 5)),
        'p50': float(np.percentile(x, 50)),
        'p95': float(np.percentile(x, 95)),
        'mean_abs': float(np.abs(x).mean()),
        'n_negative': neg, 'n_positive': pos,
        'n_zero': n - neg - pos,
        'sign_changes': bool(neg and pos),
    }


def _record(name, team, lhs, rhs, lhs_label, rhs_label, parts=None) -> dict:
    """One team's one check: both sides, the residual's shape, and a state.

    `residual = lhs - rhs`. For a CLOSURE that is a construction error; for a
    RESIDUAL it is the unowned mass; for a CONTAINMENT a negative value is the
    breach.
    """
    spec = CONTRACTS[name]
    lhs = np.asarray(lhs, dtype=float).reshape(-1)
    rhs = np.asarray(rhs, dtype=float).reshape(-1)
    r = lhs - rhs
    rec = {
        'check': name, 'team': team, 'class': spec['class'],
        'view': spec['view'], 'regime': spec['regime'],
        'lhs': lhs_label, 'rhs': rhs_label,
        'lhs_mean': float(lhs.mean()), 'rhs_mean': float(rhs.mean()),
        'residual': _dist(r),
        'residual_owner': spec['residual_owner'],
        'owner_stored': spec['owner_stored'],
    }
    level = float(np.abs(lhs).mean())
    rec['residual_share_of_level'] = (
        float(r.mean() / level) if level > TOL else None)
    rec['residual_abs_share_of_level'] = (
        float(np.abs(r).mean() / level) if level > TOL else None)
    if parts:
        rec['parts'] = {k: float(np.asarray(v, dtype=float).mean())
                        for k, v in parts.items()}
    tol = spec['tol']
    if spec['class'] == CLOSURE:
        bad = int((np.abs(r) > tol).sum())
        rec['violating_cells'] = bad
        rec['state'] = 'FAIL' if bad else 'PASS'
    elif spec['class'] == CONTAINMENT:
        bad = int((r < -tol).sum())
        rec['violating_cells'] = bad
        rec['state'] = 'BREACHED' if bad else 'HELD'
        rec['gates_here'] = False
        rec['gated_elsewhere'] = spec.get('gated_elsewhere')
    else:
        rec['violating_cells'] = None
        rec['state'] = 'MEASURED'
        if spec.get('not_a_defect'):
            rec['not_a_defect'] = spec['not_a_defect']
    return rec


def _na(name, team, why) -> dict:
    """An absence, stated. NEVER a zero.

    A team whose receiving layer was deferred did not deal zero targets; it
    dealt an unknown number that nobody modelled, and a zero here would be
    summed into a slate total as though the mass were accounted for.
    """
    spec = CONTRACTS[name]
    return {'check': name, 'team': team, 'class': spec['class'],
            'view': spec['view'], 'regime': spec['regime'],
            'state': 'NOT_APPLICABLE', 'why': why,
            'residual': None, 'is_not_zero_mass': True}


def team_rows(manifest, players) -> Outcome:
    """Resolve each team's row indices per layer, BY IDENTITY.

    `manifest` is the parsed `player_draws_manifest.json`; `players` is
    `board.json['players']`. Returns {team: {layer: [rows], 'team_volume': i}}.

    A layer declaring `row_axis == 'team'` -- `team_volume`, and A1's
    `rush_category` and `rush_player_pool` -- carries team codes as its row
    ids and is matched directly. A layer declaring `row_axis == 'gsis_id'` is
    joined to a team through the board. A positional join across layers is a
    defect this repository has already paid for, so the row axis is READ, and
    a layer declaring an axis this function does not understand is refused
    rather than assumed.
    """
    lays = (manifest or {}).get('layers') or {}
    if not lays:
        return Outcome.blocked(
            'CONSERVATION_MANIFEST_HAS_NO_LAYERS',
            'the draw manifest declares no layers, so no row can be resolved '
            'by identity and a positional guess is forbidden.',
            cause=Cause.DATA)
    tv = lays.get('team_volume')
    if not tv or not tv.get('row_ids'):
        return Outcome.blocked(
            'CONSERVATION_NO_TEAM_AXIS',
            'the manifest carries no team_volume layer with row ids, so there '
            'is no team axis to conserve mass on.', cause=Cause.DATA)
    if tv.get('row_axis') != 'team':
        return Outcome.blocked(
            'CONSERVATION_TEAM_AXIS_UNEXPECTED',
            f'team_volume declares row_axis {tv.get("row_axis")!r}, not '
            f'"team". Refusing to assume its rows are teams.',
            cause=Cause.DATA)
    # THE MANIFEST'S OWN MAP WINS, AND THE BOARD IS THE FALLBACK.
    #
    # This function used to resolve a player row's team ONLY through
    # `board.json['players']` -- the DISPLAY board, which is narrower than
    # the participant universe the simulator runs on. A layer whose rows are
    # lawful participants but not display rows therefore arrived unjoinable
    # and refused the whole board, which is the safe failure and is still a
    # failure: the invariant stops being tested. It happened to
    # `rush_category`, then to `kicking` (two kickers on no display row) and
    # `gadget_rush` (three receivers who take gadget carries and are
    # displayed nowhere).
    #
    # `add_layer` now requires a team for every gsis_id row and writes it
    # into the layer as `row_teams`, so the map travels WITH the draws. It is
    # read first. The board still fills in for a manifest sealed before that
    # existed, which is why this is a fallback rather than a replacement.
    team_of = {}
    for p in players or []:
        g, t = p.get('gsis_id'), p.get('team')
        if g and t:
            team_of[g] = t
    for lay, spec in sorted(lays.items()):
        rt = spec.get('row_teams')
        if not rt or spec.get('row_axis') != 'gsis_id':
            continue
        for g, t in zip(spec.get('row_ids') or [], rt):
            if g and t:
                team_of[str(g)] = t
    if not team_of:
        return Outcome.blocked(
            'CONSERVATION_NO_PLAYER_TEAM_MAP',
            'no player carries both a gsis_id and a team, so player rows '
            'cannot be attributed to a team. Refusing to fall back on row '
            'order.', cause=Cause.DATA)
    out, unmapped = {}, []
    for ti, t in enumerate(tv['row_ids']):
        e = {'team_volume': ti}
        for lay, spec in sorted(lays.items()):
            if lay == 'team_volume':
                continue
            axis = spec.get('row_axis')
            # A TEAM-AXIS LAYER JOINS BY TEAM. IT IS NOT AN UNKNOWN AXIS.
            #
            # This branch exempted `team_volume` BY NAME and then demanded
            # `gsis_id` of everything else, so the first team-axis layer that
            # was not called `team_volume` refused the whole board. A1's carry
            # partition reaching the artifact as `rush_category` and
            # `rush_player_pool` (both `row_axis: "team"`) did exactly that:
            # every board carrying them returned
            # BLOCKED[CONSERVATION_ROW_AXIS_UNKNOWN], which means CONSERVATION
            # WENT UNCHECKED on them -- on the two DEN@KC boards built
            # 2026-09-14/15 among others. A refusal is the safe failure and it
            # is still a failure: the invariant stopped being tested at the
            # moment new layers arrived, and nothing said so until the fence
            # in test_conservation.py counted the boards it could not score.
            #
            # The axis is still READ, never assumed, and an axis this module
            # does not understand is still refused by name below. What changes
            # is that 'team' is now understood, because it is: the row ids ARE
            # the team codes, exactly as they are for team_volume, so the join
            # is an identity match and needs no player map.
            if axis == 'team':
                ids = spec.get('row_ids') or []
                e[lay] = [i for i, code in enumerate(ids) if code == t]
                continue
            if axis != 'gsis_id':
                return Outcome.blocked(
                    'CONSERVATION_ROW_AXIS_UNKNOWN',
                    f'layer {lay!r} declares row_axis {axis!r}, which this '
                    f'module does not know how to join to a team.',
                    cause=Cause.DATA)
            ids = spec.get('row_ids') or []
            e[lay] = [i for i, g in enumerate(ids) if team_of.get(g) == t]
            unmapped += [g for g in ids if g not in team_of]
        out[t] = e
    if unmapped:
        return Outcome.blocked(
            'CONSERVATION_ROWS_WITHOUT_A_TEAM',
            f'{len(set(unmapped))} draw row(s) carry a gsis_id the board does '
            f'not place on a team, so their mass could be attributed to no '
            f'team and would vanish from every total. Refused rather than '
            f'dropped.', cause=Cause.DATA, unmapped=sorted(set(unmapped))[:20])
    return Outcome.ok(
        'CONSERVATION_ROWS_RESOLVED', value=out,
        detail=f'{len(out)} team(s) resolved by identity across '
               f'{len(lays)} layer(s)',
        layers=sorted(lays), teams=sorted(out))


def regime_from_components(applied) -> dict:
    """Which components the RUN DECLARED it applied. Never inferred.

    `applied` is the artifact's `candidate_components_applied`. Reading it is
    reading a declaration the run made about itself; deciding from the numbers
    that C3 "must have been on" would be asserting the conclusion.
    """
    got = {str(c).upper() for c in (applied or [])}
    return {r: (r in got) for r in REGIMES}


# ------------------------------------------------------------ the checks
def dropback_view(arrays, rows, team, regime) -> list:
    """The QB room: does the dropback partition hold, and does the room close
    on the team's level?"""
    out = []
    qi = list(rows.get('qb') or [])
    db, att = _get(arrays, 'qb/db'), _get(arrays, 'qb/att')
    sk, scr = _get(arrays, 'qb/sacks'), _get(arrays, 'qb/scr')
    if not qi or db is None or att is None or sk is None or scr is None:
        return [_na('team_dropback_partition', team,
                    'this team has no quarterback rows, or the QB draw set '
                    'carries no db/att/sacks/scr. No dropback mass was '
                    'modelled for it; that is not zero dropbacks.'),
                _na('qb_room_closes_on_team_dropbacks', team,
                    'no quarterback room to close'),
                _na('team_dropback_level_rounding_residual', team,
                    'no quarterback room to close')]
    D, A = db[qi].sum(0), att[qi].sum(0)
    S, C = sk[qi].sum(0), scr[qi].sum(0)
    out.append(_record('team_dropback_partition', team, D, A + S + C,
                       'sum qb/db', 'sum qb/(att+sacks+scr)',
                       parts={'attempts': A, 'sacks': S, 'scrambles': C}))
    ti = rows.get('team_volume')
    tdb = _get(arrays, 'team_volume/team_dropbacks_part')
    if ti is None or tdb is None:
        why = ('no team_volume/team_dropbacks_part in this run, so the room '
               'has no declared budget to close on')
        out.append(_na('qb_room_closes_on_team_dropbacks', team, why))
        out.append(_na('team_dropback_level_rounding_residual', team, why))
        return out
    raw = tdb[int(ti)]
    if not regime.get('R2'):
        why = ('R2 is not in this run\'s declared components, so the room is '
               'not contractually apportioned from the team level and an '
               'exact closure is not asserted by any contract')
        out.append(_na('qb_room_closes_on_team_dropbacks', team, why))
    else:
        out.append(_record('qb_room_closes_on_team_dropbacks', team, D,
                           np.maximum(np.rint(raw), 0.0),
                           'sum qb/db', 'max(rint(team_dropbacks_part), 0)'))
    out.append(_record('team_dropback_level_rounding_residual', team, D, raw,
                       'sum qb/db', 'team_dropbacks_part (continuous)'))
    return out


def target_view(arrays, rows, team, regime) -> list:
    """Targets: the C3 budget, the unowned pool, and the stored-total trap."""
    names = ('target_opportunity_closes', 'targets_within_throw_budget',
             'stored_team_targets_is_not_the_denominator')
    qi, ri = list(rows.get('qb') or []), list(rows.get('receiving') or [])
    att, tg = _get(arrays, 'qb/att'), _get(arrays, 'receiving/targets')
    if not regime.get('C3'):
        return [_na(n, team,
                    'C3 is not in this run\'s declared components. Without it '
                    'the target budget is D1\'s team_targets and the throw '
                    'process is not the denominator, so none of these '
                    'contracts is the one this run ran under.')
                for n in names]
    if not qi or att is None:
        return [_na(n, team, 'this team has no quarterback rows, so it has no '
                             'C3 throw budget') for n in names]
    budget = np.rint(att[qi].sum(0))
    out = []
    if not ri or tg is None:
        why = ('this team has no receiver rows in the draw set -- its '
               'receiving layer was not modelled on this run. NOT zero '
               'targets: an unknown number of targets was dealt by a layer '
               'that did not run for this team.')
        out.append(_na('target_opportunity_closes', team, why))
        out.append(_na('targets_within_throw_budget', team, why))
    else:
        T = tg[ri].sum(0)
        out.append(_record('target_opportunity_closes', team, budget, T,
                           'rint(sum qb/att)', 'sum receiving/targets',
                           parts={'modelled_targets': T,
                                  'throw_budget': budget}))
        out.append(_record('targets_within_throw_budget', team, budget, T,
                           'rint(sum qb/att)', 'sum receiving/targets'))
    ti = rows.get('team_volume')
    stored = _get(arrays, 'team_volume/team_targets')
    if ti is None or stored is None:
        out.append(_na('stored_team_targets_is_not_the_denominator', team,
                       'no team_volume/team_targets in this run'))
    else:
        out.append(_record('stored_team_targets_is_not_the_denominator', team,
                           stored[int(ti)], budget,
                           'team_volume/team_targets (STORED, UNUSED)',
                           'rint(sum qb/att) (the budget C3 dealt from)'))
    return out


def passing_line_view(arrays, rows, team, regime) -> list:
    """Receptions, receiving yards and receiving touchdowns against the passer
    line. One event, counted from two sides -- where C3 says so."""
    pairs = (('receptions_close_on_completions', 'qb/cmp',
              'receiving/receptions'),
             ('receiving_yards_close_on_passing_yards', 'qb/pyds',
              'receiving/receiving_yards'),
             ('receiving_td_closes_on_passing_td', 'qb/ptd',
              'receiving/receiving_td'))
    qi, ri = list(rows.get('qb') or []), list(rows.get('receiving') or [])
    if not regime.get('C3'):
        return [_na(n, team,
                    'C3 is not in this run\'s declared components, so the '
                    'passer line was NOT credited from the receiving event. '
                    'The two layers drew the same football quantity twice and '
                    'are not contractually equal; asserting equality here '
                    'would invent a contract the run did not have.')
                for n, _, _ in pairs]
    if not qi or not ri:
        return [_na(n, team,
                    'this team has no quarterback rows or no receiver rows, '
                    'so the shared passing event has only one side present. '
                    'Not a closure failure and not zero yards.')
                for n, _, _ in pairs]
    out = []
    for name, qk, rk in pairs:
        q, r = _get(arrays, qk), _get(arrays, rk)
        if q is None or r is None:
            out.append(_na(name, team,
                           f'the draw set carries no {qk if q is None else rk}'))
            continue
        out.append(_record(name, team, q[qi].sum(0), r[ri].sum(0),
                           f'sum {qk}', f'sum {rk}'))
    return out


def rushing_view(arrays, rows, team, regime) -> list:
    """Rush opportunity across RB / QB-scramble / QB-designed / OTHER.

    OTHER is the residual, and its owners -- A1's kneel, wr, te and fringe --
    are not in the artifact. It is therefore MEASURABLE and UNATTRIBUTABLE,
    and both halves of that are reported.
    """
    out = []
    qi, si = list(rows.get('qb') or []), list(rows.get('rushing') or [])
    ti = rows.get('team_volume')
    ro, scr = _get(arrays, 'qb/rush_opp'), _get(arrays, 'qb/scr')
    tc = _get(arrays, 'team_volume/team_carries')
    car = _get(arrays, 'rushing/carries')
    if not qi or ro is None or scr is None:
        return [_na(n, team, 'this team has no quarterback rows, or no '
                             'qb/rush_opp and qb/scr, so no QB rushing mass '
                             'was modelled for it')
                for n in ('qb_designed_rush_non_negative',
                          'rush_opportunity_closes',
                          'qb_rush_opportunity_within_team_carries')]
    RO, SC = ro[qi].sum(0), scr[qi].sum(0)
    DES = RO - SC
    out.append(_record('qb_designed_rush_non_negative', team, RO, SC,
                       'sum qb/rush_opp', 'sum qb/scr; the residual IS the '
                       'recovered designed-rush component'))
    if ti is None or tc is None:
        why = ('no team_volume/team_carries in this run, so there is no rush '
               'level to conserve against')
        out.append(_na('rush_opportunity_closes', team, why))
        out.append(_na('qb_rush_opportunity_within_team_carries', team, why))
        return out
    level = tc[int(ti)]
    out.append(_record('qb_rush_opportunity_within_team_carries', team, level,
                       RO, 'team_volume/team_carries', 'sum qb/rush_opp'))
    if not si or car is None:
        out.append(_na('rush_opportunity_closes', team,
                       'this team has no running-back rows in the draw set -- '
                       'its rushing layer was not modelled on this run. NOT '
                       'zero carries: the backs\' share of the level is '
                       'unknown, so the OTHER residual cannot be separated '
                       'from it.'))
        return out
    if not regime.get('A1'):
        out.append(_na('rush_opportunity_closes', team,
                       'A1 is not in this run\'s declared components, so the '
                       'six-category ownership graph is not the partition '
                       'this run used and OTHER has no declared owner.'))
        return out
    RB = car[si].sum(0)
    out.append(_record('rush_opportunity_closes', team, level, RB + SC + DES,
                       'team_volume/team_carries',
                       'RB carries + QB scrambles + QB designed rushes',
                       parts={'rb': RB, 'qb_scramble': SC, 'qb_designed': DES,
                              'wr_te_kneel_fringe_OTHER': level - (RB+SC+DES)}))
    return out


VIEW_FUNCS = {'dropbacks': dropback_view, 'targets': target_view,
              'passing_line': passing_line_view, 'touchdowns': None,
              'rushing': rushing_view}


def absent_contracts(team) -> list:
    """The contracts that are declared somewhere and cannot be written here.

    Emitted on EVERY board, for every team, rather than left out. A contract
    that cannot be checked is a standing gap in the conservation view, and a
    gap that is not printed is a gap nobody closes.
    """
    return [{'check': n, 'team': team, 'class': ABSENT,
             'view': CONTRACTS[n]['view'], 'regime': CONTRACTS[n]['regime'],
             'state': 'ABSENT_CONTRACT',
             'why': CONTRACTS[n]['why_absent'],
             'would_assert': CONTRACTS[n]['asserts'],
             'residual': None}
            for n in ABSENT_CONTRACTS]


def dashboard(arrays, rows, regime, *, game_id=None, run_id=None) -> Outcome:
    """Every conservation view, per team, over one run's sealed arrays.

    `arrays` maps 'layer/metric' to a (rows x draws) matrix. `rows` is the map
    from `team_rows`. `regime` is the map from `regime_from_components`.

    PASS means every evaluable CLOSURE held. It does NOT mean mass is
    conserved: residuals and containment breaches are carried in the evidence
    with their sizes and are deliberately non-gating, because a lawful
    unowned pool and a defect look identical to an inequality and are told
    apart only by who owns the mass.
    """
    if not rows:
        return Outcome.blocked(
            'CONSERVATION_NO_TEAMS',
            'no team row map was supplied, so there is no unit to conserve '
            'mass over. Zero teams is an error, not a clean board.',
            cause=Cause.DATA)
    if not arrays:
        return Outcome.blocked(
            'CONSERVATION_NO_ARRAYS',
            'no draw matrices were supplied. An empty draw set is an absence, '
            'not a conserved board.', cause=Cause.DATA)
    records = []
    for team in sorted(rows):
        r = rows[team]
        records += dropback_view(arrays, r, team, regime)
        records += target_view(arrays, r, team, regime)
        records += passing_line_view(arrays, r, team, regime)
        records += rushing_view(arrays, r, team, regime)
        records += absent_contracts(team)
    evaluated = [x for x in records if x.get('residual') is not None]
    if not evaluated:
        return Outcome.blocked(
            'CONSERVATION_VACUOUS',
            'no conservation check evaluated a single draw on any team. A '
            'dashboard that measured nothing has not found a conserved board; '
            'it has found nothing.', cause=Cause.DATA,
            records=records, spec_version=SPEC_VERSION)
    failed = [x for x in records if x.get('state') == 'FAIL']
    breached = [x for x in records if x.get('state') == 'BREACHED']
    na = [x for x in records if x.get('state') == 'NOT_APPLICABLE']
    absent = [x for x in records if x.get('state') == 'ABSENT_CONTRACT']
    resid = [x for x in records if x.get('state') == 'MEASURED']
    unowned = [x for x in resid if not x['owner_stored']]
    hidden = [x for x in resid if x['residual']['sign_changes']]
    ev = {'records': records, 'spec_version': SPEC_VERSION,
          'game_id': game_id, 'run_id': run_id, 'regime': dict(regime),
          'n_teams': len(rows),
          'n_evaluated': len(evaluated), 'n_not_applicable': len(na),
          'n_absent_contracts': len(absent),
          'n_closure_failures': len(failed),
          'n_containment_breaches': len(breached),
          'n_residuals_with_unstored_owner': len(unowned),
          'n_residuals_that_change_sign': len(hidden),
          'not_a_denominator': dict(NOT_A_DENOMINATOR)}
    if failed:
        worst = max(failed, key=lambda x: x['residual']['mean_abs'])
        return Outcome.fail(
            'CONSERVATION_CLOSURE_VIOLATED',
            f'{len(failed)} exact closure(s) do not hold: '
            + '; '.join(f'{x["check"]}/{x["team"]} in '
                        f'{x["violating_cells"]:,} of '
                        f'{x["residual"]["cells"]:,} draw(s)'
                        for x in failed[:6])
            + f'. Worst by mean absolute residual is {worst["check"]} on '
              f'{worst["team"]} at {worst["residual"]["mean_abs"]:.6f}. These '
              f'are constructions, so a deviation is a defect in the '
              f'construction and never a tolerance to widen.',
            first_failure=worst['check'], **ev)
    return Outcome.ok(
        'CONSERVATION_MEASURED',
        value={'teams': sorted(rows), 'closures_held': len(
            [x for x in records if x.get('state') == 'PASS']),
            'residuals': len(resid)},
        detail=f'{len(evaluated)} check(s) evaluated over {len(rows)} team(s); '
               f'{len(resid)} residual(s) measured, {len(unowned)} of them '
               f'with an owner that is not in the artifact; '
               f'{len(hidden)} residual(s) change sign across draws and '
               f'cannot be summarised by their mean; '
               f'{len(breached)} containment breach(es) recorded and not '
               f'gated here; {len(na)} check(s) not applicable; '
               f'{len(absent)} declared contract(s) have no quantity to '
               f'check against',
        **ev)


# --------------------------------------------------------------- one run
def from_run_dir(path) -> Outcome:
    """THE ONLY FUNCTION HERE THAT TOUCHES A FILE.

    Everything above is a pure function over arrays so the identical code runs
    on a sealed board, on a rehearsal, and inside a test. This loads one
    sealed run directory and calls it.

    Nothing is written. Nothing is repaired. A missing file is a named refusal
    and never an empty result.
    """
    d = pathlib.Path(path)
    # THE DRAWS ARE FOUND BY CONTENT, NOT BY ONE SPELLING OF THE FILENAME.
    #
    # This required the literal `player_draws.npz`, and five
    # 2026_01_SF_LA/pre_inactives_* boards store `player_draws.npz.gz`. They
    # reported CONSERVATION_RUN_INCOMPLETE -- "missing ['player_draws.npz']" --
    # while their draws loaded perfectly through `sealed_index.load_draws`,
    # which has handled both encodings since it was written. So conservation
    # declined to score five real boards and said the file was absent.
    #
    # It is the same extension-blindness that made three corpus fences report
    # 104 of 121 boards, one module further on: fixing the globs did not fix
    # the readers behind them. Discovery is by content; so is presence.
    draws = next((p for p in (d / 'player_draws.npz',
                              d / 'player_draws.npz.gz') if p.exists()), None)
    need = ('player_draws_manifest.json', 'board.json',
            'forecast_artifact.json')
    missing = [f for f in need if not (d / f).exists()]
    if draws is None:
        missing = ['player_draws.npz or player_draws.npz.gz'] + missing
    if missing:
        return Outcome.blocked(
            'CONSERVATION_RUN_INCOMPLETE',
            f'{d}: missing {missing}. A conservation view needs the draws, '
            f'the row identities, the team map and the run\'s own declaration '
            f'of which components it applied.', cause=Cause.DATA, run=str(d))
    man = json.load(open(d / 'player_draws_manifest.json'))
    board = json.load(open(d / 'board.json'))
    art = json.load(open(d / 'forecast_artifact.json'))
    if draws.name.endswith('.gz'):
        import gzip as _gz
        import io as _io
        z = np.load(_io.BytesIO(_gz.open(draws, 'rb').read()),
                    allow_pickle=True)
    else:
        z = np.load(draws, allow_pickle=True)
    arrays = {k.replace('__', '/', 1): z[k].astype(float) for k in z.files}
    rows = team_rows(man, board.get('players'))
    if rows.state is not State.PASS:
        return rows
    regime = regime_from_components(art.get('candidate_components_applied'))
    # `run_id` sits on the draw artifact, not at the top of the forecast
    # artifact. Read from both rather than reporting '?' for every board.
    rid = art.get('run_id') or (art.get('draw_artifact') or {}).get('run_id') \
        or man.get('run_id') or board.get('run_id')
    return dashboard(arrays, rows.value, regime,
                     game_id=art.get('game_id') or man.get('game_id'),
                     run_id=rid)


# ------------------------------------------------------------- rendering
def _fmt(x, nd=4):
    return '--' if x is None else f'{x:.{nd}f}'


def render(outcome, *, title=None) -> str:
    """The dashboard as text. One table per view, residuals as DISTRIBUTIONS.

    Deliberately never prints a residual as a single number. Every residual
    row carries mean, sd, min, max and the count of draws in which it is
    negative, because the KC rush residual reads as 0.62% of the level on its
    mean and is an over-allocation in 46.4% of the draws underneath it.
    """
    ev = outcome.evidence
    recs = ev.get('records') or []
    L = []
    head = title or f'{ev.get("game_id") or "?"} / {ev.get("run_id") or "?"}'
    L.append(f'### {head}')
    L.append('')
    L.append(f'`{outcome.state.value}[{outcome.code}]` — {outcome.detail}')
    L.append('')
    reg = ev.get('regime') or {}
    L.append('Declared regime (read from `candidate_components_applied`, '
             'never inferred): '
             + ', '.join(f'{k}={"on" if v else "off"}'
                         for k, v in sorted(reg.items())))
    L.append('')
    for view in VIEWS:
        rows = [r for r in recs if r['view'] == view]
        if not rows:
            continue
        L.append(f'**{view}**')
        L.append('')
        L.append('| check | team | class | state | lhs mean | rhs mean | '
                 'resid mean | resid sd | resid min | resid max | '
                 'draws resid<0 | owner of residual |')
        L.append('|---|---|---|---|--:|--:|--:|--:|--:|--:|--:|---|')
        for r in sorted(rows, key=lambda x: (x['check'], x['team'])):
            d = r.get('residual')
            if d is None:
                why = (r.get('why') or '')[:110]
                L.append(f'| `{r["check"]}` | {r["team"]} | {r["class"]} | '
                         f'{r["state"]} | — | — | — | — | — | — | — | '
                         f'{why} |')
                continue
            owner = r.get('residual_owner') or '—'
            if r.get('owner_stored') is False:
                owner = 'NOT IN ARTIFACT: ' + owner
            L.append(
                f'| `{r["check"]}` | {r["team"]} | {r["class"]} | '
                f'{r["state"]} | {_fmt(r["lhs_mean"])} | '
                f'{_fmt(r["rhs_mean"])} | {_fmt(d["mean"])} | '
                f'{_fmt(d["sd"])} | {_fmt(d["min"], 3)} | '
                f'{_fmt(d["max"], 3)} | {d["n_negative"]}/{d["cells"]} | '
                f'{owner[:160]} |')
        L.append('')
    hidden = [r for r in recs
              if r.get('residual') and r['residual']['sign_changes']]
    if hidden:
        L.append('**Residuals that change sign across draws — the mean does '
                 'not describe these.**')
        L.append('')
        for r in sorted(hidden, key=lambda x: -x['residual']['sd']):
            d = r['residual']
            L.append(f'- `{r["check"]}` / {r["team"]}: mean '
                     f'{d["mean"]:+.4f} but sd {d["sd"]:.4f}, range '
                     f'[{d["min"]:+.3f}, {d["max"]:+.3f}], negative in '
                     f'{d["n_negative"]} of {d["cells"]} draws '
                     f'({100 * d["n_negative"] / d["cells"]:.1f}%).')
        L.append('')
    return '\n'.join(L)
