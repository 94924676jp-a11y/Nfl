#!/usr/bin/env python3.12
"""The completion certificate refuses every incomplete success-looking run (nfl/tests/certify_suite.py).

    python3.12 nfl/tests/test_certify_suite.py

Each case builds a throw-away root holding a COPY of the real nfl/tests/run_suite.py and a few fixture modules,
one of them sabotaged, and runs the real supervisor over it. Nothing touches this repository's tree.

  clean                    -> CERTIFIED_COMPLETE (the control: the certifier can say yes)
  failing check            -> FAILED (complete, honest red)
  import-time sys.exit(0)  -> FAILED, never certified (the runner now names it; 2026-10-07 defect)
  in-test sys.exit(0)      -> FAILED, never certified
  os._exit(0) at import    -> INCOMPLETE (exit 0, no terminal record)
  os._exit(0) in a test    -> INCOMPLETE
  SIGKILL / SIGTERM        -> INCOMPLETE, signal named
  timeout                  -> INCOMPLETE, TIMEOUT
  no modules at all        -> INCOMPLETE (runner NOT_EXECUTED)
  zero-check function      -> FAILED, never certified
  foreign / stale record   -> INCOMPLETE
  duplicate + missing      -> INCOMPLETE, both named (a count-preserving swap is still caught)
  torn record              -> INCOMPLETE, TRUNCATED_RECORD
  test file added mid-run  -> INCOMPLETE, MANIFEST_CHANGED_DURING_RUN
  restricted run           -> INCOMPLETE, MISSING_MODULES
and the pure judge: exit 0 with a FAIL terminal record is INCOMPLETE (EXIT_CODE_DISAGREES).
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import textwrap

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tests import certify_suite as CS  # noqa: E402

PASSED = FAILED = 0

GOOD = '''
PASSED = FAILED = 0
def check(ok, msg):
    global PASSED, FAILED
    if ok: PASSED += 1
    else: FAILED += 1
    print(('  ok   ' if ok else '  FAIL ') + msg)
def test_one():
    check(True, 'fixture check')
'''
EMIT = '''
import json, os
def _forge(rec):
    with open(os.environ['NFL_SUITE_PROGRESS'], 'a') as fh:
        fh.write(rec)
'''
SAB = {
    'fail': GOOD.replace('check(True', 'check(False'),
    'import_exit0': 'import sys\nsys.exit(0)\n' + GOOD,
    'fn_exit0': GOOD + 'def test_two():\n    import sys\n    sys.exit(0)\n',
    'import_os_exit0': 'import os\nos._exit(0)\n' + GOOD,
    'fn_os_exit0': GOOD + 'def test_two():\n    import os\n    os._exit(0)\n',
    'sigkill': GOOD + 'def test_two():\n    import os, signal\n    os.kill(os.getpid(), signal.SIGKILL)\n',
    'sigterm': GOOD + 'def test_two():\n    import os, signal\n    os.kill(os.getpid(), signal.SIGTERM)\n',
    'sleep': GOOD + 'def test_two():\n    import time\n    time.sleep(120)\n',
    'zero_check': GOOD + 'def test_two():\n    return\n',
    'foreign': GOOD + EMIT + 'def test_two():\n    check(True, "x")\n'
               '    _forge(json.dumps({"run_id": "1-1", "phase": "suite_done", "verdict": "PASS"}) + "\\n")\n',
    'dup': GOOD + EMIT + 'def test_two():\n    check(True, "x")\n'
           '    _forge(json.dumps({"run_id": os.environ["NFL_SUITE_RUN_ID"], "phase": "module_done", '
           '"module": "nfl/tests/test_a.py", "result": "OK"}) + "\\n")\n',
    'torn': GOOD + EMIT + 'def test_two():\n    check(True, "x")\n    _forge(\'{"run_id": "torn", "pha\')\n',
    'add_file': GOOD + 'def test_two():\n    check(True, "x")\n    import pathlib\n'
                '    pathlib.Path(__file__).with_name("test_zz_late.py").write_text("PASSED = FAILED = 0\\n")\n',
}


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {msg}')
    else:
        FAILED += 1
        print(f'  FAIL {msg}')


def _root(td, modules):
    r = pathlib.Path(td) / 'root'
    (r / 'nfl/tests').mkdir(parents=True)
    shutil.copy2(_REPO / 'nfl/tests/run_suite.py', r / 'nfl/tests/run_suite.py')
    for name, src in modules.items():
        (r / f'nfl/tests/test_{name}.py').write_text(textwrap.dedent(src))
    return r


def _cert(modules, timeout=30, runner_args=()):
    with tempfile.TemporaryDirectory() as td:
        root = _root(td, modules)
        _, c = CS.certify(root, timeout, pathlib.Path(td) / 'out', runner_args, 'FIXTURE')
        return c


def _expect(name, modules, verdict, reason=None, **kw):
    c = _cert(modules, **kw)
    ok = c['VERDICT'] == verdict and (reason is None or any(r.startswith(reason) for r in c['reasons']))
    check(ok, f"{name}: {c['VERDICT']} {[r[:60] for r in c['reasons']][:3]} (exit {c['child']['exit_code']})")
    check(c['VERDICT'] != CS.CERTIFIED or name == 'clean', f'{name}: never certified unless clean')
    return c


def test_control_and_honest_failures():
    c = _expect('clean', {'a': GOOD, 'b': GOOD}, CS.CERTIFIED)
    check(c['completed_modules'] == 2 and c['manifest']['n_modules'] == 2 and c['terminal_record']['verdict'] == 'PASS',
          'clean run: identity sets match, terminal record present')
    _expect('failing check', {'a': GOOD, 'b': SAB['fail']}, CS.FAILED)
    _expect('zero-check function', {'a': GOOD, 'b': SAB['zero_check']}, CS.FAILED)


def test_normal_exits_are_never_a_pass():
    _expect('import-time sys.exit(0)', {'a': GOOD, 'b': SAB['import_exit0'], 'c': GOOD}, CS.FAILED)
    _expect('in-test sys.exit(0)', {'a': GOOD, 'b': SAB['fn_exit0'], 'c': GOOD}, CS.FAILED)


def test_hard_exits_signals_timeout():
    _expect('os._exit(0) at import', {'a': GOOD, 'b': SAB['import_os_exit0'], 'c': GOOD}, CS.INCOMPLETE,
            'MISSING_MODULES')
    _expect('os._exit(0) in a test', {'a': GOOD, 'b': SAB['fn_os_exit0']}, CS.INCOMPLETE, 'MISSING_MODULES')
    _expect('SIGKILL', {'a': GOOD, 'b': SAB['sigkill']}, CS.INCOMPLETE, 'MISSING_MODULES')
    c = _cert({'a': GOOD, 'b': SAB['sigkill']})
    check(any(r.startswith('KILLED_BY_SIGNAL SIGKILL') for r in c['reasons']), 'the signal is named')
    _expect('SIGTERM', {'a': GOOD, 'b': SAB['sigterm']}, CS.INCOMPLETE, 'MISSING_MODULES')
    _expect('timeout', {'a': GOOD, 'b': SAB['sleep']}, CS.INCOMPLETE, 'TIMEOUT', timeout=8)


def test_empty_stale_duplicate_torn_changed_restricted():
    _expect('no modules', {}, CS.INCOMPLETE)
    _expect('foreign/stale record', {'a': GOOD, 'b': SAB['foreign']}, CS.INCOMPLETE, 'FOREIGN_OR_STALE_RECORDS')
    c = _expect('duplicate + missing (count preserved)', {'a': GOOD, 'b': SAB['dup'], 'c': GOOD}, CS.INCOMPLETE,
                runner_args=('--modules', 'test_a,test_b'))
    names = ' '.join(c['reasons'])
    check('MISSING_MODULES' in names and 'DUPLICATE_MODULE_RECORDS' in names,
          'a duplicate plus a missing module is caught by identity, not count')
    _expect('torn record', {'a': GOOD, 'b': SAB['torn'], 'c': GOOD}, CS.INCOMPLETE, 'TRUNCATED_RECORD')
    _expect('test file added mid-run', {'a': GOOD, 'b': SAB['add_file']}, CS.INCOMPLETE, 'MANIFEST_CHANGED_DURING_RUN')
    _expect('restricted run', {'a': GOOD, 'b': GOOD}, CS.INCOMPLETE, 'MISSING_MODULES', runner_args=('--only', 'test_a'))


def test_pure_judge():
    exp = ['nfl/tests/test_a.py']
    rid = 'r1'
    recs = [{'run_id': rid, 'phase': 'suite_start', 'n_modules': 1},
            {'run_id': rid, 'phase': 'module_start', 'module': exp[0]},
            {'run_id': rid, 'phase': 'module_done', 'module': exp[0], 'result': 'FAIL'},
            {'run_id': rid, 'phase': 'suite_done', 'verdict': 'FAIL', 'n_modules': 1, 'n_checks_executed': 3}]
    v, r, _ = CS.judge(exp, recs, 0, False, 'SUITE FAIL\n', True)
    check(v == CS.INCOMPLETE and any(x.startswith('EXIT_CODE_DISAGREES') for x in r),
          f'exit 0 with a FAIL terminal record is INCOMPLETE ({r})')
    v, r, _ = CS.judge(exp, recs, 1, False, 'SUITE FAIL\n', True)
    check(v == CS.FAILED and r == [], 'the same evidence with exit 1 is an honest, complete FAILED')
    v, r, _ = CS.judge(exp, recs[:-1], 0, False, '', True)
    check(v == CS.INCOMPLETE and any(x.startswith('TERMINAL_RECORD_COUNT 0') for x in r),
          'no terminal record and exit 0 is INCOMPLETE, not PASS')


if __name__ == '__main__':
    for t in (test_control_and_honest_failures, test_normal_exits_are_never_a_pass, test_hard_exits_signals_timeout,
              test_empty_stale_duplicate_torn_changed_restricted, test_pure_judge):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
