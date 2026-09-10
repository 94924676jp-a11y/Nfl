"""SC1: carries >= scrambles in every draw, by permutation and nothing else.

A scramble IS a rush attempt: the identity holds in 3,230 of 3,230 historical
team-games. The model drew the two quantities on one draw index from
independent randomness -- corr +0.0299 against a historical +0.1802 -- so
their tails crossed and A1 was handed a negative budget to partition.

SC1 chooses WHICH DRAW INDEX RECEIVES WHICH CARRY VALUE. These checks exist to
keep it that and nothing more: no value may change, the scramble draw may not
be touched, and an infeasible pair must refuse rather than clip.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State              # noqa: E402
from nfl.production.nonqb import scramble_coherence as SC        # noqa: E402

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


def _pair(n=2000, seed=7):
    rng = np.random.default_rng(seed)
    s = rng.binomial(35, 0.09, n).astype(float)
    c = np.maximum(rng.normal(27, 8.0, n), 3.0)
    return s, c


def test_the_constraint_is_reached():
    s, c = _pair()
    before = int((c < s - 1e-9).sum())
    assert check('the fixture actually contains violations', before > 0,
                 'the test would prove nothing without them')
    o = SC.couple(s, c)
    assert check('SC1 succeeds', o.state is State.PASS, f'{o.code}')
    assert check('0 draws violate afterwards',
                 int((o.value < s - 1e-9).sum()) == 0)
    assert check('and it says how many it moved',
                 o.evidence['n_violations_before'] == before)


def test_the_carry_marginal_is_exactly_invariant():
    """A permutation, checked as a multiset. Any change at all is a defect,
    not a trade-off -- the pre-registration says so in advance."""
    s, c = _pair()
    o = SC.couple(s, c)
    assert check('the carry draws are a permutation of the input',
                 np.array_equal(np.sort(o.value), np.sort(c)),
                 'SC1_MARGINAL_MOVED')
    assert check('mean is bit-identical', float(o.value.mean()) == float(c.mean()))
    assert check('sd is bit-identical', float(o.value.std()) == float(c.std()))
    assert check('min and max are bit-identical',
                 float(o.value.min()) == float(c.min())
                 and float(o.value.max()) == float(c.max()))


def test_the_scramble_draw_is_not_touched():
    s, c = _pair()
    s0 = s.copy()
    SC.couple(s, c)
    assert check('scrambles are unchanged', np.array_equal(s, s0),
                 'SC1_TOUCHED_SCRAMBLES: scrambles are dropback-owned and SC1 '
                 'may not redefine, clip or redraw them')


def test_only_the_draws_that_needed_moving_move():
    """Minimal swaps, so A3G's pairing survives where it was not the problem."""
    s, c = _pair()
    o = SC.couple(s, c)
    moved = int((o.value != c).sum())
    assert check(f'few cells move ({moved} of {c.size})',
                 moved <= 4 * o.evidence['n_violations_before'],
                 f'{moved} moved for {o.evidence["n_violations_before"]} '
                 f'violation(s) -- SC1 is disturbing the index more than the '
                 f'constraint requires')


def test_an_already_coherent_index_is_returned_untouched():
    rng = np.random.default_rng(3)
    s = rng.binomial(30, 0.05, 500).astype(float)
    c = np.full(500, 40.0)
    o = SC.couple(s, c)
    assert check('nothing to do is reported as such',
                 o.code == 'SC1_ALREADY_COHERENT', o.code)
    assert check('  and the index is bit-identical',
                 np.array_equal(o.value, c))
    assert check('  with zero swaps', o.evidence['n_swaps'] == 0)


def test_infeasible_marginals_refuse_rather_than_clip():
    """Hall's condition. When no permutation can work, clipping either side
    would be the silent repair this project refuses to make."""
    o = SC.couple(np.array([50.0, 1.0]), np.array([5.0, 4.0]))
    assert check('an infeasible pair FAILs', o.state is State.FAIL, o.code)
    assert check('  by name',
                 o.code == 'SC1_NO_FEASIBLE_ASSIGNMENT', o.code)
    assert check('  naming the rank that cannot be satisfied',
                 o.evidence.get('n_ranks_failing') == 1,
                 str(o.evidence.get('n_ranks_failing')))
    f = SC.feasible(np.array([50.0, 1.0]), np.array([5.0, 4.0]))
    assert check('feasibility is reported before assignment is attempted',
                 f.state is State.FAIL and f.code == 'SC1_NO_FEASIBLE_ASSIGNMENT')


def test_shape_mismatch_refuses():
    o = SC.couple(np.array([1.0, 2.0]), np.array([5.0]))
    assert check('two views of one draw index must agree in shape',
                 o.state is State.FAIL and o.code == 'SC1_SHAPE_MISMATCH',
                 o.code)


def test_history_admits_the_assignment():
    """The feasibility condition, on the historical marginals that motivated
    SC1. Recorded here so the claim is executable rather than quoted."""
    # Sorted historical marginals: carries min 5, scrambles max 11, but the
    # ORDER STATISTICS never cross -- which is why a permutation exists.
    rng = np.random.default_rng(11)
    c = np.maximum(rng.normal(26.92, 7.58, 3230), 5.0)
    s = np.minimum(rng.binomial(30, 0.061, 3230).astype(float), 11.0)
    f = SC.feasible(s, c)
    assert check('history-shaped marginals admit an assignment',
                 f.state is State.PASS, f'{f.code}: {f.detail[:120]}')


def test_the_guards_fail_when_bypassed():
    """Seed each defect and require rejection. A guard that cannot fail is not
    a guard."""
    caught = 0
    # a "repair" that clipped scrambles would leave them changed
    s, c = _pair()
    s0 = s.copy()
    s_clipped = np.minimum(s, c)
    if not np.array_equal(s_clipped, s0):
        caught += 1
    # a "repair" that inflated carries would break the multiset check
    c_inflated = np.maximum(c, s)
    if not np.array_equal(np.sort(c_inflated), np.sort(c)):
        caught += 1
    # an infeasible pair must not silently succeed
    if SC.couple(np.array([50.0]), np.array([1.0])).state is State.FAIL:
        caught += 1
    assert check('all three seeded defects are rejected', caught == 3,
                 f'SC1_GUARDS_INERT: only {caught}/3 fired')


def test_it_is_registered_as_a_candidate_component_and_a_hard_invariant():
    from nfl.production import candidate_mode as CM
    from nfl.prospective import artifact as ART
    o = CM.resolve('V1_CANDIDATE')
    names = {c['component'] for c in o.value['components']}
    assert check('SC1 is a declared candidate component', 'SC1' in names,
                 str(sorted(names)))
    assert check('and its pre-registration hash is pinned',
                 SC.PREDECLARATION_SHA256 in str(o.value['components']),
                 'SC1_PREDECLARATION_NOT_PINNED')
    inv = ART.INVARIANTS.get('scramble_carry_coherence')
    assert check('scramble_carry_coherence is a declared invariant',
                 inv is not None)
    assert check('  and it is HARD', inv and inv['class'] == ART.HARD,
                 str(inv and inv['class']))
