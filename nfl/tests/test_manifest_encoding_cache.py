#!/usr/bin/env python3.12
"""PERF-D1 (2026-10-14): qb_allocation encodes the vintage manifest once per manifest content, not once per blob per call.

The incumbent re-ran json.dumps on all 12,883 rows (99 MB) for each of 78 depth-chart blobs on every call (25.7 s per
call; test_depth_chart_vintage_selection > 1 h). The fix caches the encodings keyed by the manifest's size and mtime;
the match itself is unchanged. These checks prove the cache is reused, invalidated by a change, and gives the same
vintages as the incumbent algorithm."""
from __future__ import annotations

import glob
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import qb_allocation as QA  # noqa: E402

PASSED = FAILED = 0


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def test_encodings_are_reused_and_follow_the_manifest():
    # a temporary manifest: touching the real 99 MB one would copy it up in an overlay and move a tracked file's mtime
    import shutil
    import tempfile
    tmp = pathlib.Path(tempfile.mkdtemp(prefix='perf_d1_'))
    (tmp / 'nfl').mkdir()
    man = tmp / 'nfl' / 'vintage_manifest.jsonl'
    man.write_text('{"blob": "nfl/vintage/x.aaaaaaaaaaaaaaaa.csv", "retrieved_at": "2026-10-01T00:00:00Z"}\n')
    saved = QA._REPO
    QA._REPO = tmp
    try:
        a, b = QA._manifest_rows(), QA._manifest_rows()
        check(a is b, 'a second call reuses the cached rows and encodings (no re-encoding)')
        check(len(a[0]) == len(a[1]) == 1, 'one encoding per row')
        with man.open('a') as fh:
            fh.write('{"blob": "nfl/vintage/y.bbbbbbbbbbbbbbbb.csv", "retrieved_at": "2026-10-02T00:00:00Z"}\n')
        c = QA._manifest_rows()
        check(c is not a and len(c[0]) == 2, 'an appended capture invalidates the cache and is seen')
    finally:
        QA._REPO = saved
        QA._MANIFEST_CACHE.clear()
        shutil.rmtree(tmp, ignore_errors=True)


def test_same_vintages_as_the_incumbent_algorithm():
    rows = QA._manifest_rows()[0]
    blobs = sorted(glob.glob(str(QA._REPO / 'nfl' / 'vintage' / QA.DEPTH_GLOB)))[:3]
    new = {p: w for _t, w, p in QA._depth_chart_vintages()}
    for p in blobs:
        h = pathlib.Path(p).name.split('.')[1]
        when = next((r.get('retrieved_at') or r.get('capture_id') for r in rows if h in json.dumps(r)), None)
        check(new.get(p) == (str(when) if when and QA.VS.parse_ts(when) is not None else None),
              f'{pathlib.Path(p).name}: the same capture clock as the incumbent per-row encoding ({when})')


def test_cutoffs_see_the_same_chart_warm_or_cold():
    """No cross-cut or cross-slate contamination: the cache holds only the manifest's encodings; selection by as_of
    happens after it. Each cut must give the identical chart whether the cache is warm (filled by an earlier, later
    cut) or cold."""
    cuts = ('2026-09-11T00:00:00Z', '2026-10-04T17:00:00Z', None)
    warm = []
    for c in reversed(cuts):                         # fill the cache from the LATEST cut first
        warm.append((c, QA.captured_depth_chart(as_of=c)))
    for c, w in warm:
        QA._MANIFEST_CACHE.clear()
        cold = QA.captured_depth_chart(as_of=c)
        same = (w.state.value, w.code, json.dumps(w.value, sort_keys=True, default=str)) == \
               (cold.state.value, cold.code, json.dumps(cold.value, sort_keys=True, default=str))
        check(same, f'cut {c or "now"}: identical chart warm and cold ({w.state.value} {w.code})')
    a, b = warm[0][1], warm[-1][1]
    check(json.dumps(a.value, sort_keys=True, default=str) != json.dumps(b.value, sort_keys=True, default=str)
          or a.code != b.code, 'the cuts are distinguishable (an earlier cut does not see the later chart)')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
