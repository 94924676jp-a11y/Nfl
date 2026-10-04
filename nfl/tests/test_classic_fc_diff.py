"""classic_fc_diff: a changed FC number is classified against OUR state and never becomes an input."""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import classic_fc_diff as D  # noqa: E402

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


def _ours(proj, chart=None, usage=None, prank=None, av='UNKNOWN_ACTIVE_STATE'):
    return {'proj': proj, 'chart_rank': chart, 'usage_rank': usage, 'projection_rank': prank, 'availability': av, 'designation': None}


def test_01_classification():
    c, _ = D.classify({'FC Proj': 0.0, 'pDepth': 'TE3'}, {'FC Proj': 7.9, 'pDepth': 'TE2'}, _ours(10.94, 3, 1, 1),
                      ['projection 0 -> 7.9', 'pDepth TE3 -> TE2', 'zero -> nonzero'])
    check('Higbee shape: FC now projects a player we already project -> OUR_STATE_SUPPORTED', c == 'OUR_STATE_SUPPORTED', c)
    c, _ = D.classify({'FC Proj': 3.97, 'pDepth': 'TE2'}, {'FC Proj': 0.0, 'pDepth': 'TE3'}, _ours(0.29, 2, 3, 2),
                      ['projection', 'pDepth TE2 -> TE3', 'nonzero -> zero'])
    check('Davis Allen shape: FC moved onto our number -> OUR_STATE_SUPPORTED', c == 'OUR_STATE_SUPPORTED', c)
    c, _ = D.classify({'FC Proj': 12.0, 'pDepth': 'WR2'}, {'FC Proj': 0.0, 'pDepth': 'WR2'}, _ours(11.0, 2, 2, 2),
                      ['projection', 'nonzero -> zero'])
    check('positive control: FC zeroes a player we still play -> FC_HAS_NEW_ROLE_INFORMATION', c == 'FC_HAS_NEW_ROLE_INFORMATION', c)
    c, _ = D.classify({'FC Proj': 0.1, 'pDepth': 'QB2'}, {'FC Proj': 0.1, 'pDepth': 'QB3'}, _ours(0.05, 2, 2, 2), ['pDepth QB2 -> QB3'])
    check('FC depth departs from our captured chart -> OUR_EVIDENCE_MAY_BE_STALE', c == 'OUR_EVIDENCE_MAY_BE_STALE', c)
    c, why = D.classify({'FC Proj': 22.2, 'pDepth': 'WR1', 'VegasPts': 23.25}, {'FC Proj': 20.7, 'pDepth': 'WR1', 'VegasPts': 23.25},
                        _ours(22.8, 1, 3, 1), ['projection'])
    check('a bare FC number move is METHODOLOGY and does not blame an unchanged sportsbook total',
          c == 'METHODOLOGY' and 'both times' in why, why)


def test_zz_every_check_passed():
    """The module's own counter, re-raised so a failure turns this module RED."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
