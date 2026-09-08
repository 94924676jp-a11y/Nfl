"""Adversarial tests for the team/player accounting invariants.

THE POINT OF THIS LAYER is that a residual must be NAMED. A reconciliation
that clips, drops or silently absorbs a discrepancy is worse than none, because
it turns a measurable defect into an invisible one. These tests therefore spend
most of their effort proving the layer REFUSES things, not that it accepts them.
"""
import json, os, pathlib, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.accounting import invariants as I                        # noqa: E402
from nfl.tests.bypass import (assert_guard_is_load_bearing,       # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0
AUDIT = (pathlib.Path(__file__).parents[1] / 'accounting'
         / 'accounting_audit.json')


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  [{detail}]' if detail else ''))


def test_a_a_clean_balance_passes_and_a_dirty_one_does_not():
    print('\nA. the basic contract')
    ok = I.check('x', {('g1',): (10.0, 10.0, 0.0), ('g2',): (5.0, 5.0, 0.0)})
    check('a balanced set passes', ok.state is State.PASS, ok.code)
    bad = I.check('x', {('g1',): (10.0, 10.0, 0.0), ('g2',): (5.0, 4.0, 0.0)})
    check('a single unexplained residual FAILS the whole invariant',
          bad.state is State.FAIL, bad.code)
    check('  and it names the worst group rather than a count only',
          bad.evidence['worst'] == "('g2',)", bad.evidence.get('worst'))
    check('  and reports how many groups were bad',
          bad.evidence['n_bad'] == 1 and bad.evidence['n_groups'] == 2)


def test_b_cancellation_across_groups_is_caught():
    print('\nB. a positive residual cancelling a negative')
    # This is the error that survives an aggregate check: sum(lhs) == sum(rhs)
    # while both groups are individually wrong.
    res = {('g1',): (10.0, 8.0, 0.0), ('g2',): (5.0, 7.0, 0.0)}
    tot_l = sum(v[0] for v in res.values()); tot_r = sum(v[1] for v in res.values())
    check('the AGGREGATE balances exactly', abs(tot_l - tot_r) < 1e-12)
    o = I.check('x', res)
    check('  but the per-group check still FAILS, which is the point',
          o.state is State.FAIL and o.evidence['n_bad'] == 2, o.code)


def test_c_named_other_versus_silent_absorption():
    print('\nC. a residual may be NAMED, never absorbed')
    o = I.check('x', {('g',): (10.0, 9.0, 1.0)}, allow_named_other=True)
    check('a residual assigned to a declared OTHER bucket passes',
          o.state is State.PASS, o.code)
    check('  and the OTHER mass is reported, not hidden',
          o.value['named_other_total'] == 1.0)
    o2 = I.check('x', {('g',): (10.0, 9.0, 1.0)})
    check('the SAME data FAILS when no OTHER bucket was declared -- a bucket '
          'cannot appear just because it would make the sum work',
          o2.state is State.FAIL
          and o2.code.startswith('UNEXPECTED_OTHER_MASS'), o2.code)
    o3 = I.check('x', {('g',): (10.0, 8.0, 1.0)}, allow_named_other=True)
    check('  and a declared bucket does not excuse the part it does not '
          'explain', o3.state is State.FAIL, o3.code)


def test_d_ordering_invariants_do_not_clip():
    print('\nD. an ordering violation is reported, never clipped')
    o = I.le_check('recs_le_targets', {('p1',): (3, 5), ('p2',): (5, 5)})
    check('receptions <= targets holds', o.state is State.PASS, o.code)
    o2 = I.le_check('recs_le_targets', {('p1',): (6, 5)})
    check('6 receptions on 5 targets FAILS', o2.state is State.FAIL, o2.code)
    check('  and the offending group is named',
          "('p1',)" in str(o2.evidence['examples']))


def test_e_the_real_data_audit():
    print('\nE. the invariants measured on real 2020-2025 pbp')
    check('the audit artifact exists', AUDIT.exists(), str(AUDIT))
    a = json.loads(AUDIT.read_text())
    check(f"it covers {a['_n_team_games']} team-games over {a['_seasons']}",
          a['_n_team_games'] > 3000)
    exact = ['team_targets_eq_sum_player_targets',
             'team_receptions_eq_sum_player_receptions',
             'team_recv_yards_eq_sum_player_recv_yards',
             'team_carries_eq_sum_player_carries',
             'team_rush_td_eq_sum_player_rush_td',
             'team_pass_td_eq_sum_recv_td',
             'player_receptions_le_targets',
             'player_rz_targets_le_targets']
    for k in exact:
        check(f'  {k} holds exactly on real data',
              a[k]['state'] == 'PASS', a[k].get('code'))
    check('  team_pass_yards_eq_team_recv_yards does NOT hold, and the audit '
          'says so rather than tolerating it',
          a['team_pass_yards_eq_team_recv_yards']['state'] == 'FAIL')


def test_f_the_lateral_exception_is_measured_and_bounded():
    print('\nF. the one documented exception')
    e = I.LATERAL_EXCEPTION
    check('the exception is recorded with counts, not prose',
          e['n_violating'] == 76 and e['n_team_games'] == 3230)
    check(f"  {e['n_explained_by_lateral']} of {e['n_violating']} are laterals",
          e['n_explained_by_lateral'] == 75)
    check('  and the ONE unexplained case is kept visible, not swept into the '
          'lateral bucket',
          e['n_unexplained'] == 1
          and e['unexplained_example']['team'] == 'IND')
    check('  the arithmetic closes: explained + unexplained == violating',
          e['n_explained_by_lateral'] + e['n_unexplained'] == e['n_violating'])
    check('  and the policy forbids widening the exception to absorb it',
          'may never be widened' in e['policy'])


def test_g_guard_deletions():
    print('\nG. guard-deletion proofs')

    def run_unexplained():
        return I.check('x', {('g',): (10.0, 8.0, 0.0)})
    assert_guard_is_load_bearing(
        run=run_unexplained, module_path='nfl.accounting.invariants',
        attr='check',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value={'n_groups': 1, 'named_other_total': 0}))
    check('G1 invariants.check is load-bearing -- bypassed, a 2-unit '
          'unexplained residual reconciles silently', True)

    def run_ordering():
        return I.le_check('x', {('p',): (99, 1)})
    assert_guard_is_load_bearing(
        run=run_ordering, module_path='nfl.accounting.invariants',
        attr='le_check',
        caught=lambda o: o.state is State.FAIL,
        returns=Outcome.ok('STUB', value={'n_groups': 1}))
    check('G2 invariants.le_check is load-bearing -- bypassed, 99 receptions '
          'on 1 target passes', True)


if __name__ == '__main__':
    test_a_a_clean_balance_passes_and_a_dirty_one_does_not()
    test_b_cancellation_across_groups_is_caught()
    test_c_named_other_versus_silent_absorption()
    test_d_ordering_invariants_do_not_clip()
    test_e_the_real_data_audit()
    test_f_the_lateral_exception_is_measured_and_bounded()
    test_g_guard_deletions()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
