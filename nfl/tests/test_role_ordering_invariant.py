"""A depth-chart starter may not be absent more often than his backup.

THE REGRESSION CASE IS REAL. James Cook, Buffalo RB1 on the official depth
chart, week-1 usage of 13 carries against Ray Davis's 1, no injury
designation, carried P(zero opportunity) 0.3719 against Davis's 0.1801 in the
board that was sealed and shipped. Nothing objected. This test is the thing
that objects.

It also pins the mistake the check itself made first: the depth vintage ranks
offence-wide WITHIN a club, so a first pass that pooled both clubs compared
Buffalo's RB1 to Detroit's and reported five inversions that were not
inversions. A club is now required, and a missing one is a refusal.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import role_invariants as RI                 # noqa: E402
from nfl.research.buf_allocation import run_role_ordering as RUN       # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402

PASSED = 0
FAILED = 0
NOT_EXECUTED = []

N = 8000


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_A_a_consistent_room_passes():
    pz = {'a': 0.05, 'b': 0.20, 'c': 0.60}
    depth = {'a': (1, 'RB'), 'b': (2, 'RB'), 'c': (3, 'RB')}
    teams = {k: 'XXX' for k in pz}
    o = RI.check(pz, depth, n_draws=N, teams=teams, label='control')
    check('A a room ordered the right way passes',
          o.state is State.PASS and o.code == RI.CODE_OK,
          f'{o.state}[{o.code}]')
    check('A it counts the pairs it actually compared',
          o.evidence['n_ordered_pairs'] == 3,
          str(o.evidence['n_ordered_pairs']))


def test_B_the_starter_absent_more_than_his_backup_is_refused():
    pz = {'starter': 0.3719, 'backup': 0.1801}
    depth = {'starter': (3, 'RB'), 'backup': (8, 'RB')}
    teams = {'starter': 'BUF', 'backup': 'BUF'}
    o = RI.check(pz, depth, n_draws=N, teams=teams,
                 names={'starter': 'James Cook', 'backup': 'Ray Davis'},
                 label='the real numbers')
    check('B the Cook/Davis inversion is refused',
          o.state is State.FAIL and o.code == RI.CODE_INVERSION,
          f'{o.state}[{o.code}]')
    if o.state is State.FAIL:
        r = o.evidence['inversions'][0]
        check('B the refusal names both players and the gap',
              r['ahead'] == 'James Cook' and r['behind'] == 'Ray Davis'
              and abs(r['excess'] - 0.1918) < 1e-9 and r['se_multiples'] > 20,
              str(r))


def test_C_monte_carlo_noise_alone_does_not_raise_a_flag():
    """The tolerance is derived from the draw count, not chosen."""
    # 0.30 vs 0.2995 is inside one SE at 8,000 draws and outside nothing.
    pz = {'a': 0.3000, 'b': 0.2995}
    depth = {'a': (1, 'WR'), 'b': (2, 'WR')}
    teams = {k: 'XXX' for k in pz}
    o = RI.check(pz, depth, n_draws=N, teams=teams, label='noise')
    check('C a gap inside the MC standard error is not an inversion',
          o.state is State.PASS, f'{o.state}[{o.code}]')
    small = RI.check(pz, depth, n_draws=50, teams=teams, label='few draws')
    check('C fewer draws widen the tolerance rather than narrow it',
          small.state is State.PASS
          and RI.se_diff(0.30, 0.2995, 50) > RI.se_diff(0.30, 0.2995, N),
          f'{small.state}[{small.code}]')
    # ... and a real gap at the same draw count still fires.
    big = RI.check({'a': 0.60, 'b': 0.20}, depth, n_draws=N, teams=teams,
                   label='real gap')
    check('C a real gap at the same draw count still fires',
          big.state is State.FAIL, f'{big.state}[{big.code}]')


def test_D_ranks_from_two_clubs_may_not_be_pooled():
    pz = {'buf_rb1': 0.3719, 'det_rb1': 0.0471}
    depth = {'buf_rb1': (3, 'RB'), 'det_rb1': (4, 'RB')}
    o = RI.check(pz, depth, n_draws=N,
                 teams={'buf_rb1': 'BUF', 'det_rb1': 'DET'},
                 names={'buf_rb1': 'James Cook', 'det_rb1': 'Jahmyr Gibbs'},
                 label='two clubs')
    check('D Cook against Gibbs is not an inversion, it is two scales',
          o.state is State.PASS and o.evidence['n_ordered_pairs'] == 0,
          f'{o.state}[{o.code}] pairs={o.evidence["n_ordered_pairs"]}')
    missing = RI.check(pz, depth, n_draws=N, teams={'buf_rb1': 'BUF'},
                       label='no club')
    check('D a player with a rank and no club is refused, not pooled',
          missing.state is State.FAIL and missing.code == RI.CODE_INPUT,
          f'{missing.state}[{missing.code}]')


def test_E_an_empty_check_is_not_a_passed_check():
    o = RI.check({}, {}, n_draws=N, teams={}, label='nothing')
    check('E no probabilities is a refusal',
          o.state is State.FAIL and o.code == RI.CODE_INPUT,
          f'{o.state}[{o.code}]')


def test_F_an_excused_starter_is_reported_not_counted():
    pz = {'starter': 0.80, 'backup': 0.10}
    depth = {'starter': (1, 'RB'), 'backup': (2, 'RB')}
    teams = {k: 'XXX' for k in pz}
    o = RI.check(pz, depth, n_draws=N, teams=teams,
                 excused={'starter': 'listed DOUBTFUL on the official report'},
                 label='excused')
    check('F an excused starter does not fail the check',
          o.state is State.PASS, f'{o.state}[{o.code}]')
    check('F but he is still reported, with the reason',
          o.evidence['n_excused'] == 1
          and 'DOUBTFUL' in o.evidence['excused'][0]['excused_because'],
          str(o.evidence['excused']))


def test_G_the_sealed_board_still_carries_the_defect():
    """The board that shipped. This must keep failing until it is repaired."""
    o = RUN.run()
    check('G the sealed DET_BUF board fails the ordering check',
          o.state is State.FAIL and o.code == RI.CODE_INVERSION,
          f'{o.state}[{o.code}] {o.detail}')
    if o.state is not State.FAIL:
        NOT_EXECUTED.append('G board inversion detail')
        return
    inv = o.evidence['inversions']
    cook = [r for r in inv if r['ahead'] == 'James Cook']
    check('G Cook over Davis is one of them',
          len(cook) == 1 and cook[0]['behind'] == 'Ray Davis'
          and cook[0]['team'] == 'BUF', str(cook))
    check('G and a second inversion nobody had seen is also caught',
          any(r['ahead'] == 'Tom Kennedy' for r in inv),
          str([(r['team'], r['ahead'], r['behind']) for r in inv]))
    check('G the two players with no depth rank are named, not ignored',
          len(o.evidence['players_without_depth_rank']) == 2,
          str(o.evidence['players_without_depth_rank']))
    check('G this reads no outcome data',
          'outcome' not in o.detail.lower())


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in (test_A_a_consistent_room_passes,
               test_B_the_starter_absent_more_than_his_backup_is_refused,
               test_C_monte_carlo_noise_alone_does_not_raise_a_flag,
               test_D_ranks_from_two_clubs_may_not_be_pooled,
               test_E_an_empty_check_is_not_a_passed_check,
               test_F_an_excused_starter_is_reported_not_counted,
               test_G_the_sealed_board_still_carries_the_defect):
        fn()
    for n in NOT_EXECUTED:
        print(f'  NOT_EXECUTED {n}')
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
