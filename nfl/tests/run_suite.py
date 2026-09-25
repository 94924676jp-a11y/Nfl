"""The repository test runner. COMMITTED, because an ad-hoc one is not evidence.

WHY THIS EXISTS, AND WHAT IT FIXES

Every test module in this repository reports through a module-level `check()`
that increments a counter and PRINTS. It does not raise. A runner that
discovers `test_*` functions and counts the ones that throw therefore reports a
clean suite while individual checks are failing -- absence of an exception read
as success, which is this project's Class A failure mode occurring inside the
measurement system itself.

This runner reads each module's own tally after running it, so a failing
`check()` is a failing suite. It also refuses a module that ran zero checks:
a module that measured nothing has not passed.

AND IT REFUSES A *FUNCTION* THAT RAN ZERO CHECKS, WHICH IS THE SAME DEFECT ONE
LEVEL DOWN.

The module-level rule was scoped to the module, so a single function that hit
`if not rows: return` before its first `check()` contributed nothing and said
nothing, while its siblings kept the module's counter above zero. WS11 found 25
functions constructed that way -- among them a leakage guard
(`test_r8_synthesis::test_k_is_not_estimated_from_the_forecast_season`) and a
determinism guard (`test_warm_session::test_d_warm_and_cold_produce_identical
_football`). Neither was firing at the time it was found, which is the whole
problem: a guard that can delete itself on a data-availability change and leave
the suite green is not a guard. "The fixture was missing" and "the property
holds" are different answers and the runner must not render them the same
colour.

So the tally is now read around EVERY test function, not once around the
module, and a function whose delta is zero is named and fails the suite.

THE ESCAPE HATCH IS `blocked()`, NOT AN ALLOW-LIST. A function that genuinely
cannot run says so by incrementing a BLOCKED counter (`test_volatility.py`
shows the construction: "counted apart and never as a pass"). This runner reads
that counter too, and a function that recorded only blocked() is reported as
BLOCKED and does not fail the suite. It is still not a pass, and it is still
printed. There is deliberately no list of functions exempted by name: an
exemption list is how a silent skip comes back wearing a permit.
"""
from __future__ import annotations

import ast
import glob
import importlib.util
import io
import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Modules whose counters are named something other than PASSED/FAILED.
#
# ('P', 'F') IS NOT OPTIONAL. Three sportsplatform modules count with those
# names, so without them `tally()` returned None, those modules were judged on
# exceptions alone, and their `check()` failures were invisible -- the exact
# defect this runner was written to end, still live in three files. Found by
# nfl/tests/test_harness_audit.py, which asserts no module reports through a
# counter this runner cannot read.
_TALLY = (('PASSED', 'FAILED'), ('passed', 'failed'), ('OK', 'BAD'),
          ('P', 'F'))

# Counters a module may use to record a check that COULD NOT RUN. Read so that
# `blocked()` is distinguishable from silence: a function that recorded only a
# blocked check is reported and is not a pass, but it does not fail the suite,
# because it said out loud that it did not measure. A function that recorded
# nothing at all said nothing at all.
_BLOCKED = ('BLOCKED', 'blocked_count', 'SKIPPED')


#: Names a module uses to record one check. Read from the SOURCE, because a
#: module that exposes no test function never runs and so can never be asked
#: at runtime what it would have measured.
_CHECK_CALLS = ('check(', 'ck(', 'ok(', 'expect(')


def _has_checks(path) -> bool:
    """Does this file plainly contain assertions nobody is executing?"""
    try:
        src = open(path, encoding='utf-8').read()
    except Exception:                                        # noqa: BLE001
        return False
    # a definition is not a call
    body = '\n'.join(ln for ln in src.splitlines()
                      if not ln.lstrip().startswith(('def ', '#')))
    return any(c in body for c in _CHECK_CALLS)


def tally(mod):
    for p, f in _TALLY:
        if hasattr(mod, p) and hasattr(mod, f):
            return int(getattr(mod, p)), int(getattr(mod, f))
    return None


def tally_tripwires(path):
    """The `test_*` functions that are the module's own tally re-raise.

    50 modules end with

        def test_zz_every_check_passed():
            if FAILED:
                raise AssertionError(...)

    which records no check and never could: it re-raises the counter this
    runner already reads, so that a bare `python3.12 nfl/tests/test_x.py` turns
    red too. Counting it as a zero-check function would put 50 false entries in
    front of the real ones, and a list nobody can read is a list nobody reads.

    IT IS RECOGNISED BY SHAPE, NOT BY NAME. A function qualifies only if it
    raises or asserts, mentions a failure counter, and calls NOTHING except
    print/AssertionError. Anything that calls production code, or `check`, or
    reads an artifact, is not a tripwire whatever it is called -- so this
    cannot become a hiding place.
    """
    out = set()
    try:
        tree = ast.parse(open(path, encoding='utf-8').read(), path)
    except (OSError, SyntaxError):
        return out
    fails = {f for _, f in _TALLY}
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith('test_'):
            continue
        nodes = list(ast.walk(fn))
        if not any(isinstance(n, (ast.Raise, ast.Assert)) for n in nodes):
            continue
        if not any(isinstance(n, ast.Name) and n.id in fails for n in nodes):
            continue
        names = set()
        for n in nodes:
            if isinstance(n, ast.Call):
                f = n.func
                names.add(f.id if isinstance(f, ast.Name)
                          else getattr(f, 'attr', '?'))
        if names <= {'print', 'AssertionError'}:
            out.add(fn.name)
    return out


def blocked_tally(mod):
    """The module's blocked counter, or 0 if it has none.

    Name-collision guard: `test_volatility.py` defines BOTH a counter `BLOCKED`
    and a function `blocked()`. Only an int is read.
    """
    for b in _BLOCKED:
        v = getattr(mod, b, None)
        if isinstance(v, int) and not isinstance(v, bool):
            return int(v)
    return 0


#: WHERE A KILLED RUN LEAVES ITS EVIDENCE.
#:
#: Every print in this runner used to happen after the last module finished.
#: Measured 2026-09-25: nine minutes under `python3.12 -u`, killed at the
#: timeout, ZERO BYTES of output. Not a buffering problem -- the process simply
#: had nothing to say yet. A suite that reports only on completion cannot be
#: used to classify anything inside a working session, and on 2026-09-24 that
#: made every SUCCESS_TESTED claim in an audit rest on a test file existing
#: rather than on a green run.
#:
#: So progress is emitted per module, as it happens, to stdout AND appended to
#: this file. A run that dies half way now leaves a readable record of what it
#: got through and what it was inside when it stopped.
PROGRESS_PATH = os.environ.get(
    'NFL_SUITE_PROGRESS', os.path.join(ROOT, 'nfl/tests/_suite_progress.jsonl'))

_T0 = time.time()

#: Every record carries the run that wrote it, and the file is APPENDED to,
#: never truncated. The first version truncated at start, so a `--only` run
#: launched while a full run was in flight silently destroyed the full run's
#: evidence -- found 2026-09-25 by doing exactly that. A reader takes the last
#: `suite_start` and filters on its run_id.
_RUN_ID = f'{int(_T0)}-{os.getpid()}'


def _emit(rec: dict, echo: str = '') -> None:
    """Append one progress record and flush. Never fails the run."""
    rec = {'run_id': _RUN_ID, 't': round(time.time() - _T0, 2), **rec}
    try:
        with open(PROGRESS_PATH, 'a') as fh:
            fh.write(json.dumps(rec, sort_keys=True) + '\n')
    except OSError:
        pass
    if echo:
        print(echo, flush=True)



def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    verbose = '-v' in argv
    # `--only SUBSTR` restricts discovery. It exists so the harness can prove
    # itself against a seeded module without a full run, and it never changes
    # how a discovered module is judged.
    only = None
    if '--only' in argv:
        only = argv[argv.index('--only') + 1]
    os.chdir(ROOT)
    for q in (ROOT, os.path.join(ROOT, 'sportsplatform')):
        if q not in sys.path:
            sys.path.insert(0, q)
    files = (sorted(glob.glob('nfl/tests/test_*.py'))
             + sorted(glob.glob('sportsplatform/**/test_*.py', recursive=True)))
    if only:
        files = [f for f in files if only in f]
    n_fn = n_raise = n_check_fail = n_check_ok = 0
    n_not_executed = []
    n_fn_zero = n_fn_blocked = n_unrecognised_tally = 0
    zero_fns, blocked_fns = [], []
    problems = []
    _emit({'phase': 'suite_start', 'n_modules': len(files)},
          f'suite: {len(files)} module(s)')
    for i, f in enumerate(files, 1):
        _emit({'phase': 'module_start', 'i': i, 'module': f},
              f'[{i}/{len(files)}] {f}')
        name = 't_' + f.replace('/', '_')[:-3]
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                spec.loader.exec_module(mod)
        except Exception:                                        # noqa: BLE001
            n_raise += 1
            problems.append(f'IMPORT {f}\n{traceback.format_exc(limit=3)}')
            _emit({'phase': 'module_done', 'i': i, 'module': f,
                   'result': 'IMPORT_ERROR'},
                  f'[{i}/{len(files)}] {f}  IMPORT ERROR')
            continue
        fns = [n for n in dir(mod)
               if n.startswith('test_') and callable(getattr(mod, n))]
        before = tally(mod)
        # A MODULE WITH NEITHER A TEST FUNCTION NOR A RECOGNISED COUNTER USED
        # TO ESCAPE BOTH GUARDS. Found 2026-09-25 by writing one.
        #
        # `UNRECOGNISED_TALLY` below is guarded by `if fns and ...`, so a module
        # exposing no `test_*` name never reaches it. `TEST_MODULE_NOT_EXECUTED`
        # used to live further down, AFTER an `if after is None: continue`, so a
        # module with no counter never reached that either. Two modules holding
        # 49 checks between them sat in exactly that gap and the suite printed
        # `0 fn, NO TALLY` and passed. The detection is hoisted here, before any
        # early exit, because a guard that a defect can walk around is not one.
        if not fns and _has_checks(f):
            n_not_executed.append(f)
            problems.append(
                f'TEST_MODULE_NOT_EXECUTED {f}: the module contains check '
                f'calls and exposes no test_* function, so this runner '
                f'executed NONE of them. Direct `python3.12 {f}` is not the '
                f'authoritative execution path and its exit code is not a '
                f'test result.')
        # AN UNRECOGNISED COUNTER IS A REFUSAL, NOT A SKIP.
        #
        # `tally` returns None when a module's counters are not one of the
        # pairs in `_TALLY`. Every per-function accounting branch below is
        # guarded by `if now is not None`, so such a module ran its tests and
        # contributed NOTHING: no checks, no failures, no zero-check entry.
        # Four modules written on 2026-09-21 used `_P, _F` and were invisible
        # exactly this way -- 177 checks reported to a human as passing that
        # the suite had never counted, one of which asserted a production
        # guard was load-bearing. A measurement system that silently ignores
        # a measurement is the false-green class inside the instrument.
        #
        # Refusing by name is what stops the next module repeating it.
        if fns and before is None:
            n_unrecognised_tally += 1
            problems.append(
                f'UNRECOGNISED_TALLY {f}\n'
                f'  {len(fns)} test function(s) ran and NOT ONE check could '
                f'be counted, because the module exposes no counter pair this '
                f'runner recognises.\n'
                f'  Every check in it is invisible: if all of them failed the '
                f'suite would still report PASS.\n'
                f'  Use one of: '
                + ', '.join(f'{a}/{b}' for a, b in _TALLY)
                + ' as MODULE-LEVEL names.')
        # PER-FUNCTION ACCOUNTING. `prev` walks forward one function at a time
        # so the delta is attributable to the function that produced it.
        prev = before
        prev_bl = blocked_tally(mod)
        tripwires = tally_tripwires(f)
        for n in fns:
            n_fn += 1
            raised_here = False
            try:
                with redirect_stdout(buf):
                    getattr(mod, n)()
            except Exception:                                    # noqa: BLE001
                raised_here = True
                n_raise += 1
                problems.append(f'RAISED {f}::{n}\n'
                                f'{traceback.format_exc(limit=3)}')
            now = tally(mod)
            now_bl = blocked_tally(mod)
            if now is not None and prev is not None:
                d_check = (now[0] - prev[0]) + (now[1] - prev[1])
                d_block = now_bl - prev_bl
                if d_check == 0 and not raised_here and n not in tripwires:
                    if d_block:
                        n_fn_blocked += 1
                        blocked_fns.append(f'{f}::{n}')
                    else:
                        n_fn_zero += 1
                        zero_fns.append(f'{f}::{n}')
            prev, prev_bl = now, now_bl
        after = tally(mod)
        if after is None:
            # A module with no tally is judged only on exceptions; say so
            # rather than implying its checks were read.
            _emit({'phase': 'module_done', 'i': i, 'module': f,
                   'result': 'NO_TALLY', 'n_fn': len(fns)},
                  f'[{i}/{len(files)}] {f}  {len(fns)} fn, NO TALLY')
            continue
        ok, bad = after
        if before is not None:
            ok -= before[0]; bad -= before[1]
        n_check_ok += ok; n_check_fail += bad
        if bad:
            lines = [ln for ln in buf.getvalue().splitlines()
                     if ln.strip().startswith('FAIL')]
            problems.append(f'CHECKS {f}: {bad} failing check(s)\n  '
                            + '\n  '.join(lines[:20]))
        elif ok == 0 and fns:
            problems.append(f'VACUOUS {f}: {len(fns)} test function(s) ran '
                            f'and recorded ZERO checks. A module that '
                            f'measured nothing has not passed.')
        # TEST_MODULE_NOT_EXECUTED (owner ruling 2026-09-23) is detected
        # above, before any early exit, so it is not repeated here.
        _emit({'phase': 'module_done', 'i': i, 'module': f,
               'result': 'FAIL' if bad else 'OK', 'n_fn': len(fns),
               'checks_ok': ok, 'checks_failing': bad},
              f'[{i}/{len(files)}] {f}  {len(fns)} fn, {ok} check(s), '
              f'{bad} failing')
    _emit({'phase': 'suite_scan_done', 'n_modules': len(files)})
    if zero_fns:
        problems.append(
            f'ZERO-CHECK FUNCTIONS: {len(zero_fns)} test function(s) ran and '
            f'recorded ZERO checks. A function that measured nothing has not '
            f'passed. If it genuinely could not run, say so with a blocked() '
            f'counter; do not return silently.\n  '
            + '\n  '.join(zero_fns))
    print(f'\nmodules {len(files)}  test functions {n_fn}  '
          f'checks {n_check_ok + n_check_fail}  '
          f'FAILING CHECKS {n_check_fail}  RAISED {n_raise}  '
          f'ZERO-CHECK FUNCTIONS {n_fn_zero}  BLOCKED FUNCTIONS '
          f'{n_fn_blocked}  UNRECOGNISED TALLIES {n_unrecognised_tally}')
    if blocked_fns:
        print('blocked (declared, not a pass, not a failure):')
        for b in blocked_fns:
            print(f'  {b}')
    for p in problems:
        print('\n' + p)
    bad = (n_check_fail + n_raise + n_fn_zero + n_unrecognised_tally
           + len(n_not_executed)
           + sum(p.startswith('VACUOUS') for p in problems))
    print('SUITE ' + ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
