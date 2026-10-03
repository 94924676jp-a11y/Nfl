"""classic_slate_run.anchor_means: draws re-centred on the projection, and nothing else about them moved."""
from __future__ import annotations

import pathlib
import random
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_run as R   # noqa: E402

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


def _corr(a, b):
    return statistics.correlation(a, b)


rng = random.Random(7)
BASE = [rng.gauss(0, 1) for _ in range(4000)]
DRAWS = {'qb|X': [max(0.0, 18 + 6 * z) for z in BASE],
         'wr|X': [max(0.0, 12 + 5 * (0.6 * z + 0.8 * rng.gauss(0, 1))) for z in BASE],
         'zero|X': [0.0] * 4000,
         'loose|X': [3.0] * 4000}
TARGETS = {'qb|X': 15.0, 'wr|X': 16.0, 'zero|X': 4.0}


def test_01_means_move_to_the_projection_and_nothing_else_does():
    out, acc = R.anchor_means(DRAWS, TARGETS)
    for k in ('qb|X', 'wr|X'):
        m = sum(out[k]) / len(out[k])
        check(f'positive control: {k} mean equals its projection target', abs(m - TARGETS[k]) < 1e-9, f'{m}')
        cv0 = statistics.pstdev(DRAWS[k]) / statistics.fmean(DRAWS[k])
        cv1 = statistics.pstdev(out[k]) / statistics.fmean(out[k])
        check(f'  {k} coefficient of variation unchanged', abs(cv0 - cv1) < 1e-9)
    check('  between-player correlation unchanged',
          abs(_corr(DRAWS['qb|X'], DRAWS['wr|X']) - _corr(out['qb|X'], out['wr|X'])) < 1e-9)
    check('  the input draws are not mutated', abs(statistics.fmean(DRAWS['qb|X']) - 18) < 0.5)


def test_02_what_cannot_be_anchored_is_named_not_forced():
    out, acc = R.anchor_means(DRAWS, TARGETS)
    check('negative control: a zero-mean player is left as drawn', out['zero|X'] == DRAWS['zero|X'])
    check('  and named with its reason', 'NOT_POSITIVE' in acc['left_as_drawn'].get('zero|X', ''), str(acc))
    check('  a player with no projection target is left as drawn and named',
          out['loose|X'] == DRAWS['loose|X'] and acc['left_as_drawn'].get('loose|X') == 'NO_PROJECTION_TARGET')
    check('  the account counts both sides', acc['n_anchored'] == 2 and acc['n_left_as_drawn'] == 2, str(acc))
    check('  each factor is recorded with its raw mean and target',
          set(acc['factors']['qb|X']) == {'factor', 'raw_mean', 'target'})


def _w(pa, pyd, car, ryd, tgt, rec, recyd, ptd=0, rtd=0, rectd=0):
    return (pa, pyd, ptd, car, ryd, rtd, tgt, rec, recyd, rectd)


def test_03_efficiency_step_moves_yards_only():
    r2 = random.Random(3)
    qb = [_w(35, max(0.0, 230 + 60 * r2.gauss(0, 1)), 4, max(0.0, 20 + 10 * r2.gauss(0, 1)), 0, 0, 0,
             ptd=r2.randint(0, 3)) for _ in range(3000)]
    wr = [_w(0, 0, 0, 0, t, max(0, t - 3), max(0.0, 8.0 * t + 15 * r2.gauss(0, 1)), rectd=r2.randint(0, 1))
          for t in (r2.randint(2, 12) for _ in range(3000))]
    rows = {'qb': {'conditional_volume': {'pass_yards': 205.0, 'pass_attempts': 35.0, 'rush_yards': 26.0,
                                          'carries': 4.0, 'rec_yards': None}},
            'wr': {'conditional_volume': {'pass_yards': None, 'rush_yards': None, 'rec_yards': 80.0,
                                          'targets': 7.0}},
            'ghost': {'conditional_volume': {'rec_yards': 40.0, 'targets': 4.0}},
            'backup': {'conditional_volume': {'pass_yards': 200.0, 'pass_attempts': 33.0}},
            'rare': {'conditional_volume': {'rec_yards': 30.0, 'targets': 4.0}}}
    backup = [_w(30, 180.0, 0, 0, 0, 0, 0) if i < 30 else _w(0, 0, 0, 0, 0, 0, 0) for i in range(3000)]
    rare = [_w(0, 0, 0, 0, 1, 0, 0.5) if i < 2 else _w(0, 0, 0, 0, 0, 0, 0) for i in range(3000)]
    sd = {'qb': qb, 'wr': wr, 'ghost': [_w(0, 0, 0, 0, 0, 0, 0)] * 3000, 'backup': backup,
          'rare': rare}
    dk, worlds, acc = R.efficiency_worlds(sd, rows, 0.02054, seed=1)
    m = lambda k, j: sum(w[j] for w in worlds[k]) / len(worlds[k])  # noqa: E731
    check('positive control: QB passing-yard mean equals the projection', abs(m('qb', 1) - 205.0) < 1e-6, m('qb', 1))
    check('  QB rushing-yard mean equals the projection', abs(m('qb', 4) - 26.0) < 1e-6)
    ypt = sum(w[8] for w in worlds['wr']) / sum(w[6] for w in worlds['wr'])
    check('  WR yards PER TARGET equal the projection (80 / 7)', abs(ypt - 80.0 / 7.0) < 1e-9, ypt)
    f = acc['factors']['backup']['pass_yards']
    check('negative control: a backup who throws in 1% of worlds is rescaled per attempt, not per game',
          abs(f - (200.0 / 33.0) / 6.0) < 1e-4, f)   # the account rounds to 4 dp
    check('  attempts, targets, catches and touchdowns are exactly as simulated',
          all(a[0] == b[0] and a[2] == b[2] and a[6] == b[6] and a[7] == b[7] and a[9] == b[9]
              for a, b in zip(sd['qb'] + sd['wr'], worlds['qb'] + worlds['wr'])))
    ints = sum(w[10] for w in worlds['qb']) / len(worlds['qb'])
    check('  interceptions are drawn at the declared rate (35 x 0.02054 = 0.72)', abs(ints - 0.719) < 0.06, ints)
    check('  receivers throw no interceptions', all(w[10] == 0 for w in worlds['wr']))
    w = worlds['qb'][0]
    check('  DK points are the scoring formula applied to the stat line',
          abs(dk['qb'][0] - R.dk_from_stats(*w)) < 1e-9)
    check('negative control: a player whose simulated yards are zero is named, not forced',
          'ghost' in acc['not_anchorable'] and acc['factors']['ghost']['rec_yards'] == 1.0, str(acc['not_anchorable']))
    check('negative control: two simulated targets in 3000 worlds are too few to measure a rate',
          acc['factors']['rare']['rec_yards'] == 1.0 and 'rare' in acc['not_anchorable'], str(acc['factors']['rare']))
    check('  no row in the projection -> not drawn and named',
          R.efficiency_worlds({'x': qb[:5]}, {}, 0.02, 1)[2]['not_anchorable'] == {'x': 'NO_PROJECTION_ROW'})


def test_04_dk_scoring_bonuses():
    check('300-yard passing bonus applies at 300', R.dk_from_stats(30, 300, 0, 0, 0, 0, 0, 0, 0, 0, 0) == 15.0)
    check('  and not at 299.9', abs(R.dk_from_stats(30, 299.9, 0, 0, 0, 0, 0, 0, 0, 0, 0) - 11.996) < 1e-9)
    check('  100-yard receiving bonus plus PPR', R.dk_from_stats(0, 0, 0, 0, 0, 0, 9, 7, 100, 1, 0) == 26.0)
    check('  an interception costs one point', R.dk_from_stats(30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2) == -2.0)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
