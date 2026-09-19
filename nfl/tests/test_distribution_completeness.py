"""P7: a distribution a threshold question can actually be answered from.

WHAT WAS MISSING AND WHY IT MATTERED

A sealed board carried mean, median, sd and p10/p25/p50/p75/p90. Three things
a prop market asks for were absent:

  * THE TAILS. p5 and p95. A reader asking "how bad is the bad case" was being
    handed p10, which is a different question.
  * THE MASS AT ZERO. For a receiving metric this is most of the question, and
    it is INVISIBLE in the quantiles whenever it exceeds five percent -- which
    for a WR3 it usually does. Measured on a synthetic 22%-zero mixture below:
    p5 and p10 are both 0.0 and neither reveals that 21.75% of the draws are
    exactly zero.
  * HOW MUCH OF THE NUMBER IS SIMULATION NOISE. `sd` is the football's
    uncertainty. MCSE is the simulator's. A reader who reads one for the other
    either over-trusts a 200-draw run or thinks a 20,000-draw run is vague.

WHAT THESE TESTS PIN, AND WHAT THEY DELIBERATELY DO NOT

They pin the MEANING of each new field against distributions whose answers are
known by construction -- a point mass, a uniform, a known-fraction zero
mixture -- not the values on any particular board. A test that asserted today's
numbers would be a snapshot of a seed.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.product import distributions as D                       # noqa: E402

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


REQUIRED = ('mean', 'median', 'sd', 'p5', 'p10', 'p25', 'p50', 'p75', 'p90',
            'p95', 'p_zero', 'mcse_mean', 'mcse_median_halfwidth95', 'n_draws')


def test_the_summary_carries_every_field_a_threshold_query_needs():
    s = D.summary(np.arange(1000, dtype=float))
    for f in REQUIRED:
        check(f'the summary carries {f}', f in s, str(sorted(s)))
    check('the percentile names follow one derivable rule',
          all(f'p{p}' in s for p in D.PCTS), str(D.PCTS))
    check('and the tails are declared in PCTS rather than special-cased',
          5 in D.PCTS and 95 in D.PCTS, str(D.PCTS))


def test_the_quantiles_are_ordered_and_bracket_the_median():
    x = np.random.default_rng(11).gamma(2.0, 30.0, 5000)
    s = D.summary(x)
    vals = [s[f'p{p}'] for p in sorted(D.PCTS)]
    check('quantiles are non-decreasing in p', all(
        a <= b for a, b in zip(vals, vals[1:])), str(vals))
    check('p50 and median are the same number', s['p50'] == s['median'])
    check('p5 is below p95', s['p5'] < s['p95'])


def test_p_zero_is_the_exact_draw_fraction_and_not_a_quantile_artifact():
    """The case the quantiles cannot see.

    22% of the draws are exactly zero. p5 and p10 are both 0.0 and say nothing
    about how much mass is there -- a reader would have to guess between 5%
    and 25%. p_zero answers it exactly.
    """
    rng = np.random.default_rng(7)
    zero = rng.random(2000) < 0.22
    x = np.where(zero, 0.0, rng.gamma(2.0, 18.0, 2000))
    s = D.summary(x)
    check('p_zero equals the exact fraction of zero draws',
          abs(s['p_zero'] - zero.mean()) < 5e-5,
          f"{s['p_zero']} vs {zero.mean()}")
    check('while p5 shows only 0.0', s['p5'] == 0.0, str(s['p5']))
    check('and p10 shows only 0.0 as well', s['p10'] == 0.0, str(s['p10']))
    check('so the zero mass is recoverable ONLY from p_zero',
          s['p_zero'] > 0.2 and s['p5'] == s['p10'] == 0.0)


def test_p_zero_is_zero_when_nothing_is_zero_rather_than_absent():
    s = D.summary(np.full(500, 7.5))
    check('a distribution with no zero draws reports p_zero 0.0',
          s['p_zero'] == 0.0, str(s['p_zero']))
    check('and it is present, not omitted -- absent and zero are different '
          'claims', 'p_zero' in s)


def test_mcse_of_the_mean_is_simulation_noise_and_not_football_uncertainty():
    """They are different quantities and the test proves they move apart.

    Quadrupling the draw count leaves `sd` where it was -- the football did
    not change -- and halves `mcse_mean`. A single "uncertainty" number could
    not do both.
    """
    rng = np.random.default_rng(3)
    small = D.summary(rng.normal(50, 12, 1000))
    big = D.summary(rng.normal(50, 12, 16000))
    check('sd is about the same at 1,000 and 16,000 draws',
          abs(small['sd'] - big['sd']) < 1.5,
          f"{small['sd']} vs {big['sd']}")
    check('mcse_mean falls by about 4x when draws rise 16x',
          2.5 < small['mcse_mean'] / big['mcse_mean'] < 6.5,
          f"{small['mcse_mean']} vs {big['mcse_mean']}")
    check('mcse_mean is far smaller than sd, so the two cannot be confused '
          'by eye', big['mcse_mean'] < big['sd'] / 10)


def test_mcse_of_the_mean_is_exactly_sd_over_root_n():
    x = np.random.default_rng(5).normal(20, 5, 4096)
    s = D.summary(x)
    want = float(x.std(ddof=1) / np.sqrt(x.size))
    check('mcse_mean is sd/sqrt(n), stated and not approximated',
          abs(s['mcse_mean'] - round(want, 4)) < 1e-9,
          f"{s['mcse_mean']} vs {want}")


def test_the_median_mcse_is_distribution_free():
    """It must not assume a shape, because receiving metrics do not have one.

    A normal-approximation MCSE with a density estimate would need a
    bandwidth, which is a constant with no source. The binomial order-statistic
    bracket needs none, and the test drives it with a bimodal mixture that no
    density estimate would handle gracefully.
    """
    rng = np.random.default_rng(13)
    bimodal = np.concatenate([rng.normal(5, 1, 4000), rng.normal(80, 4, 4000)])
    s = D.summary(bimodal)
    check('it returns a finite number on a bimodal distribution',
          np.isfinite(s['mcse_median_halfwidth95']),
          str(s['mcse_median_halfwidth95']))
    check('and it is positive', s['mcse_median_halfwidth95'] > 0)
    tight = D.summary(np.full(1000, 3.0))
    check('a point mass has a median half-width of exactly zero -- no '
          'simulation noise where there is no variation',
          tight['mcse_median_halfwidth95'] == 0.0,
          str(tight['mcse_median_halfwidth95']))


def test_the_median_mcse_shrinks_as_draws_grow():
    rng = np.random.default_rng(17)
    a = D.summary(rng.gamma(2.0, 25.0, 1000))['mcse_median_halfwidth95']
    b = D.summary(rng.gamma(2.0, 25.0, 64000))['mcse_median_halfwidth95']
    check('more draws means a tighter bracket on the median', b < a,
          f'{b} vs {a}')


def test_too_few_draws_returns_nan_rather_than_a_confident_small_number():
    """The honest answer to "how noisy is this median" at n=4 is: unknown.

    Returning a small number because the arithmetic happens to work would be
    a confident statement built on four points.
    """
    s = D.summary(np.array([1.0, 2.0, 3.0, 4.0]))
    check('the median MCSE is NaN below the minimum draw count',
          np.isnan(s['mcse_median_halfwidth95']),
          str(s['mcse_median_halfwidth95']))
    check('but the mean MCSE, which needs only two, is finite',
          np.isfinite(s['mcse_mean']), str(s['mcse_mean']))
    one = D.summary(np.array([9.0]))
    check('and with a single draw even the mean MCSE refuses',
          np.isnan(one['mcse_mean']), str(one['mcse_mean']))


def test_an_exact_threshold_probability_needs_no_gaussian_step():
    """P7's requirement, stated as a test.

    The sportsbook line is a number, not a quantile. Answering it from p50 and
    sd would impose a shape the draws do not have; `p_over` counts draws.
    """
    rng = np.random.default_rng(23)
    zero = rng.random(20000) < 0.30
    x = np.where(zero, 0.0, rng.gamma(1.6, 24.0, 20000))
    line = 34.5
    exact = float((x > line).mean())
    check('p_over counts draws strictly above the line',
          abs(D.p_over(x, line) - round(exact, 4)) < 1e-9)
    s = D.summary(x)
    from math import erf, sqrt
    gauss = 0.5 * (1 - erf((line - s['mean']) / (s['sd'] * sqrt(2))))
    check('and a Gaussian read of the same mean and sd disagrees materially, '
          'which is why the draws are kept',
          abs(gauss - exact) > 0.02, f'gauss {gauss:.4f} vs exact {exact:.4f}')


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
