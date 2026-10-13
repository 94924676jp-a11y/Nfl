#!/usr/bin/env python3.12
"""roster_eligibility reads the declared availability.NAME_ALIASES: DK 'Joshua Palmer' is the roster's 'Josh Palmer'
(2026-10-12 BUF@LAR read him NOT_ON_WEEK_ROSTER). A name with no declared alias still fails closed."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from nfl.tools import roster_eligibility as E  # noqa: E402


PASSED = FAILED = 0


def check(ok, label=''):
    """Counted check (nfl/tests/run_suite.py reads PASSED/FAILED around every test function)."""
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)

def test_declared_alias_resolves_and_unknown_name_fails_closed():
    pool = {('Joshua Palmer', 'BUF'): {'pos': 'WR', 'ids': ['1']}, ('Nobody Known', 'BUF'): {'pos': 'WR', 'ids': ['2']},
            ('Ronnie Rivers', 'LAR'): {'pos': 'RB', 'ids': ['3']}}
    rows = [{'full_name': 'Josh Palmer', 'team': 'BUF', 'status': 'ACT'},
            {'full_name': 'Ronnie Rivers', 'team': 'LA', 'status': 'RES'}]
    r = E.classify(pool, rows)
    check(r[('Joshua Palmer', 'BUF')]['eligible'] and r[('Joshua Palmer', 'BUF')]['reason'] == 'ACTIVE_ROSTER', "r[('Joshua Palmer', 'BUF')]['eligible'] and r[('Joshua Palmer', 'BUF')]['reason'] == 'ACTIVE_ROSTER'")
    check(r[('Nobody Known', 'BUF')]['reason'] == 'NOT_ON_WEEK_ROSTER', "r[('Nobody Known', 'BUF')]['reason'] == 'NOT_ON_WEEK_ROSTER'")
    check(r[('Ronnie Rivers', 'LAR')]['reason'] == 'RESERVE' and not r[('Ronnie Rivers', 'LAR')]['eligible'], "r[('Ronnie Rivers', 'LAR')]['reason'] == 'RESERVE' and not r[('Ronnie Rivers', 'LAR')]['eligible']")


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED when run standalone."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    test_declared_alias_resolves_and_unknown_name_fails_closed()
    test_zz_every_check_passed()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
