"""R8: per-team QB dropback closure, and the reliability-weighted appearance model.

Two families of check. The first proves that every team dropback belongs to
exactly one quarterback on that team and that the artifact says so. The second
proves that R8's regime moves with evidence rather than the calendar, and that
every refusal R7 introduced survives into it.
"""
from __future__ import annotations

import inspect
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import candidate_mode as CM                      # noqa: E402
from nfl.production import qb_accounting as QBACC                    # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7                  # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8                  # noqa: E402
from nfl.production.nonqb import layers as LY                        # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _rows(teams):
    return [{'season': 2026, 'week': 1, 'team': t, 'db': 0, 'gsis_id': g}
            for t, g in teams]


# ================================================== A. QB dropback closure
def test_the_residual_is_measured_not_asserted():
    """It used to be a hard-coded string in the return statement."""
    src = inspect.getsource(QBACC.reconcile_team)
    check('the closure warning is no longer an unconditional literal',
          "warnings=['sum of QB dropbacks does not equal team dropbacks" not in src)
    check('  and the function now takes a dropback budget',
          'team_dropback_draws' in
          inspect.signature(QBACC.reconcile_team).parameters)


def test_closure_holds_when_it_holds_and_is_reported_as_such():
    D = {'db': np.array([[10, 12], [7, 5], [20, 20], [1, 1]]),
         'rush_opp': np.zeros((4, 2))}
    rows = _rows([('SF', 'a'), ('SF', 'b'), ('LA', 'c'), ('LA', 'd')])
    o = QBACC.reconcile_team(
        D, rows,
        team_dropback_draws={'SF': np.array([17.0, 17.0]),
                             'LA': np.array([21.0, 21.0])},
        integer_level=True)
    c = (o.value or {}).get('per_team_dropback_closure') or {}
    check('an exactly-closing set is reported CLOSES',
          o.state is State.PASS and c.get('status') == 'CLOSES', str(c)[:200])
    check('  with the cell count, not just a word',
          c.get('draw_cells') == 4 and c.get('violating_cells') == 0, str(c))
    check('  and no warning is raised', not (o.evidence.get('warnings') or []))


def test_a_real_shortfall_is_caught():
    """THE GUARD. If this stops failing, the closure test has stopped testing."""
    D = {'db': np.array([[10, 12], [7, 5], [20, 20], [1, 1]]),
         'rush_opp': np.zeros((4, 2))}
    rows = _rows([('SF', 'a'), ('SF', 'b'), ('LA', 'c'), ('LA', 'd')])
    o = QBACC.reconcile_team(
        D, rows,
        team_dropback_draws={'SF': np.array([18.0, 17.0]),   # SF is one short
                             'LA': np.array([21.0, 21.0])},
        integer_level=True)
    c = (o.value or {}).get('per_team_dropback_closure') or {}
    check('a one-dropback shortfall is caught',
          c.get('status') == 'DOES_NOT_CLOSE', str(c)[:200])
    check('  exactly one cell violates', c.get('violating_cells') == 1, str(c))
    check('  and the warning is raised',
          bool(o.evidence.get('warnings')), str(o.evidence.get('warnings')))


def test_cross_team_compensation_can_never_hide_a_defect():
    """SF over by one and LA under by one must NOT net to zero."""
    D = {'db': np.array([[18, 18], [20, 20]]), 'rush_opp': np.zeros((2, 2))}
    rows = _rows([('SF', 'a'), ('LA', 'b')])
    o = QBACC.reconcile_team(
        D, rows,
        team_dropback_draws={'SF': np.array([17.0, 17.0]),
                             'LA': np.array([21.0, 21.0])},
        integer_level=True)
    c = (o.value or {}).get('per_team_dropback_closure') or {}
    check('a matched surplus and shortfall still fail',
          c.get('status') == 'DOES_NOT_CLOSE', str(c)[:200])
    check('  and both teams are counted as violating',
          c.get('violating_cells') == 4, str(c.get('violating_cells')))
    tot = sum(v['qb_sum_mean'] for v in (c.get('per_team') or {}).values())
    check('  even though the GAME total is exactly right', abs(tot - 38.0) < 1e-9,
          str(tot))


def test_a_missing_budget_refuses_rather_than_checking_nothing():
    D = {'db': np.array([[10, 12], [20, 20]]), 'rush_opp': np.zeros((2, 2))}
    rows = _rows([('SF', 'a'), ('LA', 'b')])
    o = QBACC.reconcile_team(D, rows,
                             team_dropback_draws={'SF': np.array([10.0, 12.0])},
                             integer_level=True)
    check('a team with no budget is a named refusal',
          o.state is State.FAIL and
          o.code == 'QB_TEAM_DROPBACK_BUDGET_KEY_MISMATCH',
          f'{o.state}[{o.code}]')


def test_no_budget_at_all_is_not_a_pass():
    D = {'db': np.array([[10, 12]]), 'rush_opp': np.zeros((1, 2))}
    o = QBACC.reconcile_team(D, _rows([('SF', 'a')]))
    c = (o.value or {}).get('per_team_dropback_closure') or {}
    check('closure without a budget is NOT_MEASURED, not CLOSES',
          c.get('status') == 'NOT_MEASURED', str(c)[:160])


def test_apportionment_still_closes_by_construction():
    N = np.array([17, 21, 30], float)
    S = np.array([[0.6, 0.5, 0.34], [0.4, 0.5, 0.66]])
    o = QBACC.apportion_dropbacks(N, S, ['a', 'b'])
    check('largest remainder closes exactly', o.state is State.PASS, o.code)
    if o.state is State.PASS:
        check('  in every draw', bool(np.all(o.value.sum(0) == np.rint(N))),
              str(o.value.sum(0)))


def test_shares_that_do_not_cover_the_budget_are_refused():
    o = QBACC.apportion_dropbacks(np.array([17.0]), np.array([[0.6], [0.3]]),
                                  ['a', 'b'])
    check('an uncovered budget refuses rather than renormalising',
          o.state is State.FAIL and
          o.code == 'APPORTION_SHARE_DOES_NOT_COVER_BUDGET', o.code)


# ============================================ B. the synthesis
def test_r8_inherits_r6_and_supersedes_r7():
    r7 = CM.resolve(CM.V1_CANDIDATE_R7).value['flags']
    r8 = CM.resolve(CM.V1_CANDIDATE_R8).value['flags']
    check('R8 does not also carry the R7 mechanism',
          'appearance_r7' not in r8, str(r8))
    check('  and names its own', r8.get('appearance_r8') is True)
    for k, v in r7.items():
        if k == 'appearance_r7':
            continue
        check(f'  R8 keeps {k}', r8.get(k) == v, f'{k}={r8.get(k)}')
    for mode in (CM.V1_CANDIDATE, CM.V1_CANDIDATE_R5, CM.V1_CANDIDATE_R6,
                 CM.V1_CANDIDATE_R7):
        check(f'  {mode} does not carry appearance_r8',
              'appearance_r8' not in CM.resolve(mode).value['flags'])
    check('  R8 declares it introduces no constant',
          CM.R8_REPAIR.get('introduces_no_constant') is True)
    check('  and that no week number is in the design',
          CM.R8_REPAIR.get('no_week_number_in_the_design') is True)


def test_the_design_contains_no_week_number():
    """The whole hypothesis: the regime moves with evidence, not the calendar."""
    a = {'w': 1, 'pos': 'WR', 'rank': 1, 'n_cur': 4, 'n_prior': 20,
         'crossed': False, 'cm_within': 0, 'cm_carried': 0, 'app_cur': 0.8,
         'app_ewma': 0.8, 'app_ewma_cur': 0.8, 'rate3_cur': 0.8,
         'snap_ewma_cur': 0.5, 'prev_appeared': 1, 'inj_available': 0,
         'v1': None}
    b = dict(a)
    b['w'] = 14                       # week 14 instead of week 1
    xa, xb = R8.featurise(a, 1.2), R8.featurise(b, 1.2)
    # R7's own week-1 indicator is the one calendar column, and it is there
    # because the season boundary must stay explicitly represented (owner
    # directive C). Everything else must be invariant to the week number.
    diff = [i for i, (p, q) in enumerate(zip(xa, xb)) if p != q]
    check('changing only the week number moves at most the week-1 indicator',
          len(diff) <= 1, f'{len(diff)} column(s) moved: {diff}')
    c = dict(a)
    c['n_cur'] = 0
    xc = R8.featurise(c, 1.2)
    check('  while changing the EVIDENCE COUNT moves many columns',
          sum(1 for p, q in zip(xa, xc) if p != q) >= 5)


def test_the_reliability_weight_is_estimated_not_chosen():
    fr = R8.enriched_frame()
    if not check('the enriched frame builds', fr.state is State.PASS, fr.code):
        return
    k = R8.reliability_k(fr.value)
    check('k is estimated', k.state is State.PASS, k.code)
    if k.state is not State.PASS:
        return
    e = k.evidence
    # The evidence stores each quantity rounded to six places, so the ratio of
    # the stored pair matches the unrounded constant only to about 1e-5. The
    # tolerance is an arithmetic allowance for that rounding, not a modelling
    # one -- the check is that k IS the ratio, not that it is near it.
    check('  from a within/between variance ratio',
          abs(e['within_player_variance'] / e['between_player_variance']
              - k.value) < 1e-4, str(e))
    check('  over a stated number of player-seasons',
          e['n_player_seasons'] > 1000, str(e['n_player_seasons']))
    check('  and it is declared as estimated', e['estimated_not_chosen'] is True)


def test_the_weight_moves_from_zero_to_one_with_evidence():
    k = 1.2176
    check('no current-season evidence gives weight 0',
          R8.weight(0, k) == 0.0)
    check('  one game gives about 0.45',
          abs(R8.weight(1, k) - 1 / (1 + k)) < 1e-12)
    check('  and it is monotone in n',
          all(R8.weight(n, k) < R8.weight(n + 1, k) for n in range(0, 15)))
    check('  approaching but never reaching 1',
          R8.weight(200, k) < 1.0 and R8.weight(200, k) > 0.99)


def test_k_is_not_estimated_from_the_forecast_season():
    fr = R8.enriched_frame()
    if fr.state is not State.PASS:
        return
    a = R8.reliability_k(fr.value, cut=2024 * 100)
    b = R8.reliability_k(fr.value, cut=2026 * 100)
    check('a cut is honoured', a.state is State.PASS and b.state is State.PASS)
    if a.state is State.PASS and b.state is State.PASS:
        check('  and an earlier cut sees fewer player-seasons',
              a.evidence['n_player_seasons'] <
              b.evidence['n_player_seasons'],
              f"{a.evidence['n_player_seasons']} vs "
              f"{b.evidence['n_player_seasons']}")


def test_this_games_snap_share_is_not_a_feature():
    """It was, for one run, and scored an in-sample Brier of 0.041."""
    base = {'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3, 'n_prior': 10,
            'crossed': False, 'cm_within': 0, 'cm_carried': 0, 'v1': None}
    a = R8.featurise({**base, 'snap': 0.9}, 1.2)
    b = R8.featurise({**base, 'snap': None}, 1.2)
    check('the current row\'s snap share does not reach the design', a == b)


def test_every_r7_refusal_survives_into_r8():
    check('the unsupported cell is the same one',
          R8.UNSUPPORTED_CELL == R7.UNSUPPORTED_CELL)
    check('  and is still detected',
          R8.is_unsupported({'n_prior': 0, 'rank': None}) and
          not R8.is_unsupported({'n_prior': 0, 'rank': 2}))
    check('  the three states are still distinct',
          len({R8.KNOWN_HEALTHY, R8.NO_HISTORY, R8.UNKNOWN_STATUS}) == 3)
    check('  no history is still NO_HISTORY',
          R8.state_of({'n_prior': 0, 'rank': 1, 'inj_available': 1})
          == R8.NO_HISTORY)
    f = R8.fit(2026)
    if check('the R8 fit runs', f.state is State.PASS, f.code):
        check('  and still drops the degenerate cell',
              f.evidence.get('n_dropped_unsupported_cell', 0) > 0,
              str(f.evidence.get('n_dropped_unsupported_cell')))
        check('  training stops strictly before the forecast season',
              max(f.evidence['train_seasons']) < 2026,
              str(f.evidence['train_seasons']))
    o = R8.predict(2026, 1, [{'gsis_id': 'x', 'position': 'WR', 'team': 'SF'}],
                   [], observed_before=None, kickoff_utc=None)
    check('  and a prediction with no clock still refuses',
          o.state is State.FAIL and o.code == 'R8_NO_CLOCK',
          f'{o.state}[{o.code}]')


def test_the_season_boundary_is_still_explicitly_represented():
    a = {'w': 1, 'pos': 'WR', 'rank': 1, 'n_cur': 0, 'n_prior': 20,
         'crossed': True, 'cm_within': 0, 'cm_carried': 2, 'v1': None}
    b = dict(a)
    b['cm_carried'] = 0
    check('the carried streak still has its own column',
          R8.featurise(a, 1.2) != R8.featurise(b, 1.2))
    c = dict(a)
    c['crossed'] = False
    check('  and so does the crossing itself',
          R8.featurise(a, 1.2) != R8.featurise(c, 1.2))


def test_two_appearance_mechanisms_at_once_are_refused():
    import nfl.production.run_forecast as RF
    src = inspect.getsource(RF.build)
    check('run_forecast refuses an ambiguous appearance spec',
          'APPEARANCE_SPEC_AMBIGUOUS' in src)
    o = LY._run_real(2026, 1, [], [], 20260908, 4, test_only=True,
                     appearance_spec='not-a-mechanism')
    check('  and an unknown one is still a named FAIL',
          o.state is State.FAIL and o.code == 'APPEARANCE_SPEC_UNKNOWN',
          f'{o.state}[{o.code}]')
    check('  while the default is still the frozen mechanism',
          inspect.signature(LY.appearance)
          .parameters['appearance_spec'].default == 'frozen')


def test_the_frozen_prospective_walk_is_shared_not_copied():
    from nfl.production.nonqb import appearance_model as AM
    check('appearance_model exposes the prospective rows',
          hasattr(AM, 'prospective_feature_rows'))
    src = inspect.getsource(AM.predict)
    check('  and predict consumes them rather than recomputing',
          '_prospective(' in src and 'F.featurise_p3' in src)
    r8src = inspect.getsource(R8.predict)
    check('  and R8 calls it rather than restating the walk',
          'prospective_feature_rows' in r8src)


def test_no_player_or_team_is_hard_coded():
    src = open(os.path.join(_ROOT,
                            'nfl/production/nonqb/appearance_r8.py')).read()
    for bad in ('Nacua', 'McCaffrey', 'Kittle', 'Adams', 'Purdy', 'Stafford',
                "'SF'", "'LA'"):
        check(f'  no hard-coded {bad}', bad not in src, bad)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
