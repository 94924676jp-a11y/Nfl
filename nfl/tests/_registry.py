"""Expose a `@check`-registered module to run_suite as discoverable test functions.

WHY THIS EXISTS. `run_suite.py` is the authoritative execution path and it discovers `test_*`
functions and reads module-level PASSED/FAILED counters. A module that instead collects its checks
into a list and runs them from `main()` exposes neither, so the runner reports
`0 fn, NO TALLY / TEST_MODULE_NOT_EXECUTED` and runs NONE of its checks -- while
`python3.12 nfl/tests/<module>.py` prints a confident "N passed, 0 failed". That is this project's
Class A failure mode inside the measurement system: a green line that measured nothing the suite can
see. Eighteen modules in this tree were already in that state, including test_lineage,
test_readiness, test_v1_projection and test_sunday_run.

`emit(globals(), RESULTS)` at the bottom of such a module turns each registered check into a real
`test_*` function in the module namespace and keeps PASSED/FAILED updated as they run, so the runner
executes and counts them. It changes no check and no assertion; it only makes them visible.
"""
from __future__ import annotations

import re


def _slug(name: str, i: int) -> str:
    s = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:70]
    return f'test_{i:02d}_{s or "check"}'


def emit(namespace: dict, results) -> list:
    """Define one test_* function per registered check, plus the tally the runner reads."""
    namespace.setdefault('PASSED', 0)
    namespace.setdefault('FAILED', 0)
    namespace.setdefault('NOT_EXECUTED', [])
    made = []
    for i, (name, fn) in enumerate(results, start=1):
        def _wrap(_name=name, _fn=fn):
            try:
                detail = _fn()
            except AssertionError as e:
                namespace['FAILED'] += 1
                print(f'FAIL  {_name}\n        {e}')
                raise
            except Exception as e:  # noqa: BLE001
                namespace['FAILED'] += 1
                print(f'ERROR {_name}\n        {type(e).__name__}: {e}')
                raise
            namespace['PASSED'] += 1
            print(f'pass  {_name}\n        {detail}')
            return detail
        fname = _slug(name, i)
        _wrap.__name__ = fname
        _wrap.__doc__ = name
        namespace[fname] = _wrap
        made.append(fname)
    return made


# THE TALLY TRIPWIRE IS NOT GENERATED HERE, deliberately. run_suite recognises it by AST SHAPE from
# the module's own source -- a function that raises, names a failure counter and calls nothing but
# print or AssertionError -- so one defined inside this helper is invisible to that check and gets
# counted as a zero-check function instead. Each module carries its own literal tripwire.
