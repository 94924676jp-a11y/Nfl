"""A mutated frozen pregame set produces NO grade. Proved at both graders.

WHAT IS PROTECTED

`pregame_frozen` holds the thing being graded: the sealed player draws, their
manifest, and the salary file. If the postgame path can write into it, the
forecast is being marked by a paper it was allowed to edit afterwards. That is
the most direct form of the leakage this project exists to prevent, and it would
not look like a bug -- it would look like a good grade.

WHAT WAS ALREADY COVERED, AND WHAT WAS NOT

`test_postgame_slate_is_addressable.py` already seeds a stray file into a second
slate's frozen directory and checks the guard returns
`PREGAME_FROZEN_SET_MUTATED`, and that the default slate is unaffected. That is
real coverage and it also establishes the slate parameterisation is not cosmetic.

What it does not establish is the protected action: that a CALLER refuses and
produces no grade. Under this project's standard a return value is not a proof --

    bad state -> guard fires -> caller receives failure -> the protected action
    demonstrably does not occur

So this file drives the two real production entry points,
`grade_projections.grade` and `grade_portfolios.grade`, and asserts on what they
return and on what they never reach.

BOTH GRADERS, BECAUSE THE SHAPE IS DUPLICATED

`grade_projections.py:92` and `grade_portfolios.py:155` each call the guard and
each `return intact` on failure. Two independent call sites means proving one
says nothing about the other, and the duplication is exactly where one of them
gets edited later and loses the check.

AND THE BYPASS HALF

Stubbed to the guard's pass shape, each grader must get PAST the guard on the
same mutated slate. It does not need to succeed -- what matters is that the
refusal it returned before was the guard's and nobody else's.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bypass import guard_bypassed                               # noqa: E402
from nfl.postgame import outcome as OC                          # noqa: E402
from nfl.postgame import grade_projections as GPROJ             # noqa: E402
from nfl.postgame import grade_portfolios as GPORT              # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

PASSED = FAILED = 0
MUTATED = 'PREGAME_FROZEN_SET_MUTATED'
#: The guard's real pass shape. A stub of the wrong shape proves nothing.
PASS_SHAPE = Outcome.ok('PREGAME_FROZEN_INTACT', value=[])
GRADERS = (('grade_projections', GPROJ, 'nfl.postgame.grade_projections'),
           ('grade_portfolios', GPORT, 'nfl.postgame.grade_portfolios'))


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _copy_slate(tmp):
    """A real slate copied to a temp root, so mutating it harms nothing."""
    src = OC._DEFAULT.root
    if not src.exists():
        return None
    root = Path(tmp) / 'LOADBEARING_SLATE'
    shutil.copytree(src, root)
    return OC.slate(root=root)


def _outcome_path(sl):
    """The copied slate's own outcome artifact, so `require` passes."""
    for p in (sl.root / 'POSTGAME_OUTCOME' / 'OUTCOME.json',
              sl.artifact):
        if p and Path(p).exists():
            return Path(p)
    return None


# ============================================ the guard's verdicts (context)

def test_an_intact_copy_reports_intact():
    with tempfile.TemporaryDirectory() as tmp:
        sl = _copy_slate(tmp)
        if sl is None:
            print('  skip  the real slate does not exist to copy')
            return
        o = OC.assert_pregame_untouched(sl)
        check('a faithful copy is reported intact', o.state is State.PASS,
              f'{o.state} {o.code}: {o.detail[:90]}')


def test_an_extra_file_is_a_mutation():
    with tempfile.TemporaryDirectory() as tmp:
        sl = _copy_slate(tmp)
        if sl is None:
            print('  skip  the real slate does not exist to copy')
            return
        (sl.pregame_frozen / 'STRAY.txt').write_text('x')
        o = OC.assert_pregame_untouched(sl)
        check('an added file refuses', o.state is not State.PASS, str(o.state))
        check(f'with {MUTATED}', o.code == MUTATED, str(o.code))


def test_a_REMOVED_file_is_also_a_mutation():
    """Deletion is the direction an over-eager cleanup goes, and it must fail."""
    with tempfile.TemporaryDirectory() as tmp:
        sl = _copy_slate(tmp)
        if sl is None:
            print('  skip  the real slate does not exist to copy')
            return
        gone = sl.pregame_frozen / 'sealed_player_draws_manifest.json'
        if not gone.exists():
            print('  skip  the manifest is not present in the copy')
            return
        gone.unlink()
        o = OC.assert_pregame_untouched(sl)
        check('a removed file refuses too', o.code == MUTATED,
              f'{o.state} {o.code}')
        ev = o.evidence or {}
        check('and the missing file is named in the detail',
              'sealed_player_draws_manifest.json' in o.detail, o.detail[:120])


# ======================== PROTECTED ACTION: neither grader produces a grade

def test_neither_grader_grades_a_mutated_frozen_set():
    for name, mod, _path in GRADERS:
        with tempfile.TemporaryDirectory() as tmp:
            sl = _copy_slate(tmp)
            if sl is None:
                print(f'  skip  {name}: the real slate does not exist to copy')
                continue
            op = _outcome_path(sl)
            if op is None:
                print(f'  skip  {name}: the copy carries no outcome artifact')
                continue
            (sl.pregame_frozen / 'STRAY.txt').write_text('x')
            o = mod.grade(outcome_path=op, sl=sl)
            check(f'{name}: refuses', o.state is not State.PASS,
                  f'{o.state} {o.code}')
            check(f'{name}: with the guard\'s own code', o.code == MUTATED,
                  f'{o.code}: {o.detail[:110]}')
            check(f'{name}: AND returns no grade', o.value in (None, {}, []),
                  f'{type(o.value).__name__}')


def test_the_same_graders_get_further_on_an_UNMUTATED_slate():
    """Otherwise the refusals above could be a broken fixture, not a guard."""
    for name, mod, _path in GRADERS:
        with tempfile.TemporaryDirectory() as tmp:
            sl = _copy_slate(tmp)
            if sl is None:
                print(f'  skip  {name}: no slate to copy')
                continue
            op = _outcome_path(sl)
            if op is None:
                print(f'  skip  {name}: no outcome artifact')
                continue
            o = mod.grade(outcome_path=op, sl=sl)
            check(f'{name}: an intact slate does NOT report {MUTATED}',
                  o.code != MUTATED, f'{o.state} {o.code}: {o.detail[:110]}')
            print(f'       {name} on an intact slate: {o.state.name}/{o.code}')


# ========================================================= THE BYPASS HALF

def test_bypassing_the_guard_lets_both_graders_past_it():
    for name, mod, path in GRADERS:
        with tempfile.TemporaryDirectory() as tmp:
            sl = _copy_slate(tmp)
            if sl is None:
                print(f'  skip  {name}: no slate to copy')
                continue
            op = _outcome_path(sl)
            if op is None:
                print(f'  skip  {name}: no outcome artifact')
                continue
            (sl.pregame_frozen / 'STRAY.txt').write_text('x')
            with guard_bypassed('nfl.postgame.outcome',
                                'assert_pregame_untouched',
                                returns=PASS_SHAPE):
                o = mod.grade(outcome_path=op, sl=sl)
            check(f'{name}: bypassed, it no longer reports {MUTATED}',
                  o.code != MUTATED, f'{o.state} {o.code}')
            print(f'       {name} bypassed on a MUTATED slate: '
                  f'{o.state.name}/{o.code}')


def test_the_bypass_reaches_the_guard_each_grader_actually_calls():
    """Both graders must import the guard from the module being stubbed.

    If a grader held its own reference the bypass would be a no-op and the test
    above would pass for the wrong reason.
    """
    for name, mod, _path in GRADERS:
        oc = getattr(mod, 'OC', None)
        check(f'{name} reaches the guard through nfl.postgame.outcome',
              oc is OC, f'{name}.OC is {oc!r}')


def test_the_bypass_stub_matches_the_guards_pass_shape():
    with tempfile.TemporaryDirectory() as tmp:
        sl = _copy_slate(tmp)
        if sl is None:
            print('  skip  no slate to copy')
            return
        real = OC.assert_pregame_untouched(sl)
        check('the stub state matches the real pass state',
              PASS_SHAPE.state is real.state, f'{PASS_SHAPE.state} {real.state}')
        check('the stub code matches the real pass code',
              PASS_SHAPE.code == real.code, f'{PASS_SHAPE.code} {real.code}')


def test_the_real_default_slate_is_never_touched_by_this_file():
    """Every mutation above happens in a temp copy. Prove it after the fact."""
    o = OC.assert_pregame_untouched()
    check('the real default slate is still intact', o.state is State.PASS,
          f'{o.state} {o.code}: {o.detail[:90]}')


if __name__ == '__main__':
    import traceback
    for _n in sorted(k for k in dict(globals()) if k.startswith('test_')):
        print(f'## {_n}')
        try:
            globals()[_n]()
        except Exception:                                      # noqa: BLE001
            FAILED += 1
            traceback.print_exc()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    sys.exit(1 if FAILED else 0)
