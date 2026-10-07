#!/usr/bin/env python3.12
"""Hard Rock capture contract and settlement states (nfl/market/showdown_prop_shadow.py). Downstream only.

    python3.12 nfl/tests/test_prop_capture_contract.py

  contract    no sidecar / missing field / not Hard Rock / hash mismatch -> refused by name; a complete one passes
  settlement  over, under, PUSH on an integer line, VOID_NO_ACTION when the player did not participate,
              UNRESOLVED when no official actual exists (never a loss, never a win)
  order       a prop seal at or after kickoff is refused; a seal with no worlds is refused
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.market import showdown_prop_shadow as PS  # noqa: E402

PASSED = FAILED = 0


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _refused(fn, code, msg):
    try:
        fn()
        check(False, f'{msg}: not refused')
    except SystemExit as e:
        check(str(e).startswith(code), f'{msg} ({str(e)[:90]})')


def _board(td, side=None):
    b = pathlib.Path(td) / 'HR_X_Y_BOARD.csv'
    b.write_text('market,selection,points,over,under,ts_utc\nplayer_receptions,A B,4.5,-110,-110,2026-10-12T15:00:00Z\n')
    if side is not None:
        (pathlib.Path(td) / 'HR_X_Y_BOARD.csv.CAPTURE.json').write_text(json.dumps(side))
    return b


def _side(b, **kw):
    s = {'book': 'Hard Rock Bet', 'jurisdiction': 'FL', 'product': 'sportsbook app', 'settlement_rules':
         'house rules page as captured 2026-10-12 (sha256 ...)', 'captured_at_utc': '2026-10-12T15:00:00Z',
         'captured_by': 'networked agent', 'board_sha256': hashlib.sha256(b.read_bytes()).hexdigest()}
    s.update(kw)
    return s


def test_contract():
    with tempfile.TemporaryDirectory() as td:
        b = _board(td)
        _refused(lambda: PS.capture_contract(b), 'CAPTURE_CONTRACT_INCOMPLETE', 'a board with no sidecar is refused')
        b = _board(td, _side(_board(td), jurisdiction=''))
        _refused(lambda: PS.capture_contract(b), 'CAPTURE_CONTRACT_INCOMPLETE', 'a missing jurisdiction is refused')
        b = _board(td, _side(_board(td), book='Other Book'))
        _refused(lambda: PS.capture_contract(b), 'BOOK_NOT_HARD_ROCK', 'a board from another book is refused')
        b = _board(td, _side(_board(td), board_sha256='0' * 64))
        _refused(lambda: PS.capture_contract(b), 'BOARD_HASH_MISMATCH', 'a sidecar for other bytes is refused')
        b = _board(td, _side(_board(td)))
        c = PS.capture_contract(b)
        check(c['book'] == 'Hard Rock Bet' and c['settlement_rules'], 'a complete contract passes and is returned')


def test_settlement_states():
    r = {'line': 4.5}
    check(PS.settle_row(r, {'value': 5, 'participated': True}) == 'WIN_OVER', 'over')
    check(PS.settle_row(r, {'value': 4, 'participated': True}) == 'WIN_UNDER', 'under')
    check(PS.settle_row({'line': 4.0}, {'value': 4, 'participated': True}) == 'PUSH', 'exactly on an integer line is a PUSH')
    check(PS.settle_row(r, {'value': 0, 'participated': False}) == 'VOID_NO_ACTION',
          'did not participate -> VOID_NO_ACTION, not an under')
    check(PS.settle_row(r, None) == 'UNRESOLVED', 'no official actual -> UNRESOLVED, not a loss')
    check(PS.settle_row(r, {'value': None, 'participated': None}) == 'UNRESOLVED', 'a blank actual is not a zero')
    with tempfile.TemporaryDirectory() as td:
        (pathlib.Path(td) / 'PROP_GRADING_LEDGER.jsonl').write_text('\n'.join(json.dumps(x) for x in (
            {'player': 'A', 'team': 'X', 'our_variable': 'receptions', 'line': 4.5},
            {'player': 'B', 'team': 'X', 'our_variable': 'receptions', 'line': 3.0},
            {'player': 'C', 'team': 'Y', 'our_variable': 'receptions', 'line': 2.5},
            {'player': 'D', 'team': 'Y', 'our_variable': 'receptions', 'line': 1.5})) + '\n')
        acts = pathlib.Path(td) / 'act.json'
        acts.write_text(json.dumps({'A|X': {'receptions': 6, 'participated': True}, 'B|X': {'receptions': 3, 'participated': True},
                                    'C|Y': {'receptions': 0, 'participated': False}}))
        out = PS.settle(td, acts)
        check(out['settled'] == {'WIN_OVER': 1, 'PUSH': 1, 'VOID_NO_ACTION': 1, 'UNRESOLVED': 1},
              f"ledger settles into the four states plus UNRESOLVED ({out['settled']})")


def test_seal_order():
    with tempfile.TemporaryDirectory() as td:
        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat()
        _refused(lambda: PS.seal(td, td, 'X_Y', past), 'PROP_SEAL_AFTER_KICKOFF', 'a seal after kickoff is refused')
        fut = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat()
        _refused(lambda: PS.seal(td, td, 'X_Y', fut), 'PROP_SEAL_NO_WORLDS', 'a seal with no simulated worlds is refused')


if __name__ == '__main__':
    for t in (test_contract, test_settlement_states, test_seal_order):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
