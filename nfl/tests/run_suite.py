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
"""
from __future__ import annotations

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


def tally(mod):
    for p, f in _TALLY:
        if hasattr(mod, p) and hasattr(mod, f):
            return int(getattr(mod, p)), int(getattr(mod, f))
    return None


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
        for n in fns:
            n_fn += 1
            try:
                with redirect_stdout(buf):
                    getattr(mod, n)()
            except Exception:                                    # noqa: BLE001
                n_raise += 1
                problems.append(f'RAISED {f}::{n}\n'
                                f'{traceback.format_exc(limit=3)}')
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
    print(f'\nmodules {len(files)}  test functions {n_fn}  '
          f'checks {n_check_ok + n_check_fail}  '
          f'FAILING CHECKS {n_check_fail}  RAISED {n_raise}')
    for p in problems:
        print('\n' + p)
    bad = n_check_fail + n_raise + sum(p.startswith('VACUOUS') for p in problems)
    print('SUITE ' + ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
