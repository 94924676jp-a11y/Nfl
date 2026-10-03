"""classic_upload_verify: the upload file is checked against DK's pool and the owner's entries, not ours.

Each rule gets a file that is legal except for that one breach (refused) beside the legal file (passes).
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_upload_verify as U   # noqa: E402
from nfl.tests._controls import observe            # noqa: E402

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


def _p(i, pos, team, game, salary=5000):
    return {'dk_id': str(i), 'dk_name': f'P{i}', 'dk_pos': pos, 'flex_eligible': pos in ('RB', 'WR', 'TE'),
            'salary': salary, 'game_info': f'{game} 10/04/2026 01:00PM ET'}


POOL = [_p(1, 'QB', 'BUF', 'NE@BUF', 7000), _p(2, 'RB', 'BUF', 'NE@BUF'), _p(3, 'RB', 'BAL', 'TEN@BAL'),
        _p(4, 'WR', 'BUF', 'NE@BUF'), _p(5, 'WR', 'NE', 'NE@BUF'), _p(6, 'WR', 'BAL', 'TEN@BAL'),
        _p(7, 'TE', 'BAL', 'TEN@BAL', 4000), _p(8, 'RB', 'TEN', 'TEN@BAL', 4000),
        _p(9, 'DST', 'BAL', 'TEN@BAL', 3000), _p(10, 'WR', 'TEN', 'TEN@BAL', 4000),
        _p(11, 'WR', 'TEN', 'TEN@BAL', 30000), _p(12, 'QB', 'NE', 'NE@BUF', 6000)]
ENTRIES = [{'entry_id': 'E1', 'contest_name': 'Big', 'contest_id': 'C150', 'entry_fee': '$0.50'},
           {'entry_id': 'E2', 'contest_name': 'Big', 'contest_id': 'C150', 'entry_fee': '$0.50'},
           {'entry_id': 'E3', 'contest_name': 'Small', 'contest_id': 'C20', 'entry_fee': '$0.25'}]
L1 = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
L2 = ['1', '2', '3', '4', '5', '6', '7', '10', '9']
L3 = ['1', '2', '8', '4', '5', '6', '7', '10', '9']


def _file(*rows):
    return [list(U.HEADER)] + [list(r) for r in rows]


def _good():
    return _file(['E1', 'Big', 'C150', '$0.50'] + L1, ['E2', 'Big', 'C150', '$0.50'] + L2,
                 ['E3', 'Small', 'C20', '$0.25'] + L3)


def _edit(row, col, val):
    f = _good()
    f[row][col] = val
    return f


def test_01_the_legal_file_passes_and_reports_cross_contest_overlap():
    o = U.verify(_good(), POOL, ENTRIES, set())
    check('negative control: a legal file is verified', o.state.value == 'PASS', f'{o.code} {o.detail}')
    ov = (o.evidence or {}).get('cross_contest_identical_lineups', {})
    check('  the smaller contest reports 0 lineups shared with the larger',
          ov.get('C20_in_C150', {}).get('shared_lineups') == 0, str(ov))
    f = _good()
    f[3][4:] = L1
    o = U.verify(f, POOL, ENTRIES, set())
    check('  and counts a lineup copied from the larger contest',
          (o.evidence or {}).get('cross_contest_identical_lineups', {}).get('C20_in_C150', {})
          .get('shared_lineups') == 1, str(o.evidence))


def test_02_each_breach_is_refused():
    cases = {
        'wrong header': (_edit(0, 4, 'CPT'), 'header'),
        'unknown entry': (_edit(1, 0, 'E9'), 'not one of the owner'),
        'entry under the wrong contest': (_edit(3, 2, 'C150'), 'filed under'),
        'player not in the DK pool': (_edit(1, 5, '999'), 'not in the DK pool'),
        'QB in an RB slot': (_edit(1, 5, '12'), 'cannot fill RB'),
        'DST in FLEX': (_edit(2, 11, '9'), 'a player appears twice'),
        'salary over the cap': (_edit(2, 11, '11'), 'over 50000'),
        'repeated player': (_edit(1, 6, '2'), 'appears twice'),
    }
    for label, (f, needle) in cases.items():
        o = U.verify(f, POOL, ENTRIES, set())
        v = (o.evidence or {}).get('violations', [])
        check(f'positive control: {label} is refused', o.state.value == 'FAIL' and any(needle in x for x in v),
              str(v))
    f = _good()
    f.pop()
    o = U.verify(f, POOL, ENTRIES, set())
    observe('nfl.tools.classic_upload_verify:verify:UPLOAD_VERIFY_VIOLATIONS', o)
    check('positive control: an owner entry left without a lineup is refused',
          any('has no lineup' in x for x in (o.evidence or {}).get('violations', [])), str(o.evidence))
    o = U.verify(_good(), POOL, ENTRIES, {'8'})
    check('positive control: a reported-OUT player is refused',
          any('reported OUT' in x for x in (o.evidence or {}).get('violations', [])), str(o.evidence))
    f = _good()
    f[2][4:] = L1
    o = U.verify(f, POOL, ENTRIES, set())
    check('positive control: a duplicate lineup inside one contest is refused',
          any('duplicate lineup' in x for x in (o.evidence or {}).get('violations', [])), str(o.evidence))


def test_03_empty_is_a_refusal_not_a_pass():
    o = U.verify([], POOL, ENTRIES, set())
    observe('nfl.tools.classic_upload_verify:verify:UPLOAD_VERIFY_EMPTY_INPUT', o)
    check('positive control: an empty file is BLOCKED', o.state.value == 'BLOCKED', o.code)
    o = U.verify(_file(), POOL, ENTRIES, set())
    check('  a header with no lineups is BLOCKED', o.state.value == 'BLOCKED', o.code)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
