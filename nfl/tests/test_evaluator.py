"""The evaluator must SCORE, must REFUSE, and must never return a verdict.

Every check here is behavioural. A scoring module that returns a plausible
number for nonsense input is worse than no scoring module, because it makes a
comparison look like it happened.
"""
from __future__ import annotations

import ast
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.production import evaluator as EV                           # noqa: E402

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


def test_A_the_scores_are_the_scores():
    print('\nA. Brier and log loss against values computed by hand')
    y = np.array([1., 0., 1., 0.])
    p = np.array([0.8, 0.1, 0.6, 0.4])
    want_b = float(((p - y) ** 2).mean())
    check('Brier matches the definition', abs(EV.brier(y, p) - want_b) < 1e-12,
          f'{EV.brier(y, p)} vs {want_b}')
    ll, nclip = EV.log_loss(y, p)
    want_l = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    check('  log loss matches the definition', abs(ll - want_l) < 1e-12,
          f'{ll} vs {want_l}')
    check('  and reports 0 clipped rows when nothing was clipped', nclip == 0,
          str(nclip))
    # A PERFECT AND A WORST-CASE FORECAST, so the scale is anchored.
    check('  a perfect forecast scores Brier 0',
          EV.brier(y, y) == 0.0, str(EV.brier(y, y)))
    check('  a maximally wrong forecast scores Brier 1',
          EV.brier(y, 1 - y) == 1.0, str(EV.brier(y, 1 - y)))
    ll2, n2 = EV.log_loss(np.array([1.0]), np.array([0.0]))
    check('  a confident miss is CLIPPED and the clip is COUNTED',
          n2 == 1 and np.isfinite(ll2), f'{ll2}, clipped {n2}')


def test_B_it_refuses_rather_than_returning_a_number():
    print('\nB. every refusal is NAMED, and none returns 0.0 or nan')
    for args, code in (
            ((np.array([]), np.array([])), 'EVALUATOR_EMPTY'),
            ((np.array([1., 0.]), np.array([0.5])),
             'EVALUATOR_LENGTH_MISMATCH'),
            ((np.array([1., 0.]), np.array([0.5, 1.4])),
             'EVALUATOR_PROBABILITY_OUT_OF_RANGE'),
            ((np.array([1., 0.]), np.array([0.5, np.nan])),
             'EVALUATOR_NON_FINITE_PREDICTION'),
            ((np.array([1., 2.]), np.array([0.5, 0.5])),
             'EVALUATOR_OUTCOME_NOT_BINARY')):
        try:
            EV.brier(*args)
            check(f'{code} is raised', False, 'returned a number instead')
        except EV.EvaluatorError as e:
            check(f'{code} is raised', str(e).split(':')[0] == code, str(e)[:70])
    try:
        EV.clustered_delta(EV.SCORERS['brier'], np.array([1., 0.]),
                           np.array([.5, .5]), np.array([.5, .5]),
                           np.array(['g', 'g']))
        check('a one-cluster bootstrap is refused', False, 'returned an interval')
    except EV.EvaluatorError as e:
        check('a one-cluster bootstrap is refused',
              'TOO_FEW_CLUSTERS' in str(e), str(e)[:70])


def test_C_clustering_is_required_and_widens_the_interval():
    print('\nC. clustering is not optional, and it is not cosmetic')
    src = open(EV.__file__).read()
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == 'clustered_delta')
    args = [a.arg for a in fn.args.args]
    n_default = len(fn.args.defaults)
    required = args[:len(args) - n_default]
    check('`clusters` is a REQUIRED argument, not a keyword with a default',
          'clusters' in required, f'required: {required}')
    # BEHAVIOURAL: correlated rows inside a cluster must widen the interval
    # against pretending every row is its own cluster.
    rng = np.random.default_rng(4)
    g = np.repeat(np.arange(60), 8)
    eff = rng.standard_normal(60)[g] * 0.8
    y = (rng.random(g.size) < 1 / (1 + np.exp(-eff))).astype(float)
    a = np.clip(0.5 + 0.2 * eff, .01, .99)
    b = np.full(g.size, 0.5)
    wide = EV.clustered_delta(EV.SCORERS['brier'], y, a, b, g, r=400)
    narrow = EV.clustered_delta(EV.SCORERS['brier'], y, a, b,
                                np.arange(g.size), r=400)
    w = wide['ci95_clustered'][1] - wide['ci95_clustered'][0]
    n = narrow['ci95_clustered'][1] - narrow['ci95_clustered'][0]
    check('  clustering by the real group gives a WIDER interval than iid',
          w > n, f'clustered width {w:.5f} vs iid {n:.5f}')
    print(f'       clustered {w:.5f}   iid {n:.5f}   ratio {w / n:.2f}x')


def test_D_coverage_and_sharpness_are_reported_together():
    print('\nD. coverage alone is not calibration')
    rng = np.random.default_rng(11)
    D = rng.standard_normal((300, 4000))
    y = rng.standard_normal(300)
    cov = EV.interval_coverage(D, y)
    shp = EV.sharpness(D)
    check('every declared level is covered', set(cov) == set(EV.LEVELS),
          str(sorted(cov)))
    for lv in EV.LEVELS:
        e = cov[lv]['empirical']
        check(f'  {lv:.2f} nominal -> {e:.3f} empirical, within 0.06',
              abs(e - lv) < 0.06, f'{e}')
    check('sharpness needs NO outcome and is reported at the same levels',
          set(shp) == set(EV.LEVELS), str(sorted(shp)))
    check('  and widths increase with the level',
          all(shp[a]['mean_width'] < shp[b]['mean_width']
              for a, b in zip(EV.LEVELS, EV.LEVELS[1:])),
          str({k: round(v['mean_width'], 3) for k, v in shp.items()}))
    # A USELESSLY WIDE MODEL REACHES NOMINAL COVERAGE. This is the whole
    # reason sharpness is here and it is asserted, not assumed.
    fat = EV.interval_coverage(D * 8, y)
    check('  a 8x-too-wide model still covers >= nominal at every level',
          all(fat[lv]['empirical'] >= lv for lv in EV.LEVELS),
          str({k: round(v['empirical'], 3) for k, v in fat.items()}))
    check('  and sharpness is what exposes it',
          EV.sharpness(D * 8)[0.9]['mean_width']
          > 4 * shp[0.9]['mean_width'])


def test_E_the_baseline_comparison_returns_no_verdict():
    print('\nE. it measures against a baseline and stops there')
    rng = np.random.default_rng(7)
    n = 500
    g = rng.integers(0, 90, n)
    y = (rng.random(n) < 0.3).astype(float)
    pm = np.clip(0.3 + 0.25 * (y - 0.3) + 0.05 * rng.standard_normal(n),
                 .01, .99)
    pb = np.full(n, 0.3)
    o = EV.against_baseline(y, pm, pb, g, 'constant')
    check('it returns a PASS Outcome with both arms scored',
          o.state is State.PASS and 'model' in o.value and 'baseline' in o.value,
          f'{o.state}[{o.code}]')
    check('  the no-skill constant reference is reported beside them',
          abs(o.evidence['constant_brier']
              - o.evidence['base_rate'] * (1 - o.evidence['base_rate'])) < 1e-9)
    check('  both deltas carry a CLUSTERED interval',
          o.evidence['brier']['cluster_bootstrap']
          and o.evidence['log_loss']['cluster_bootstrap'])
    # STRUCTURAL, NOT A WORD SEARCH. My first version grepped the evidence for
    # 'verdict' and failed on the module's own governance line, which says a
    # verdict is NOT returned. Searching prose for a word cannot tell a claim
    # from its disclaimer. The property is that no field ADJUDICATES: no key
    # names a pass/fail, and every number is a score, an interval or a count.
    keys = set(o.evidence) | set(o.value)
    judging = {k for k in keys if any(w in k.lower() for w in (
        'pass', 'fail', 'verdict', 'promote', 'accept', 'reject', 'clears',
        'threshold'))}
    check('  no evidence key adjudicates -- they are scores, intervals, counts',
          not judging, f'adjudicating keys: {sorted(judging)}')
    check('  and no threshold constant is applied to produce a boolean',
          not any(isinstance(v, bool) and k not in ('cluster_bootstrap',)
                  for k, v in o.evidence.items()),
          str({k: v for k, v in o.evidence.items() if isinstance(v, bool)}))
    bad = EV.against_baseline(np.array([]), np.array([]), np.array([]),
                              np.array([]))
    check('  an empty comparison is BLOCKED, never scored 0.0',
          bad.state is State.BLOCKED, f'{bad.state}[{bad.code}]')


def test_F_the_baseline_family_it_scores_against_exists():
    print('\nF. the baselines are the ones already in the tree, not new ones')
    try:
        from nfl.research.baselines import estimators as B
    except ImportError as e:
        check('nfl.research.baselines.estimators imports', False, repr(e))
        return
    have = [n for n in ('prior', 'in_season', 'season_to_date', 'recent_n',
                        'ewma', 'shrunk', 'role_average', 'league_prior')
            if hasattr(B, n)]
    check(f'{len(have)} declared baseline estimator(s) are importable',
          len(have) >= 6, str(have))
    print(f'       {have}')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_scores_are_the_scores,
               test_B_it_refuses_rather_than_returning_a_number,
               test_C_clustering_is_required_and_widens_the_interval,
               test_D_coverage_and_sharpness_are_reported_together,
               test_E_the_baseline_comparison_returns_no_verdict,
               test_F_the_baseline_family_it_scores_against_exists):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    raise SystemExit(1 if FAILED else 0)
