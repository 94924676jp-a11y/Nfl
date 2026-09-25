"""A week default is a date default, and this one silently expired.

`refresh_boards.py --week` defaulted to 1. The scheduled workflow passes no
week, so `--all-upcoming` asked for week-1 games with a kickoff ahead of now.
Correct for seven days, empty ever since, and the refusal told the operator to
pass a flag they had just passed. Nine consecutive scheduled runs reported it.

Measured 2026-09-25: week 1 yields 0 upcoming games, week 3 yields 15, week 4
yields 16.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import refresh_boards as R                        # noqa: E402

PASSED = 0
FAILED = 0
BLOCKED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  blocked {label}: {why}')


def test_A_week_is_not_defaulted():
    print('\nA. the argument no longer carries a date')
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, default=None)
    # Read the real parser's default out of the module source rather than
    # trusting a reimplementation of it here.
    src = (_REPO / 'nfl/tools/refresh_boards.py').read_text()
    check("--week is declared with default=None",
          "'--week', type=int, default=None" in src,
          'a literal week default is a date that expires')
    check('and the reason is recorded next to it',
          'A week default is a date default' in src)


def test_B_the_week_is_resolved_once_and_written_back():
    print('\nB. the shape of my own first fix, which was wrong')
    src = (_REPO / 'nfl/tools/refresh_boards.py').read_text()
    check('a.week is assigned, not just read into a local',
          'a.week = current_week(a.season)' in src,
          'the first version left a.week None and ORC.plan/ORC.run filtered '
          'the snapshot on the string "None"')
    check('and the three consumers all read a.week',
          src.count('a.week') >= 3, src.count('a.week'))


def test_C_current_week_finds_the_first_week_with_a_future_kickoff():
    print('\nC. resolution against the real schedule')
    try:
        wk = R.current_week(2026)
    except SystemExit as e:
        blocked('current_week', f'schedule unavailable here: {e}')
        return
    check('a week is resolved', isinstance(wk, int) and wk >= 1, wk)
    check('and it is not week 1, because week 1 has no future kickoff',
          wk > 1, wk)
    earlier = R.upcoming(2026, wk - 1) if wk > 1 else []
    check('the week before it has no upcoming games',
          not earlier, earlier[:3])
    check('the resolved week does', len(R.upcoming(2026, wk)) > 0)


def test_D_an_empty_match_is_not_a_usage_error():
    print('\nD. the refusal that blamed the operator')
    src = (_REPO / 'nfl/tools/refresh_boards.py').read_text()
    check('NO_UPCOMING_GAMES_IN_WINDOW exists',
          'NO_UPCOMING_GAMES_IN_WINDOW' in src)
    check('and says the flag was supplied',
          'The flag was supplied and matched nothing' in src)
    check('NO_GAME_SELECTED survives for the case it actually describes',
          'NO_GAME_SELECTED' in src)
    check('the scan is bounded so a broken schedule cannot spin',
          '_MAX_WEEK' in src)
    check('and a schedule with no future game says so, not a usage error',
          'NO_WEEK_HAS_A_FUTURE_KICKOFF' in src)
