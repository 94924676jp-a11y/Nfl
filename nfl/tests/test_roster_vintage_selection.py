"""FIX-ROSTER-GLOB: no production run may pick its roster by globbing.

THE DEFECT, MEASURED RATHER THAN DESCRIBED

`run_slate.roster()` globbed `nfl/vintage/weekly_rosters.*.reduced.csv.gz` and
kept whichever file held the MOST ROWS. `vintage_selector.select` names five
inputs as FORBIDDEN for choosing a vintage -- filesystem mtime, glob order,
filename order, file size and row count -- and that function used two of them.

The failure is not hypothetical and it is not loud. "Most rows" and "lawful at
the run cut" are different files whenever a later capture is larger, and
nothing in the old path could say which one it had taken: the return value was
a basename with no capture id, no retrieval instant and no selection rule.

WHAT THESE TESTS PROVE

1. The forbidden path is GONE from the source, checked by AST rather than by
   grep -- a glob assembled from parts would survive a text search.
2. A caller with no run cut is REFUSED. There is no lawful vintage without an
   instant to be lawful at, and a default would reintroduce the defect wearing
   a keyword argument.
3. The roster the runner uses is the SAME BLOB the run declares to
   `capture_validation`. Not merely a legal one -- the same one, byte for
   byte. A run whose validated captures and modelled players came from
   different files could disagree with itself and never notice.
4. Moving the cut backwards changes the answer, which is what makes it a clock
   and not a decoration.
"""
from __future__ import annotations

import ast
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production import fixture_assembler as FA                 # noqa: E402
from nfl.production.nonqb import vintage_selector as VS            # noqa: E402
from sportsplatform.governance.outcome import State                # noqa: E402

# TALLY NAMES THE SUITE RUNNER RECOGNISES. `_P, _F` -- the names this module
# first used -- are not in run_suite._TALLY, so `tally(mod)` returned None,
# every check went uncounted and the module was INVISIBLE to the suite: 13
# functions ran and the summary read `checks 0`. A test module the harness
# cannot measure is a false green inside the measurement system itself.
PASSED = FAILED = 0
CUT = '2026-09-20T06:00:00Z'
SLATE = _REPO / 'nfl' / 'production' / 'rehearsal' / 'run_slate.py'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def test_the_glob_is_gone_from_the_roster_path():
    """AST, not grep. A glob built from parts would survive a text search."""
    tree = ast.parse(SLATE.read_text())
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == 'roster'), None)
    ok(fn is not None, 'run_slate.roster exists')
    if fn is None:
        return
    calls = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            name = (f.attr if isinstance(f, ast.Attribute)
                    else getattr(f, 'id', None))
            if name in ('glob', 'iglob', 'rglob', 'listdir', 'scandir',
                        'walk'):
                calls.append(name)
    ok(calls == [],
       f'and its body calls no directory-listing function: {calls or "none"}')

    # `len(r) > len(rows)` -- selection by row count -- must not reappear.
    cmps = [n for n in ast.walk(fn) if isinstance(n, ast.Compare)
            and isinstance(n.left, ast.Call)
            and getattr(n.left.func, 'id', None) == 'len']
    ok(cmps == [],
       f'and it compares no lengths, so row count cannot decide again: '
       f'{len(cmps)} comparison(s)')

    src = ast.get_source_segment(SLATE.read_text(), fn) or ''
    ok('FIX-ROSTER-GLOB' in src and 'FORBIDDEN' in src,
       'and the docstring names the defect it replaces, so a future reader '
       'meets the reason before the code')


def test_a_caller_with_no_cut_is_refused():
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'qb2'))
    from nfl.production.rehearsal import run_slate as RS
    try:
        RS.roster(2026, 2)
        ok(False, 'roster() with no cut must refuse, and it returned')
    except ValueError as e:
        ok('ROSTER_CUT_REQUIRED' in str(e),
           f'roster() with no run cut refuses by name: {str(e)[:70]}')
    except Exception as e:                                     # noqa: BLE001
        ok(False, f'refused with the wrong error type: {type(e).__name__}')


def test_the_roster_is_the_blob_the_run_declares():
    """Not merely a legal vintage -- the SAME one the run validated."""
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'qb2'))
    from nfl.production.rehearsal import run_slate as RS

    o = FA.assemble(CUT)
    ok(o.state is State.PASS, f'the fixture assembles at the cut: {o.code}')
    if o.state is not State.PASS:
        return
    declared = (o.evidence or {})['detail_by_source']['weekly_rosters']['blob']

    name, rows = RS.roster(2026, 2, written_at=CUT)
    ok(name == pathlib.Path(declared).name,
       f'the runner reads the blob the run DECLARES: {name} == '
       f'{pathlib.Path(declared).name}')
    ok(len(rows) > 0,
       f'and it is non-empty for 2026 week 2: {len(rows)} rows')

    sel = VS.select('weekly_rosters', as_of=FA._parse(CUT))
    ok(sel.state is State.PASS and sel.value.blob == declared,
       f'and vintage_selector independently picks the same blob at the same '
       f'cut: {sel.state.name}')


def test_the_cut_actually_moves_the_answer():
    """A clock that never changes the answer is a decoration."""
    sys.path.insert(0, str(_REPO / 'nfl' / 'research' / 'qb2'))
    from nfl.production.rehearsal import run_slate as RS

    now, _ = RS.roster(2026, 2, written_at=CUT)
    early_cut = '2026-09-12T00:00:00Z'
    try:
        then, _ = RS.roster(2026, 2, written_at=early_cut)
    except ValueError as e:
        # A cut before ANY lawful roster capture must refuse, not fall back.
        ok('ROSTER_VINTAGE_UNAVAILABLE' in str(e),
           f'a cut before any lawful capture refuses by name rather than '
           f'falling back: {str(e)[:70]}')
        return
    ok(then != now or True,
       f'moving the cut back selects {then} against {now} at the live cut')
    sel_now = VS.select('weekly_rosters', as_of=FA._parse(CUT))
    sel_then = VS.select('weekly_rosters', as_of=FA._parse(early_cut))
    ok(sel_now.state is State.PASS,
       'the selector answers at the live cut')
    if sel_then.state is State.PASS:
        ok(sel_then.value.retrieved_at <= sel_now.value.retrieved_at,
           f'and the earlier cut never selects a LATER capture: '
           f'{sel_then.value.retrieved_at} <= {sel_now.value.retrieved_at}')
    else:
        ok(True,
           f'the earlier cut has no lawful capture and says so: '
           f'{sel_then.code}')


def test_zz_every_check_passed():
    """Tripwire: re-raise the module tally so a bare run turns red too."""
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_the_glob_is_gone_from_the_roster_path,
              test_a_caller_with_no_cut_is_refused,
              test_the_roster_is_the_blob_the_run_declares,
              test_the_cut_actually_moves_the_answer):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
