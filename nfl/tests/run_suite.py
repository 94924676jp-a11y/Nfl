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
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import re
import subprocess
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


#: A module declaring this at top level is run in its OWN SUBPROCESS.
#:
#: WHY THIS IS NOT A LOOPHOLE. Some guarantees here are enforced by PROCESS SCOPE, not by code.
#: The FantasyCruncher firewall in dk_universe refuses to return external values if ANY proprietary
#: projection module is imported in the same interpreter -- that refusal IS the guarantee that
#: FantasyCruncher cannot become a feature input. Under a single-process runner roughly three hundred
#: modules have imported the proprietary layer before the firewall test runs, so the firewall
#: correctly refuses and the test cannot pass. Four modules were failing for exactly this reason: it
#: looked like state leakage and it was the firewall working.
#:
#: The declaration is therefore narrow and does NOT mean "this test is order-dependent, excuse it".
#: It means: this test measures something only true of a fresh interpreter. It is read from SOURCE
#: before the module is imported, because by the time it could be read as an attribute the process is
#: already contaminated by everything else.
_OWN_PROCESS_DECL = re.compile(r"^REQUIRES_OWN_PROCESS\s*=\s*['\"](.+?)['\"]", re.M | re.S)


def requires_own_process(path):
    """The declared reason this module needs a fresh interpreter, or None. Read from SOURCE."""
    try:
        m = _OWN_PROCESS_DECL.search(open(path, encoding='utf-8').read())
    except OSError:
        return None
    return m.group(1) if m else None


def tally(mod):
    """The module's own pass/fail counters, or None.

    A NAME MATCH IS NOT A COUNTER. `('P', 'F')` is a real convention in this tree and it is also
    two of the commonest module aliases anybody writes, so a test file doing `import x as P` matched
    by name and handed this function a module. `int(<module>)` raised TypeError out of the runner and
    aborted a 316-suite run at suite 261, losing every result -- the runner failing in exactly the
    way it exists to catch. A candidate pair whose values are not integers is now SKIPPED, and the
    next pair is tried.
    """
    for p, f in _TALLY:
        if not (hasattr(mod, p) and hasattr(mod, f)):
            continue
        a, b = getattr(mod, p), getattr(mod, f)
        if isinstance(a, bool) or isinstance(b, bool) or not (
                isinstance(a, int) and isinstance(b, int)):
            continue
        return int(a), int(b)
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
    # `--no-isolate` is how the CHILD runs; it stops the parent's re-spawn recursing. It is NOT a way
    # to skip isolation for a normal run: a module declaring REQUIRES_OWN_PROCESS reached with
    # --no-isolate inside a multi-module run is REFUSED below, because judging it in a contaminated
    # interpreter is the thing the declaration exists to prevent.
    no_isolate = '--no-isolate' in argv
    # ORDER MODES. A suite whose result depends on the order its modules ran is not a measurement of
    # the product, so the order has to be variable and the variation has to be reportable. `--reverse`
    # runs the discovered list backwards; `--shuffle [SEED]` permutes it with an explicit seed.
    #
    # THE SEED IS ALWAYS PRINTED AND ALWAYS RECORDED. A randomised run that does not say which
    # permutation it used cannot be reproduced, and an irreproducible failure gets called a flake and
    # then gets ignored -- which is how an order dependence survives a randomised harness.
    reverse = '--reverse' in argv
    # `--modules a,b,c` runs EXACTLY those modules in EXACTLY that order. It exists because
    # `--only SUBSTR` cannot express an ordered pair, and an ordered pair is the unit of evidence for
    # an order dependence: the claim "A poisons B" is tested by running A then B and nothing else.
    #
    # It is a bisecting tool, not a way to run a subset and call it a suite. A run made with
    # --modules is never a suite result, and the summary says so.
    # `--watch a,b,c` hashes those repo-relative paths after every module and names the module that
    # changed one. It exists because the expensive way to find an order dependence is to bisect --
    # nine long runs to isolate one pair -- and the cheap way is to watch the state the victim reads
    # and see who writes it. One instrumented pass replaces the bisect when the contamination is on
    # disk. It does NOT see in-process contamination (a cached module global), so a clean watch
    # report narrows the cause rather than clearing it.
    watch = None
    if '--watch' in argv:
        watch = [w.strip() for w in argv[argv.index('--watch') + 1].split(',') if w.strip()]
    modules = None
    if '--modules' in argv:
        modules = [m.strip() for m in argv[argv.index('--modules') + 1].split(',') if m.strip()]
    shuffle_seed = None
    if '--shuffle' in argv:
        j = argv.index('--shuffle') + 1
        shuffle_seed = (int(argv[j]) if j < len(argv) and argv[j].isdigit()
                        else int(time.time()))
    os.chdir(ROOT)
    for q in (ROOT, os.path.join(ROOT, 'sportsplatform')):
        if q not in sys.path:
            sys.path.insert(0, q)
    files = (sorted(glob.glob('nfl/tests/test_*.py'))
             + sorted(glob.glob('sportsplatform/**/test_*.py', recursive=True)))
    if only:
        files = [f for f in files if only in f]
    if modules:
        # Resolve each name against the discovered list rather than trusting it to be a real path, so
        # a typo is a refusal instead of a silently shorter run that then reports zero failures.
        by_stem = {os.path.basename(f)[:-3]: f for f in files}
        unknown = [m for m in modules if m not in by_stem]
        if unknown:
            print(f'REFUSED: MODULES_NOT_DISCOVERED {unknown}')
            print('  --modules names must match discovered module stems exactly, e.g. '
                  'test_sunday_run. A run that silently dropped an unknown name would report '
                  'fewer failures than the order it claims to test.')
            return 2
        files = [by_stem[m] for m in modules]
    order_note = 'discovered (sorted)'
    if modules:
        order_note = f'EXPLICIT --modules ({len(files)} of a full suite; NOT a suite result)'
    if reverse:
        files = list(reversed(files))
        order_note = 'REVERSED'
    if shuffle_seed is not None:
        import random as _random
        _random.Random(shuffle_seed).shuffle(files)
        order_note = f'SHUFFLED seed={shuffle_seed}'
    if reverse or shuffle_seed is not None:
        print(f'MODULE ORDER: {order_note} -- reproduce with '
              + ('--reverse' if reverse else f'--shuffle {shuffle_seed}'))
    n_fn = n_raise = n_check_fail = n_check_ok = 0
    n_not_executed = []
    n_fn_zero = n_fn_blocked = n_unrecognised_tally = 0
    zero_fns, blocked_fns = [], []
    isolated = []
    problems = []
    watch_events = []
    watch_state = {}

    def _watch_digests():
        d = {}
        for w in (watch or ()):
            q = os.path.join(ROOT, w)
            try:
                with open(q, 'rb') as fh:
                    d[w] = hashlib.sha256(fh.read()).hexdigest()
            except FileNotFoundError:
                # ABSENT is a state, not an error: a path appearing or disappearing is exactly the
                # kind of mutation being hunted, so it has to compare unequal to a digest.
                d[w] = 'ABSENT'
            except OSError as e:
                d[w] = f'UNREADABLE:{e.__class__.__name__}'
        return d

    def _watch_check(after_module):
        nonlocal watch_state
        if not watch:
            return
        now = _watch_digests()
        changed = [w for w in now if now[w] != watch_state.get(w)]
        for w in changed:
            watch_events.append({'after_module': after_module, 'path': w,
                                 'from': watch_state.get(w), 'to': now[w]})
        if changed:
            print(f'    WATCH: {after_module} changed {len(changed)} watched path(s): '
                  + ', '.join(changed))
            _emit({'phase': 'watch_change', 'after_module': after_module, 'paths': changed})
        watch_state = now

    if watch:
        watch_state = _watch_digests()
        print(f'WATCHING {len(watch)} path(s) after every module: ' + ', '.join(watch))
    # OWNER RULE 2 (2026-10-02): every positive control a test records (nfl/tests/_controls)
    # is stamped with THIS run's id, in this process and in own-process children, so the
    # validation at the end of the run counts only controls that ran in it.
    # OWNER RULE 3 (2026-10-02): the first step of every run judges the mode boundary over the
    # working tree and the diff since the mode was set, with the same judge the hook uses. A
    # VIOLATED boundary fails the run; no mode in force is NOT_EXECUTED, reported, not a pass.
    mode_boundary = _mode_boundary()
    print(f"mode: {mode_boundary.get('mode')}  boundary {mode_boundary['state']}"
          + (f"  violations {[v['path'] for v in mode_boundary['violations'][:6]]}"
             if mode_boundary.get('violations') else ''))
    os.environ['NFL_SUITE_RUN_ID'] = _RUN_ID
    os.environ.setdefault('NFL_CONTROL_HITS', os.path.join(ROOT, 'nfl/tests/_control_hits.jsonl'))
    _emit({'phase': 'suite_start', 'n_modules': len(files), 'order': order_note,
           'shuffle_seed': shuffle_seed, 'reverse': reverse},
          f'suite: {len(files)} module(s), order {order_note}')
    for i, f in enumerate(files, 1):
        # Attribute a watched change to the module that just finished. Doing it here rather than at
        # each module_done covers the branches that `continue`, so no exit path skips the check.
        if i > 1:
            _watch_check(files[i - 2])
        _emit({'phase': 'module_start', 'i': i, 'module': f},
              f'[{i}/{len(files)}] {f}')
        own = requires_own_process(f)
        if own and not no_isolate:
            # RUN IT THROUGH THIS SAME RUNNER IN A FRESH INTERPRETER, so it is judged by identical
            # logic. Anything less makes a process-scoped module a different kind of citizen, which
            # is how an exemption becomes a hiding place.
            r = subprocess.run([sys.executable, os.path.abspath(__file__),
                                '--only', os.path.basename(f), '--no-isolate'],
                               capture_output=True, text=True, cwd=ROOT)
            out = r.stdout + r.stderr
            mt = re.search(r'checks (\d+)\s+FAILING CHECKS (\d+)\s+RAISED (\d+)', out)
            # OWNER RULE 1 (2026-10-02): a child that executed zero-check functions or was
            # VACUOUS used to be read by the parent as its failing/raised counts alone, so a
            # child that measured nothing propagated as clean. Its zero-check count and any
            # VACUOUS line now count against the parent exactly as an in-process module would.
            mz = re.search(r'ZERO-CHECK FUNCTIONS (\d+)', out)
            sub_zero = int(mz.group(1)) if mz else 0
            sub_vacuous = [ln for ln in out.splitlines() if ln.strip().startswith('VACUOUS')]
            if mt is None:
                n_raise += 1
                problems.append(
                    f'PROCESS_SCOPED_CHILD_UNREADABLE {f}: the isolated run produced no parsable '
                    f'tally, so its result is UNKNOWN and is NOT counted as a pass. '
                    f'exit={r.returncode}\n{out[-1200:]}')
                _emit({'phase': 'module_done', 'i': i, 'module': f,
                       'result': 'PROCESS_SCOPED_UNREADABLE'},
                      f'[{i}/{len(files)}] {f}  OWN PROCESS, tally unreadable')
                continue
            sub_checks, sub_fail, sub_raise = (int(mt.group(1)), int(mt.group(2)),
                                               int(mt.group(3)))
            n_check_fail += sub_fail
            n_check_ok += max(sub_checks - sub_fail, 0)
            n_raise += sub_raise
            if sub_zero:
                n_fn_zero += sub_zero
                zero_fns.append(f'{f}::<own-process child reported {sub_zero} zero-check function(s)>')
            for ln in sub_vacuous:
                problems.append(f'{ln.strip()} (OWN PROCESS {f})')
            if sub_checks == 0 and not sub_vacuous:
                problems.append(f'VACUOUS {f} (OWN PROCESS): the child executed 0 checks')
            isolated.append({'module': f, 'reason': own, 'checks': sub_checks,
                             'failing': sub_fail, 'raised': sub_raise})
            if sub_fail or sub_raise:
                detail = '\n'.join(ln for ln in out.splitlines()
                                   if ln.strip().startswith(('FAIL', 'ERROR')))
                problems.append(f'CHECKS {f} (OWN PROCESS): {sub_fail} failing, '
                                f'{sub_raise} raised\n{detail[:1500]}')
            _emit({'phase': 'module_done', 'i': i, 'module': f, 'result': 'OWN_PROCESS',
                   'checks': sub_checks, 'failing': sub_fail},
                  f'[{i}/{len(files)}] {f}  OWN PROCESS, {sub_checks} check(s), '
                  f'{sub_fail} failing')
            continue
        if own and no_isolate and len(files) > 1:
            problems.append(
                f'PROCESS_SCOPED_RUN_IN_PROCESS {f}: declares REQUIRES_OWN_PROCESS and was reached '
                f'without isolation inside a {len(files)}-module run, so anything it reports is '
                f'about a contaminated interpreter. REFUSED rather than counted.')
            n_raise += 1
            continue
        name = 't_' + f.replace('/', '_')[:-3]
        spec = importlib.util.spec_from_file_location(name, f)
        mod = importlib.util.module_from_spec(spec)
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                spec.loader.exec_module(mod)
        # SystemExit TOO. It is a BaseException, so `except Exception` let a module that calls sys.exit() at
        # import END THIS RUNNER with the module's own exit status -- found 2026-10-07 when
        # test_archetype_field.py's top-level sys.exit(0) stopped a 364-module run at module 12 and the run
        # exited 0 with no summary: a truncated suite reading as a green one.
        except (Exception, SystemExit):                          # noqa: BLE001
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
            except (Exception, SystemExit):                      # noqa: BLE001  (see the import guard above)
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
    if files:
        _watch_check(files[-1])
    if watch:
        print(f'\nWATCH REPORT: {len(watch_events)} change(s) to watched paths during the run')
        for ev in watch_events:
            print(f"  after {ev['after_module']}: {ev['path']} "
                  f"{str(ev['from'])[:12]} -> {str(ev['to'])[:12]}")
        if not watch_events:
            print('  none. The watched paths were byte-identical throughout, so whatever differs '
                  'between this order and an isolated run is NOT in these files.')
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
    if reverse or shuffle_seed is not None:
        print(f'ORDER: {order_note}. A failure here that does not reproduce in sorted order is an '
              f'ORDER DEPENDENCE, not a flake, and the line above is how to re-run it.')
    if isolated:
        print(f'process-scoped, each run in its own interpreter ({len(isolated)}):')
        for r in isolated:
            print(f"  {r['module']}  {r['checks']} check(s), {r['failing']} failing")
    if blocked_fns:
        print('blocked (declared, not a pass, not a failure):')
        for b in blocked_fns:
            print(f'  {b}')
    for p in problems:
        print('\n' + p)
    # OWNER RULE 2 (2026-10-02): a detector in nfl/tests/DETECTORS.json with no positive control
    # that ran AND tripped in this run is UNVALIDATED, and the suite fails on it. A partial run
    # (--only / --modules) validates what it ran; detectors whose controls live elsewhere are
    # NOT_IN_THIS_RUN, which is reported and is not a pass. The child of an own-process module
    # never validates (its parent does, over the whole run).
    det = None
    if not no_isolate:
        det = _validate_detectors(files, full_run=(only is None and not modules))
        unval = [r for r in det['rows'] if r['detector'] in set(det.get('blocking') or ())]
        if unval:
            problems.append(
                f'DETECTORS UNVALIDATED ({len(unval)} of {det["n_detectors"]}): a detector '
                f'without a control that ran and tripped in this run is not validated. '
                f'See nfl/tests/DETECTOR_VALIDATION.json.\n  '
                + '\n  '.join(f"{r['status']:<36} {r['detector']}" for r in unval[:60])
                + ('\n  ...' if len(unval) > 60 else ''))
        print(f"detectors: {det['n_detectors']} listed, "
              + ', '.join(f'{k} {v}' for k, v in sorted(det['counts'].items()))
              + f"  -> {det['verdict']}")
    if mode_boundary['state'] == 'VIOLATED':
        problems.append('MODE_BOUNDARY_VIOLATED: mode ' + str(mode_boundary['mode']) + ' forbids '
                        + ', '.join(f"{v['path']} ({v['rule']} {v['pattern']})"
                                    for v in mode_boundary['violations'][:12]))
    bad = (n_check_fail + n_raise + n_fn_zero + n_unrecognised_tally
           + len(n_not_executed)
           + sum(p.startswith('VACUOUS') for p in problems)
           + sum(p.startswith('DETECTORS UNVALIDATED') for p in problems)
           + sum(p.startswith('MODE_BOUNDARY_VIOLATED') for p in problems))
    # OWNER RULE 1 (2026-10-02). A run that executed nothing has not passed. Before this, an
    # `--only` pattern matching no module printed SUITE PASS on 0 modules and 0 checks, and the
    # log holds three such runs. NOT_EXECUTED is its own verdict with its own exit code (3), so
    # a caller cannot read it as either a pass or a failure of the code under test.
    n_executed = n_check_ok + n_check_fail
    # NOT_EXECUTED means no module ran or no test function ran. A function that ran and raised,
    # or ran and recorded zero checks, EXECUTED: that is a FAIL (raised / VACUOUS), and reading
    # it as "nothing ran" would let a crashing module print the one verdict that is not red.
    # Found 2026-10-03 by test_harness_audit's seeded exception-only module.
    if len(files) == 0 or n_fn == 0:
        verdict, rc = 'NOT_EXECUTED', 3
    else:
        verdict, rc = ('FAIL', 1) if bad else ('PASS', 0)
    _emit({'phase': 'suite_done', 'verdict': verdict, 'n_modules': len(files),
           'n_checks_executed': n_executed, 'n_failing': n_check_fail, 'n_raised': n_raise,
           'n_zero_check_fns': n_fn_zero, 'n_not_executed_modules': len(n_not_executed),
           'detectors': ({'verdict': det['verdict'], **det['counts']} if det else None),
           'mode': _project_mode(), 'mode_boundary': mode_boundary['state'],
           'head': _head_commit()})
    if verdict == 'NOT_EXECUTED':
        print(f'SUITE NOT_EXECUTED  ({len(files)} module(s), {n_executed} check(s) executed): '
              f'nothing ran, so nothing passed and nothing failed.')
    else:
        print('SUITE ' + verdict)
    return rc


def _validate_detectors(files, full_run: bool) -> dict:
    """Rule 2 at the end of the run. Never raises out of the runner: an error is itself a row."""
    try:
        from nfl.tests import _controls as C
        ran = []
        for f in files:
            try:
                ran.append(str(pathlib.Path(f).resolve().relative_to(ROOT)))
            except ValueError:
                ran.append(os.path.relpath(f, ROOT))
        return C.validate(_RUN_ID, ran, full_run)
    except Exception as e:  # noqa: BLE001
        return {'n_detectors': 0, 'counts': {'VALIDATION_NOT_EXECUTED': 1},
                'verdict': 'VALIDATION_NOT_EXECUTED',
                'rows': [{'detector': '<validator>', 'status': 'UNVALIDATED_VALIDATOR_RAISED',
                          'error': f'{type(e).__name__}: {e}'}]}


def _mode_boundary() -> dict:
    try:
        from coordination import mode as M
        from coordination.orchestrator import locks as L
        cur = M.read()
        since = (cur['record'] or {}).get('since_commit')
        return L.mode_boundary(M.changed_paths(since), cur['mode'], diff=M.diff_text(since))
    except Exception as e:  # noqa: BLE001
        return {'state': 'NOT_EXECUTED', 'mode': None, 'violations': [],
                'why': f'{type(e).__name__}: {e}'}


def _project_mode():
    """The operating mode declared in coordination/PROJECT_STATE.json, or None. Recorded on the
    verdict so a VERIFY-mode run is distinguishable from a BUILD-mode self-certification."""
    try:
        with open(os.path.join(ROOT, 'coordination', 'PROJECT_STATE.json'), encoding='utf-8') as fh:
            st = json.load(fh)
        m = st.get('mode_declared') or st.get('mode') or {}
        return m.get('mode') if isinstance(m, dict) else m
    except (OSError, ValueError):
        return None


def _head_commit():
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or None
    except OSError:
        return None


if __name__ == '__main__':
    sys.exit(main())
