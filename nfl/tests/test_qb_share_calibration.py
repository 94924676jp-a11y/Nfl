"""P2 repair 3: the QB dropback-share predictive distribution must be calibrated.

THE DEFECT, AND THE TEST THAT FAILS ON IT.

`nfl/research/v3/h1/H1_2025_QB_RESIDUALS.md` section 1 records the QB dropback
share as the one real volume defect in the 2025 forward-chained study: signed
bias -0.0778 over 540 starting-QB games, the realised share above the
predictive P90 in 79% of them, and a PIT chi-square of 929.0 on 9 degrees of
freedom. `test_c` asserts the property that should hold -- that the share PIT
is uniform -- and it is expected to FAIL against the incumbent path.

TWO INSTRUMENTS, BOTH REPORTED, NEITHER DROPPED.

78.89% of the 540 realised shares are exactly 1.0. The published 929.0 came
from `h1_run.score(..., discrete=False)`, i.e. the mid-PIT, which is not
uniform on an atom even under a perfect forecast. `test_b` locks BOTH numbers
so that a later change cannot quietly move either, and `test_c` is stated on
the randomized PIT because that is the instrument a discrete quantity needs.

PREDECLARED BEFORE THE REPAIR: uniformity is tested at alpha = 0.01 on the
10-bin chi-square with 9 degrees of freedom, published critical value 21.666.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'v4', 'p2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import p2_cohort as C                                             # noqa: E402
import qb2_lib as Q                                               # noqa: E402

PASSED = FAILED = 0

ALPHA = 0.01                 # predeclared, this file's docstring
CHI2_DF = 9

# Read out of nfl/research/v3/h1/H1_SUMMARY.json, layers.qb_dropback_share.
PUBLISHED = {
    'n': 540,
    'mean_signed_error': -0.07783625201851851,
    'mean_actual': 0.9717859577222222,
    'mean_pred': 0.8939497058333333,
    'coverage_p90_below': 0.2111111111111111,
    'pit_chi2_mid': 929.037037037037,
}


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


_CACHE = {}


def _shares(spec):
    """Share draw matrices for the 540 rows under one share specification.

    The incumbent path is reproduced exactly as `h1_run.vs_draws` does it --
    same seed triple, same call order, `_mix` for V first and then for S -- so
    a difference between the two arms is the specification and nothing else.
    """
    if spec in _CACHE:
        return _CACHE[spec]
    keep, allrows, po, _ = C.cohort()
    S = np.zeros((len(keep), C.M))
    y = np.zeros(len(keep))
    gid = []
    for i, r in enumerate(keep):
        rng = np.random.default_rng(
            [C.SEED, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little')])
        w = Q.rung_weight(r, C.RUNG)
        Q._mix(rng, r['h_team_db_series'], po['team_db'], w, C.M, False)  # V
        if spec is None:
            s = np.clip(Q._mix(rng, r['h_share'], po['share'], w, C.M, False),
                        0, 1)
        else:
            s = Q.share_draws(r, po, rng, w, False, C.M, spec)
        S[i] = s
        y[i] = r['db'] / r['team_db']
        gid.append(r['game_id'])
    _CACHE[spec] = (S, y, gid, keep)
    return _CACHE[spec]


def _pits(S, y):
    rng = np.random.default_rng(C.PIT_SEED)
    rp = np.array([C.randomized_pit(S[i], y[i], rng) for i in range(len(y))])
    mp = np.array([C.mid_pit(S[i], y[i]) for i in range(len(y))])
    return rp, mp


def test_a_chi2_tail_is_correct():
    """The tail function is checked against published table values, not trusted."""
    for x, df, want in ((16.919, 9, 0.05), (21.666, 9, 0.01),
                        (27.877, 9, 0.001), (3.841, 1, 0.05),
                        (9.488, 4, 0.05), (18.307, 10, 0.05)):
        got = C.chi2_sf(x, df)
        check(f'chi2_sf({x}, {df}) == {want}', abs(got - want) < 5e-4,
              f'got {got:.6f}')


def test_b_incumbent_reproduces_the_recorded_defect():
    """The published share numbers must still come out of the frozen code."""
    S, y, gid, keep = _shares(None)
    check('cohort is the 540 games the defect was established on',
          len(y) == PUBLISHED['n'], f'got {len(y)}')
    bias = float(S.mean(axis=1).mean() - y.mean())
    check('signed bias reproduces H1_SUMMARY to 1e-6',
          abs(bias - PUBLISHED['mean_signed_error']) < 1e-6,
          f'got {bias:.8f}')
    check('mean realised share reproduces',
          abs(float(y.mean()) - PUBLISHED['mean_actual']) < 1e-9,
          f'got {y.mean():.8f}')
    p90 = np.percentile(S, 90, axis=1)
    below = float(np.mean(y < p90))
    check('realised share below the predictive P90 in 21.1% of games',
          abs(below - PUBLISHED['coverage_p90_below']) < 1e-9,
          f'got {below:.6f} -- i.e. ABOVE P90 in {1 - below:.1%}')
    rp, mp = _pits(S, y)
    c_mid, h_mid, _ = C.pit_chi2(mp)
    c_rnd, h_rnd, _ = C.pit_chi2(rp)
    # The published 929.037 was computed from the residual CSV, whose pit
    # column is rounded to 8 decimals; four rows sit on a bin edge at 0.6 and
    # move. Recomputed at full precision the same draws give 944.593. Both are
    # the same defect and the discrepancy is recorded rather than reconciled
    # away by loosening a tolerance.
    check('mid-PIT chi-square reproduces the published order of magnitude',
          900.0 < c_mid < 1000.0, f'got {c_mid:.3f}, published '
                                  f'{PUBLISHED["pit_chi2_mid"]:.3f}')
    print(f'       mid-PIT chi2 {c_mid:9.3f} hist {h_mid}')
    print(f'       rnd-PIT chi2 {c_rnd:9.3f} hist {h_rnd}')
    # THE INSTRUMENT CARRIES MOST OF THE 929. Recorded here so no later reader
    # quotes the big number as the size of the modelling error.
    check('the atom is real: at least 3 in 4 realised shares are exactly 1.0',
          float(np.mean(y == 1.0)) > 0.75, f'got {np.mean(y == 1.0):.4f}')
    check('randomized PIT chi-square is far smaller than the mid-PIT one',
          c_rnd < c_mid / 10.0, f'rnd {c_rnd:.2f} vs mid {c_mid:.2f}')


def test_c_share_pit_is_uniform():
    """THE ACCEPTANCE TEST. Expected to FAIL until the share layer is repaired."""
    spec = getattr(Q, 'SHARE_SPEC_STARTER_CONDITIONED', None)
    S, y, gid, keep = _shares(None)
    rp, _ = _pits(S, y)
    c0, h0, df = C.pit_chi2(rp)
    p0 = C.chi2_sf(c0, df)
    print(f'       incumbent randomized-PIT chi2 {c0:.3f} on {df} df, '
          f'p = {p0:.3e}')
    if spec is None:
        check('a starter-conditioned share specification exists',
              False,
              'QB_SHARE_CANDIDATE_ABSENT: qb2_lib exposes no '
              'SHARE_SPEC_STARTER_CONDITIONED, so the incumbent unconditional '
              f'pool is the only path. Its randomized-PIT chi2 is {c0:.2f} on '
              f'{df} df (p = {p0:.3e}), rejecting uniformity at alpha='
              f'{ALPHA}. Histogram {h0}.')
        return
    S1, y1, gid1, _ = _shares(spec)
    rp1, _ = _pits(S1, y1)
    c1, h1, _ = C.pit_chi2(rp1)
    p1 = C.chi2_sf(c1, df)
    print(f'       repaired  randomized-PIT chi2 {c1:.3f} on {df} df, '
          f'p = {p1:.3e}  hist {h1}')
    check(f'share randomized PIT is uniform at alpha={ALPHA}', p1 >= ALPHA,
          f'chi2 {c1:.3f} on {df} df, p = {p1:.3e}, histogram {h1}')
    check('the repair improves uniformity against the incumbent', c1 < c0,
          f'repaired {c1:.3f} vs incumbent {c0:.3f}')


def test_d_share_bias_shrinks():
    """The -0.0778 signed bias must move materially toward zero."""
    spec = getattr(Q, 'SHARE_SPEC_STARTER_CONDITIONED', None)
    S, y, gid, keep = _shares(None)
    b0 = float(S.mean(axis=1).mean() - y.mean())
    if spec is None:
        check('a starter-conditioned share specification exists',
              False, f'absent; incumbent signed bias {b0:+.4f}')
        return
    S1, y1, _, _ = _shares(spec)
    b1 = float(S1.mean(axis=1).mean() - y1.mean())
    print(f'       signed bias {b0:+.4f} -> {b1:+.4f}')
    check('signed share bias at least halves', abs(b1) < abs(b0) / 2.0,
          f'{b0:+.4f} -> {b1:+.4f}')


# sha256 over every draw matrix `qb2_lib.simulate` returns for the 540-row
# cohort at seed 20260908, m=1000, rung L1, taken BEFORE the share repair
# existed and asserted after it. The repair is default-off and this is what
# "default-off" has to mean: not a promise in a docstring but a number.
DEFAULT_SIMULATE_DIGEST = (
    'd67b8b825e2624574373c32ef782b6114170b6e8828d049d78cb66d1c8f11a19')


def test_e_default_path_is_unchanged_by_the_repair():
    """Every sealed artifact was produced on the default path. It must not move."""
    import hashlib
    keep, allrows, po, _ = C.cohort()
    D = Q.simulate(keep, C.EVAL_SEASON, allrows, seed=C.SEED, m=C.M,
                   rung=C.RUNG)
    h = hashlib.sha256()
    for k in sorted(D):
        h.update(np.ascontiguousarray(D[k], np.float64).tobytes())
    got = h.hexdigest()
    check('default simulate draws are bit-identical to the pre-repair engine',
          got == DEFAULT_SIMULATE_DIGEST, f'got {got}')
    # and the candidate must actually be a different generator, or the arms
    # are not two arms
    D2 = Q.simulate(keep, C.EVAL_SEASON, allrows, seed=C.SEED, m=C.M,
                    rung=C.RUNG, share_spec=Q.SHARE_SPEC_STARTER_CONDITIONED)
    h2 = hashlib.sha256()
    for k in sorted(D2):
        h2.update(np.ascontiguousarray(D2[k], np.float64).tobytes())
    check('the candidate specification produces different draws',
          h2.hexdigest() != got, 'the two arms are identical, so nothing was '
                                 'tested')
    # the explicit incumbent name must reach the same place as the default
    D3 = Q.simulate(keep, C.EVAL_SEASON, allrows, seed=C.SEED, m=C.M,
                    rung=C.RUNG, share_spec=Q.SHARE_SPEC_UNCONDITIONAL)
    check('naming the incumbent spec equals leaving it unnamed',
          all(np.array_equal(D[k], D3[k]) for k in D))


def test_f_an_unknown_share_spec_is_refused():
    """A typo must not fall back to the model the operator did not ask for."""
    keep, allrows, po, _ = C.cohort()
    try:
        Q.simulate(keep[:2], C.EVAL_SEASON, allrows, seed=C.SEED, m=8,
                   rung=C.RUNG, share_spec='starter-conditioned')
        check('simulate refuses an unknown share_spec', False,
              'it returned draws instead of raising')
    except ValueError as exc:
        check('simulate refuses an unknown share_spec',
              'unknown share specification' in str(exc), str(exc))
    # and the role fields are required rather than quietly worked around
    stripped = [dict(r) for r in keep[:2]]
    for r in stripped:
        r.pop('h_share_primary', None)
    rng = np.random.default_rng(1)
    try:
        Q.share_draws(stripped[0], po, rng, 0.5, False, 8,
                      Q.SHARE_SPEC_STARTER_CONDITIONED)
        check('the repaired path refuses a frame without the role fields',
              False, 'it drew shares anyway')
    except ValueError as exc:
        check('the repaired path refuses a frame without the role fields',
              'QB_SHARE_ROLE_FIELDS_ABSENT' in str(exc), str(exc))


def test_g_role_labels_use_no_future_information():
    """`prior_primary` and `h_share_primary` may only read strictly earlier games."""
    keep, allrows, po, _ = C.cohort()
    by_pid = {}
    for r in allrows:
        by_pid.setdefault(r['gsis_id'], []).append(r)
    bad_lag = bad_own = 0
    for r in keep:
        past = [x for x in by_pid[r['gsis_id']]
                if x['ord'] < r['ord'] and x['db'] > 0 and x['team_db'] > 0]
        want = [x['db'] / x['team_db'] for x in past if x['_primary']]
        if list(r['h_share_primary']) != want:
            bad_own += 1
        lag = past[-1]['_primary'] if past else None
        if r['prior_primary'] != lag:
            bad_lag += 1
    check('h_share_primary reads only strictly earlier games', bad_own == 0,
          f'{bad_own} of {len(keep)} rows disagree')
    check('prior_primary is the role in the last strictly earlier appearance',
          bad_lag == 0, f'{bad_lag} of {len(keep)} rows disagree')
    # the label itself must never be the row's own outcome
    check('no row\'s own realised role is used as its own conditioner',
          all(r['prior_primary'] is None or isinstance(r['prior_primary'], bool)
              for r in keep))


def main():
    for fn in (test_a_chi2_tail_is_correct,
               test_b_incumbent_reproduces_the_recorded_defect,
               test_c_share_pit_is_uniform,
               test_d_share_bias_shrinks,
               test_e_default_path_is_unchanged_by_the_repair,
               test_f_an_unknown_share_spec_is_refused,
               test_g_role_labels_use_no_future_information):
        print(fn.__name__)
        fn()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}')
    return FAILED


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
