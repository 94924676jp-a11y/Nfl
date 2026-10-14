#!/usr/bin/env python3.12
"""BENCH-D4: prospective benchmark game clusters.

per_game carries no away/home fields, so the clubs come from the game id; a club with no game raises, never becoming a
cluster of its own (which scored 8 Classic games as 16 independent clusters). Every prospective scorer uses the helper."""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.benchmark.clusters import club_to_game, game_of  # noqa: E402

PASSED = FAILED = 0
B = _REPO / 'nfl' / 'research' / 'benchmark'


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def test_clubs_come_from_the_game_id():
    m = club_to_game({'2026_04_ARI_NYG': {'state': 'PASS'}, '2026_04_LA_PHI': {}})
    check(m == {'ARI': '2026_04_ARI_NYG', 'NYG': '2026_04_ARI_NYG', 'LA': '2026_04_LA_PHI', 'PHI': '2026_04_LA_PHI'},
          f'both clubs of each game map to it ({m})')
    check(club_to_game({'g': {'away': 'X', 'home': 'Y'}}) == {'X': 'g', 'Y': 'g'}, 'explicit away/home are still read')
    check(club_to_game(None) == {}, 'no per_game -> empty map')


def test_a_club_without_a_game_refuses():
    try:
        game_of({'ARI': 'g1'}, 'NYG')
        check(False, 'an unmapped club raises')
    except KeyError as e:
        check('CLUB_WITHOUT_GAME' in str(e), f'an unmapped club raises a named error ({e})')
    try:
        club_to_game({'2026_04_ARI_NYG': {}, '2026_05_ARI_SF': {}})
        check(False, 'a club in two games raises')
    except ValueError:
        check(True, 'a club in two games of one slate raises')


def test_the_w4_classic_slate_is_eight_games():
    d = json.loads((_REPO / 'nfl/dfs/salaries/DK_2026W4_EARLY_DRAWS.json').read_text())
    m = club_to_game(d['per_game'])
    clubs = {k.rsplit('|', 1)[1] for k in d['draws']}
    check(len(set(m.values())) == 8 and clubs <= set(m), f'16 clubs map to 8 games ({len(clubs)} clubs, {len(set(m.values()))} games)')


def test_every_prospective_scorer_uses_the_helper():
    for f in ('four_arm.py', 'prospective_scorecard.py', 'joint_calibration.py'):
        s = (B / f).read_text()
        check('club_to_game(' in s and 'game_of(' in s and 'club2game.get(' not in s and 'club2game[' not in s,
              f'{f} uses club_to_game/game_of and has no club-sized fallback')
    fa = json.loads((B / 'FOUR_ARM_EXPLORATORY.json').read_text())
    check(fa['pooled']['n_games'] == 11, f"the committed four-arm benchmark counts 11 games ({fa['pooled']['n_games']})")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
