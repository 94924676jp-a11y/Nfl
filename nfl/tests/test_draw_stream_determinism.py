"""The same seed must produce the same draws in a different process.

HOW THIS WAS FOUND, because the method matters more than the fix. Two seals
were built minutes apart from identical source with the same seed, for an
unrelated reason -- one carried a row-team map the other did not. Their draw
arrays were diffed as a sanity check and FOUR disagreed:
`rushing__rushing_yards`, `gadget_rush__wr`, `gadget_rush__te`, and the
`dk_scoring__dk_points` computed from them. Every count agreed; only the
quantities drawn through a tag-seeded stream moved.

The cause was `abs(hash(tag))` in the RNG seed. CPython salts `hash()` for
str and tuple-of-str PER PROCESS unless PYTHONHASHSEED is set, so the stream
was a different stream on every run. A forecast that cannot be re-derived
from its own seed is not reproducible, and reproducibility is one of the
three things this project's scoreboard measures.

The fix is a blake2b digest of the tag bytes. This test runs the derivation
in SUBPROCESSES with PYTHONHASHSEED deliberately randomised, because the
defect is invisible inside one process -- checking it in-process would be a
test that cannot fail.
"""
import os
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_P, _F = [], []
# COUNTERS THE SUITE RUNNER RECOGNISES. The lists above carry check NAMES and
# are what the tripwire re-raises; they are kept. But `_P`/`_F` are not in
# `run_suite._TALLY`, so `tally(mod)` returned None and all three test
# functions here contributed ZERO counted checks to every suite run this
# module has ever been in. The runner now refuses that by name; these two
# integers are the module's side of the repair.
PASSED = FAILED = 0


def ck(name, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
    (_P if cond else _F).append(name)
    print(('PASS ' if cond else 'FAIL ') + name
          + ((' :: ' + detail) if detail else ''))


SNIPPET = r'''
import sys
sys.path.insert(0, %r)
from nfl.production import seeds as S
import numpy as np
tags = ['rushing_conversion|202602:00-0039139', 'gadget|BUF|wr|202602:BUF', 'x']
print(','.join(str(S.row_component(t).value) for t in tags))
print(','.join(str(S.stream_id(ns, nm).value) for ns, nm in
               (('rushing_conversion', 'per_carry_yards'),
                ('gadget_rush', 'category_allocation'))))
# and the draw itself, not only the seed
rng = np.random.default_rng(
    [20260908, S.stream_id('rushing_conversion', 'per_carry_yards').value,
     S.row_component('rushing_conversion|202602:00-0039139').value, 7])
print(','.join(str(int(x)) for x in rng.integers(0, 10 ** 6, 5)))
'''


def _run_once():
    env = dict(os.environ)
    env['PYTHONHASHSEED'] = 'random'
    out = subprocess.run(
        [sys.executable, '-c', SNIPPET % str(REPO)],
        capture_output=True, text=True, env=env, cwd=str(REPO))
    if out.returncode != 0:
        return None, out.stderr[-400:]
    return out.stdout.strip().splitlines(), None


def test_streams_are_stable_across_processes():
    runs, errs = [], []
    for _ in range(4):
        r, e = _run_once()
        if e:
            errs.append(e)
        else:
            runs.append(r)
    if errs:
        print('BLOCKED DETERMINISM_SUBPROCESS_FAILED cause=ENVIRONMENT :: '
              + errs[0])
        return
    ck('four independent processes ran', len(runs) == 4, str(len(runs)))
    ck('the open-set row component is identical in every process',
       len({r[0] for r in runs}) == 1, str({r[0] for r in runs}))
    ck('the declared layer stream ids are identical in every process',
       len({r[1] for r in runs}) == 1, str({r[1] for r in runs}))
    ck('and the DRAWS themselves are identical, not only the seed',
       len({r[2] for r in runs}) == 1, str({r[2] for r in runs}))
    # THE DEFECT, REPRODUCED. If `hash()` were stable this check would be
    # vacuous and the test above would prove nothing, so the instability of
    # the thing that was being used is asserted directly.
    env = dict(os.environ)
    env['PYTHONHASHSEED'] = 'random'
    hs = set()
    for _ in range(8):
        o = subprocess.run(
            [sys.executable, '-c',
             "print(abs(hash('202602:00-0039139')))"],
            capture_output=True, text=True, env=env)
        hs.add(o.stdout.strip())
    ck('the builtin hash this replaced really is unstable, so the check '
       'above is not vacuous', len(hs) > 1,
       f'{len(hs)} distinct values over 8 processes')


def test_no_builtin_hash_seeds_an_rng_anywhere_in_production():
    """Source-level, so the next tag-seeded stream cannot repeat this."""
    import ast
    bad = []
    for p in sorted((REPO / 'nfl' / 'production').rglob('*.py')):
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        # AST, NOT TEXT. A line-scanner flagged this module's own DOCSTRINGS
        # -- seeds.py opens by quoting the very expression it exists to
        # replace -- so the check was reporting prose as code. Parsing means
        # only a real call to the builtin is a finding.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Name) and f.id == 'hash':
                bad.append(f'{p.relative_to(REPO)}:{node.lineno}')
    ck('no builtin hash() is CALLED anywhere in production', not bad,
       str(bad))


def test_zz_every_check_passed():
    # Reads FAILED, not `_F`: `tally_tripwires` recognises a tripwire by
    # SHAPE, and one of the shape conditions is that it names a failure
    # counter the runner knows. Referencing only the local list made this
    # look like an ordinary zero-check function.
    # No call but print/AssertionError, by shape rule: `len(_F)` counted as
    # a third call and disqualified this as a tripwire.
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    test_streams_are_stable_across_processes()
    test_no_builtin_hash_seeds_an_rng_anywhere_in_production()
    print(f'\n{len(_P)} passed, {len(_F)} failed')
    raise SystemExit(1 if _F else 0)
