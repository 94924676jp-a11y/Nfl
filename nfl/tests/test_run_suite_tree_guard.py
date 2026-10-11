#!/usr/bin/env python3.12
"""The runner's tree guard (task #45 P0-1) is itself tested: a module that writes into the repository turns
the real runner red and is named; a module that writes nothing stays green; and the snapshot logic sees a
modified tracked file, a new untracked file and a re-modified dirty file, but not an ignored one.

WHY. On 2026-10-11, run directly, test_slate_to_portfolio rewrote three tracked files and no runner noticed.
A guard that has never been seen to fire is not a guard, so this file seeds a real writer and runs the real
runner over it, the same construction test_harness_audit uses for failing checks.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import run_suite as RS  # noqa: E402

TESTS_DIR = _REPO / 'nfl/tests'
PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _git(root, *a):
    return subprocess.run(['git', *a], cwd=root, capture_output=True, text=True, check=True)


def test_01_snapshot_sees_what_a_write_changes():
    print('\n01. the snapshot sees tracked, untracked and re-dirtied paths, and not ignored ones')
    with tempfile.TemporaryDirectory() as d:
        _git(d, 'init', '-q')
        _git(d, 'config', 'user.email', 't@t')
        _git(d, 'config', 'user.name', 't')
        pathlib.Path(d, 'tracked.txt').write_text('a\n')
        pathlib.Path(d, 'dirty.txt').write_text('a\n')
        pathlib.Path(d, '.gitignore').write_text('cache.json\n')
        _git(d, 'add', '.')
        _git(d, 'commit', '-q', '-m', 'base')
        pathlib.Path(d, 'dirty.txt').write_text('already dirty\n')      # dirty before the run starts
        s0 = RS.tree_snapshot(d)
        check('negative control: two snapshots of an untouched tree are equal',
              RS.tree_diff(s0, RS.tree_snapshot(d)) == [], RS.tree_diff(s0, RS.tree_snapshot(d)))
        pathlib.Path(d, 'tracked.txt').write_text('b\n')
        pathlib.Path(d, 'new.txt').write_text('new\n')
        pathlib.Path(d, 'dirty.txt').write_text('dirtier\n')
        pathlib.Path(d, 'cache.json').write_text('{}')
        diff = RS.tree_diff(s0, RS.tree_snapshot(d))
        check('a modified tracked file is seen', 'tracked.txt' in diff, diff)
        check('a new untracked, not-ignored file is seen', 'new.txt' in diff, diff)
        check('a file already dirty before the run is seen when it changes again', 'dirty.txt' in diff, diff)
        check('an ignored file is out of reach (declared, not hidden)', 'cache.json' not in diff, diff)
        check('the exclusion is by exact path', RS.tree_diff(s0, RS.tree_snapshot(d), ['new.txt']) ==
              sorted(set(diff) - {'new.txt'}))
        os.remove(pathlib.Path(d, 'new.txt'))
        pathlib.Path(d, 'tracked.txt').write_text('a\n')
        pathlib.Path(d, 'dirty.txt').write_text('already dirty\n')
        check('a write that is undone before the check leaves no trace (net change is what is judged)',
              RS.tree_diff(s0, RS.tree_snapshot(d)) == [], RS.tree_diff(s0, RS.tree_snapshot(d)))


def _run_suite(only):
    return subprocess.run([sys.executable, str(TESTS_DIR / 'run_suite.py'), '--only', only],
                          capture_output=True, text=True, cwd=str(_REPO), timeout=300)


WRITER = '''
import pathlib
PASSED = FAILED = 0


def test_writes_into_the_repository():
    global PASSED
    pathlib.Path(__file__).with_name('_zzz_tree_guard_probe.txt').write_text('written by a test')
    PASSED += 1
'''

CLEAN = '''
import pathlib, tempfile
PASSED = FAILED = 0


def test_writes_only_under_a_temporary_root():
    global PASSED
    pathlib.Path(tempfile.mkdtemp(), 'x.txt').write_text('fine')
    PASSED += 1
'''


def test_02_the_real_runner_turns_red_on_a_writer_and_names_it():
    print('\n02. a seeded module that writes into the repository turns the real runner red')
    seed = TESTS_DIR / 'test_zzz_seeded_tree_writer.py'
    probe = TESTS_DIR / '_zzz_tree_guard_probe.txt'
    try:
        seed.write_text(WRITER)
        r = _run_suite(seed.stem)
        out = r.stdout
        check('the runner exits non-zero', r.returncode != 0, f'rc={r.returncode}')
        check('it prints SUITE FAIL', 'SUITE FAIL' in out, out[-300:])
        check('it names TREE_WRITTEN, the module and the path',
              'TREE_WRITTEN' in out and seed.name in out and probe.name in out, out[-500:])
    finally:
        for p in (seed, probe):
            if p.exists():
                p.unlink()
        check('the seed and the probe are removed afterwards', not seed.exists() and not probe.exists())


def test_03_a_module_that_writes_only_to_a_temporary_root_is_green():
    print('\n03. and it is not simply always red')
    seed = TESTS_DIR / 'test_zzz_seeded_tree_clean.py'
    try:
        seed.write_text(CLEAN)
        r = _run_suite(seed.stem)
        check('a module writing only under a temporary root passes',
              r.returncode == 0 and 'SUITE PASS' in r.stdout and 'TREE_WRITTEN' not in r.stdout,
              f'rc={r.returncode} {r.stdout[-300:]}')
    finally:
        if seed.exists():
            seed.unlink()
    check('that seed is removed too', not seed.exists())


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    assert FAILED == 0, f'{FAILED} check(s) failed'


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            _f()
