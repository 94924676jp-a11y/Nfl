"""classic_portfolio: every DraftKings Classic rule, proven on a lineup built to break it.

The verifier is the last thing between the optimiser and an upload file, so each rule gets a lineup
that is legal except for that one rule (it must be refused) beside the legal lineup (it must pass).
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.opt import classic_portfolio as P   # noqa: E402

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


def _p(pos, team, opp, game, salary=5000, state='PROJECTED', designation=None):
    return {'pos': pos, 'team': team, 'opp': opp, 'game': game, 'salary': salary,
            'state': state if pos != 'DST' else 'PROJECTED_DST', 'designation': designation}


META = {
    'qb': _p('QB', 'BUF', 'NE', 'G1', 7000),
    'rb1': _p('RB', 'BUF', 'NE', 'G1', 6000), 'rb2': _p('RB', 'BAL', 'TEN', 'G2', 6000),
    'wr1': _p('WR', 'BUF', 'NE', 'G1', 6000), 'wr2': _p('WR', 'NE', 'BUF', 'G1', 5000),
    'wr3': _p('WR', 'BAL', 'TEN', 'G2', 5000), 'te': _p('TE', 'BAL', 'TEN', 'G2', 4000),
    'flex': _p('RB', 'TEN', 'BAL', 'G2', 4000), 'dst': _p('DST', 'BAL', 'TEN', 'G2', 3000),
    # replacements, each breaking one rule
    'dst_vs_qb': _p('DST', 'NE', 'BUF', 'G1', 3000),
    'wr_out': _p('WR', 'BAL', 'TEN', 'G2', 5000, designation='OUT'),
    'wr_unproj': _p('WR', 'BAL', 'TEN', 'G2', 5000, state='NOT_PROJECTED'),
    'wr_rich': _p('WR', 'BAL', 'TEN', 'G2', 15000),
    'rb_g1': _p('RB', 'BUF', 'NE', 'G1', 4000), 'wr_g1': _p('WR', 'NE', 'BUF', 'G1', 5000),
    'te_g1': _p('TE', 'NE', 'BUF', 'G1', 4000), 'dst_g1': _p('DST', 'BUF', 'NE', 'G1', 3000),
    'wr_g1b': _p('WR', 'BUF', 'NE', 'G1', 4000),
}
LEGAL = ['qb', 'rb1', 'rb2', 'wr1', 'wr2', 'wr3', 'te', 'flex', 'dst']


def swap(old, new):
    return [new if x == old else x for x in LEGAL]


def test_01_the_legal_lineup_passes_and_slots_correctly():
    v = P.verify_lineup(LEGAL, META)
    check('negative control: a legal QB/RB/RB/WR/WR/WR/TE/FLEX/DST lineup has no violation', v == [], str(v))
    s = P.slot_assign(LEGAL, META)
    check('  slot order fills QB,RB,RB,WR,WR,WR,TE,FLEX,DST',
          [META[d]['pos'] for d in s][:7] == ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE']
          and META[s[8]]['pos'] == 'DST' and META[s[7]]['pos'] in ('RB', 'WR', 'TE')
          and sorted(s) == sorted(LEGAL), str(s))


def test_02_each_rule_refuses_its_own_breach():
    cases = {
        'eight players': (LEGAL[:-1], 'not 9'),
        'a repeated player': (swap('flex', 'rb1'), 'twice'),
        'two DST, no TE': (swap('te', 'dst_vs_qb'), 'shape'),
        'salary over the cap': (swap('wr3', 'wr_rich'), 'cap'),
        'a reported-OUT receiver': (swap('wr3', 'wr_out'), 'OUT'),
        'a non-projected receiver': (swap('wr3', 'wr_unproj'), 'non-playable'),
        'DST facing the quarterback': (swap('dst', 'dst_vs_qb'), 'DST facing'),
        'QB without a same-team pass catcher': (swap('wr1', 'wr_g1'), 'stack'),
        'every player from one game': (['qb', 'rb1', 'rb_g1', 'wr1', 'wr2', 'wr_g1', 'te_g1', 'wr_g1b',
                                        'dst_g1'], 'fewer than 2 games'),
    }
    for label, (lu, needle) in cases.items():
        v = P.verify_lineup(lu, META)
        check(f'positive control: {label} is refused', any(needle in x for x in v), str(v))


def test_03_declared_rules_are_the_ones_the_artifact_names():
    check('QB stack minimum is declared, not inferred', P.QB_STACK_MIN == 1)
    check('DST-against-own-QB is forbidden by declaration', P.FORBID_DST_AGAINST_QB is True)
    check('the cap is the DraftKings Classic cap', P.SALARY_CAP == 50000)
    check('each owner contest size maps to its own profile',
          set(P.PROFILE_BY_ENTRY_COUNT) == {150, 20, 3}
          and len(set(P.PROFILE_BY_ENTRY_COUNT.values())) == 3)


def test_04_slot_assignment_is_a_total_order():
    m = dict(META)
    m['wr_twin'] = _p('WR', 'BAL', 'TEN', 'G2', 5000)       # same salary as wr2 and wr3
    lu = ['qb', 'rb1', 'rb2', 'wr1', 'wr2', 'wr_twin', 'te', 'flex', 'dst']
    orders = {tuple(P.slot_assign(list(perm), m)) for perm in (lu, lu[::-1], sorted(lu), sorted(lu, reverse=True))}
    check('positive control: equal salaries get the same slots whatever order the lineup arrives in',
          len(orders) == 1, str(orders))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
