"""Conditional vs unconditional player means, and the floor that withholds one.

WHAT THIS MODULE ASSERTS
========================
1. THE DECOMPOSITION IS ARITHMETICALLY RIGHT on constructed draws where the
   answer is known by hand, including the degenerate cases: always plays,
   never plays, plays exactly at the floor and one below it.
2. AN OUTCOME IS NOT AN OPPORTUNITY. A player who takes a carry and gains
   nothing still participated. Conditioning on a non-zero OUTCOME would score
   him as absent, which is the conflation the module exists to prevent, so
   only declared opportunity arrays may drive the mask.
3. A PLAYER IN NO OPPORTUNITY LAYER IS `None`, NEVER ZERO. "We cannot measure
   his participation" and "he never participates" are different claims and
   rendering the first as the second is this project's signature defect.
4. THE CONDITIONAL MEAN IS WITHHELD BELOW THE DRAW FLOOR rather than printed
   with a caveat. A mean over a handful of draws is noise with a decimal
   point.
5. THE REAL ARTIFACT DECOMPOSES AS MEASURED. Cooper Rush 9.23 -> 14.04 at
   P=0.657, Jordan Love 15.25 -> 15.94 at P=0.957. Those two rows are the
   whole argument: the same table, one number nearly conditional already and
   one half composed of worlds the player sat out.
"""
import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research.unsealed.conditionality import (  # noqa: E402
    MIN_CONDITIONAL_DRAWS,
    ConditionalityError,
    decompose,
    flag_misreadable,
    opportunity_mask,
    table,
)

PASSED = FAILED = BLOCKED = 0

RUN = os.path.join(_ROOT, 'nfl', 'research', 'unsealed',
                   '2026_03_ATL_GB', '2fc4e9599f0889f1')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def near(a, b, tol=1e-9):
    return a is not None and abs(a - b) < tol


def test_the_arithmetic_is_right_where_the_answer_is_known():
    # 1000 draws: he plays in the first 400, scoring 10; sits the rest at 0.
    vals = np.concatenate([np.full(400, 10.0), np.zeros(600)])
    mask = np.concatenate([np.ones(400, bool), np.zeros(600, bool)])
    d = decompose(vals, mask)
    check('unconditional mean is the full average', near(d['mean_unconditional'], 4.0))
    check('conditional mean is the played-worlds average',
          near(d['mean_given_opportunity'], 10.0))
    check('participation share is exact', near(d['p_any_modelled_opportunity'], 0.4))
    check('the ratio is the ratio', near(d['conditionality_ratio'], 2.5))
    check('the basis names what was conditioned on',
          d['basis'] == 'CONDITIONED_ON_ANY_MODELLED_OPPORTUNITY')


def test_a_player_who_always_plays_has_no_gap():
    vals = np.full(1000, 7.0)
    d = decompose(vals, np.ones(1000, bool))
    check('P is one', near(d['p_any_modelled_opportunity'], 1.0))
    check('conditional equals unconditional',
          near(d['mean_given_opportunity'], d['mean_unconditional']))
    check('ratio is one', near(d['conditionality_ratio'], 1.0))


def test_the_draw_floor_withholds_rather_than_prints_noise():
    vals = np.concatenate([np.full(MIN_CONDITIONAL_DRAWS, 10.0),
                           np.zeros(1000)])
    mask = np.concatenate([np.ones(MIN_CONDITIONAL_DRAWS, bool),
                           np.zeros(1000, bool)])
    at = decompose(vals, mask)
    check('exactly at the floor is reported',
          at['mean_given_opportunity'] is not None,
          at['basis'])
    below = decompose(vals[1:], mask[1:])
    check('one draw below the floor is WITHHELD',
          below['mean_given_opportunity'] is None
          and below['basis'] == 'TOO_FEW_QUALIFYING_DRAWS',
          below['basis'])
    check('and the unconditional mean is still reported',
          below['mean_unconditional'] is not None)
    check('and the count that failed the floor is stated',
          below['n_draws_with_opportunity'] == MIN_CONDITIONAL_DRAWS - 1)


def test_unmeasurable_participation_is_none_and_never_zero():
    d = decompose(np.full(100, 3.0), None)
    check('P is None, not 0.0', d['p_any_modelled_opportunity'] is None)
    check('the conditional mean is None', d['mean_given_opportunity'] is None)
    check('the basis says the layer is missing', d['basis'] == 'NO_OPPORTUNITY_LAYER')
    check('and the note refuses the zero reading',
          'not the same as never participating' in d['note'])


def test_an_outcome_is_not_an_opportunity():
    """A back who carries twice for no gain participated."""
    layers = {'rushing': {'row_ids': ['X']}}
    arrays = {'rushing__carries': np.array([[2.0, 0.0, 3.0, 0.0]]),
              'rushing__rushing_yards': np.array([[0.0, 0.0, 12.0, 0.0]])}
    mask = opportunity_mask(arrays, layers, 'X')
    check('the mask follows carries, not yards',
          mask is not None and list(mask) == [True, False, True, False],
          str(None if mask is None else list(mask)))
    check('a zero-yard carry counts as participation', bool(mask[0]))


def test_opportunity_is_the_union_across_a_players_layers():
    layers = {'rushing': {'row_ids': ['X']}, 'receiving': {'row_ids': ['X']}}
    arrays = {'rushing__carries': np.array([[1.0, 0.0, 0.0]]),
              'receiving__targets': np.array([[0.0, 1.0, 0.0]])}
    mask = opportunity_mask(arrays, layers, 'X')
    check('a carry OR a target counts', list(mask) == [True, True, False],
          str(list(mask)))


def test_empty_input_raises_rather_than_returning_a_clean_zero():
    try:
        decompose(np.array([]), None)
        check('empty draws raise', False, 'returned instead of raising')
    except ConditionalityError:
        check('empty draws raise', True)
    try:
        table({}, {}, 'dk_scoring', 'dk_points')
        check('a missing layer raises', False, 'returned instead of raising')
    except ConditionalityError:
        check('a missing layer raises', True)


def test_the_real_artifact_decomposes_as_measured():
    manifest = os.path.join(RUN, 'player_draws_manifest.json')
    npz = os.path.join(RUN, 'player_draws.npz')
    if not (os.path.exists(manifest) and os.path.exists(npz)):
        return blocked('real artifact', f'run artifact absent under {RUN}')
    m = json.load(open(manifest))
    z = np.load(npz, allow_pickle=True)
    rows = table({k: z[k] for k in z.keys()}, m['layers'], 'dk_scoring', 'dk_points')
    by_id = {r['gsis_id']: r for r in rows}

    rush = by_id.get('00-0033662')   # Cooper Rush
    love = by_id.get('00-0036264')   # Jordan Love
    if not (rush and love):
        return blocked('real artifact', 'expected QB rows absent from dk_scoring')

    check('Cooper Rush participates in about two thirds of worlds',
          abs(rush['p_any_modelled_opportunity'] - 0.657) < 0.002,
          str(rush['p_any_modelled_opportunity']))
    check('his unconditional mean is the 9.23 the table prints',
          abs(rush['mean_unconditional'] - 9.23) < 0.01,
          str(rush['mean_unconditional']))
    check('his conditional mean is a normal starter line',
          abs(rush['mean_given_opportunity'] - 14.04) < 0.05,
          str(rush['mean_given_opportunity']))
    check('Jordan Love has almost no gap, because he almost always plays',
          love['conditionality_ratio'] < 1.10
          and love['p_any_modelled_opportunity'] > 0.95,
          f"{love['conditionality_ratio']:.3f} at P={love['p_any_modelled_opportunity']:.3f}")
    check('so the two rows are NOT the same quantity',
          rush['conditionality_ratio'] > 1.4 > love['conditionality_ratio'])
    check('rows come back ordered by the unconditional mean',
          all(rows[i]['mean_unconditional'] >= rows[i + 1]['mean_unconditional']
              for i in range(len(rows) - 1)))

    flagged = flag_misreadable(rows)
    check('the flag catches Rush and misses Love',
          any(r['gsis_id'] == '00-0033662' for r in flagged)
          and not any(r['gsis_id'] == '00-0036264' for r in flagged))
    check('and it catches Penix, the most misreadable row on the slate',
          any(r['gsis_id'] == '00-0039917' and r['conditionality_ratio'] > 3
              for r in flagged))
    print(f'       {len(flagged)} of {len(rows)} rows flagged as misreadable')


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
