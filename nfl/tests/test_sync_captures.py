#!/usr/bin/env python3.12
"""sync_captures: an append of verified bytes, refused by name in every other case."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import sync_captures as SC  # noqa: E402
from nfl.tests import _registry  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _row(cid, src, blob, data):
    return json.dumps({'capture_id': cid, 'source': src, 'state': 'PASS', 'value': {
        'blob': blob, 'blob_file_sha256': hashlib.sha256(data).hexdigest()}})


@check('a local manifest that is a prefix of the remote plans exactly the missing rows and their blobs')
def _prefix_plans():
    a, b = b'aaa', b'bbb'
    local = [_row('1', 'injuries', 'nfl/vintage/x.1.gz', a)]
    remote = local + [_row('2', 'injuries', 'nfl/vintage/x.2.gz', b), json.dumps({'capture_id': '2', 'source': 'y', 'state': 'BLOCKED'})]
    o = SC.plan(local, remote)
    assert o.state.name == 'PASS' and o.evidence['n_rows'] == 2 and o.evidence['n_blobs'] == 1, (o.code, o.evidence)
    assert list(o.value['blobs']) == ['nfl/vintage/x.2.gz']
    return o.detail


@check('two forked logs are UNIONED: remote-only rows appended in remote order, local-only rows kept, fork recorded')
def _forked_union():
    shared = _row('1', 'a', 'nfl/vintage/p.gz', b'1')
    local = [shared, _row('L', 'a', 'nfl/vintage/local_only.gz', b'L')]
    remote = [shared, _row('R1', 'a', 'nfl/vintage/r1.gz', b'r1'), _row('R2', 'a', 'nfl/vintage/r2.gz', b'r2')]
    o = SC.plan(local, remote)
    assert o.state.name == 'PASS' and o.value['forked'] == {'fork_row': 1, 'n_local_only_rows': 1, 'n_remote_only_rows': 2,
                                                            'MEANING': o.value['forked']['MEANING']}, (o.code, o.value.get('forked'))
    assert [json.loads(l)['capture_id'] for l in o.value['new_lines']] == ['R1', 'R2']
    return o.detail


@check('a blob path named on BOTH sides of the fork with different hashes refuses the sync')
def _fork_conflict():
    shared = _row('1', 'a', 'nfl/vintage/p.gz', b'1')
    local = [shared, _row('L', 'a', 'nfl/vintage/same.gz', b'local bytes')]
    remote = [shared, _row('R', 'a', 'nfl/vintage/same.gz', b'remote bytes')]
    o = SC.plan(local, remote)
    assert o.state.name == 'FAIL' and o.code == 'SYNC_BLOB_CONFLICT_ACROSS_FORK', (o.code, o.detail)
    return o.detail


@check('a blob whose bytes do not hash to the manifest is refused and nothing is appended')
def _hash_mismatch():
    good = b'good bytes'; row = _row('7', 'injuries', 'nfl/vintage/zz.test.gz', good)
    o = SC.run(dry_run=True, fetch=lambda: 'deadbeef' * 5,
               show=lambda sha, path: ('\n'.join([*_local_lines(), row])).encode() if path == SC.MANIFEST else b'tampered')
    assert o.state.name == 'FAIL' and o.code == 'SYNC_BLOB_HASH_MISMATCH', (o.code, o.detail)
    assert not (_REPO / 'nfl/vintage/zz.test.gz').exists()
    return o.detail


def _local_lines():
    return (_REPO / SC.MANIFEST).read_text().splitlines()


@check('a dry run against an injected remote names rows, blobs and bytes and writes nothing')
def _dry_run():
    data = b'fresh capture bytes'; row = _row('20991231T000000Z', 'depth_charts', 'nfl/vintage/zz.dry.gz', data)
    before = len(_local_lines())
    o = SC.run(dry_run=True, fetch=lambda: 'cafe' * 10,
               show=lambda sha, path: ('\n'.join([*_local_lines(), row])).encode() if path == SC.MANIFEST else data)
    assert o.state.name == 'PASS' and o.code == 'SYNC_DRY_RUN', (o.code, o.detail)
    assert o.value['n_rows_appended'] == 1 and o.value['n_blobs_written'] == 1 and o.value['bytes_written'] == len(data)
    assert len(_local_lines()) == before and not (_REPO / 'nfl/vintage/zz.dry.gz').exists()
    return o.detail


@check('nothing new is reported as NOTHING_NEW with the remote sha, never as an applied sync')
def _nothing_new():
    o = SC.run(dry_run=False, fetch=lambda: 'feed' * 10, show=lambda sha, path: ('\n'.join(_local_lines())).encode())
    assert o.state.name == 'PASS' and o.code == 'SYNC_NOTHING_NEW' and o.value['remote_sha'].startswith('feed'), (o.code,)
    return o.detail


@check('a failed fetch is BLOCKED with cause NETWORK, not a failed sync')
def _fetch_failed():
    o = SC.run(dry_run=True, fetch=lambda: None, show=lambda s, p: b'')
    assert o.state.name == 'BLOCKED' and o.code == 'SYNC_FETCH_FAILED' and str((o.evidence or {}).get('cause')) in ('NETWORK', 'Cause.NETWORK'), (o.state, o.code)
    return o.detail


_EMITTED = _registry.emit(globals(), RESULTS)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main() -> int:
    for fname in _EMITTED:
        try:
            globals()[fname]()
        except Exception:  # noqa: BLE001
            pass
    print(f'\n{PASSED} passed, {FAILED} failed, {len(RESULTS)} checks')
    return 1 if FAILED else 0


if __name__ == '__main__':
    raise SystemExit(main())
