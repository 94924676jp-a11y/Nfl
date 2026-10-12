#!/usr/bin/env python3.12
"""roster_eligibility reads the declared availability.NAME_ALIASES: DK 'Joshua Palmer' is the roster's 'Josh Palmer'
(2026-10-12 BUF@LAR read him NOT_ON_WEEK_ROSTER). A name with no declared alias still fails closed."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from nfl.tools import roster_eligibility as E  # noqa: E402


def test_declared_alias_resolves_and_unknown_name_fails_closed():
    pool = {('Joshua Palmer', 'BUF'): {'pos': 'WR', 'ids': ['1']}, ('Nobody Known', 'BUF'): {'pos': 'WR', 'ids': ['2']},
            ('Ronnie Rivers', 'LAR'): {'pos': 'RB', 'ids': ['3']}}
    rows = [{'full_name': 'Josh Palmer', 'team': 'BUF', 'status': 'ACT'},
            {'full_name': 'Ronnie Rivers', 'team': 'LA', 'status': 'RES'}]
    r = E.classify(pool, rows)
    assert r[('Joshua Palmer', 'BUF')]['eligible'] and r[('Joshua Palmer', 'BUF')]['reason'] == 'ACTIVE_ROSTER'
    assert r[('Nobody Known', 'BUF')]['reason'] == 'NOT_ON_WEEK_ROSTER'
    assert r[('Ronnie Rivers', 'LAR')]['reason'] == 'RESERVE' and not r[('Ronnie Rivers', 'LAR')]['eligible']


if __name__ == '__main__':
    test_declared_alias_resolves_and_unknown_name_fails_closed()
    print('PASS')
