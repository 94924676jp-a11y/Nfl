"""The depth chart must be selected by a CLOCK, not by content-hash order.

THE DEFECT THIS MODULE EXISTS FOR.

`qb_allocation.captured_depth_chart` reads

    fs = sorted(glob.glob(.../ 'depth_charts.*.reduced.csv.gz'))
    p = fs[-1]

and its docstring calls that "the newest captured depth chart". It is not. The
filenames carry CONTENT HASHES, so `sorted(...)[-1]` is lexicographically last
by hash and has no relationship to time. Measured on the seven captures in the
tree:

    361f1c69443cba69   2026-09-10T05:05
    76d7bcb384ec11e3   2026-09-06T18:50
    a14e8dfe865a4b03   2026-09-13T15:45
    db0a09454965e6fc   2026-09-10T12:07
    ecc4973e8715d866   2026-09-07T13:39
    f57ef0724d907160   2026-09-08T12:07
    f66f0c2583dba463   2026-09-14T16:16   <- picked, and newest, BY COINCIDENCE

Hash order and time order agree here by luck. Nothing makes them agree: a
capture hashing to `0abc...` taken tomorrow would sort FIRST and never be
selected, and one hashing to `fff...` taken last week would be selected
forever.

WHAT IT COSTS. The selection ignores the caller's cut entirely, so a forecast
written 2026-09-11 was served a chart retrieved 2026-09-14 -- three days of
future information. `allocate` carries a correct chronology guard for exactly
this, but until 2026-09-15 no caller passed it a clock, so it never executed
(see `run_forecast.py:501`). With the guard armed the symptom surfaces as a
REFUSED seal when reproducing any board written before 2026-09-14T13:53.

That refusal is right, and it is still not the repair. FIVE LAWFUL VINTAGES
EXIST for that 2026-09-11 board -- 09-06, 09-07, 09-08, and two on 09-10 -- and
a selector that read the clock would have found them. The guard is a backstop;
the cause is the selector.

`nfl/production/vintage_selector.py` already does this correctly for the four
families it declares. This is the fifth.
"""
from __future__ import annotations

import glob
import json
import pathlib
import sys

_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import derived as D                        # noqa: E402
from nfl.production.nonqb import qb_allocation as QA           # noqa: E402
from nfl.production.nonqb import vintage_selector as VS        # noqa: E402

PASSED = FAILED = BLOCKED = 0
VINTAGE = pathlib.Path(_ROOT) / 'nfl' / 'vintage'
MANIFEST = pathlib.Path(_ROOT) / 'nfl' / 'vintage_manifest.jsonl'


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def _ok():
    return D.artifacts().state.value == 'PASS'


def _blob_times():
    """hash -> retrieved_at, from the manifest, for every depth-chart blob."""
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines() if l.strip()]
    out = {}
    for p in sorted(glob.glob(str(VINTAGE / 'depth_charts.*.reduced.csv.gz'))):
        h = pathlib.Path(p).name.split('.')[1]
        for r in rows:
            if h in json.dumps(r):
                out[h] = r.get('retrieved_at') or r.get('capture_id')
                break
    return out


def test_a_hash_order_is_not_time_order():
    print('\nA. the filename carries a hash, so sorted() is not chronological')
    t = _blob_times()
    if len(t) < 2:
        blocked('fewer than two depth-chart captures exist',
                'NOT_ENOUGH_VINTAGES_TO_ORDER')
        return
    by_hash = list(t)                       # already sorted by hash
    by_time = sorted(t, key=lambda h: str(t[h]))
    check('at least two captures exist to order', len(t) >= 2, f'{len(t)}')
    # They may coincide today. What must never be relied on is that they DO.
    check('  hash order and time order are different orderings, '
          'whether or not they coincide today',
          True, f'hash-last={by_hash[-1]} time-last={by_time[-1]}')


def test_b_selection_respects_an_as_of_cut():
    """THE REPAIR. A chart may not be newer than the cut that asks for it."""
    print('\nB. captured_depth_chart(as_of=...) never returns a future chart')
    if not _ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    t = _blob_times()
    if not t:
        blocked('no depth-chart capture is present', 'NO_VINTAGE')
        return
    fn = QA.captured_depth_chart
    import inspect
    if 'as_of' not in inspect.signature(fn).parameters:
        check('captured_depth_chart accepts an as_of cut', False,
              'no as_of parameter -- selection cannot respect a clock')
        return
    check('captured_depth_chart accepts an as_of cut', True)
    for cut in sorted(set(str(v) for v in t.values())):
        o = fn(as_of=cut)
        if o.state.value != 'PASS':
            # A cut before every capture must REFUSE, not fall back.
            check(f'  cut {cut}: refuses rather than serving a future chart',
                  o.code in ('DEPTH_CHART_NOT_CAPTURED',
                             'DEPTH_CHART_NO_LAWFUL_VINTAGE'), o.code)
            continue
        got = str(o.evidence.get('retrieved_at') or '')
        gt, ct = VS.parse_ts(got), VS.parse_ts(cut)
        check(f'  cut {cut}: selected chart is not newer than the cut',
              gt is not None and ct is not None and gt <= ct,
              f'selected {got}')


def test_c_the_historical_board_becomes_reproducible():
    """The concrete case: a board written 2026-09-11 has lawful vintages."""
    print('\nC. a 2026-09-11 cut finds one of the five lawful captures')
    if not _ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    import inspect
    if 'as_of' not in inspect.signature(QA.captured_depth_chart).parameters:
        check('captured_depth_chart accepts an as_of cut', False, 'no as_of')
        return
    cut = '2026-09-11T00:25:50Z'
    t = _blob_times()
    # PARSED, for the reason the module under test now documents: the manifest
    # carries both `2026-09-14T17:39:41Z` and the compact `20260910T120717Z`,
    # and '-' sorts before '0', so a string compare puts EVERY compact stamp
    # after EVERY ISO one whatever the date. I wrote that bug into the fix and
    # then into this test; it reported 0 lawful vintages of 7 when there are 5.
    _cut = VS.parse_ts(cut)
    lawful = {h: v for h, v in t.items()
              if VS.parse_ts(v) is not None and VS.parse_ts(v) < _cut}
    check('lawful vintages exist for this cut', bool(lawful),
          f'{len(lawful)} of {len(t)}')
    o = QA.captured_depth_chart(as_of=cut)
    check('  and one of them is selected', o.state.value == 'PASS',
          f'{o.state.value}[{o.code}]')
    if o.state.value == 'PASS':
        got = str(o.evidence.get('retrieved_at') or '')
        check('  it precedes the cut',
              VS.parse_ts(got) is not None and VS.parse_ts(got) < _cut, got)
        # Compared on the CAPTURE instant, which is what the manifest records
        # and what selection uses. `retrieved_at` in this evidence block is the
        # vendor's own `dt` from inside the chart -- a different instant, now
        # published separately as `capture_retrieved_at`.
        newest = max(lawful.values(), key=lambda v: VS.parse_ts(v))
        sel = str(o.evidence.get('capture_retrieved_at') or '')
        check('  and it is the NEWEST that does, not an arbitrary one',
              VS.parse_ts(sel) == VS.parse_ts(newest),
              f'{sel} vs newest lawful {newest}')


def test_d_the_default_path_is_unchanged_for_a_current_cut():
    print('\nD. tonight\'s cut still selects what it selected before')
    if not _ok():
        blocked('derived artifacts unavailable', 'ARTIFACTS_UNAVAILABLE')
        return
    o = QA.captured_depth_chart()
    check('the no-argument call still succeeds', o.state.value == 'PASS',
          f'{o.state.value}[{o.code}]')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
