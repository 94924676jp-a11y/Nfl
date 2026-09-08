"""The test harness is itself measured. It was wrong once and printed green.

WHAT HAPPENED

Every module here reports through a module-level `check()` that increments a
counter and PRINTS -- it does not raise. The ad-hoc runner in use before
2026-09-08 counted only test functions that threw. With one failing check
deliberately seeded it still printed `TESTS 302  FAILURES 0`. That is this
project's Class A failure mode -- absence of an exception read as success --
occurring inside the measurement system, which is worse than a bad model
because it is what tells you whether the model is bad.

`nfl/tests/run_suite.py` is the committed replacement. This file proves it
turns red, against BOTH reporting styles in the repository, by seeding a real
failing module and running the real runner over it.
"""
from __future__ import annotations

import glob
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
from contextlib import redirect_stdout

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = FAILED = 0
TESTS_DIR = _REPO / 'nfl' / 'tests'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _run_suite(only):
    return subprocess.run(
        [sys.executable, str(TESTS_DIR / 'run_suite.py'), '--only', only],
        capture_output=True, text=True, cwd=str(_REPO), timeout=300)


# The two reporting styles actually present in this repository.
SEEDS = {
    'tally-backed': '''
PASSED = FAILED = 0


def check(label, ok):
    global PASSED, FAILED
    if ok:
        PASSED += 1
    else:
        FAILED += 1
        print(f'  FAIL {label}')


def test_seeded():
    check('SEEDED tally failure', False)
    check('a passing one beside it', True)
''',
    'exception-only': '''
def test_seeded():
    assert False, 'SEEDED exception failure'
''',
    'vacuous': '''
PASSED = FAILED = 0


def test_seeded():
    pass
''',
}


# ==========================================================================
def test_A_the_runner_turns_red_on_each_style():
    print('\nA. a seeded failure turns the real runner red, in every style')
    for style, body in SEEDS.items():
        name = f'test_zzz_seeded_{style.replace("-", "_")}.py'
        path = TESTS_DIR / name
        try:
            path.write_text(body)
            r = _run_suite(name[:-3])
            out = r.stdout
            check(f'  {style}: the runner exits non-zero',
                  r.returncode != 0, f'rc={r.returncode}')
            check(f'  {style}: it prints SUITE FAIL',
                  'SUITE FAIL' in out, out[-200:])
            check(f'  {style}: and it names the seeded module',
                  name in out, out[-300:])
        finally:
            # SELF-CLEANING. A seeded failure left behind would be a defect
            # this file introduced while testing for defects.
            if path.exists():
                path.unlink()
            check(f'  {style}: the seed is removed afterwards',
                  not path.exists())


def test_B_a_clean_module_is_green():
    print('\nB. and it is not simply always red')
    name = 'test_zzz_seeded_clean.py'
    path = TESTS_DIR / name
    try:
        path.write_text('PASSED = FAILED = 0\n\n\ndef test_ok():\n'
                        '    global PASSED\n    PASSED += 1\n')
        r = _run_suite(name[:-3])
        check('  a clean tally-backed module passes',
              r.returncode == 0 and 'SUITE PASS' in r.stdout,
              f'rc={r.returncode} {r.stdout[-200:]}')
    finally:
        if path.exists():
            path.unlink()
    check('  and that seed is removed too', not path.exists())


def test_C_every_module_is_observed():
    print('\nC. no module can fail internally while the runner reports green')
    import importlib
    rs_mod = importlib.import_module('nfl.tests.run_suite')
    os.chdir(_REPO)
    for q in (str(_REPO), str(_REPO / 'sportsplatform')):
        if q not in sys.path:
            sys.path.insert(0, q)
    files = (sorted(glob.glob('nfl/tests/test_*.py'))
             + sorted(glob.glob('sportsplatform/**/test_*.py', recursive=True)))
    tally = exception_only = vacuous = 0
    unobserved = []
    for f in files:
        spec = importlib.util.spec_from_file_location(
            'audit_' + f.replace('/', '_')[:-3], f)
        mod = importlib.util.module_from_spec(spec)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                spec.loader.exec_module(mod)
        except Exception:                                        # noqa: BLE001
            continue
        fns = [n for n in dir(mod)
               if n.startswith('test_') and callable(getattr(mod, n))]
        # READ THE RUNNER'S OWN LIST, never a copy of it. A hardcoded copy
        # here would drift from the runner and this audit would then certify a
        # capability the runner does not have -- the same defect one level up.
        has_tally = rs_mod.tally(mod) is not None
        if has_tally:
            tally += 1
        elif fns:
            # Judged on exceptions alone. That is sound ONLY if the module
            # really does raise rather than print -- these use bare `assert`.
            exception_only += 1
            src = pathlib.Path(f).read_text()
            if 'def check(' in src and 'raise' not in src:
                unobserved.append(f)
        else:
            vacuous += 1
    check(f'{len(files)} modules discovered: {tally} tally-backed, '
          f'{exception_only} exception-only, {vacuous} with no test function',
          len(files) > 25, str(len(files)))
    check('  NO module reports through a counter the runner cannot read -- '
          'that combination is the one that prints green while failing',
          not unobserved, str(unobserved))
    check('  and no module has zero test functions', vacuous == 0, str(vacuous))


def test_D_the_runner_refuses_a_vacuous_module():
    print('\nD. a module that measured nothing has not passed')
    src = (TESTS_DIR / 'run_suite.py').read_text()
    check('the runner has an explicit VACUOUS branch', 'VACUOUS' in src)
    check('  it counts vacuous modules as failure',
          "p.startswith('VACUOUS')" in src)
    check('  and it reads a tally rather than counting exceptions',
          'def tally' in src and 'FAILING CHECKS' in src)


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for _n in sorted(n for n in dir() if n.startswith('test_')):
        globals()[_n]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
