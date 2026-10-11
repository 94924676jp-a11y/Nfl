#!/usr/bin/env python3.12
"""An ACTIVE player can carry a structured workload expectation, and no file is certified while it is unmodelled
(task #45 P1-1, owner ruling 2026-10-11: "active does not mean full workload").

What is proven:
  1. A packet item can say ACTIVE + participation LIMITED with the reporting it came from, and resolve() carries it.
  2. The schema refuses: participation on an INACTIVE item, an unknown expectation, a LIMITED expectation with no detail.
  3. The release record names a structured LIMITED expectation as UNMODELLED_EVIDENCE when the projection row carries
     no participation model, and stops naming it when one is consumed. A FULL expectation is never flagged.
Nothing here turns "limited" into a snap share. That needs the measured model (P1-2), not this schema.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import test_classic_release as TR  # noqa: E402  (synthetic chain builder)
from nfl.tools import classic_release as R  # noqa: E402
from nfl.tools import sunday_evidence as SE  # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _packet(td, players):
    p = pathlib.Path(td) / 'pk.json'
    p.write_text(json.dumps({'packet_id': 'T', 'source': 'OWNER_RELAYED', 'received_at': '2026-10-11T16:10:00Z',
                             'players': players}))
    return p


LIMITED = {'name': 'Terry McLaurin', 'team': 'WAS', 'status': 'ACTIVE', 'cited': 'AGGREGATOR',
           'participation': {'expectation': 'LIMITED', 'detail': 'limited snaps (Garafolo)',
                             'quote': 'likely not a full go'}}


def test_01_a_limited_active_item_loads_and_resolves():
    print('\n01. ACTIVE + LIMITED loads, and the expectation survives resolution')
    with tempfile.TemporaryDirectory() as d:
        o = SE.load(_packet(d, [LIMITED]))
    check('the packet loads', o.state.value == 'PASS', o.detail)
    pool = [{'dk_id': '44418755', 'dk_name': 'Terry McLaurin', 'team': 'WAS', 'dk_pos': 'WR'}]
    r = SE.resolve(o.value, pool)
    res = (r.value or {}).get('players', {}).get('44418755') or {}
    check('resolution keeps the claim ACTIVE and its status a present one',
          res.get('claim') == 'ACTIVE' and res.get('status') not in SE.AV.ABSENT_STATUSES, res)
    check('and carries the participation expectation verbatim', res.get('participation') == LIMITED['participation'],
          res.get('participation'))


def test_02_the_schema_refuses_what_it_cannot_mean():
    print('\n02. refusals')
    cases = [
        ('participation on an INACTIVE item', dict(LIMITED, status='INACTIVE')),
        ('an unknown expectation', dict(LIMITED, participation={'expectation': 'HALF', 'detail': 'x'})),
        ('LIMITED with no detail or quote', dict(LIMITED, participation={'expectation': 'LIMITED'})),
    ]
    for label, item in cases:
        with tempfile.TemporaryDirectory() as d:
            o = SE.load(_packet(d, [item]))
        check(f'refused: {label}', o.state.value == 'FAIL' and o.code == 'EVIDENCE_PACKET_SCHEMA', (o.code, o.detail))
    with tempfile.TemporaryDirectory() as d:
        o = SE.load(_packet(d, [dict(LIMITED, participation={'expectation': 'FULL'})]))
    check('negative control: FULL needs no detail', o.state.value == 'PASS', o.detail)
    with tempfile.TemporaryDirectory() as d:
        o = SE.load(_packet(d, [{k: v for k, v in LIMITED.items() if k != 'participation'}]))
    check('negative control: an item without participation still loads (old packets unchanged)', o.state.value == 'PASS')


def _with_participation(d, expectation, modelled):
    """The synthetic certified chain with one player carrying a structured expectation; hashes re-linked."""
    d = pathlib.Path(d)
    slate, pk = TR._synthetic(d)
    b = d / f'DK_{slate}_EARLY'
    st = json.loads(pathlib.Path(f'{b}_STATE.json').read_text())
    st['players']['1']['current_availability']['resolution'] = {'participation': {'expectation': expectation,
                                                                                  'detail': 'reported'}}
    pathlib.Path(f'{b}_STATE.json').write_text(json.dumps(st))
    pathlib.Path(f'{b}_PROJ.json').write_text(json.dumps(
        {'rows': {'1': {'participation_model': {'id': 'X'}} if modelled else {}}}))
    # re-link every hash that depends on STATE and PROJ, as a real rebuild would
    sh = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()  # noqa: E731
    dr = json.loads(pathlib.Path(f'{b}_DRAWS.json').read_text())
    dr.update(state_sha256=sh(f'{b}_STATE.json'), projection_sha256=sh(f'{b}_PROJ.json'))
    pathlib.Path(f'{b}_DRAWS.json').write_text(json.dumps(dr))
    import numpy as np
    with open(f'{b}_WORLDS.npz', 'wb') as fh:
        np.savez_compressed(fh, stats=np.zeros((1, 1, 1), dtype=np.int16), points=np.zeros((1, 1, 2)),
                            meta=np.frombuffer(json.dumps({'projection_sha256': sh(f'{b}_PROJ.json')}).encode(),
                                               dtype=np.uint8))
    bk = {'inputs_sha256': {'STATE.json': sh(f'{b}_STATE.json'), 'PROJ.json': sh(f'{b}_PROJ.json'),
                            'DRAWS.json': sh(f'{b}_DRAWS.json'), 'WORLDS.npz': sh(f'{b}_WORLDS.npz')}}
    pathlib.Path(f'{b}_RESEARCH_BOOK.json').write_text(json.dumps(bk))
    sl = json.loads(pathlib.Path(f'{b}_SEAL.json').read_text())
    sl.update(projection_sha256=sh(f'{b}_PROJ.json'), worlds_sha256=sh(f'{b}_WORLDS.npz'),
              research_book_sha256=sh(f'{b}_RESEARCH_BOOK.json'))
    pathlib.Path(f'{b}_SEAL.json').write_text(json.dumps(sl))
    po = json.loads(pathlib.Path(f'{b}_PORTFOLIOS.json').read_text())
    po.update(inputs_sha256={'state': sh(f'{b}_STATE.json'), 'proj': sh(f'{b}_PROJ.json'),
                             'draws': sh(f'{b}_DRAWS.json')}, research_book_sha256=sh(f'{b}_RESEARCH_BOOK.json'))
    pathlib.Path(f'{b}_PORTFOLIOS.json').write_text(json.dumps(po))
    return slate, pk


def test_03_the_release_record_names_an_unmodelled_restriction():
    print('\n03. a LIMITED expectation the projection did not model blocks certification; a modelled one does not')
    real_wa, real_def = R.world_accounting, R.OPEN_FORECAST_DEFECTS
    now = dt.datetime(2099, 1, 1, 16, 0, tzinfo=dt.timezone.utc)
    try:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = TR._clean_accounting, {}
        for exp, modelled, want in (('LIMITED', False, R.CURRENT_BUT_UNCERTIFIED),
                                    ('LIMITED', True, R.CURRENT_AND_CERTIFIED),
                                    ('FULL', False, R.CURRENT_AND_CERTIFIED)):
            with tempfile.TemporaryDirectory() as d:
                slate, pk = _with_participation(d, exp, modelled)
                r = R.evaluate(slate, latest_packet=pk, out_dir=d, now=now)
            flagged = any('UNMODELLED_EVIDENCE' in x for x in r['reasons']['uncertified'])
            check(f'{exp}, participation model consumed={modelled} -> {want}',
                  r['release_state'] == want and flagged == (want != R.CURRENT_AND_CERTIFIED),
                  (r['release_state'], r['reasons']))
    finally:
        R.world_accounting, R.OPEN_FORECAST_DEFECTS = real_wa, real_def


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
