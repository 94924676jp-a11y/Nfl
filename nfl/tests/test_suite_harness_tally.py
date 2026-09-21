"""The harness must REFUSE a module whose checks it cannot count.

WHY THIS TEST EXISTS

On 2026-09-21 four test modules were written using module-level `_P, _F`.
That pair is not in `run_suite._TALLY`, so `tally(mod)` returned None, every
per-function accounting branch was skipped, and the modules reported `checks
0` while the suite said PASS. 177 checks -- including one asserting that a
production guard was load-bearing -- were reported to a human as passing and
had never been counted. If every one of them had failed, the suite would
still have been green.

Fixing those four modules is not the repair. The repair is that the harness
can no longer ignore a module it cannot measure, so the fifth module to make
the mistake is caught by the instrument instead of by luck.

THE PROOF IS END TO END, NOT A UNIT CALL

A fixture module with an unrecognised counter AND a deliberately failing
check is written into the discovery path, the real runner is invoked on it as
a subprocess, and the test asserts the runner exits non-zero naming
UNRECOGNISED_TALLY. A unit test of `tally()` would not prove the runner acts
on the answer, which is precisely what went wrong.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = FAILED = 0
RUNNER = _REPO / 'nfl' / 'tests' / 'run_suite.py'
#: Written into the discovery path and removed in a finally. The name is
#: deliberately loud so a leaked copy is obvious rather than quietly joining
#: the real suite.
FIXTURE = _REPO / 'nfl' / 'tests' / 'test_zzz_TEMP_tally_fixture.py'

BAD_COUNTER = '''"""Temporary fixture. Unrecognised counter, one failing check."""
_P, _F = 0, 0


def ck(cond):
    global _P, _F
    if cond:
        _P += 1
    else:
        _F += 1


def test_one_check_that_fails():
    ck(False)
'''

GOOD_COUNTER = BAD_COUNTER.replace('_P, _F = 0, 0', 'PASSED = FAILED = 0') \
    .replace('global _P, _F', 'global PASSED, FAILED') \
    .replace('_P += 1', 'PASSED += 1').replace('_F += 1', 'FAILED += 1')


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _run_suite_on_fixture(source: str):
    FIXTURE.write_text(source)
    try:
        return subprocess.run(
            [sys.executable, str(RUNNER), '--only',
             'test_zzz_TEMP_tally_fixture'],
            cwd=str(_REPO), capture_output=True, text=True, timeout=300)
    finally:
        FIXTURE.unlink(missing_ok=True)


def test_an_unrecognised_counter_is_refused_not_skipped():
    r = _run_suite_on_fixture(BAD_COUNTER)
    ok(r.returncode != 0,
       f'the runner exits non-zero on an unmeasurable module '
       f'(rc={r.returncode})')
    ok('UNRECOGNISED_TALLY' in r.stdout,
       'and names the refusal UNRECOGNISED_TALLY')
    ok('SUITE FAIL' in r.stdout, 'and the suite verdict is FAIL')
    ok('PASSED/FAILED' in r.stdout,
       'and tells the author which names are accepted')
    ok('UNRECOGNISED TALLIES 1' in r.stdout,
       f'and counts it in the summary line')


def test_the_same_module_with_a_recognised_counter_is_measured():
    """Control: the refusal is about COUNTABILITY, not about failing."""
    r = _run_suite_on_fixture(GOOD_COUNTER)
    ok('UNRECOGNISED TALLIES 0' in r.stdout,
       'a recognised counter is not refused')
    ok('FAILING CHECKS 1' in r.stdout,
       'and its failing check is COUNTED rather than ignored')
    ok(r.returncode != 0, 'so the suite fails for the real reason instead')


def test_no_module_in_the_tree_has_an_unrecognised_counter():
    """The repair is complete, not just applied to the four known modules."""
    import glob
    import importlib.util
    import io
    from contextlib import redirect_stdout
    sys.path.insert(0, str(_REPO / 'sportsplatform'))
    from nfl.tests import run_suite as RS
    offenders = []
    files = (sorted(glob.glob(str(_REPO / 'nfl/tests/test_*.py')))
             + sorted(glob.glob(str(_REPO / 'sportsplatform/**/test_*.py'),
                                recursive=True)))
    for f in files:
        if pathlib.Path(f) == FIXTURE:
            continue
        spec = importlib.util.spec_from_file_location('probe_' + pathlib.Path(
            f).stem, f)
        mod = importlib.util.module_from_spec(spec)
        try:
            with redirect_stdout(io.StringIO()):
                spec.loader.exec_module(mod)
        except Exception:                                    # noqa: BLE001
            continue
        fns = [n for n in dir(mod)
               if n.startswith('test_') and callable(getattr(mod, n))]
        if fns and RS.tally(mod) is None:
            offenders.append(pathlib.Path(f).name)
    ok(not offenders,
       f'every module with test functions exposes a countable tally '
       f'({len(files)} scanned); offenders: {offenders}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


def main():
    for t in (test_an_unrecognised_counter_is_refused_not_skipped,
              test_the_same_module_with_a_recognised_counter_is_measured,
              test_no_module_in_the_tree_has_an_unrecognised_counter):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
