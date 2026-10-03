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


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
