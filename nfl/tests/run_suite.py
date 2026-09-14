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
import os
import sys
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
    n_fn_zero = n_fn_blocked = 0
    zero_fns, blocked_fns = [], []
    problems = []
    for f in files:
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
            continue
        fns = [n for n in dir(mod)
               if n.startswith('test_') and callable(getattr(mod, n))]
        before = tally(mod)
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
            if verbose:
                print(f'  {f}: {len(fns)} function(s), NO TALLY (exceptions '
                      f'only)')
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
        if verbose:
            print(f'  {f}: {len(fns)} function(s), {ok} check(s), {bad} failing')
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
          f'{n_fn_blocked}')
    if blocked_fns:
        print('blocked (declared, not a pass, not a failure):')
        for b in blocked_fns:
            print(f'  {b}')
    for p in problems:
        print('\n' + p)
    bad = (n_check_fail + n_raise + n_fn_zero
           + sum(p.startswith('VACUOUS') for p in problems))
    print('SUITE ' + ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
