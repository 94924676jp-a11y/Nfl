"""B4's iteration: converges on a season, fails on a week, and says which.

FOUR CLAIMS, EACH TESTED SEPARATELY, because B4 is the decisive comparator's
engine and its failure mode was silent until it was measured.

WHAT WENT WRONG. B4 was declared with an `n_passes` hyperparameter and fixed
Jacobi iteration. On a design where each unit faces exactly one opponent the
iteration OSCILLATES WITH PERIOD 2 -- it flips between giving all the credit
to the offence and all of it to the defence -- so `n_passes` selects between
two arbitrary answers rather than tuning anything. Measured on a synthetic
one-week frame: max |off| is 0.0000 at 1, 3 and 5 passes and 0.9000 at 2 and
4. On the full 2025 pass frame it converges properly, the iterate-to-iterate
change decaying 0.01362, 0.00880, 0.00191, 0.00189, 0.00039 and reaching
0.00004 by the eleventh pass.

The estimator now iterates to a tolerance and reports convergence. `n_passes`
is gone, and B4 carries no hyperparameter at all.
"""
from __future__ import annotations

import glob
import hashlib
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                     # noqa: E402
from nfl.research.oas1 import baselines as BL                           # noqa: E402
from nfl.research.oas1 import frame as FR                               # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _one_week(n_pairs=8, per=30):
    """Each club faces exactly one opponent: the disconnected design."""
    teams = [f'T{i:02d}' for i in range(2 * n_pairs)]
    rows = []
    for k in range(0, 2 * n_pairs, 2):
        for o, d in ((teams[k], teams[k + 1]), (teams[k + 1], teams[k])):
            for _ in range(per):
                rows.append({'offense_team': o, 'defense_team': d,
                             'epa': 0.3 * (k + 1)})
    return rows


def _round_robin(n=8, per=12, seed=3):
    rng = np.random.default_rng(seed)
    teams = [f'T{i:02d}' for i in range(n)]
    rows = []
    for i, o in enumerate(teams):
        for j, d in enumerate(teams):
            if i == j:
                continue
            for _ in range(per):
                rows.append({'offense_team': o, 'defense_team': d,
                             'epa': float(0.10 * i - 0.05 * j
                                          + rng.normal(0, 0.4))})
    return rows


def test_A_a_full_season_converges():
    print('\nA. a connected schedule converges')
    b = sorted(glob.glob(os.path.join(_ROOT,
                                      'nfl/vintage/pbp_2025.*.csv.gz')))
    if not b:
        NOT_EXECUTED.append('A: no 2025 capture')
        print('  NOT_EXECUTED: no 2025 pbp capture')
        return
    p = pathlib.Path(b[-1])
    fr = FR.build(p, vintage_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    check('the 2025 frame builds', fr.state is State.PASS,
          f'{fr.state}[{fr.code}]')
    if fr.state is not State.PASS:
        NOT_EXECUTED.append('A: frame refused')
        return
    for cls in ('pass', 'rush'):
        kept = [r for r in fr.value['kept'] if r['play_class'] == cls]
        mu = float(np.mean([r['epa'] for r in kept]))
        off, dfn, info = BL._b4(kept, mu)
        check(f'{cls}: the full season CONVERGES', info['converged'] is True,
              str({k: info[k] for k in ('converged', 'n_iter',
                                        'final_change')}))
        check(f'  within the iteration cap ({BL.B4_MAX_ITER})',
              info['n_iter'] < BL.B4_MAX_ITER, str(info['n_iter']))
        check(f'  to below the declared tolerance {BL.B4_TOL:g}',
              info['final_change'] < BL.B4_TOL, str(info['final_change']))
        check('  and it used the converged iterate, not a fallback',
              info['used'] == 'CONVERGED_ITERATE', info['used'])
        check('  the change trace shrinks rather than flipping',
              info['change_trace'][-1] < info['change_trace'][0],
              str(info['change_trace'][:4]))
        check('  and the result is a real adjustment, not zero',
              max(abs(v) for v in off.values()) > 0.01,
              str(max(abs(v) for v in off.values())))


def test_B_a_one_week_design_fails_to_converge():
    print('\nB. a disconnected week does NOT converge')
    rows = _one_week()
    mu = float(np.mean([r['epa'] for r in rows]))
    off, dfn, info = BL._b4(rows, mu)
    check('it does NOT converge', info['converged'] is False,
          str({k: info[k] for k in ('converged', 'n_iter')}))
    check('  it exhausted the iteration cap rather than settling',
          info['n_iter'] == BL.B4_MAX_ITER, str(info['n_iter']))
    check('  and the change never shrank -- it is oscillating, not slow',
          abs(info['change_trace'][-1] - info['change_trace'][0]) < 1e-9,
          str(info['change_trace'][:4]))
    # The oscillation itself, demonstrated: alternate iterates differ.
    tr = info['change_trace']
    check('  the trace is flat at a nonzero value, the signature of a '
          'period-2 flip rather than convergence',
          len(tr) > 2 and tr[0] > 1e-3 and abs(tr[1] - tr[0]) < 1e-9,
          str(tr[:4]))


def test_C_non_convergence_invokes_the_declared_fallback():
    print('\nC. the fallback is the declared single pass, and it is zero here')
    rows = _one_week()
    mu = float(np.mean([r['epa'] for r in rows]))
    off, dfn, info = BL._b4(rows, mu)
    check('the fallback is the DECLARED one',
          info['used'] == 'SINGLE_PASS_FALLBACK', info['used'])
    check('  and it names why', 'oscillating' in (info.get('why') or ''),
          (info.get('why') or '')[:70])
    check('  the single-pass estimate is ZERO for every offensive unit -- '
          'the identification collapse, arithmetically',
          max(abs(v) for v in off.values()) < 1e-9,
          f'max |off| {max(abs(v) for v in off.values()):.3e}')
    check('  and zero for every defensive unit',
          max(abs(v) for v in dfn.values()) < 1e-9,
          f'max |def| {max(abs(v) for v in dfn.values()):.3e}')
    check('  which matches the declared spec text for non-convergence',
          'SINGLE-PASS' in BL.SPECS['B4']['non_convergence'].upper(),
          BL.SPECS['B4']['non_convergence'][:70])
    check('B4 carries NO hyperparameter, so no tuner can pick an iterate',
          BL.GRIDS['B4'] == {}, str(BL.GRIDS['B4']))
    check('  and `n_passes` is gone from the shrink directions',
          'n_passes' not in BL.SHRINK_DIRECTION,
          str(sorted(BL.SHRINK_DIRECTION)))


def test_D_fallback_use_is_surfaced_in_evaluation_metadata():
    print('\nD. a reader of the evaluation can see the fallback fired')
    rows = _one_week()
    test = [{**r, 'offense_is_home': True, 'season': 2026, 'week': 2,
             'ordinal': 202602, 'game_id': 'gX', 'play_id': i}
            for i, r in enumerate(rows[:20])]
    hist = [{**r, 'offense_is_home': True, 'season': 2026, 'week': 1,
             'ordinal': 202601, 'game_id': f'g{i // 30}', 'play_id': 1000 + i}
            for i, r in enumerate(rows)]
    for name in ('B4', 'B5'):
        cfg = {} if name == 'B4' else {'kappa': 0.5, 'rho': 0.85}
        p = BL.predict(name, hist, test, cfg)
        check(f'{name} predicts', p.state is State.PASS, f'{p.state}[{p.code}]')
        if p.state is not State.PASS:
            continue
        fb = p.evidence['fallbacks']
        check(f'  {name} carries the b4 convergence block in its evidence',
              isinstance(fb.get('b4'), dict), str(sorted(fb)))
        check(f'  and it records converged=False',
              fb['b4']['converged'] is False, str(fb['b4'].get('converged')))
        check(f'  and names the fallback used',
              fb['b4']['used'] == 'SINGLE_PASS_FALLBACK',
              str(fb['b4'].get('used')))
    # And on a converging design it says so.
    conn = _round_robin()
    ch = [{**r, 'offense_is_home': True, 'season': 2026, 'week': 1,
           'ordinal': 202601, 'game_id': f'g{i // 12}', 'play_id': i}
          for i, r in enumerate(conn)]
    ct = [{**r, 'ordinal': 202602, 'week': 2, 'season': 2026,
           'game_id': 'gY', 'play_id': 99000 + i}
          for i, r in enumerate(conn[:20])]
    p = BL.predict('B4', ch, ct, {})
    check('on a CONNECTED design the same metadata reports convergence',
          p.state is State.PASS
          and p.evidence['fallbacks']['b4']['converged'] is True,
          str(p.evidence['fallbacks'].get('b4')))
    check('  and names the converged iterate as what was used',
          p.evidence['fallbacks']['b4']['used'] == 'CONVERGED_ITERATE',
          str(p.evidence['fallbacks']['b4'].get('used')))


def test_E_b1_fallbacks_stay_counted_and_visible():
    print('\nE. B1`s cold-start fallback is counted, never silent')
    conn = _round_robin()
    hist = [{**r, 'offense_is_home': True, 'season': 2026, 'week': 1,
             'ordinal': 202601, 'game_id': f'g{i // 12}', 'play_id': i}
            for i, r in enumerate(conn)]
    test = [{**r, 'ordinal': 202602, 'week': 2, 'season': 2026,
             'game_id': 'gZ', 'play_id': 50000 + i}
            for i, r in enumerate(conn[:40])]
    # No 2025 rows in hist, so every B1 lookup must fall back and SAY SO.
    p = BL.predict('B1', hist, test, {'rho': 0.85})
    check('B1 predicts', p.state is State.PASS, f'{p.state}[{p.code}]')
    n = p.evidence['fallbacks']['to_B0']
    check('  every unit lookup with no prior season is COUNTED',
          n == 2 * len(test), f'{n} against {2 * len(test)} lookups')
    check('  and the prediction is the league mean, which is what that means',
          float(np.std(p.value)) < 1e-12, str(float(np.std(p.value))))
    check('  so a silent cold start is impossible to miss in the evidence',
          'to_B0' in p.evidence['fallbacks'],
          str(sorted(p.evidence['fallbacks'])))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_full_season_converges,
               test_B_a_one_week_design_fails_to_converge,
               test_C_non_convergence_invokes_the_declared_fallback,
               test_D_fallback_use_is_surfaced_in_evaluation_metadata,
               test_E_b1_fallbacks_stay_counted_and_visible):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
