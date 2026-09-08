"""Team/player accounting invariants. Every residual mass must be NAMED.

THE RULE THIS ENFORCES

A reconciliation that clips, drops or silently absorbs a discrepancy is worse
than no reconciliation, because it converts a measurable defect into an
invisible one. Every check here returns the residual explicitly. Where a
residual is structural -- a fifth skill player, an offensive lineman on a tackle-
eligible target, a lateral -- it is named as an OTHER bucket rather than hidden.

WHAT IS AND IS NOT MECHANICALLY TRUE, measured on 2020-2025 pbp:

  team targets    == sum of player targets            EXACT, no residual
  team receptions == sum of player receptions          EXACT
  team recv yards == sum of player receiving yards     EXACT
  passing yards   == receiving yards, at team level    EXCEPT LATERALS -- see below
  passing TD      == receiving TD                      EXACT
  team carries    == RB + QB + WR/TE/other carries     EXACT, OTHER is real
  receptions      <= targets                           per player, EXACT
  red-zone opps   <= total opps                        per player, EXACT

Each is asserted per team-game, not merely in aggregate: a positive residual on
one team cancelling a negative on another would pass an aggregate check and is
exactly the kind of error that survives into production.
"""
from __future__ import annotations

import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

# Positions that are NOT in the project's skill frame. Their touches are real
# and are named rather than dropped.
OTHER_BUCKET = 'OTHER_NON_SKILL'


def check(name: str, residuals: dict, tol: float = 1e-9,
          allow_named_other: bool = False) -> Outcome:
    """One invariant over many groups. Returns the residuals, never hides them.

    `residuals` maps a group key to (lhs, rhs, other) where `other` is the
    explicitly-named residual mass. The invariant holds when
    lhs - rhs - other == 0 for EVERY group.
    """
    bad = {}
    total_other = 0.0
    for k, v in residuals.items():
        lhs, rhs, other = (list(v) + [0.0])[:3]
        total_other += other
        d = lhs - rhs - other
        if abs(d) > tol:
            bad[str(k)] = {'lhs': lhs, 'rhs': rhs, 'named_other': other,
                           'unexplained': d}
    if bad:
        worst = max(bad.items(), key=lambda kv: abs(kv[1]['unexplained']))
        return Outcome.fail(
            f'INVARIANT_VIOLATED_{name.upper()}',
            f'{name}: {len(bad)} of {len(residuals)} group(s) carry an '
            f'UNEXPLAINED residual. Worst {worst[0]}: lhs {worst[1]["lhs"]}, '
            f'rhs {worst[1]["rhs"]}, named other {worst[1]["named_other"]}, '
            f'unexplained {worst[1]["unexplained"]}. A residual that is not '
            f'named is not reconciled, and clipping it would convert a '
            f'measurable defect into an invisible one.',
            invariant=name, n_groups=len(residuals), n_bad=len(bad),
            worst=worst[0], examples=dict(list(bad.items())[:5]))
    if total_other and not allow_named_other:
        return Outcome.fail(
            f'UNEXPECTED_OTHER_MASS_{name.upper()}',
            f'{name}: balances only because {total_other} of residual mass was '
            f'assigned to a named OTHER bucket, and this invariant was declared '
            f'to have none.', invariant=name, other=total_other)
    return Outcome.ok(f'INVARIANT_HOLDS_{name.upper()}',
                      value={'n_groups': len(residuals),
                             'named_other_total': total_other},
                      detail=f'{name}: holds on all {len(residuals)} group(s)'
                             + (f', named OTHER mass {total_other}'
                                if total_other else ''))


def le_check(name: str, pairs: dict) -> Outcome:
    """A <= B invariant, per group. No clipping: a violation is reported."""
    bad = {str(k): v for k, v in pairs.items() if v[0] > v[1]}
    if bad:
        worst = max(bad.items(), key=lambda kv: kv[1][0] - kv[1][1])
        return Outcome.fail(
            f'ORDERING_VIOLATED_{name.upper()}',
            f'{name}: {len(bad)} of {len(pairs)} group(s) violate the bound. '
            f'Worst {worst[0]}: {worst[1][0]} > {worst[1][1]}. Clipping this '
            f'would hide it.',
            invariant=name, n_bad=len(bad), examples=dict(list(bad.items())[:5]))
    return Outcome.ok(f'ORDERING_HOLDS_{name.upper()}',
                      value={'n_groups': len(pairs)},
                      detail=f'{name}: holds on all {len(pairs)} group(s)')


def reconcile_team_player(team_totals: dict, player_rows: list, field: str,
                          other_positions: tuple = ()) -> dict:
    """Build the residual map for a team-level == sum-of-players invariant.

    Players outside the skill frame go to a NAMED bucket, not to the floor.
    """
    got = collections.defaultdict(float)
    other = collections.defaultdict(float)
    for r in player_rows:
        k = (r['season'], r['week'], r['team'])
        if other_positions and r.get('position') in other_positions:
            other[k] += float(r.get(field) or 0.0)
        else:
            got[k] += float(r.get(field) or 0.0)
    return {k: (float(v), got.get(k, 0.0), other.get(k, 0.0))
            for k, v in team_totals.items()}


# ==========================================================================
# THE ONE DOCUMENTED EXCEPTION, measured rather than assumed
# ==========================================================================
#
# `passing_yards == receiving_yards` at team level FAILS on 76 of 3,230
# team-games, 2020-2025. Measured breakdown:
#
#     75 of 76 contain a LATERAL RECEPTION.
#      1 of 76 does not.
#
# On a lateral the passer is credited the full advance while `receiving_yards`
# is charged only to the initial receiver, so the two totals legitimately
# diverge. Example, LA 2020 week 6: "pass short right to 10-C.Kupp to LA 23 for
# -5 yards. Lateral to 27-D.Henderson pushed ob at LA 32 for 9 yards" --
# passing_yards 4.0, receiving_yards 0.0.
#
# THE REMAINING ONE IS NOT EXPLAINED AND IS NOT SWEPT UP. IND 2022 week 16:
# passing_yards 13.0 against receiving_yards 12.0 on a play the description
# records as a 12-yard completion with no lateral. That is an upstream
# inconsistency of 1 yard. It is left VISIBLE as an unexplained residual
# rather than folded into the lateral bucket, because a bucket that absorbs
# whatever is left over stops being evidence about anything.
LATERAL_EXCEPTION = {
    'invariant': 'team_pass_yards_eq_team_recv_yards',
    'seasons': [2020, 2021, 2022, 2023, 2024, 2025],
    'n_team_games': 3230,
    'n_violating': 76,
    'n_explained_by_lateral': 75,
    'n_unexplained': 1,
    'unexplained_example': {'season': 2022, 'week': 16, 'team': 'IND',
                            'passing_yards': 13.0, 'receiving_yards': 12.0,
                            'note': 'no lateral on the play; upstream '
                                    'inconsistency of 1 yard, left visible'},
    'policy': ('A lateral residual is NAMED and permitted. Anything else is '
               'an unexplained residual and stays a FAIL. The exception may '
               'never be widened to make an unexplained case pass.'),
}
