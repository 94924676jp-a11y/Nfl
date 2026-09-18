"""One statistic, three populations, and a premise that did not survive it.

The review's gate was "sealed worlds negative, history positive". These checks
pin what the measurement actually found: history is indistinguishable from
zero on yards AND on points, in both seasons, with and without club
de-meaning. Every historical interval contains zero.

The checks are written so that a LATER measurement which does find a positive
historical coupling will fail them loudly rather than quietly agreeing with
whatever is on disk.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.coupling import game_offense_coupling as GC          # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

ART = _REPO/'nfl/research/coupling/GAME_OFFENSE_COUPLING.json'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_the_definition_is_stated_and_excludes_receiving():
    check('A the metric names itself', GC.METRIC == 'GAME_OFFENSE_COUPLING')
    check('A receiving yards are excluded, and the reason travels with it',
          'NOT added' in GC.DEFINITION
          and 'passing yards again' in GC.DEFINITION, GC.DEFINITION)
    check('A two-point plays are excluded', 'two-point' in GC.DEFINITION)


def test_B_the_correlation_helper_is_honest_about_small_and_flat_input():
    check('B two points give no correlation', GC._r([1, 2], [1, 2]) is None)
    check('B a constant series gives none either',
          GC._r([1, 1, 1, 1], [1, 2, 3, 4]) is None)
    r = GC._r([1, 2, 3, 4], [1, 2, 3, 4])
    check('B a perfect line gives 1.0', abs(r - 1.0) < 1e-12, str(r))
    check('B and an interval is refused where it would be meaningless',
          GC._fisher_ci(1.0, 100) is None and GC._fisher_ci(0.5, 3) is None)
    ci = GC._fisher_ci(0.0, 285)
    check('B a zero r at n=285 gives a symmetric interval around zero',
          ci and abs(ci[0] + ci[1]) < 1e-9 and ci[1] > 0, str(ci))


def test_C_history_is_not_positive_on_either_statistic():
    if not ART.exists():
        NOT_EXECUTED.append('C measured artifact absent')
        return
    d = json.loads(ART.read_text())
    h = d['historical']
    check('C both seasons were measured', len(h) == 2, str(sorted(h)))
    for season, row in h.items():
        ci = row['r_ci95']
        check(f'C {season} yardage coupling is indistinguishable from zero',
              ci is not None and ci[0] < 0 < ci[1],
              f"r={row['r']:+.4f} ci={ci}")
        ci = row['r_points_ci95']
        check(f'C {season} POINTS coupling is indistinguishable from zero too',
              ci is not None and ci[0] < 0 < ci[1],
              f"r={row['r_points']:+.4f} ci={ci}")
        ci = row['r_club_demeaned_ci95']
        check(f'C {season} survives club de-meaning, so it is not an '
              f'opponent-strength artefact',
              ci is not None and ci[0] < 0 < ci[1],
              f"r={row['r_club_demeaned']:+.4f} ci={ci}")
    check('C so the review premise "history is positive" is NOT supported',
          all(row['r_ci95'][0] < 0 < row['r_ci95'][1] for row in h.values()))


def test_D_the_simulated_negative_is_real_but_small():
    if not ART.exists():
        NOT_EXECUTED.append('D simulated')
        return
    d = json.loads(ART.read_text())
    s = d['simulated']
    check('D the simulated coupling excludes zero',
          s['r_ci95'][1] < 0, f"r={s['r']:+.4f} ci={s['r_ci95']}")
    check('D it is negative', s['r'] < 0, str(s['r']))
    check('D and it is small: inside one historical yardage interval',
          any(h['r_ci95'][0] <= s['r'] <= h['r_ci95'][1]
              for h in d['historical'].values()),
          str({k: v['r_ci95'] for k, v in d['historical'].items()}))
    check('D the coverage caveat travels with it',
          'lower bound' in s['coverage_caveat'])


def test_E_nothing_was_injected_and_the_populations_are_distinguished():
    if not ART.exists():
        NOT_EXECUTED.append('E governance')
        return
    ev = json.loads(ART.read_text())['evidence']
    check('E no correlation is written into the simulator',
          'no correlation constant' in ev['nothing_is_injected'])
    check('E the two populations are declared not to estimate one quantity',
          'SIGN test' in ev['populations_are_not_the_same_quantity'])
    check('E and the missing score is named as the finding it is',
          'no score' in ev['points_cannot_be_compared_to_the_simulation'])
    check('E no live outcome data was read',
          ev['uses_live_game_outcome_data'] is False)


def test_F_the_measurement_reruns_and_agrees_with_what_is_on_disk():
    """A stored number nobody can reproduce is a story, not a measurement."""
    o = GC.simulated()
    check('F the simulated frame rebuilds', o.state is State.PASS,
          f'{o.state}[{o.code}]')
    if o.state is not State.PASS or not ART.exists():
        NOT_EXECUTED.append('F rerun agreement')
        return
    r = GC._r(o.value['a'], o.value['b'])
    stored = json.loads(ART.read_text())['simulated']['r']
    check('F and reproduces the stored simulated r exactly',
          abs(r - stored) < 1e-12, f'{r} vs {stored}')
    check('F over both clubs, named', o.value['clubs'] == ['BUF', 'DET'],
          str(o.value['clubs']))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_the_definition_is_stated_and_excludes_receiving,
               test_B_the_correlation_helper_is_honest_about_small_and_flat_input,
               test_C_history_is_not_positive_on_either_statistic,
               test_D_the_simulated_negative_is_real_but_small,
               test_E_nothing_was_injected_and_the_populations_are_distinguished,
               test_F_the_measurement_reruns_and_agrees_with_what_is_on_disk):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
