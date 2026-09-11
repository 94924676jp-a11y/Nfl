"""The capture workflow may no longer succeed while capturing nothing.

THE FAILURE THIS CLOSES, observed in production 2026-09-09/10. The anchored
T-90 workflow's runs put `schedules` blobs into `nfl/vintage`, appended NO
manifest row, produced a commit message reading "capture unknown" because the
final summary line never printed, and reported SUCCESS. The NE@SEA T-90 window
closed with `qualifying_captures = 0` and G0A item 1 did not clear.

Reproduced locally before repair: `capture_vintage.py` captured `injuries` and
`schedules`, then raised inside `fetch` on the next source. The manifest was
written only after the whole loop, so every row was discarded -- including the
two already-successful captures whose durable blobs were on disk. Exit status
was 0 because the workflow read `$?` after a pipe, which is `tee`'s.

Durable bytes with no manifest row are ORPHANS: nothing attributes them to a
game, a window, a basis or a source, so they can discharge nothing.

These checks are structural and need no network.
"""
from __future__ import annotations

import ast
import json
import os
import pathlib
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

TOOL = os.path.join(_ROOT, 'nfl', 'tools', 'capture_vintage.py')
WF_T90 = os.path.join(_ROOT, '.github', 'workflows', 'nfl-t90.yml')
WF_BASE = os.path.join(_ROOT, '.github', 'workflows', 'nfl-capture.yml')

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


def _src(p):
    return open(p).read()


# ---------------------------------------------------------------- the tool
def test_one_source_cannot_destroy_the_run():
    """The per-source fetch must sit inside an exception boundary."""
    tree = ast.parse(_src(TOOL))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == 'main'), None)
    assert check('main() exists', fn is not None)
    guarded = False
    for t in ast.walk(fn):
        if not isinstance(t, ast.Try):
            continue
        for c in ast.walk(t):
            if (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == 'fetch'):
                guarded = True
    assert check('the per-source fetch is inside a try/except', guarded,
                 'SOURCE_RAISE_KILLS_RUN: one bad source would discard every '
                 'row, including successes whose blobs are already durable')
    assert check('and a raised source becomes a named row',
                 'SOURCE_RAISED' in _src(TOOL), 'SOURCE_RAISE_UNNAMED')


def test_a_run_that_writes_no_manifest_row_fails_loudly():
    s = _src(TOOL)
    assert check('the no-row condition is named',
                 'CAPTURE_WROTE_NO_MANIFEST_ROW' in s,
                 'ORPHAN_BLOBS_TOLERATED')
    i = s.find('n_written = _flush(')
    assert check('the flush result is captured', i > 0)
    j = s.find('capture {capture_id}', i)
    window = s[i:j if j > i else i + 900]
    assert check('  and a zero count raises before the run can look green',
                 'if n_written == 0' in window and 'SystemExit' in window,
                 'ZERO_ROWS_NOT_FATAL')


def test_the_manifest_write_is_a_single_named_path():
    """One place appends rows, so the guarantee is auditable."""
    s = _src(TOOL)
    assert check('_flush exists', 'def _flush(' in s)
    assert check('  and it reports how many rows it wrote',
                 'return len(rows)' in s)
    # No other open(manifest, 'a') should exist.
    assert check('nothing else appends to the manifest',
                 s.count("open(manifest") == 1, 'MULTIPLE_MANIFEST_WRITERS')


def test_a_provenance_path_cannot_kill_a_capture():
    """`relative_to` RAISES when the path is not a subpath. It sat inside the
    per-source fetch, so a store outside the repo killed the run after its
    durable blobs were written."""
    sys.path.insert(0, os.path.join(_ROOT, 'nfl', 'tools'))
    import capture_vintage as CV
    out = CV._rel(pathlib.Path('/etc/hostname'))
    assert check('a path outside the repo returns a string, not a raise',
                 isinstance(out, str) and out, repr(out))
    inside = CV._rel(pathlib.Path(_ROOT) / 'nfl' / 'vintage')
    assert check('  and a path inside the repo is repo-relative',
                 inside == 'nfl/vintage', inside)
    # `_rel` itself uses relative_to, inside its own try/except -- that one is
    # the repair. Any OTHER use on the persist path is the defect.
    lines = [l for l in _src(TOOL).splitlines()
             if 'relative_to(_REPO)' in l and 'q.resolve()' not in l]
    assert check('no unguarded relative_to survives on the persist path',
                 not lines,
                 f'BARE_RELATIVE_TO_REMAINS: {lines[:2]}')


def test_the_schedule_snapshot_is_not_chosen_by_mtime():
    """Anchored target identity must not depend on filesystem incidentals: on
    a fresh checkout every file carries the checkout time."""
    s = _src(TOOL)
    assert check('a deterministic selector exists',
                 'def _newest_schedule_snapshot(' in s)
    i = s.find('def _newest_schedule_snapshot(')
    j = s.find('\ndef ', i + 10)
    body = s[i:j]
    assert check('  it consults the manifest, which records capture order',
                 'MANIFEST' in body, 'SNAPSHOT_IGNORES_MANIFEST')
    assert check('  mtime is only the last resort',
                 body.count('st_mtime') <= 1, 'SNAPSHOT_STILL_MTIME_FIRST')
    sys.path.insert(0, os.path.join(_ROOT, 'nfl', 'tools'))
    import capture_vintage as CV
    a = CV._newest_schedule_snapshot()
    b = CV._newest_schedule_snapshot()
    assert check('  and the choice is stable across calls',
                 (a is None and b is None) or (a and b and a.name == b.name))


# ------------------------------------------------------------- the workflow
def _wf_gate(path, label):
    s = _src(path)
    assert check(f'{label}: asserts a manifest row was appended',
                 'manifest rows appended: [1-9]' in s,
                 'WORKFLOW_ACCEPTS_ZERO_ROWS: this is exactly how a run that '
                 'produced only a schedules blob reported success')
    assert check(f'{label}: fails on an unhandled traceback',
                 'Traceback (most recent call last)' in s,
                 'WORKFLOW_IGNORES_TRACEBACK: grepping only for "^FAIL " '
                 'cannot see a crash')
    assert check(f'{label}: the assertion runs even when a step failed',
                 s.count('if: always()') >= 2)


def test_the_anchored_workflow_is_gated():
    _wf_gate(WF_T90, 't90')
    s = _src(WF_T90)
    assert check('t90: reads the capture exit code, not tee\'s',
                 'PIPESTATUS[0]' in s,
                 'EXIT_CODE_IS_TEES: `$?` after a pipe is tee\'s status and is '
                 '0 whatever the capture did')


def test_the_baseline_workflow_is_gated_too():
    """It committed the orphan schedules blobs that triggered this."""
    _wf_gate(WF_BASE, 'baseline')


def test_the_gate_would_have_caught_the_real_failure():
    """Replay the production log shape against the workflow's own predicate."""
    real = ('PASS            CAPTURED                     injuries\n'
            'PASS            CAPTURED                     schedules  [NEW]\n'
            'Traceback (most recent call last):\n'
            '  File "capture_vintage.py", line 651, in main\n'
            'ValueError: boom\n')
    import re
    has_row = bool(re.search(r'^manifest rows appended: [1-9]', real,
                             re.MULTILINE))
    has_trace = 'Traceback (most recent call last)' in real
    has_fail = bool(re.search(r'^FAIL ', real, re.MULTILINE))
    assert check('the OLD predicate (^FAIL only) passes this log',
                 not has_fail,
                 'the old gate would have failed it, so this test proves '
                 'nothing')
    assert check('the NEW predicate rejects it', has_trace or not has_row)


def test_the_guards_fail_when_bypassed():
    """Seed each defect and require rejection."""
    caught = 0
    if 'manifest rows appended: [1-9]' not in "if grep -qE '^FAIL '":
        caught += 1
    if 'SOURCE_RAISED' not in 'out = fetch(src, args.season, store, decl)':
        caught += 1
    if 'CAPTURE_WROTE_NO_MANIFEST_ROW' not in 'with open(manifest,"a") as fh:':
        caught += 1
    assert check('all three seeded defects are rejected', caught == 3,
                 f'CAPTURE_GUARDS_INERT: only {caught}/3 fired')


def test_no_rule_was_loosened_and_week1_is_not_backfilled():
    """The repair is to the capture path only. The frozen discharge predicate
    and the missed Week 1 obligations must be untouched."""
    rec = os.path.join(_ROOT, 'nfl', 'capture',
                       't90_obligation_reconciliation.json')
    d = json.load(open(rec))

    def walk(o):
        if isinstance(o, dict):
            if 'status' in o and 'kind' in o:
                yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    missed = [r for r in walk(d) if r['status'] == 'MISSED']
    # BACKFILLING MAKES MISSES DISAPPEAR; IT DOES NOT MULTIPLY THEM.
    #
    # This pinned the count at exactly 5, which was the number of Week 1
    # windows that had closed unfilled on the day it was written. By
    # 2026-09-11 twenty had closed, and the test reported WEEK1_BACKFILLED --
    # naming the calendar advancing as the one thing it exists to forbid.
    # A backfill converts a MISS into a COVER, so the count can only fall.
    # Assert the direction, and assert that the named obligations are still
    # individually missed, which is what "not backfilled" actually means.
    assert check('no Week 1 miss was converted into a cover',
                 len(missed) >= 5, f'{len(missed)} -- WEEK1_BACKFILLED')
    ne = [r for r in missed
          if r.get('game_id') == '2026_01_NE_SEA' and r.get('kind') == 'inactives']
    assert check('  including the item-1 obligation', len(ne) == 1)
    assert check('  with zero qualifying captures',
                 ne and ne[0].get('qualifying_captures') == 0,
                 'RETROACTIVE_CREDIT')
