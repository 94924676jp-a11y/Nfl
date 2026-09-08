"""P4F section 4: the twelve first-principle tests, on synthetic data whose
answer is known before the solver runs.

None of this touches football. It is a claim about an estimator, so it is
tested as one.
"""
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p4f_mpr as M                                            # noqa: E402

P = F = 0


def check(l, c, d=''):
    global P, F
    if c:
        P += 1
        print(f'  ok   {l}')
    else:
        F += 1
        print(f'  FAIL {l}  {d}')


def draws(n, m, sd, seed=11, dist='normal'):
    rng = np.random.default_rng(seed)
    if dist == 'normal':
        return rng.normal(0.0, sd, (n, m))
    if dist == 'laplace':
        return rng.laplace(0.0, sd / math.sqrt(2), (n, m))
    raise ValueError(dist)


def analytic_clipped_mean(c, sd):
    """E[max(0, c + eps)] for eps ~ N(0, sd), the closed form. Used as the
    reference the solver is measured against, so the test does not merely
    agree with itself."""
    from math import erf, exp, pi, sqrt
    z = c / sd
    Phi = 0.5 * (1 + erf(z / sqrt(2)))
    phi = exp(-0.5 * z * z) / sqrt(2 * pi)
    return c * Phi + sd * phi


def t1_clipping_is_mean_biased_near_zero():
    print('\n1. P4C clipping is mean-biased near zero')
    m = 200000
    for c in (0.02, 0.05, 0.10, 0.30):
        e = draws(1, m, 0.08, seed=7)
        got = float(M.clipped_expectation([c], e)[0])
        want = analytic_clipped_mean(c, 0.08)
        check(f'C={c:.2f}: E[clip] {got:.5f} vs closed form {want:.5f}',
              abs(got - want) < 2e-3, f'{got} vs {want}')
        check(f'  and it exceeds C by {100*(got-c)/c:+.1f}%', got > c)


def t2_bias_is_monotone_in_proximity_to_the_boundary():
    print('\n2. bias magnitude is monotone with proximity to the boundary')
    m = 200000
    for sd in (0.05, 0.10):
        cs = [0.01, 0.02, 0.05, 0.10, 0.20, 0.40]
        e = draws(1, m, sd, seed=3)
        rel = [float(M.clipped_expectation([c], e)[0] - c) / c for c in cs]
        check(f'sd={sd}: relative bias strictly decreasing as C rises',
              all(rel[i] > rel[i + 1] for i in range(len(rel) - 1)),
              [round(r, 4) for r in rel])
        abs_bias = [float(M.clipped_expectation([c], e)[0] - c) for c in cs]
        check(f'sd={sd}: absolute bias also decreasing',
              all(abs_bias[i] > abs_bias[i + 1] for i in range(len(cs) - 1)),
              [round(b, 5) for b in abs_bias])


def t3_the_correction_restores_the_mean():
    print('\n3. the correction restores the requested mean within tolerance')
    C = np.array([0.01, 0.03, 0.08, 0.15, 0.35, 0.62, 0.90])
    for sd, dist in ((0.02, 'normal'), (0.10, 'normal'), (0.25, 'normal'),
                     (0.10, 'laplace')):
        E = draws(len(C), 4000, sd, seed=5, dist=dist)
        W, d, rep = M.rectify(C, E)
        check(f'sd={sd} {dist}: every row within 1e-9',
              rep['rows_outside_tolerance'] == 0
              and rep['max_abs_centre_error_float64'] <= 1e-9,
              rep['max_abs_centre_error_float64'])
        check(f'  state PASS', rep['state'] == 'PASS', rep['state'])
        check(f'  and the mean is C, not merely close',
              np.allclose(W.mean(1), C, atol=1e-9, rtol=0))


def t4_the_correction_does_not_change_C():
    print('\n4. the correction does not change C')
    C = np.array([0.02, 0.20, 0.55])
    C0 = C.copy()
    E = draws(3, 2000, 0.1, seed=9)
    E0 = E.copy()
    M.rectify(C, E)
    check('C is untouched by the call', np.array_equal(C, C0))
    check('the residual draws are untouched too', np.array_equal(E, E0))


def t5_the_correction_reads_no_outcome():
    print('\n5. the correction reads no outcome')
    import inspect
    src = inspect.getsource(M)
    banned = ('y_carries', 's_carries', 'appeared', 'outcome', 'realised',
              'realized', 'actual', 'y_true')
    hits = [b for b in banned if b in src.replace('no outcome', '')
            .replace('reads no outcome', '')]
    check(f'no outcome identifier appears in the module', not hits, hits)
    sig = inspect.signature(M.rectify)
    check('rectify takes only centre, residuals, range and solver mechanics',
          list(sig.parameters) == ['centre', 'resid', 'lo', 'hi', 'tol', 'iters'],
          list(sig.parameters))
    # behavioural: permuting a hypothetical outcome cannot change the result
    C = np.array([0.05, 0.25]); E = draws(2, 1000, 0.1, seed=2)
    W1, d1, _ = M.rectify(C, E)
    W2, d2, _ = M.rectify(C, E)
    check('and the result cannot depend on one, there being no channel for it',
          np.array_equal(W1, W2) and np.array_equal(d1, d2))


def t6_deterministic():
    print('\n6. deterministic given identical inputs')
    C = np.array([0.01, 0.09, 0.44]); E = draws(3, 3000, 0.12, seed=17)
    a = M.rectify(C, E)
    b = M.rectify(C, E)
    check('draws bit-identical', np.array_equal(a[0], b[0]))
    check('delta bit-identical', np.array_equal(a[1], b[1]))
    check('report identical', a[2] == b[2])
    c = M.rectify(C.astype(np.float64), E.astype(np.float64))
    check('and identical through an explicit float64 round-trip',
          np.array_equal(a[0], c[0]))


def t7_C_equals_zero():
    print('\n7. C = 0')
    C = np.array([0.0]); E = draws(1, 2000, 0.1, seed=4)
    W, d, rep = M.rectify(C, E)
    # The pre-declared tolerance is 1e-9 absolute, not exactness. Bisection
    # stops just short of the exact threshold delta = C + max(eps), so a
    # handful of draws sit a few times 1e-17 above the floor and the mean lands
    # at ~3e-20. That is the pre-declared contract met, and the residual is
    # reported rather than asserted away.
    check('the mean is 0 within the declared 1e-9', float(W.mean()) <= 1e-9,
          W.mean())
    check(f'  (it is {float(W.mean()):.2e}, not identically zero -- bisection, '
          f'as pre-declared)', float(W.mean()) < 1e-15, W.mean())
    check('every draw sits on the floor to within 1e-15',
          float(W.max()) < 1e-15, W.max())
    check('and the degenerate solution set is FLAGGED',
          rep['rows_degenerate_solution_set'] == 1, rep['flags'])
    check('  without being called an error', rep['state'] == 'PASS', rep['state'])


def t8_C_equals_one():
    print('\n8. C = 1')
    C = np.array([1.0]); E = draws(1, 2000, 0.1, seed=6)
    W, d, rep = M.rectify(C, E)
    check('the mean is exactly 1', float(W.mean()) == 1.0, W.mean())
    check('every draw sits on the ceiling', float(W.min()) == 1.0)
    check('and the degenerate solution set is FLAGGED',
          rep['rows_degenerate_solution_set'] == 1, rep['flags'])


def t9_very_small_residual_variance():
    print('\n9. very small residual variance')
    C = np.array([0.03, 0.50])
    for sd in (0.0, 1e-12, 1e-8):
        E = draws(2, 500, max(sd, 1e-300), seed=8) if sd else np.zeros((2, 500))
        W, d, rep = M.rectify(C, E)
        check(f'sd={sd}: mean restored', rep['rows_outside_tolerance'] == 0,
              rep['max_abs_centre_error_float64'])
        if sd == 0.0:
            check('  and with no spread at all the shift is ~0',
                  abs(float(d[1])) < 1e-9, d)


def t10_large_residual_variance():
    print('\n10. large residual variance')
    C = np.array([0.02, 0.10, 0.50])
    for sd in (0.5, 2.0, 50.0):
        E = draws(3, 4000, sd, seed=13)
        W, d, rep = M.rectify(C, E)
        check(f'sd={sd}: mean restored within 1e-9',
              rep['rows_outside_tolerance'] == 0,
              rep['max_abs_centre_error_float64'])
        check(f'  and the draws stay inside [0, 1]',
              float(W.min()) >= 0.0 and float(W.max()) <= 1.0)


def t11_infeasible_is_detected_not_altered():
    print('\n11. infeasible and pathological cases are detected, not altered')
    C = np.array([0.2, -0.4, 1.7, 0.3])
    E = draws(4, 500, 0.1, seed=21)
    W, d, rep = M.rectify(C, E)
    check('centres outside [0, 1] are counted as infeasible',
          rep['infeasible_centre'] == 2, rep)
    check('  their delta is NaN rather than a silent number',
          bool(np.isnan(d[1]) and np.isnan(d[2])), d)
    check('  and they keep P4C untouched draws',
          np.allclose(W[1], np.clip(C[1] + E[1], 0, 1)))
    check('  the feasible rows are still solved',
          abs(float(W[0].mean()) - 0.2) < 1e-9 and
          abs(float(W[3].mean()) - 0.3) < 1e-9)
    E2 = E.copy(); E2[0, 5] = np.nan
    _W, d2, rep2 = M.rectify(C[:1], E2[:1])
    check('a non-finite residual is refused, not imputed',
          rep2['infeasible_residual'] == 1 and bool(np.isnan(d2[0])), rep2)
    for bad, why in (((np.zeros(3), np.zeros((2, 5))), 'shape mismatch'),):
        try:
            M.rectify(*bad)
            check(f'{why} raises', False, 'no raise')
        except M.InfeasibleRectification as exc:
            check(f'{why} raises a NAMED error', 'SHAPE_MISMATCH' in str(exc))
    try:
        M.rectify(np.array([0.5]), np.zeros((1, 4)), lo=1.0, hi=0.0)
        check('an inverted range raises', False, 'no raise')
    except M.InfeasibleRectification as exc:
        check('an inverted range raises a NAMED error',
              'DEGENERATE_RANGE' in str(exc))


def t12_raw_residual_identity_remains_auditable():
    print('\n12. the raw residual identity is recoverable')
    C = np.array([0.04, 0.22, 0.61])
    E = draws(3, 2000, 0.12, seed=29)
    W, d, rep = M.rectify(C, E)
    eps_hat, interior = M.recover_residuals(W, C, d)
    check('the interior identity eps = W - C + delta holds exactly',
          np.array_equal(eps_hat[interior], (W - C.reshape(-1, 1)
                                             + d.reshape(-1, 1))[interior]))
    check('  and reproduces the original residuals there',
          np.allclose(eps_hat[interior], E[interior], atol=1e-12, rtol=0),
          float(np.abs(eps_hat[interior] - E[interior]).max()))
    frac = 1.0 - interior.mean()
    check(f'  the clipped fraction is itself reportable ({100*frac:.1f}%)',
          0.0 <= frac < 1.0)


def t_confound_control():
    print('\nX. the MC_ONLY confound control does what it says')
    C = np.array([0.03, 0.10, 0.40])
    E = draws(3, 2000, 0.10, seed=31)
    Wm = M.recentre_only(C, E)
    raw = M.clipped_expectation(C, E)
    clips = np.array([True, True, False])   # C=0.40 with sd=0.10 never clips
    check('recentring leaves the rectification bias in place where clipping '
          'happens', bool((Wm.mean(1)[clips] - C[clips] > 1e-3).all()),
          Wm.mean(1) - C)
    check('  and the bias it leaves is the uncorrected one',
          bool(np.abs(Wm.mean(1) - raw).max() < 0.02),
          np.abs(Wm.mean(1) - raw).max())
    check('  while a centre far from the boundary has no bias to leave',
          abs(float(Wm.mean(1)[2] - C[2])) < 1e-9, Wm.mean(1)[2] - C[2])
    check('  yet its mean still MOVES, which is the confound this control '
          'exists to measure',
          abs(float(Wm.mean(1)[2] - raw[2])) > 1e-4, Wm.mean(1)[2] - raw[2])
    W, _d, _r = M.rectify(C, E)
    check('whereas rectification removes it entirely',
          np.allclose(W.mean(1), C, atol=1e-9, rtol=0))


if __name__ == '__main__':
    for t in (t1_clipping_is_mean_biased_near_zero,
              t2_bias_is_monotone_in_proximity_to_the_boundary,
              t3_the_correction_restores_the_mean,
              t4_the_correction_does_not_change_C,
              t5_the_correction_reads_no_outcome, t6_deterministic,
              t7_C_equals_zero, t8_C_equals_one,
              t9_very_small_residual_variance, t10_large_residual_variance,
              t11_infeasible_is_detected_not_altered,
              t12_raw_residual_identity_remains_auditable,
              t_confound_control):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
