"""classic_slate_state: quarterback order from the captured chart, proven in the shape it fails.

The week-4 defect: a starter reported OUT kept rank 1, so his backup was discounted as a backup,
and a practice-squad quarterback on no chart took the passing volume from usage history.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_slate_state as C   # noqa: E402
from nfl.tests._controls import observe          # noqa: E402

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


CHART = {'CHI': {'order': ['W', 'B', 'K'], 'dt': 'd', 'capture_id': 'c'},
         'NYJ': {'order': ['G', 'L'], 'dt': 'd', 'capture_id': 'c'}}
DEPTH = {'S': {'pregame_rank': 1}}


def test_01_a_reported_out_starter_vacates_rank_one():
    r = C._qb_rank('QB', 'CHI', 'B', CHART, DEPTH, out_gsis={'W'})
    check('positive control: QB1 reported OUT -> his QB2 ranks 1', r == 1, str(r))
    r = C._qb_rank('QB', 'CHI', 'B', CHART, DEPTH, out_gsis=set())
    check('  negative control: nobody out -> QB2 stays rank 2', r == 2, str(r))
    r = C._qb_rank('QB', 'CHI', 'S', CHART, DEPTH, out_gsis={'W'})
    check('  a quarterback absent from a chart that covers his club ranks below everyone listed',
          r == 3, str(r))
    r = C._qb_rank('WR', 'CHI', 'S', CHART, DEPTH, out_gsis={'W'})
    check('  other positions keep the usage-history rank', r == 1, str(r))


def test_02_next_healthy_gets_starter_evidence_only_behind_an_out_starter():
    c = C._next_healthy_context('QB', 'CHI', 'B', CHART, {'W'})
    observe('nfl.tools.classic_slate_state:_next_healthy_context:DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT', c)
    check('positive control: QB1 out -> next healthy QB carries the next-healthy tier',
          c.get('state') == C.NEXT_HEALTHY_TIER and c['in_predicted_starting_group'] is True, str(c))
    check('  negative control: QB1 healthy -> no starter evidence for anyone',
          C._next_healthy_context('QB', 'NYJ', 'L', CHART, set()) == {}
          and C._next_healthy_context('QB', 'NYJ', 'G', CHART, set()) == {})
    check('  the third quarterback behind an out starter is not named',
          C._next_healthy_context('QB', 'CHI', 'K', CHART, {'W'}) == {})
    check('  and the tier is never the owner-relayed or confirmed label',
          C.NEXT_HEALTHY_TIER not in ('OWNER_RELAYED_CONFIRMED_STARTER', 'CONFIRMED_INACTIVE'))


CHART_POS = {'LA': {'order': ['Q'], 'by_pos': {'WR': ['PUKA', 'ADAMS', 'M'], 'TE': []},
                    'dt': 'd', 'capture_id': 'c'}}
USAGE = {'PUKA': {'pregame_rank': 3}, 'ADAMS': {'pregame_rank': 1}, 'M': {'pregame_rank': 2},
         'X': {'pregame_rank': 4}}


def test_03_skill_rank_is_the_better_of_usage_and_chart():
    r = C._qb_rank('WR', 'LA', 'PUKA', CHART_POS, USAGE)
    check('positive control: returning WR1, usage rank 3, chart rank 1 -> rank 1', r == 1, str(r))
    r = C._qb_rank('WR', 'LA', 'ADAMS', CHART_POS, USAGE)
    check('  negative control: usage 1 beats chart 2 -> rank 1, never demoted to 2', r == 1, str(r))
    r = C._qb_rank('WR', 'LA', 'M', CHART_POS, USAGE)
    check('  usage 2, chart 3 -> 2 (the chart never worsens a rank)', r == 2, str(r))
    r = C._qb_rank('WR', 'LA', 'X', CHART_POS, USAGE)
    check('  off the chart -> usage rank unchanged', r == 4, str(r))
    r = C._qb_rank('WR', 'LA', 'M', CHART_POS, USAGE, out_gsis={'PUKA', 'ADAMS'})
    check('  chart rank counts only receivers not reported out', r == 1, str(r))
    r = C._qb_rank('TE', 'LA', 'NOBODY', CHART_POS, {})
    check('  no usage and no chart rank -> None, not zero and not rank 1', r is None, str(r))
    r = C._qb_rank('WR', 'NYJ', 'PUKA', CHART, USAGE)
    check('  a club chart with no position block falls back to usage', r == 3, str(r))
    for g in USAGE:
        u = USAGE[g]['pregame_rank']
        check(f'  invariant: rank({g}) <= usage rank {u}',
              C._qb_rank('WR', 'LA', g, CHART_POS, USAGE) <= u)


def test_04_a_chart_alone_lifts_only_into_formation_slots():
    chart = {'CIN': {'order': [], 'by_pos': {'RB': ['B', 'P', 'T'], 'WR': ['1', '2', '3', '4', '5']}, 'dt': 'd', 'capture_id': 'c'}}
    usage = {'B': {'pregame_rank': 1}, 'P': {'pregame_rank': 2}}
    r = C._qb_rank('RB', 'CIN', 'T', chart, usage)
    check('positive control: a no-usage RB3 behind two healthy backs gets no rank from the chart', r is None, str(r))
    r = C._qb_rank('RB', 'CIN', 'T', chart, usage, out_gsis={'B'})
    check('  negative control: with RB1 out the same back is next man up (RB2) and is lifted', r == 2, str(r))
    r = C._qb_rank('WR', 'CIN', '4', chart, {})
    check('  a no-usage WR4 is lifted (three WRs start, one spare)', r == 4, str(r))
    r = C._qb_rank('WR', 'CIN', '5', chart, {})
    check('  a no-usage WR5 is not', r is None, str(r))
    r = C._qb_rank('RB', 'CIN', 'T', chart, {'T': {'pregame_rank': 3}})
    check('  a player WITH usage history keeps the better of usage and chart', r == 3, str(r))


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
