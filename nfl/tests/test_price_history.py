#!/usr/bin/env python3.12
"""A price may only be compared against an already-sealed forecast, and one pass is not a line.

`capture/registry.py` already declares the Hard Rock snapshot DOWNSTREAM_COMPARATOR_ONLY with the
right reason -- a model that has seen the line is no longer independent evidence about the line -- and
a declaration is not a mechanism. The load-bearing check here is arithmetic: a seal written AFTER the
price was captured makes the comparison meaningless, and `comparable()` must refuse it.

The other checks exist because of a defect this module already committed. The first version keyed
observations on `price_id` alone, which refused 791 of 969 rows: two-sided markets carry `over_id` and
`under_id` and leave `price_id` empty. Guessing a field name instead of reading the schema is the
named defect class, so the side-keying is pinned here.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.market import price_history as PH  # noqa: E402

from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _board(d, name, rows):
    p = d / name
    with p.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(PH.REQUIRED_BOARD_COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in PH.REQUIRED_BOARD_COLUMNS})
    return p


def _row(**kw):
    base = {'market': 'total_points', 'selection': 'Game', 'points': '44.5', 'is_main': 'True',
            'over': '-110', 'under': '-110', 'price': '', 'ts_utc': '2026-09-21T22:00:00+00:00',
            'age_min': '1.0', 'price_id': '', 'over_id': 'g:hard_rock:total_points:over_44_5',
            'under_id': 'g:hard_rock:total_points:under_44_5'}
    base.update(kw)
    return base


@check('a price captured before the seal is refused')
def t_price_before_seal():
    seal = {'written_at': '2026-09-21T22:30:00+00:00', 'kickoff_utc': '2026-09-22T00:15:00+00:00'}
    o = PH.comparable(seal, {'ts_utc': '2026-09-21T22:00:00+00:00'})
    assert o.state.name == 'FAIL' and o.code == 'PRICE_PREDATES_THE_SEAL', o.code
    ok = PH.comparable(seal, {'ts_utc': '2026-09-21T23:00:00+00:00'})
    assert ok.state.name == 'PASS', f'{ok.code}: {ok.detail}'
    assert ok.value['minutes_seal_to_price'] == 30.0
    return ('a line that existed 30 minutes before the seal is refused; one captured 30 minutes '
            'after it is comparable')


@check('an in-play price is refused')
def t_post_kickoff():
    seal = {'written_at': '2026-09-21T22:00:00+00:00', 'kickoff_utc': '2026-09-22T00:15:00+00:00'}
    o = PH.comparable(seal, {'ts_utc': '2026-09-22T01:00:00+00:00'})
    assert o.state.name == 'FAIL' and o.code == 'PRICE_IS_POST_KICKOFF', o.code
    return 'a price captured after kickoff is not the price the forecast could have been acted on at'


@check('an unparseable timestamp on either side FAILs rather than defaulting')
def t_unparseable():
    o = PH.comparable({'written_at': 'sometime'}, {'ts_utc': '2026-09-21T22:00:00+00:00'})
    assert o.state.name == 'FAIL' and o.code == 'COMPARABILITY_TIMESTAMP_UNPARSEABLE', o.code
    o2 = PH.comparable({'written_at': '2026-09-21T22:00:00+00:00'}, {'ts_utc': None})
    assert o2.state.name == 'FAIL', o2.code
    return 'neither side may be missing a time and be waved through'


@check('a two-sided market yields both sides, keyed separately')
def t_two_sided():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _board(d, 'HR_X_BOARD_a.csv', [_row()])
    o = PH.load_board(p)
    assert o.state.name == 'PASS', f'{o.code}: {o.detail}'
    assert o.value['n_observations'] == 2, (
        f'one two-sided row produced {o.value["n_observations"]} observations. Over and under are '
        f'two priced sides with two keys and they move independently.')
    sides = {ob['side']: ob for ob in o.value['observations']}
    assert set(sides) == {'OVER', 'UNDER'}
    assert sides['OVER']['price'] == '-110' and sides['UNDER']['price'] == '-110'
    assert sides['OVER']['price_id'] != sides['UNDER']['price_id']
    return 'over and under become separate observations with separate keys and their own prices'


@check('a one-sided market still works, and 791 rows are no longer refused')
def t_one_sided_and_real_board():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _board(d, 'HR_X_BOARD_b.csv', [
        _row(market='moneyline', points='', over='', under='', price='-300',
             price_id='g:hard_rock:moneyline:lar', over_id='', under_id='')])
    o = PH.load_board(p)
    assert o.state.name == 'PASS' and o.value['n_observations'] == 1, o.code
    assert o.value['observations'][0]['side'] == 'SINGLE'
    real = _REPO / 'nfl/market/raw/HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv'
    if real.exists():
        ro = PH.load_board(real)
        assert ro.state.name == 'PASS', (
            f'the real board is refused: {ro.code}. It was refused once already because price_id '
            f'was required of every row; if that has come back the 12 two-sided market types are '
            f'silently gone again.')
        assert ro.value['n_observations'] > 969, (
            f'{ro.value["n_observations"]} observations from 969 rows. Two-sided rows must each '
            f'yield two, so the count has to EXCEED the row count.')
        return (f'one-sided row yields 1 side; the real board yields '
                f'{ro.value["n_observations"]} observations from 969 rows')
    return 'one-sided row yields 1 side (real board not present)'


@check('a row with a time but no key anywhere is refused whole')
def t_no_key_refused():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _board(d, 'HR_X_BOARD_c.csv', [_row(), _row(price_id='', over_id='', under_id='')])
    o = PH.load_board(p)
    assert o.state.name == 'FAIL' and o.code == 'BOARD_UNDATED_OR_UNKEYED_ROWS', o.code
    assert 'NO_KEY' in o.evidence['examples'][0]['why']
    return 'one unkeyable row refuses the file rather than quietly halving the board'


@check('closing-line value refuses one capture pass instead of reporting no movement')
def t_clv_refuses():
    if not PH.STORE.exists():
        raise AssertionError(f'{PH.STORE} not built; run nfl/market/price_history.py')
    art = json.loads(PH.STORE.read_text())
    pid = next(iter(art['markets']))
    o = PH.closing_line_value(pid, store=art)
    if o.state.name == 'PASS':
        assert o.value['n_passes'] >= PH.MIN_PASSES_FOR_MOVEMENT
        return f'movement is now measurable over {o.value["n_passes"]} passes; this check retires'
    assert o.code == PH.CLV_UNCOMPUTABLE, o.code
    assert o.evidence['cause'] == 'DATA' and 'OUT-043' in o.evidence['outbox']
    assert art['n_markets_with_movement_measurable'] == 0, (
        'some market now has movement, so the blanket refusal is wrong for it')
    return (f'all {art["n_markets"]} priced sides were captured once; a movement of zero would be '
            f'reporting an absence as a measurement')


@check('two passes far enough apart do produce movement')
def t_two_passes():
    d = pathlib.Path(tempfile.mkdtemp())
    _board(d, 'HR_X_BOARD_t1.csv', [_row(ts_utc='2026-09-21T20:00:00+00:00', over='-110')])
    _board(d, 'HR_X_BOARD_t2.csv', [_row(ts_utc='2026-09-21T23:00:00+00:00', over='-130')])
    saved = PH.STORE
    try:
        PH.STORE = d / 'store.json'
        o = PH.build(sorted(str(x) for x in d.glob('*BOARD*.csv')))
        assert o.state.name == 'PASS', o.code
        art = json.loads(PH.STORE.read_text())
        pid = 'g:hard_rock:total_points:over_44_5'
        c = PH.closing_line_value(pid, store=art)
        assert c.state.name == 'PASS', f'{c.code}: {c.detail}'
        assert c.value['opening']['price'] == '-110' and c.value['closing']['price'] == '-130'
        assert 'last price CAPTURED' in c.value['CLOSING_MEANS'], (
            'the artifact must say that the last observed pass is not necessarily the close')
    finally:
        PH.STORE = saved
    return 'three hours apart gives two passes, -110 opening to -130 closing, labelled as captured'


@check('rows inside one scrape are one pass, not movement')
def t_same_pass():
    d = pathlib.Path(tempfile.mkdtemp())
    _board(d, 'HR_X_BOARD_s.csv', [_row(ts_utc='2026-09-21T22:00:00+00:00', over='-110'),
                                   _row(ts_utc='2026-09-21T22:08:00+00:00', over='-112')])
    saved = PH.STORE
    try:
        PH.STORE = d / 'store.json'
        PH.build(sorted(str(x) for x in d.glob('*BOARD*.csv')))
        art = json.loads(PH.STORE.read_text())
        m = art['markets']['g:hard_rock:total_points:over_44_5']
        assert m['n_observations'] == 2 and m['n_capture_passes'] == 1, (
            f'{m["n_capture_passes"]} passes from two rows 8 minutes apart. The one real board '
            f'spans 8.5 minutes in a single scrape, so treating that as movement would invent a '
            f'line history out of one capture.')
    finally:
        PH.STORE = saved
    return 'two rows 8 minutes apart are two observations and one pass'


@check('this module cannot push a price back into a projection')
def t_one_direction():
    src = (_REPO / 'nfl/market/price_history.py').read_text()
    body = src.split('"""', 2)[2]
    for bad in ('proj_v1', 'DK_WEEK3_PROJ', 'player_prior', 'role_state'):
        assert bad not in body, (
            f'{bad} is reachable from the price-history module body. Comparison runs one way: a '
            f'sealed forecast is scored against a price and the price never travels back.')
    art = json.loads(PH.STORE.read_text())
    assert 'no projection is adjusted toward a price' in art['NEVER']
    return 'no projection module is importable from here, and the artifact states the direction'


# EXPOSE EVERY CHECK TO run_suite, which is the authoritative execution path. Without this the
# runner reports `0 fn, NO TALLY` and executes NONE of them, while a direct run of this file prints
# a confident pass. See nfl/tests/_registry.py.
_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    # The tally tripwire, in this module's own source because run_suite recognises it by shape.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001  -- already printed and counted by the wrapper
            pass
    test_zz_every_check_passed.__doc__
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
