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
    'superseded_by_r2': (
        'CORRECTED 2026-09-10. The measurement above is of the PRE-R2 layer, '
        'where QB V1 drew its own level. Under R2 the level is a '
        'largest-remainder apportionment of rint(team_dropbacks_part) and '
        'closure is integer-exact by construction, so `holds: False` describes '
        'a configuration the candidate no longer runs. reconcile_team now '
        'MEASURES closure per team per draw instead of asserting it fails.'),
    'holds_under_r2': True,
}


def reconcile_team(D, rows, team_rush_draws=None,
                   team_rushes_realised: dict | None = None,
                   team_dropback_draws: dict | None = None,
                   integer_level: bool = False) -> Outcome:
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
        # THE KEY SHAPE IS CHECKED, NOT ASSUMED. This looked budgets up by the
        # (season, week, team) tuple and silently `continue`d on a miss. Every
        # other function in this file -- reconcile_team_volume, and
        # football_engine's caller -- keys the same map by TEAM alone, so a
        # caller using the house shape matched nothing, checked zero teams,
        # and this returned PASS with vs_team_rush_draws_checked: True. The
        # file's own note already recorded that this guard 'has never refused
        # anything'. A guard given no input is not a guard.
        missing = [k for k in keys
                   if not (hasattr(team_rush_draws, 'get')
                           and (team_rush_draws.get(k) is not None
                                or team_rush_draws.get(k[-1]) is not None))]
        if missing:
            return Outcome.fail(
                'QB_TEAM_RUSH_BUDGET_KEY_MISMATCH',
                f'{len(missing)} of {len(keys)} team-game(s) have no entry in '
                f'the supplied team_rush_draws map, so the containment check '
                f'would silently examine nothing. Accepted keys are the '
                f'(season, week, team) tuple or the bare team. Refusing rather '
                f'than reporting a check that did not run.',
                n_missing=len(missing), n_keys=len(keys),
                examples=[str(k) for k in missing[:5]])
        bad = {}
        for k in keys:
            budget = team_rush_draws.get(k)
            if budget is None:
                budget = team_rush_draws.get(k[-1])
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
    # ------------------------------------------------------------------
    # THE RESIDUAL IS NOW MEASURED. IT USED TO BE ASSERTED.
    #
    # This function returned the literal warning "sum of QB dropbacks does not
    # equal team dropbacks" on EVERY call, from a hard-coded list in the return
    # statement, having measured nothing of the kind. `run_forecast` turned any
    # warning into the FAIL verdict QB_ALLOCATION_RESIDUAL_PRESENT, so every
    # sealed artifact this project has ever produced carries a failing
    # invariant that was a string rather than a finding.
    #
    # Under R2 the assertion is FALSE. The per-quarterback level is a
    # largest-remainder apportionment of rint(team_dropbacks_part);
    # `apportion_dropbacks` refuses outright if the shares do not cover the
    # budget, and closure is integer-exact by construction in every draw.
    #
    # So the warning is now raised only when a supplied team dropback budget
    # actually fails to close, and the closure is reported with its cell counts
    # either way. A caller that supplies no budget gets NOT_MEASURED -- not a
    # pass, and not the old unconditional failure.
    closure = {'status': 'NOT_MEASURED',
               'why': 'no team dropback draw was supplied to this call, so '
                      'closure was not examined. This is not evidence that it '
                      'holds.'}
    warnings = []
    if team_dropback_draws is not None:
        cells = bad = 0
        worst = 0.0
        per_team, skipped = {}, []
        for k in keys:
            b = team_dropback_draws.get(k)
            if b is None:
                b = team_dropback_draws.get(k[-1])
            if b is None:
                skipped.append(str(k))
                continue
            b = np.asarray(b, float)
            q = np.asarray(D['db'])[by[k]].sum(0)
            if q.shape != b.shape:
                return Outcome.fail(
                    'CROSS_DRAW_INDEX_MISMATCH',
                    f'{k}: QB dropback draws have shape {q.shape} against a '
                    f'team budget of {b.shape}. These must share one draw '
                    f'index, and comparing them across two would be '
                    f'meaningless rather than merely wrong.')
            target = np.rint(b) if integer_level else b
            d = np.abs(q - target) if integer_level else np.maximum(q - b, 0.0)
            n_bad = int((d > 1e-9).sum())
            cells += int(q.size)
            bad += n_bad
            worst = max(worst, float(d.max()) if d.size else 0.0)
            per_team[str(k)] = {'cells': int(q.size), 'violating': n_bad,
                                'qb_sum_mean': round(float(q.mean()), 6),
                                'budget_mean': round(float(b.mean()), 6)}
        if skipped:
            return Outcome.fail(
                'QB_TEAM_DROPBACK_BUDGET_KEY_MISMATCH',
                f'{len(skipped)} of {len(keys)} team-game(s) have no entry in '
                f'the supplied team_dropback_draws map, so closure would be '
                f'reported from a check that examined nothing. Accepted keys '
                f'are the (season, week, team) tuple or the bare team.',
                n_missing=len(skipped), examples=skipped[:5])
        closure = {
            'status': 'CLOSES' if bad == 0 else 'DOES_NOT_CLOSE',
            'test': ('sum of QB dropbacks == rint(team dropback draw), per '
                     'team per draw' if integer_level else
                     'sum of QB dropbacks <= team dropback draw, per team '
                     'per draw'),
            'integer_level': bool(integer_level),
            'draw_cells': cells, 'violating_cells': bad,
            'worst_absolute_deviation': round(worst, 9),
            'per_team': per_team,
            'no_cross_team_compensation': ('each team is compared only against '
                                           'its own budget; a surplus on one '
                                           'team can never offset a shortfall '
                                           'on the other')}
        if bad:
            warnings.append(
                f'sum of QB dropbacks does not equal team dropbacks in '
                f'{bad} of {cells} draw cell(s); worst deviation {worst:.6f}. '
                f'See ALLOCATION_RESIDUAL.')
    return Outcome.ok(
        'QB_TEAM_ACCOUNTING_MEASURED',
        value={'n_team_games': len(keys),
               'single_qb': _bias(single), 'multi_qb': _bias(multi),
               'vs_team_rush_draws_checked': team_rush_draws is not None,
               'vs_realised_team_rushes': diag,
               'per_team_dropback_closure': closure,
               'named_residual': ALLOCATION_RESIDUAL},
        detail=f'{len(keys)} team-game(s), {len(multi)} with more than one '
               f'quarterback; per-team dropback closure {closure["status"]}.',
        per_team_dropback_closure=closure,
        warnings=warnings)


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


# =====================================================================
# R4: the QB layer against the TEAM VOLUME layer, on one draw index.
#
# `reconcile_team` already carries a hard check of QB rush opportunity against
# a same-draw team rush budget. It has never refused anything, because no
# production caller has ever passed `team_rush_draws`. A guard that has never
# been given its input is not a guard -- this repository has the same lesson
# recorded about `assert_batch_games_are_new`.
#
# There was no dropback counterpart at all, and that is where the error lives.
# MEASURED on the real 2026 week-1 roster, 32 teams x 200 draws:
#
#     D1 team dropbacks         36.75
#     QB-summed dropbacks       79.76      ratio 2.17
#     cells where the QBs collectively out-drop their own team
#                               5,930 of 6,400   (92.7%)
#     teams with exactly one QB row      1 of 32
#
# The cause is not a bug in QB V1. It is that the QB layer models a passer's
# line CONDITIONAL ON BEING THE TEAM'S PRIMARY PASSER, and nothing selects
# which of a team's 2.62 rostered quarterbacks that is. Every other position
# passes through the appearance layer; the QB does not.
#
# This module does not invent that selection. It makes its absence a NAMED
# FAILURE instead of an invisible 2.17x.
# =====================================================================

QB_TEAM_VOLUME_IDENTITIES = (
    ('qb_dropback_within_team_volume',
     'the quarterbacks of one team cannot collectively drop back more times '
     'than their team does, in the same draw.'),
    ('qb_rush_within_team_carries',
     'the quarterbacks of one team cannot collectively take more rushing '
     'opportunities than their team has carries, in the same draw.'),
)

QB_PRIMARY_PASSER_GAP = (
    'QB_PRIMARY_PASSER_SELECTION: no model selects which rostered quarterback '
    'is the team\'s primary passer. Appearance is not the same question -- a '
    'backup can appear without taking a snap at quarterback -- so the P3 '
    'appearance mechanism does not answer it. Until it is answered, a '
    'prospective slate forecasts 2.62 starters per team.')


def reconcile_team_volume(D, rows, team_dropback_draws=None,
                          team_carry_draws=None, integer_level=False) -> Outcome:
    """QB draws against the D1 team volume draws, on the SAME draw index.

    Both arguments map (team) -> a draw vector. A team absent from a map is
    skipped and counted, never silently treated as satisfied.
    """
    n_rows = int(np.asarray(D['db']).shape[0])
    if len(rows) != n_rows:
        return Outcome.fail(
            'QB_ACCOUNTING_SHAPE_MISMATCH',
            f'{len(rows)} row(s) against {n_rows} draw row(s)')
    if team_dropback_draws is None and team_carry_draws is None:
        return Outcome.not_applicable(
            'QB_TEAM_VOLUME_NOT_SUPPLIED',
            'neither team dropback nor team carry draws were supplied, so '
            'nothing was checked. Reported as not applicable rather than as a '
            'reconciliation that passed.')
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if r.get('team'):
            by[r['team']].append(i)
    if not by:
        return Outcome.fail('QB_ACCOUNTING_EMPTY',
                            'no QB row carries a team, so nothing can be '
                            'reconciled against a team quantity')
    viol, ev = [], {'n_teams': len(by), 'n_qb_rows': n_rows,
                    'qb_rows_per_team': round(n_rows / max(len(by), 1), 3),
                    'identities_checked': [n for n, _ in
                                           QB_TEAM_VOLUME_IDENTITIES]}
    skipped = []
    for name, field, budget in (
            ('qb_dropback_within_team_volume', 'db', team_dropback_draws),
            ('qb_rush_within_team_carries', 'rush_opp', team_carry_draws)):
        if budget is None:
            ev[f'{name}_status'] = 'NOT_SUPPLIED'
            continue
        cells = over = 0
        drawn = tot = 0.0
        for t, idx in by.items():
            b = budget.get(t)
            if b is None:
                skipped.append(t)
                continue
            b = np.asarray(b, float)
            q = np.asarray(D[field])[idx].sum(0)
            if q.shape != b.shape:
                return Outcome.fail(
                    'CROSS_DRAW_INDEX_MISMATCH',
                    f'{name}: QB draws have shape {q.shape} against the team '
                    f'budget {b.shape}. These must share one draw index.')
            cells += q.size
            if integer_level and name == 'qb_dropback_within_team_volume':
                # R2 REPLACES THIS INVARIANT, AND SAYS SO IN ADVANCE. Under R2
                # the per-QB level is a largest-remainder apportionment of
                # rint(team_dropbacks_part), so the team sum EQUALS the integer
                # budget and may exceed the float one by up to 0.5. The
                # pre-registration (section 2) declares exactly this: "the
                # invariant changes from float-exact to integer-exact ... R2
                # must not be reported as preserving the current invariant".
                #
                # This is a STRICTER test, not a loosened one: the incumbent
                # asks sum <= budget, and this asks sum == rint(budget)
                # exactly. Measured under R2: 0 violating cells.
                over += int((np.abs(q - np.rint(b)) > 1e-9).sum())
            else:
                over += int((q > b + 1e-9).sum())
            drawn += float(q.sum())
            tot += float(b.sum())
        ev[f'{name}_cells'] = cells
        ev[f'{name}_violations'] = over
        ev[f'{name}_ratio'] = round(drawn / tot, 4) if tot else None
        if over:
            viol.append((name, over, cells))
    if skipped:
        ev['teams_without_a_budget'] = sorted(set(skipped))
    if viol:
        return Outcome.fail(
            'QB_TEAM_VOLUME_INCOHERENT',
            '; '.join(f'{k}: {c} of {n} cell(s)' for k, c, n in viol)
            + '. ' + QB_PRIMARY_PASSER_GAP,
            violations=[{'identity': k, 'cells': c, 'of': n}
                        for k, c, n in viol],
            research_gap=QB_PRIMARY_PASSER_GAP, **ev)
    return Outcome.ok('QB_TEAM_VOLUME_COHERENT', value=ev, **ev)


# --------------------------------------------------------------- XL1 / OWN-1
QB_ALLOCATION_LEAK = (
    'A quarterback can be in the depth-chart allocation and absent from QB '
    'V1s forecast rows: QB V1 refuses a passer with no prior appearance, '
    'which is correct. What was NOT correct is what happened next -- his '
    'allocated dropback share was applied to nobody and simply left the '
    'system. The team budget then silently shrank. This is the projects own '
    'worst defect class, an absence read as success, and it is named here '
    'rather than repaired, because deciding what a team does with an '
    'unforecastable quarterbacks share is a modelling question and not an '
    'accounting one.')


def reconcile_allocation_share(allocation, forecast_ids_by_team,
                               tolerance=1e-6) -> Outcome:
    """Every unit of allocated dropback share must reach a forecastable passer.

    `allocation` maps team -> {'pids': [...], 'shares': (n_qb, m)}.
    `forecast_ids_by_team` maps team -> the gsis_ids QB V1 actually forecast.

    Refuses by name when share mass is allocated to a quarterback nobody can
    forecast. It does NOT renormalise: generating a fallback allocation is
    forbidden, and silently rescaling the incumbents would hide the gap in the
    one number that would otherwise reveal it.
    """
    if not allocation:
        return Outcome.not_applicable(
            'NO_QB_ALLOCATION',
            'no allocation was supplied, so there is no share mass to '
            'reconcile. This is not a pass.')
    ev, leaks = {}, []
    total_mass = total_lost = 0.0
    for team, a in sorted(allocation.items()):
        have = set(forecast_ids_by_team.get(team) or ())
        pids = list(a.get('pids') or ())
        sh = np.asarray(a.get('shares'), float)
        if sh.ndim != 2 or sh.shape[0] != len(pids):
            return Outcome.fail(
                'QB_ALLOCATION_SHAPE_MISMATCH',
                f'{team}: {len(pids)} pid(s) against shares of shape '
                f'{sh.shape}; a share cannot be attributed to a passer',
                team=team)
        mass = float(sh.sum(0).mean())
        lost = float(sum(sh[j].mean() for j, p in enumerate(pids)
                         if p not in have))
        total_mass += mass
        total_lost += lost
        if lost > tolerance:
            leaks.append({'team': team, 'share_lost': round(lost, 6),
                          'of_mass': round(mass, 6),
                          'unforecastable': [p for p in pids
                                             if p not in have]})
    ev['n_teams'] = len(allocation)
    ev['total_share_mass'] = round(total_mass, 6)
    ev['total_share_lost'] = round(total_lost, 6)
    ev['fraction_of_dropbacks_lost'] = (
        round(total_lost / total_mass, 6) if total_mass > 0 else None)
    ev['teams_leaking'] = len(leaks)
    if leaks:
        worst = max(leaks, key=lambda x: x['share_lost'])
        return Outcome.fail(
            'QB_ALLOCATION_SHARE_UNCONSUMED',
            f'{len(leaks)} team(s) allocate dropback share to a quarterback '
            f'QB V1 did not forecast; {total_lost:.4f} of {total_mass:.4f} '
            f'share units reach nobody, worst {worst["team"]} at '
            f'{worst["share_lost"]:.4f}. {QB_ALLOCATION_LEAK}',
            leaks=sorted(leaks, key=lambda x: -x['share_lost']), **ev)
    return Outcome.ok(
        'QB_ALLOCATION_SHARE_CONSUMED', value=ev,
        detail=f'every unit of allocated dropback share across '
               f'{len(allocation)} team(s) reaches a forecastable passer',
        **ev)


# ---------------------------------------------------------------- XL1 / OWN-4
ZERO_DRAW_ERASURE = (
    'QB V1 draws its OWN level -- V from the team-dropback pool and S from the '
    'share pool, DB = rint(V*S) -- which is the quantity D1 and QB3 already '
    'own. The composition reconciles that duplicate by division, so where QB '
    'V1s independent level happens to be zero the ratio is undefined and the '
    'allocated dropbacks were dropped. The zero-denominator behaviour is not '
    'an edge case; it is the signature of two layers owning one level.')


def conserve_allocated_mass(target, drawn, seed_parts) -> Outcome:
    """Which draw each cell should be composed FROM, so no allocated mass dies.

    Returns a source index per draw. Unaffected cells map to themselves, so
    their composition is bit-for-bit what it was. A cell holding allocated
    opportunity whose own level draw is zero borrows a DONOR draw from the same
    row: every rate in `qb2_lib.simulate` is a row-level scalar, so any
    non-zero draw of that row carries the same rates, and scaling it to the
    allocated target reproduces exactly what the composition would have done
    had the level draw not been zero.

    Nothing is fitted. Nothing is clipped. No survivor is renormalised. If the
    row has no non-zero draw at all there is nothing to borrow and the caller
    must REFUSE -- allocated mass may never be silently dropped or reassigned.
    """
    t = np.asarray(target, float)
    d = np.asarray(drawn, float)
    if t.shape != d.shape:
        return Outcome.fail(
            'MASS_CONSERVATION_SHAPE_MISMATCH',
            f'target {t.shape} against drawn {d.shape}; these must be the '
            f'same draw index', target_shape=list(t.shape),
            drawn_shape=list(d.shape))
    src = np.arange(t.size)
    need = (d <= 0) & (t > 0)
    n_need = int(need.sum())
    ev = {'n_draws': int(t.size), 'cells_needing_repair': n_need,
          'allocated_dropbacks_at_risk': round(float(t[need].sum()), 6),
          'max_single_draw_at_risk': (round(float(t[need].max()), 6)
                                      if n_need else 0.0)}
    if not n_need:
        return Outcome.ok('MASS_CONSERVED_NO_REPAIR_NEEDED', value=src,
                          detail='every cell holding allocated opportunity has '
                                 'a non-zero level draw of its own', **ev)
    donor = np.flatnonzero(d > 0)
    ev['donor_draws_available'] = int(donor.size)
    if not donor.size:
        return Outcome.fail(
            'QB_COMPOSITION_NO_DONOR_DRAW',
            f'{n_need} draw(s) hold {t[need].sum():.4f} allocated dropbacks '
            f'and this row drew zero dropbacks in EVERY draw, so no donor '
            f'exists. Refused: allocated mass may not be dropped and may not '
            f'be reassigned to anybody else. {ZERO_DRAW_ERASURE}', **ev)
    rng = np.random.default_rng(list(seed_parts))
    src[need] = donor[rng.integers(0, donor.size, n_need)]
    return Outcome.ok(
        'MASS_CONSERVED_BY_DONOR_DRAW', value=src,
        detail=f'{n_need} cell(s) borrowed a donor draw from the same row',
        mechanism='donor draw from the same row, scaled to the allocated '
                  'target; row-level rates are identical across a row',
        no_survivor_renormalisation=True, nothing_fitted=True,
        unaffected_cells_map_to_themselves=True, **ev)


def measure_composition_amplification(target, drawn) -> Outcome:
    """Is the composition STRETCHING a draw beyond its own support?

    `conserve_allocated_mass` says, and the engine relies on it, that "any
    non-zero draw of that row carries the same rates, so scaling it to the
    allocated target reproduces exactly what the composition would have done".

    THAT CLAIM IS FALSE FOR A SMALL DRAW, and this function measures how false.
    The rates in `qb2_lib.simulate` are row-level scalars, but a DRAW of one
    dropback does not carry a rate -- it carries one Bernoulli realisation of
    it. Composing by `target / drawn` multiplies that realisation, not the
    rate. A donor with db = 1 and ptd = 1 allocated 20 dropbacks yields 20
    passing touchdowns on 20 dropbacks: a 100% touchdown rate that the row's
    own parameters never contained.

    Measured on the real 2026 week-1 slate, ARI/LAC, m=200: 4.50% of raw
    dropback draws are exactly 1; the factor reaches 59.85; and a quarterback
    whose raw passing-TD draw maxes at 5 emerges with a composed maximum of
    49.14. An NFL record is 7.

    THE CONDITION IS PARAMETER-FREE: `drawn < target` is exactly "this draw is
    being stretched upward", with nothing fitted and no threshold chosen. The
    repair is NOT in this function -- removing the duplicate level draw is
    pre-registered as R2 and is not authorised here. What is fixed is the
    verdict: the engine reported PASS[QB_COMPOSITION_MASS_CONSERVED] while
    emitting this, and mass conservation was never the property in doubt.
    """
    t = np.asarray(target, float)
    d = np.asarray(drawn, float)
    if t.shape != d.shape:
        return Outcome.fail(
            'AMPLIFICATION_SHAPE_MISMATCH',
            f'target {t.shape} against drawn {d.shape}')
    live = (t > 0) & (d > 0)
    if not bool(live.any()):
        return Outcome.not_applicable(
            'AMPLIFICATION_NOT_APPLICABLE',
            'no cell carries both allocated mass and a non-zero draw')
    fac = np.zeros_like(t)
    fac[live] = t[live] / d[live]
    stretched = live & (d < t)
    ev = {'n_cells': int(live.sum()),
          'n_stretched': int(stretched.sum()),
          'frac_stretched': round(float(stretched.sum() / live.sum()), 6),
          'factor_max': round(float(fac.max()), 4),
          'factor_mean_over_live': round(float(fac[live].mean()), 4),
          'factor_median_over_live': round(float(np.median(fac[live])), 4),
          'n_factor_over_3': int((fac > 3).sum()),
          'n_factor_over_10': int((fac > 10).sum()),
          'min_denominator': round(float(d[live].min()), 4),
          'condition': 'drawn < target -- parameter-free, nothing fitted',
          'repair_is_not_here': 'R2 (remove the duplicate QB level draw); '
                                'pre-registered, not authorised in this task'}
    if not int(stretched.sum()):
        return Outcome.ok('QB_COMPOSITION_RATE_FIDELITY_OK',
                          value=ev, detail='no draw is stretched upward', **ev)
    return Outcome.fail(
        'QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED',
        f'{ev["n_stretched"]} of {ev["n_cells"]} cell(s) compose by stretching '
        f'a draw beyond its own support (factor up to {ev["factor_max"]}, '
        f'smallest denominator {ev["min_denominator"]}). The composed cell '
        f'carries the donor draw\'s realised rates multiplied, not the row\'s '
        f'rates, so derived fields inherit amplified sampling noise. Mass is '
        f'still conserved; rate fidelity is not, and reporting only the former '
        f'as PASS asserted a property that was never checked.', **ev)


def apportion_dropbacks(team_dropbacks, shares, pids) -> Outcome:
    """R2 step 2: split an INTEGER team dropback budget across quarterbacks.

    Largest-remainder (Hamilton), exactly as pre-registered in
    `nfl/research/r2/predeclaration_qb_level_ownership_r2.md` sha256
    3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c section 2.

    WHY THIS EXISTS. QB V1 draws its own level -- `DB = rint(V x S)` from the
    team-dropback pool and the share pool -- which is the quantity D1 and QB3
    already own. `run_game` reconciled the duplicate by dividing one level by
    the other, and dividing by a small draw is what produced composition
    factors up to 59.85 and a 49.14 passing-touchdown tail. R2 removes the
    duplicate rather than bounding the ratio.

    WHY LARGEST REMAINDER, AND WHY AFTER ALLOCATION. Integerising each
    quarterback independently (`rint(share_j x N_t)`) does not sum to `N_t`;
    the rounding residual is exactly the silent mass loss OWN-4 exists to
    prevent. Largest remainder gives the residual to the largest fractional
    parts and closes EXACTLY, by construction, in every draw. Nothing is
    fitted and no parameter is introduced.

    TIE-BREAK, DECLARED IN THE PRE-REGISTRATION AND NOT CHOSEN HERE: descending
    share, then gsis_id ascending. Deterministic, so the apportionment is
    reproducible across processes.

    `team_dropbacks` is (m,), `shares` is (n_qb, m) summing to 1 per draw,
    `pids` is the n_qb gsis ids in the same row order. Returns (n_qb, m) ints
    with column sums exactly rint(team_dropbacks).
    """
    N = np.maximum(np.rint(np.asarray(team_dropbacks, float)), 0).astype(np.int64)
    S = np.asarray(shares, float)
    if S.ndim != 2 or S.shape[1] != N.shape[0]:
        return Outcome.fail(
            'APPORTION_SHAPE_MISMATCH',
            f'shares {S.shape} against a team budget of {N.shape}; these must '
            f'agree on the draw axis')
    if len(pids) != S.shape[0]:
        return Outcome.fail(
            'APPORTION_PID_MISMATCH',
            f'{len(pids)} pid(s) for {S.shape[0]} share row(s)')
    if S.shape[0] == 0:
        return Outcome.fail(
            'APPORTION_NO_QUARTERBACK',
            'a team budget was supplied with no quarterback to receive it. '
            'Allocated mass may never be silently dropped, so this refuses '
            'rather than returning an empty apportionment.')
    neg = int((S < -1e-9).sum())
    if neg:
        return Outcome.fail('APPORTION_NEGATIVE_SHARE',
                            f'{neg} negative share cell(s)', n_negative=neg)
    # THE SHARES MUST ACCOUNT FOR THE WHOLE BUDGET BEFORE IT IS APPORTIONED.
    # If the rows supplied cover only part of the allocated share -- OWN-1's
    # `QB_ALLOCATION_SHARE_UNCONSUMED` leak, where the allocation names a
    # quarterback QB V1 never forecast -- then no apportionment of these rows
    # can close, and saying only "does not close" would hide a cause the
    # project already has a name and a fix for (C0).
    colsum = S.sum(0)
    deficit = 1.0 - colsum
    worst = float(np.max(np.abs(deficit)))
    if worst > 1e-6:
        j = int(np.argmax(np.abs(deficit)))
        return Outcome.fail(
            'APPORTION_SHARE_DOES_NOT_COVER_BUDGET',
            f'the supplied shares sum to {colsum[j]:.6f} in the worst draw, '
            f'not 1. {worst * 100:.4f}% of the team dropback budget is '
            f'allocated to a quarterback that is not among these rows, so no '
            f'apportionment of these rows can close. This is the OWN-1 '
            f'unconsumed-share leak surfacing as a hard failure instead of a '
            f'silent loss; the declared remedy is C0, and the mass is NOT '
            f'shared out among the survivors.',
            worst_share_deficit=round(worst, 8),
            worst_draw=j, n_qb=int(S.shape[0]),
            no_survivor_renormalisation=True)
    exact = S * N[None, :]
    base = np.floor(exact).astype(np.int64)
    rem = exact - base
    short = N - base.sum(0)
    # Order once: descending remainder, then the declared tie-break. A stable
    # sort over pre-sorted keys applies them in reverse priority order.
    out = base.copy()
    for j in range(N.shape[0]):
        k = int(short[j])
        if k <= 0:
            continue
        # Sorted by (-remainder, -share, pid): exactly the declared tie-break,
        # written so it cannot be misread.
        idx = sorted(range(S.shape[0]),
                     key=lambda i: (-rem[i, j], -S[i, j], str(pids[i])))
        for i in idx[:k]:
            out[i, j] += 1
    closes = bool(np.all(out.sum(0) == N))
    if not closes:
        worst = int(np.max(np.abs(out.sum(0) - N)))
        return Outcome.fail(
            'APPORTION_DOES_NOT_CLOSE',
            f'largest remainder failed to close; worst draw off by {worst}. '
            f'This is a construction, so a failure here is a defect in the '
            f'apportionment itself, never a tolerance to widen.', worst=worst)
    return Outcome.ok(
        'QB_DROPBACKS_APPORTIONED', value=out,
        detail=f'{S.shape[0]} quarterback(s) over {N.shape[0]} draw(s), '
               f'integer-exact in every draw',
        n_qb=int(S.shape[0]), n_draws=int(N.shape[0]),
        team_budget_mean=round(float(N.mean()), 4),
        closes_exactly=True, method='largest_remainder_hamilton',
        tie_break='descending share, then gsis_id ascending',
        nothing_fitted=True)
