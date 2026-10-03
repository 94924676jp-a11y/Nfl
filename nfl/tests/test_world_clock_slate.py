"""world_clock.for_target: the slate-relative freshness verdict, proven in the shape it fails.

Positive control: a seeded schedule whose earlier-week game has no score in the warehouse ->
EVIDENCE_BEHIND_THE_SLATE. Negative control: a same-week game already played, with every earlier
game scored -> EVIDENCE_COVERS_THE_SLATE (the false red semantic_freshness gives on a Saturday).
Empty: a target week with nothing before it -> BLOCKED/EMPTY_INPUT, never PASS.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State   # noqa: E402
from nfl.production import world_clock as W           # noqa: E402
from nfl.tests._controls import observe               # noqa: E402

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


def _seed(scored_games):
    td = pathlib.Path(tempfile.mkdtemp(prefix='wcslate_'))
    tg = td / 'TEAM_GAME.json'
    rows = []
    for g in scored_games:
        for club in g.split('_')[2:]:
            rows.append({'season': 2026, 'game_id': g, 'club': club, 'points': 20, 'week': int(g.split('_')[1])})
    tg.write_text(json.dumps({'rows': rows}))
    return tg


SCHED = [
    {'season': 2026, 'week': 3, 'game_id': '2026_03_AAA_BBB', 'gameday': '2026-09-21'},
    {'season': 2026, 'week': 3, 'game_id': '2026_03_CCC_DDD', 'gameday': '2026-09-21'},
    {'season': 2026, 'week': 4, 'game_id': '2026_04_EEE_FFF', 'gameday': '2026-10-01'},
    {'season': 2026, 'week': 4, 'game_id': '2026_04_AAA_CCC', 'gameday': '2026-10-04'},
]


def test_01_a_missing_earlier_game_blocks_the_slate():
    saved = W.TEAM_GAME
    try:
        W.TEAM_GAME = _seed(['2026_03_AAA_BBB'])
        o = W.for_target(2026, 4, as_of='2026-10-03', rows=SCHED)
        observe('nfl.production.world_clock:for_target:EVIDENCE_BEHIND_THE_SLATE', o)
        check('positive control: week-3 CCC@DDD unscored -> EVIDENCE_BEHIND_THE_SLATE',
              o.state is State.FAIL and o.code == 'EVIDENCE_BEHIND_THE_SLATE'
              and o.evidence['missing_games'] == ['2026_03_CCC_DDD'], f'{o.state} {o.code} {o.evidence}')
    finally:
        W.TEAM_GAME = saved


def test_02_a_same_week_thursday_game_does_not_block():
    saved = W.TEAM_GAME
    try:
        W.TEAM_GAME = _seed(['2026_03_AAA_BBB', '2026_03_CCC_DDD'])
        o = W.for_target(2026, 4, as_of='2026-10-03', rows=SCHED)
        check('negative control: weeks < 4 all scored, Thursday week-4 game unscored -> COVERS',
              o.state is State.PASS and o.code == 'EVIDENCE_COVERS_THE_SLATE'
              and o.evidence['same_week_games_already_played'] == ['2026_04_EEE_FFF'],
              f'{o.state} {o.code}')
        w = W.semantic_freshness(as_of='2026-10-03', rows=SCHED)
        check('  and the world-relative verdict on the same seed is the false red this replaces '
              'for slate gating', w.state is State.FAIL and w.code == 'EVIDENCE_BEHIND_THE_WORLD',
              f'{w.state} {w.code}')
    finally:
        W.TEAM_GAME = saved


def test_03_nothing_before_the_target_week_is_not_a_pass():
    o = W.for_target(2026, 3, as_of='2026-09-20', rows=SCHED)
    observe('nfl.production.world_clock:for_target:SLATE_FRESHNESS_EMPTY_INPUT', o)
    check('no consumed game -> BLOCKED/EMPTY_INPUT', o.state is State.BLOCKED
          and o.code == 'SLATE_FRESHNESS_EMPTY_INPUT', f'{o.state} {o.code}')


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
