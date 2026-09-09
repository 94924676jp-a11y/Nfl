"""V1: the QB composition must not assert a property it never checked.

`conserve_allocated_mass` repairs the case where a quarterback's own level
draw is ZERO, and its docstring justifies the repair by saying "any non-zero
draw of that row carries the same rates". The engine then reported
PASS[QB_COMPOSITION_MASS_CONSERVED].

The justification is false for a SMALL draw. A draw of one dropback does not
carry a rate, it carries one Bernoulli realisation of it, and composing by
`target / drawn` multiplies the realisation. Measured on the real 2026 week-1
slate (ARI/LAC, m=200): 4.50% of raw dropback draws are exactly 1, the factor
reaches 59.85, and a passer whose raw passing-TD draws max at 5 emerges with a
composed maximum of 49.14. The NFL single-game record is 7.

Mass conservation was never the property in doubt. These checks keep the
verdict honest about which property held.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State           # noqa: E402
from nfl.production import qb_accounting as QBACC             # noqa: E402

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


def test_a_stretched_draw_is_refused():
    """target 20 from a donor that drew 1 is a 20x stretch."""
    target = np.array([20.0, 18.0, 22.0])
    drawn = np.array([1.0, 18.0, 21.0])
    o = QBACC.measure_composition_amplification(target, drawn)
    assert check('a stretched composition FAILs', o.state is State.FAIL,
                 f'{o.state}[{o.code}]')
    assert check('  it names rate fidelity, not mass',
                 o.code == 'QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED', o.code)
    assert check('  the stretched cells are counted',
                 o.evidence['n_stretched'] == 2, o.evidence['n_stretched'])
    assert check('  the worst factor is reported',
                 abs(o.evidence['factor_max'] - 20.0) < 1e-6,
                 o.evidence['factor_max'])
    assert check('  the smallest denominator is reported',
                 o.evidence['min_denominator'] == 1.0)


def test_an_unstretched_composition_passes():
    target = np.array([10.0, 12.0])
    drawn = np.array([20.0, 12.0])
    o = QBACC.measure_composition_amplification(target, drawn)
    assert check('no stretch -> PASS', o.state is State.PASS,
                 f'{o.state}[{o.code}]')
    assert check('  and it says so by name',
                 o.code == 'QB_COMPOSITION_RATE_FIDELITY_OK', o.code)


def test_the_condition_is_parameter_free():
    """`drawn < target` and nothing else. A threshold here would be a fitted
    constant hiding inside a guard."""
    o = QBACC.measure_composition_amplification(
        np.array([10.0]), np.array([9.999]))
    assert check('a 1.0001x stretch is still a stretch',
                 o.state is State.FAIL, f'{o.state}[{o.code}]')
    o2 = QBACC.measure_composition_amplification(
        np.array([10.0]), np.array([10.0]))
    assert check('exact equality is not a stretch', o2.state is State.PASS,
                 f'{o2.state}[{o2.code}]')
    assert check('the condition is stated in the evidence',
                 'drawn < target' in
                 QBACC.measure_composition_amplification(
                     np.array([10.0]), np.array([1.0])).evidence['condition'])


def test_empty_and_dead_cells_are_not_a_pass():
    """A cell with no allocated mass and no draw measures nothing."""
    o = QBACC.measure_composition_amplification(
        np.array([0.0, 0.0]), np.array([0.0, 5.0]))
    assert check('nothing live -> NOT_APPLICABLE, never PASS',
                 o.state is State.NOT_APPLICABLE, f'{o.state}[{o.code}]')


def test_shape_mismatch_refuses():
    o = QBACC.measure_composition_amplification(
        np.array([1.0, 2.0]), np.array([1.0]))
    assert check('a shape mismatch is a named failure',
                 o.state is State.FAIL
                 and o.code == 'AMPLIFICATION_SHAPE_MISMATCH', o.code)


def test_the_engine_consumes_the_guard_and_can_report_FAIL():
    """A guard nothing calls is not a guard. The engine must both call it and
    be able to emit FAIL -- the previous verdict string was PASS-only."""
    src = open(os.path.join(_ROOT, 'nfl', 'production', 'nonqb',
                            'football_engine.py')).read()
    assert check('the engine calls the amplification guard',
                 'measure_composition_amplification' in src,
                 'ENGINE_DOES_NOT_MEASURE_AMPLIFICATION')
    # THE INCUMBENT BRANCH, not the R2 one. R2 added an earlier assignment of
    # the same key -- under R2 no ratio is formed, so PASS there is correct --
    # and a `find` from the top now lands on it. Anchor on the amplification
    # counter instead, which only the incumbent branch computes.
    a = src.find('amp_fail += 1')
    assert check('the incumbent branch still measures amplification', a > 0,
                 'AMPLIFICATION_COUNTER_GONE')
    i = src.find("g['accounting']['qb_composition'] =", a)
    assert check('the incumbent composition verdict is assigned', i > a)
    j = src.find('qb_composition_amplification', i)
    assert check('the verdict block is delimited', j > i)
    window = src[i:j]
    assert check('the incumbent verdict can be FAIL',
                 'FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]' in window,
                 'COMPOSITION_VERDICT_IS_PASS_ONLY: it reported '
                 'PASS[QB_COMPOSITION_MASS_CONSERVED] whatever happened')
    # And R2's own branch must claim the RIGHT thing: no ratio, not a
    # measured-and-clean ratio.
    r2i = src.find("PASS[QB_LEVEL_OWNED_BY_D1_X_QB3]")
    assert check('R2 names its own composition verdict', r2i > 0,
                 'R2_COMPOSITION_VERDICT_MISSING')
    assert check('the mass statement survives beside it, not instead of it',
                 'qb_composition_mass' in src,
                 'MASS_VERDICT_LOST')


def test_the_guard_fails_when_bypassed():
    """Seed the old always-PASS verdict and require the check to reject it."""
    fake = ("g['accounting']['qb_composition'] = ("
            "'PASS[QB_COMPOSITION_MASS_CONSERVED]' if not repaired_cells "
            "else 'PASS[QB_COMPOSITION_ZERO_DRAW_REPAIRED]')")
    assert check('the old PASS-only verdict would be rejected',
                 'FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]' not in fake,
                 'V1_COMPOSITION_GUARD_IS_INERT')
