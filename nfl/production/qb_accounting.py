"""Whole-chain QB accounting. PER DRAW, not in aggregate.

WHY PER DRAW AND NOT IN AGGREGATE

A draw set whose *means* reconcile can still contain draws that are impossible.
Averaged over 125,000 cells, this layer's first candidate set reconciled to
three decimal places while containing 84 cells with more passing touchdowns
than completions, 189 with more interceptions than incompletions, and 22,749 --
18.2% -- in which a quarterback had fewer rushing opportunities than his own
scrambles. An aggregate check would have passed all three. See
`nfl/research/qb2/addendum_qb2_coherence.md`.

WHAT IS MECHANICALLY TRUE, measured on qb.pkl 2022-2025 over 2,645 QB
player-games carrying an attempt, touchdown or interception:

    dropbacks   == attempts + sacks + scrambles     EXACT (the QB1 identity)
    completions <= attempts                         0 violations
    passing TD  <= completions                      0 violations
    interceptions <= attempts - completions         0 violations
    rush opportunities == designed + scrambles      EXACT by construction
    rush TD     <= rush opportunities               0 violations

These are hard identities in the source. A draw that breaks one is not a
mis-calibrated draw, it is an impossible one, and this module FAILS rather than
clipping it. Clipping would convert a measurable defect into an invisible one.

WHAT IS NOT MECHANICALLY TRUE, and is NAMED rather than enforced

The sum of independently-allocated QB dropbacks over a team-game is NOT the
team's dropback count, and cannot be made so without information this project
does not have at prediction time. See ALLOCATION_RESIDUAL below.
"""
from __future__ import annotations

import collections
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.accounting.invariants import (LATERAL_EXCEPTION,  # noqa: E402
                                       QB_DROPBACK_IDENTITY)
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

# (name, kind, lhs keys, rhs keys, why it is load-bearing)
#   'eq' -> lhs must equal rhs exactly, in every cell
#   'le' -> lhs must not exceed rhs, in any cell
PER_DRAW_IDENTITIES = (
    ('dropback_identity', 'eq', ('att', 'sacks', 'scr'), ('db',),
     'the QB1 binding identity. pass_attempt INCLUDES sacks and spikes, so '
     'deriving attempts by subtracting sacks from dropbacks is wrong by 5,586 '
     'plays over four seasons.'),
    ('rush_opportunity_composition', 'eq', ('scr', 'drush'), ('rush_opp',),
     'rush opportunity is COMPOSED from scrambles plus designed rushes, never '
     'drawn whole. Drawn whole it fell below its own scramble count in 18.2% '
     'of cells.'),
    ('completions_within_attempts', 'le', ('cmp',), ('att',),
     'a completion is an attempt.'),
    ('passing_td_within_completions', 'le', ('ptd',), ('cmp',),
     'a passing touchdown is a completion. Drawn from attempts instead, this '
     'manufactured touchdowns on incomplete passes.'),
    ('interceptions_within_incompletions', 'le', ('int',), ('att', '-cmp'),
     'an interception is an incompletion. Drawn from attempts instead, this '
     'charged interceptions to passes the same draw had completed.'),
    ('rush_td_within_opportunities', 'le', ('rtd',), ('rush_opp',),
     'a rushing touchdown is a rushing opportunity.'),
    ('scrambles_within_opportunities', 'le', ('scr',), ('rush_opp',),
     'a scramble is a rushing opportunity for the quarterback who ran it.'),
)


def _sum(D, keys):
    t = None
    for k in keys:
        neg = k.startswith('-')
        v = D[k[1:] if neg else k]
        t = (-v if neg else v) if t is None else (t - v if neg else t + v)
    return t


def reconcile_draws(D, tol: float = 1e-9) -> Outcome:
    """Every predeclared QB identity, in every draw cell. No clipping."""
    missing = sorted({k.lstrip('-') for _, _, a, b, _ in PER_DRAW_IDENTITIES
                      for k in a + b} - set(D))
    if missing:
        # ABSENCE IS NOT SUCCESS. A check that cannot run has not passed.
        return Outcome.blocked(
            'QB_ACCOUNTING_INPUT_INCOMPLETE',
            f'cannot reconcile: the draw set has no {missing}. A skipped '
            f'identity is not a satisfied identity.',
            cause=Cause.DATA, missing=missing)
    cells = int(np.asarray(D['db']).size)
    if cells == 0:
        return Outcome.blocked(
            'QB_ACCOUNTING_EMPTY',
            'the draw set is empty; zero draw cells is an error, not a '
            'reconciliation', cause=Cause.DATA)
    report, bad = {}, {}
    for name, kind, a, b, why in PER_DRAW_IDENTITIES:
        d = _sum(D, a) - _sum(D, b)
        n = int((np.abs(d) > tol).sum()) if kind == 'eq' else int((d > tol).sum())
        report[name] = {'kind': kind, 'violating_cells': n,
                        'worst_excess': float(d.max()), 'why': why}
        if n:
            bad[name] = n
    if bad:
        worst = max(bad, key=bad.get)
        return Outcome.fail(
            'QB_DRAW_ACCOUNTING_VIOLATED',
            f'{len(bad)} of {len(PER_DRAW_IDENTITIES)} per-draw identities '
            f'fail over {cells} draw cells. Worst: {worst}, {bad[worst]} '
            f'cell(s). These are impossible states, not mis-calibrated ones, '
            f'and clipping them would hide the defect that produced them.',
            n_cells=cells, violations=bad, report=report)
    return Outcome.ok(
        'QB_DRAW_ACCOUNTING_HOLDS',
        value={'n_cells': cells, 'identities': len(PER_DRAW_IDENTITIES),
               'report': report},
        detail=f'all {len(PER_DRAW_IDENTITIES)} identities hold on every one '
               f'of {cells} draw cells')


# ==========================================================================
# THE RESIDUAL THAT IS NAMED RATHER THAN ENFORCED
# ==========================================================================
#
# Measured 2024, 540 team-games, 200 draws, on the corrected layer:
#
#   single-QB team-games  n=456   drawn 34.454 vs realised 36.803   -2.349
#   multi-QB  team-games  n= 84   drawn 62.510 vs realised 36.607  +25.903
#
# In a multi-QB team-game the layer allocates each quarterback his own
# prior-only share of team dropbacks, and two quarterbacks who have each
# historically taken most of their team's dropbacks sum to well over one team's
# worth. That is the mechanism behind the +79.8-yard multi-QB passing bias this
# layer already reports.
#
# IT IS NOT NORMALISED, AND THE REASON IS LEAKAGE, NOT DIFFICULTY.
# Normalising shares across a team-game requires knowing which quarterbacks
# will appear. The evaluation frame's QB set is built from realised appearance
# (a dropback actually taken), so dividing by its total would feed realised
# participation back into a pregame forecast. The prospective participation
# source that could supply it is CAPTURE_PATH_READY_SOURCE_UNPUBLISHED, and
# prereg s3 forbids depth-chart guesswork as the substitute. The over-
# allocation is therefore the honest price of not leaking, and it is reported
# on every run.
ALLOCATION_RESIDUAL = {
    'invariant': 'sum_of_QB_dropbacks_eq_team_dropbacks',
    'holds': False,
    'season_measured': 2024, 'n_team_games': 540, 'draws': 200,
    'single_qb': {'n': 456, 'drawn': 34.454, 'realised': 36.803,
                  'bias': -2.349},
    'multi_qb': {'n': 84, 'drawn': 62.510, 'realised': 36.607,
                 'bias': +25.903},
    'cause': 'prior-only shares are not normalised within a team-game',
    'why_not_fixed': ('normalising requires prediction-time participation. '
                      'The eligible QB set is built from realised appearance, '
                      'so normalising over it would leak the outcome into the '
                      'forecast. The prospective source is '
                      'CAPTURE_PATH_READY_SOURCE_UNPUBLISHED and depth-chart '
                      'guesswork is forbidden by prereg s3.'),
    'policy': 'reported on every run, never clipped and never smoothed away',
}


def reconcile_team(D, rows, team_rush_draws=None,
                   team_rushes_realised: dict | None = None) -> Outcome:
    """Team-level checks. The allocation residual is measured, not enforced.

    TWO DIFFERENT QUESTIONS, AND THEY MUST NOT BE MERGED.

    `team_rush_draws` is a forecast from the carries layer on the SAME draw
    indices. Both sides are then pregame quantities in one joint draw, and a
    quarterback drawing more rushing opportunities than his team drew rushing
    plays is a genuine incoherence -> FAIL.

    `team_rushes_realised` is what the team actually ran. Comparing a pregame
    draw against it is comparing a forecast to an outcome, and calling the
    excess a defect would be defining a defect against a realised outcome. It
    is reported as a NAMED diagnostic residual and never as a failure.
    Measured 2024 with realised counts: 67 of 108,000 draw cells, 0.062%,
    in 7 of 540 team-games.
    """
    n_rows = int(np.asarray(D['db']).shape[0])
    if len(rows) != n_rows:
        return Outcome.fail(
            'QB_ACCOUNTING_SHAPE_MISMATCH',
            f'{len(rows)} row(s) against {n_rows} draw row(s); a '
            f'reconciliation over mismatched frames is meaningless',
            n_rows=len(rows), n_draws=n_rows)
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by[(r['season'], r['week'], r['team'])].append(i)
    if not by:
        return Outcome.blocked('QB_ACCOUNTING_EMPTY', 'no team-games to '
                               'reconcile', cause=Cause.DATA)
    keys = list(by)
    single = [k for k in keys if len(by[k]) == 1]
    multi = [k for k in keys if len(by[k]) > 1]

    def _bias(ks):
        if not ks:
            return None
        d = np.array([D['db'][by[k]].sum(0).mean() for k in ks])
        t = np.array([sum(rows[i]['db'] for i in by[k]) for k in ks])
        return {'n': len(ks), 'drawn': float(d.mean()),
                'realised': float(t.mean()), 'bias': float((d - t).mean())}

    # HARD, and only against a same-draw forecast.
    if team_rush_draws is not None:
        bad = {}
        for k in keys:
            budget = team_rush_draws.get(k) if hasattr(
                team_rush_draws, 'get') else None
            if budget is None:
                continue
            over = int((D['rush_opp'][by[k]].sum(0)
                        > np.asarray(budget, float) + 1e-9).sum())
            if over:
                bad[str(k)] = over
        if bad:
            return Outcome.fail(
                'QB_RUSHES_EXCEED_TEAM_RUSH_DRAWS',
                f'{len(bad)} team-game(s) draw more QB rushing opportunities '
                f'than the carries layer drew team rushing plays, on the same '
                f'draw index. Both sides are pregame quantities, so this is '
                f'incoherence rather than forecast error.',
                n_bad=len(bad), examples=dict(list(bad.items())[:5]))

    # DIAGNOSTIC ONLY, against a realised count. Never a failure.
    diag = None
    if team_rushes_realised:
        cells = viol = games = 0
        for k in keys:
            tr = team_rushes_realised.get(k)
            if tr is None:
                continue
            s = D['rush_opp'][by[k]].sum(0)
            cells += int(s.size)
            o = int((s > float(tr) + 1e-9).sum())
            viol += o
            games += bool(o)
        diag = {'draw_cells': cells, 'exceeding_realised_team_rushes': viol,
                'rate': (viol / cells) if cells else None,
                'team_games_affected': games, 'n_team_games': len(keys),
                'interpretation': 'a pregame draw above a realised count is '
                                  'forecast error in the right tail, NOT a '
                                  'coherence defect. Defining a defect against '
                                  'a realised outcome manufactures one for any '
                                  'forecaster, including a correct one.'}
    return Outcome.ok(
        'QB_TEAM_ACCOUNTING_MEASURED',
        value={'n_team_games': len(keys),
               'single_qb': _bias(single), 'multi_qb': _bias(multi),
               'vs_team_rush_draws_checked': team_rush_draws is not None,
               'vs_realised_team_rushes': diag,
               'named_residual': ALLOCATION_RESIDUAL},
        detail=f'{len(keys)} team-game(s), {len(multi)} with more than one '
               f'quarterback. The share-allocation residual is NAMED and '
               f'quantified, not clipped.',
        warnings=['sum of QB dropbacks does not equal team dropbacks; see '
                  'ALLOCATION_RESIDUAL'])


def reconcile_cross_layer(D, receiving=None, receiving_td=None) -> Outcome:
    """QB passing yards against player receiving yards, and passing TD against
    receiving TD. DEFERRED when the receiving layer is not in the same run --
    a check that did not run has not passed."""
    if receiving is None:
        return Outcome.deferred(
            'CROSS_LAYER_RECONCILIATION_NOT_RUN',
            'the receiving draw set was not supplied to this run, so team '
            'passing yards against player receiving yards and passing TD '
            'against receiving TD could not be reconciled. This is recorded '
            'as owed rather than reported as satisfied.',
            owed={'needs': ['receiving yard draws aligned to the same '
                            'team-games and draw indices',
                            'receiving TD draws'],
                  'exception_to_preserve': LATERAL_EXCEPTION,
                  'blocking_stage': 'conversion (RC1 baseline; SIGNAL_WEAK)'})
    py = np.asarray(D['pyds'])
    ry = np.asarray(receiving)
    if py.shape != ry.shape:
        return Outcome.fail(
            'CROSS_LAYER_SHAPE_MISMATCH',
            f'passing yards {py.shape} against receiving yards {ry.shape}; '
            f'these must be the same team-games and the same draw indices',
            passing=list(py.shape), receiving=list(ry.shape))
    d = py.sum(0) - ry.sum(0)
    n_bad = int((np.abs(d) > 1e-9).sum())
    out = {'n_draws': int(py.shape[1]), 'violating_draws': n_bad,
           'worst_abs_residual': float(np.abs(d).max()),
           'lateral_exception': LATERAL_EXCEPTION}
    if receiving_td is not None:
        t = np.asarray(D['ptd']).sum(0) - np.asarray(receiving_td).sum(0)
        out['td_violating_draws'] = int((np.abs(t) > 1e-9).sum())
        if out['td_violating_draws']:
            return Outcome.fail(
                'PASSING_TD_RECEIVING_TD_MISMATCH',
                f'{out["td_violating_draws"]} draw(s) where team passing '
                f'touchdowns do not equal receiving touchdowns. This one has '
                f'no lateral exception: it is EXACT in the source.', **out)
    if n_bad:
        return Outcome.fail(
            'PASSING_YARDS_RECEIVING_YARDS_MISMATCH',
            f'{n_bad} draw(s) where team passing yards do not equal player '
            f'receiving yards. A lateral residual is NAMED and permitted; '
            f'anything else stays a failure and the exception may never be '
            f'widened to make an unexplained case pass.', **out)
    return Outcome.ok('CROSS_LAYER_RECONCILED', value=out,
                      detail=f'passing and receiving reconcile on all '
                             f'{py.shape[1]} draw(s)')


def summary() -> dict:
    """What this layer asserts and what it merely names. For the artifact."""
    return {
        'per_draw_identities': [
            {'name': n, 'kind': k, 'lhs': list(a), 'rhs': list(b), 'why': w}
            for n, k, a, b, w in PER_DRAW_IDENTITIES],
        'named_residual_not_enforced': ALLOCATION_RESIDUAL,
        'preserved_exceptions': {
            'lateral': LATERAL_EXCEPTION,
            'qb_dropback_identity': QB_DROPBACK_IDENTITY,
        },
    }
