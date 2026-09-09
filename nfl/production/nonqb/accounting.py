"""Joint non-QB accounting. PER DRAW, and vacuously-passing is impossible.

WHY THIS IS A MODULE AND NOT A BLOCK INSIDE THE REHEARSAL

The first version of these checks lived inline in `engine_rehearsal.py` and
printed deviations. A printed deviation is a diagnostic; it does not stop
anything. The QB chain already learned this lesson the expensive way -- a draw
set whose means reconciled to three decimal places contained 22,749 impossible
cells -- so the non-QB chain gets the same treatment: named identities,
checked in every cell, FAIL rather than clip.

WHAT IS MECHANICALLY TRUE in the frozen P4C allocator

    sum_i share[i in group] + other[group] == 1      per draw, simplex mode
    share >= 0                                       per cell
    sum_i targets[i] + other*team_targets == team_targets
    receptions <= targets                            a reception is a target
    receiving TD <= receptions
    receiving yards >= 0
    share[i, j] == 0 wherever appearance[i, j] == 0

The last one is the load-bearing one. It is what ties the allocation layer to
the same draw index as the appearance layer; without it a player could receive
opportunity in a draw in which he did not play, and nothing downstream would
notice.

WHAT IS NOT MECHANICALLY TRUE, and is NAMED rather than enforced

`other` is the mass allocated to players outside the modelled set. It is a
real quantity with a name and it is reported. It is NOT a residual that
absorbs disagreement: if the identities above do not hold, this module fails,
it does not widen `other` to make them hold.

TOLERANCE. The allocator computes in float32. RELATIVE_TOL is the declared
equivalence margin for the two `eq` identities; it is a float32 arithmetic
allowance, not a modelling allowance, and no identity here is permitted a
tolerance chosen to make a run pass.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

RELATIVE_TOL = 1e-4          # float32 accumulation over <= a few hundred terms

# (name, why it is load-bearing)
NONQB_IDENTITIES = (
    ('share_simplex_closure',
     'the modelled players plus the named OTHER mass are the whole group. If '
     'this fails the allocator has lost or created opportunity.'),
    ('share_non_negative',
     'a negative share is not a small share, it is an impossible one.'),
    ('player_opportunity_within_team',
     'player opportunity summed over a team plus OTHER must equal the team '
     'volume the environment layer drew. No layer may independently redraw a '
     'team quantity that already exists upstream.'),
    ('receptions_within_targets',
     'a reception is a target.'),
    ('receiving_td_within_receptions',
     'a receiving touchdown is a reception.'),
    ('receiving_yards_non_negative',
     'negative receiving yards are possible in football and not in this '
     'baseline, which draws yards as receptions times a positive rate.'),
    ('allocation_only_when_available',
     'a player who did not appear in draw j may not receive opportunity in '
     'draw j. This is what ties the allocation layer to the appearance layer '
     'on ONE draw index.'),
)
IDENTITY_NAMES = tuple(n for n, _ in NONQB_IDENTITIES)


def _groups(starts, counts):
    return list(zip(list(starts), list(counts)))


def reconcile_nonqb(share, other, team_volume, player_opportunity,
                    appearance, starts, counts,
                    receptions=None, receiving_td=None,
                    receiving_yards=None) -> Outcome:
    """Check every identity in every cell.

    share              (n_players, m)   allocation shares
    other              (n_groups, m)    named out-of-model mass
    team_volume        (n_groups, m)    the upstream team draw
    player_opportunity (n_players, m)   share * team volume, broadcast by group
    appearance         (n_players, m)   1 where the player appeared
    """
    S = np.asarray(share, np.float64)
    O = np.asarray(other, np.float64)
    V = np.asarray(team_volume, np.float64)
    T = np.asarray(player_opportunity, np.float64)
    A = np.asarray(appearance, np.float64)
    g = _groups(starts, counts)

    # A CHECK OVER ZERO CELLS IS NOT A PASSING CHECK. Absence read as success
    # is the failure mode this project pays for most often, and an accounting
    # module that reports PASS on an empty draw set is exactly that.
    if S.ndim != 2 or S.size == 0 or not g:
        return Outcome.fail(
            'NONQB_ACCOUNTING_VACUOUS',
            f'nothing to reconcile: share has shape {S.shape} over '
            f'{len(g)} group(s). A check that examined no cell has not '
            f'passed.', shape=list(S.shape), n_groups=len(g))
    n, m = S.shape
    for name, arr in (('other', O), ('team_volume', V)):
        if arr.shape != (len(g), m):
            return Outcome.fail(
                'CROSS_DRAW_INDEX_MISMATCH',
                f'{name} has shape {arr.shape} against {(len(g), m)}. These '
                f'layers must share one draw index.', got=list(arr.shape))
    for name, arr in (('player_opportunity', T), ('appearance', A)):
        if arr.shape != (n, m):
            return Outcome.fail(
                'CROSS_DRAW_INDEX_MISMATCH',
                f'{name} has shape {arr.shape} against {(n, m)}. These layers '
                f'must share one draw index.', got=list(arr.shape))

    viol, ev = [], {'n_players': n, 'n_draws': m, 'n_groups': len(g),
                    'n_cells_checked': int(n * m)}

    grp_share = np.stack([S[a:a + c].sum(0) for a, c in g])
    d = np.abs(grp_share + O - 1.0)
    ev['share_simplex_closure_maxdev'] = float(d.max())
    if d.max() > RELATIVE_TOL:
        viol.append(('share_simplex_closure', int((d > RELATIVE_TOL).sum()),
                     float(d.max())))

    neg = int((S < 0).sum())
    ev['share_non_negative_violations'] = neg
    if neg:
        viol.append(('share_non_negative', neg, float(S.min())))

    grp_opp = np.stack([T[a:a + c].sum(0) for a, c in g])
    lhs, rhs = grp_opp + O * V, V
    scale = np.maximum(np.abs(rhs), 1.0)
    d2 = np.abs(lhs - rhs) / scale
    ev['player_opportunity_within_team_maxreldev'] = float(d2.max())
    if d2.max() > RELATIVE_TOL:
        viol.append(('player_opportunity_within_team',
                     int((d2 > RELATIVE_TOL).sum()), float(d2.max())))

    if receptions is not None:
        R = np.asarray(receptions, np.float64)
        bad = int((R > np.rint(T) + 1e-9).sum())
        ev['receptions_within_targets_violations'] = bad
        if bad:
            viol.append(('receptions_within_targets', bad,
                         float((R - np.rint(T)).max())))
        if receiving_td is not None:
            D = np.asarray(receiving_td, np.float64)
            bad = int((D > R).sum())
            ev['receiving_td_within_receptions_violations'] = bad
            if bad:
                viol.append(('receiving_td_within_receptions', bad,
                             float((D - R).max())))
        if receiving_yards is not None:
            Y = np.asarray(receiving_yards, np.float64)
            bad = int((Y < 0).sum())
            ev['receiving_yards_non_negative_violations'] = bad
            if bad:
                viol.append(('receiving_yards_non_negative', bad,
                             float(Y.min())))

    bad_avail = int(((A <= 0) & (S > 0)).sum())
    ev['allocation_only_when_available_violations'] = bad_avail
    if bad_avail:
        viol.append(('allocation_only_when_available', bad_avail,
                     float(S[(A <= 0)].max() if (A <= 0).any() else 0.0)))

    ev['other_mass_mean'] = float(O.mean())
    ev['other_mass_interpretation'] = (
        'opportunity allocated to players outside the modelled set. A named '
        'quantity, never a residual that absorbs disagreement.')
    ev['identities_checked'] = list(IDENTITY_NAMES)
    ev['relative_tol'] = RELATIVE_TOL

    if viol:
        return Outcome.fail(
            'NONQB_DRAW_ACCOUNTING_VIOLATED',
            '; '.join(f'{k}: {c} cell(s), worst {w:.6g}' for k, c, w in viol),
            violations=[{'identity': k, 'cells': c, 'worst': w}
                        for k, c, w in viol], **ev)
    return Outcome.ok('NONQB_DRAW_ACCOUNTING_OK', value=ev, **ev)


def reconcile_chain(team_env, appear, part, tc, conv, td) -> Outcome:
    """Accounting over a chain that did not execute is NOT_APPLICABLE.

    Reporting PASS because there was nothing to check is the same defect as
    sealing an empty artifact, so the state is named separately.
    """
    stages = (('team_environment', team_env), ('appearance', appear),
              ('participation', part), ('targets_carries', tc),
              ('receiving_conversion', conv), ('td_layer', td))
    absent = [f'{k}={v.state.value}[{v.code}]' for k, v in stages
              if v is None or v.state is not State.PASS]
    if absent:
        return Outcome.not_applicable(
            'NONQB_ACCOUNTING_NOT_REACHED',
            f'the chain did not execute: {absent}. There are no draws to '
            f'reconcile, which is not the same as reconciled draws.',
            absent=absent)
    return Outcome.ok('NONQB_CHAIN_EXECUTED', value=len(stages))
