"""J1 tests: the joint team-volume draw mode, and what it must not change."""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'j1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.production import team_volume_v1 as TV                    # noqa: E402

PASSED = FAILED = 0
TEAMS = ['KC', 'BUF', 'PHI', 'SF']
HIST_TC_DB = -0.393


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _draw(joint, m=1200, seed=20260908):
    TV.cache_clear()
    o = TV.forecast(2026, 1, TEAMS, m=m, seed=seed, joint_residuals=joint)
    assert o.state is State.PASS, o.code
    sim = collections.defaultdict(dict)
    for (met, t), v in o.value.items():
        sim[t][met] = np.asarray(v, float)
    return o, sim


def test_A_default_is_off():
    print('\nA. the default does not change')
    check('the module default is independent draws',
          TV.JOINT_RESIDUALS_DEFAULT is False)
    o, _ = _draw(None)
    check('  and forecast() with no argument uses it',
          o.evidence['draw_mode'] == 'independent_per_metric',
          o.evidence['draw_mode'])
    check('  switching it on is therefore an explicit act',
          _draw(True)[0].evidence['draw_mode'] == 'joint_residuals')


def test_B_the_coupling_is_recovered_only_in_joint_mode():
    print('\nB. the coupling')
    _, ind = _draw(False)
    _, jnt = _draw(True)
    ci = np.mean([np.corrcoef(ind[t]['team_carries'],
                              ind[t]['team_dropbacks_part'])[0, 1]
                  for t in TEAMS])
    cj = np.mean([np.corrcoef(jnt[t]['team_carries'],
                              jnt[t]['team_dropbacks_part'])[0, 1]
                  for t in TEAMS])
    check('independent draws reproduce essentially no coupling',
          abs(ci) < 0.10, ci)
    check(f'  joint draws reproduce the historical {HIST_TC_DB}',
          abs(cj - HIST_TC_DB) < 0.10, cj)
    check('  and the sign is right, which the independent mode cannot promise',
          cj < 0, cj)


def test_C_the_marginals_are_not_disturbed():
    print('\nC. no fit moves')
    _, ind = _draw(False, m=3000)
    _, jnt = _draw(True, m=3000)
    for met in TV.METRICS:
        a = np.mean([ind[t][met].mean() for t in TEAMS])
        b = np.mean([jnt[t][met].mean() for t in TEAMS])
        rel = abs(b - a) / max(abs(a), 1e-9)
        check(f'  {met}: mean within 3% ({a:.2f} vs {b:.2f})', rel < 0.03, rel)


def test_D_determinism_in_both_modes():
    print('\nD. draw semantics')
    for joint in (False, True):
        _, a = _draw(joint, m=300, seed=5)
        _, b = _draw(joint, m=300, seed=5)
        _, c = _draw(joint, m=300, seed=6)
        same = all(np.array_equal(a[t][m], b[t][m])
                   for t in TEAMS for m in TV.METRICS)
        diff = any(not np.array_equal(a[t][m], c[t][m])
                   for t in TEAMS for m in TV.METRICS)
        check(f'  joint={joint}: same seed reproduces exactly', same)
        check(f'  joint={joint}: a different seed does not', diff)


def test_E_the_cache_is_still_draw_equivalent_in_both_modes():
    """R2 proved the per-slate fit cache is draw-equivalent. That property must
    survive the new mode, so it is re-checked under both."""
    print('\nE. the R2 cache property survives')
    for joint in (False, True):
        TV.cache_clear()
        cold = TV.forecast(2026, 1, TEAMS, m=200, seed=11,
                           joint_residuals=joint)
        warm = TV.forecast(2026, 1, TEAMS, m=200, seed=11,
                           joint_residuals=joint)   # cache now populated
        same = all(np.array_equal(np.asarray(cold.value[k]),
                                  np.asarray(warm.value[k]))
                   for k in cold.value)
        check(f'  joint={joint}: cached and uncached draws are identical', same)


def test_F_recorded_j1_result():
    print('\nF. the recorded experiment')
    f = os.path.join(_ROOT, 'nfl', 'research', 'j1', 'j1_results.json')
    if not os.path.exists(f):
        check('j1_results.json exists', False, f)
        return
    r = json.load(open(f))
    check('the result cites its pre-registration',
          len(r.get('prereg_sha256', '')) == 64)
    check('  it is labelled EXPLORATORY', 'EXPLORATORY' in r['label'])
    check('  all four folds ran', len(r['evaluation_seasons_run']) == 4,
          r['evaluation_seasons_run'])
    check('  no fold was averaged in as a nan',
          all(np.isfinite(r['pooled'][a]['energy_score']) for a in r['arms']))
    c = r['contrasts']
    check('  A1 carve-QB-first does NOT meet the acceptance rule',
          not c['A1_carve_qb_first_minus_A0']['meets_acceptance_rule'])
    check('    because its interval includes zero',
          not c['A1_carve_qb_first_minus_A0']['ci_excludes_zero'])
    check('  A2 causal split does NOT meet it',
          not c['A2_causal_split_minus_A0']['meets_acceptance_rule'])
    check('    and one of its marginals breaches the 2% bound',
          not c['A2_causal_split_minus_A0']['no_marginal_worse_than_2pct'],
          c['A2_causal_split_minus_A0']['worst_marginal_crps_relative_change'])
    check('  A3 joint residual DOES meet every clause',
          c['A3_joint_residual_minus_A0']['meets_acceptance_rule'])
    a3, a0 = r['pooled']['A3_joint_residual'], r['pooled']['A0_control']
    check('  A3 recovers the coupling and A0 does not',
          a3['abs_corr_error_vs_historical'] < 0.05
          < a0['abs_corr_error_vs_historical'],
          (a3['mean_corr_tc_db'], a0['mean_corr_tc_db']))
    check('  A3 clips nothing while A0 clips', a3['inv_clipped_draws'] == 0.0
          and a0['inv_clipped_draws'] > 0.0)
    for iv in ('inv_components_sum_to_team_carries',
               'inv_qb_rush_within_team_carries'):
        check(f'  A3 violates {iv} never', a3[iv] == 0.0, a3[iv])


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
