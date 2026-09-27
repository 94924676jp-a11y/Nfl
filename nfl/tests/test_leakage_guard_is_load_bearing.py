"""`assert_no_postgame_inputs` stops the stage from running. Proved, not asserted.

WHY THIS FILE EXISTS

`nfl/tests/test_production_pipeline.py` already calls the guard directly and
checks it returns POSTGAME_INPUT_DECLARED. That establishes the guard's return
value and nothing else. Under the standard this project works to, a return value
is not a proof:

    bad state -> guard fires -> caller receives failure -> the protected action
    demonstrably does not occur

The protected action here is the most consequential one in the pipeline: a stage
function EXECUTING on inputs that include a field which only exists after the
game has been played. A guard that returned FAIL while `fn` ran anyway would
leak future information into a historical simulation and every existing test
would still pass.

So these tests observe `fn`. A canary records whether it was called, and the
claim is about the canary, not about a code string.

TWO PROTECTED ACTIONS, NOT ONE

  1. the offending stage's own `fn` must not run;
  2. every LATER stage's `fn` must not run either, because `halted_by` is set.
     The pipeline previously recorded a refusal and then went on to execute the
     QB model on unresolved players and seal the artifact. Halting is the repair
     and it is worth its own observation.

AND THE BYPASS HALF

Each proof is run twice: once with the guard in place, once with it stubbed to
its PASS shape (`Outcome.ok('INPUTS_ARE_PREGAME', ...)`, which is what the real
guard returns on success -- a stub returning None would break the caller and the
test would pass for the wrong reason). If `fn` stays unexecuted with the guard
bypassed, then the guard is not what stopped it and the proof is void.
"""
from __future__ import annotations

import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bypass import guard_bypassed                               # noqa: E402
from nfl.production import pipeline as PL                       # noqa: E402
from sportsplatform.governance.outcome import Outcome, State    # noqa: E402

PASSED = FAILED = 0
GUARD = 'assert_no_postgame_inputs'
MODULE = 'nfl.production.pipeline'
PASS_SHAPE = Outcome.ok('INPUTS_ARE_PREGAME', value=[])


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _postgame_field():
    """A real member of POSTGAME_FIELDS, read from the module."""
    fields = sorted(PL.POSTGAME_FIELDS)
    assert fields, 'POSTGAME_FIELDS is empty; this test would be vacuous'
    return fields[0]


def _pipeline(tmp):
    return PL.Pipeline(run_id='LOADBEARING_PROOF', out_dir=pathlib.Path(tmp),
                       arm='test', written_at='2026-09-27T01:00:00Z')


def _stages():
    """Two declared stages, in declaration order."""
    return list(PL.STAGES)[:2]


def _run(*, leak: bool):
    """Execute two stages, the first declaring a postgame input if `leak`.

    Returns (calls, results) where `calls` is the list of stages whose function
    actually executed.
    """
    calls = []
    with tempfile.TemporaryDirectory() as tmp:
        p = _pipeline(tmp)
        first, second = _stages()
        bad = [_postgame_field()] if leak else ['h_ewma']
        r1 = p.run_stage(first, lambda: calls.append(first),
                         declared_inputs=bad)
        r2 = p.run_stage(second, lambda: calls.append(second),
                         declared_inputs=['h_ewma'])
    return calls, (r1, r2)


# ============================================ the guard refuses at all (given)

def test_the_guard_itself_names_the_violation():
    f = _postgame_field()
    o = PL.assert_no_postgame_inputs('feature_build', ['h_ewma', f])
    check('a postgame input is refused', o.state is not State.PASS, str(o.state))
    check('with POSTGAME_INPUT_DECLARED',
          o.code == 'POSTGAME_INPUT_DECLARED', str(o.code))
    check('and the offending field is named',
          f in (o.evidence.get('fields') or []), str(o.evidence.get('fields')))
    check('a pregame-only declaration passes',
          PL.assert_no_postgame_inputs('feature_build', ['h_ewma']).state
          is State.PASS)


# ================================ PROTECTED ACTION 1: the stage does not run

def test_the_leaking_stage_function_does_not_execute():
    calls, (r1, _) = _run(leak=True)
    check('the stage is reported FAIL', r1.state == 'FAIL', str(r1.state))
    check('with the guard code', r1.code == 'POSTGAME_INPUT_DECLARED',
          str(r1.code))
    check('AND the stage function never ran', _stages()[0] not in calls,
          str(calls))


def test_without_a_leak_the_same_stage_does_run():
    """Otherwise the proof above could be a broken pipeline, not a guard."""
    calls, (r1, _) = _run(leak=False)
    check('a clean stage is not FAIL', r1.state != 'FAIL',
          f'{r1.state} {r1.code}')
    check('and its function DID run', _stages()[0] in calls, str(calls))


# ============================= PROTECTED ACTION 2: later stages do not run

def test_every_later_stage_function_is_also_prevented():
    calls, (_, r2) = _run(leak=True)
    check('the later stage is NOT_APPLICABLE', r2.state == 'NOT_APPLICABLE',
          str(r2.state))
    check('with STAGE_NOT_REACHED', r2.code == 'STAGE_NOT_REACHED', str(r2.code))
    check('AND its function never ran', _stages()[1] not in calls, str(calls))
    check('nothing at all executed', calls == [], str(calls))


def test_the_halt_is_attributed_to_the_stage_that_leaked():
    with tempfile.TemporaryDirectory() as tmp:
        p = _pipeline(tmp)
        first, second = _stages()
        p.run_stage(first, lambda: None,
                    declared_inputs=[_postgame_field()])
        check('halted_by names the stage', p.halted_by[0] == first,
              str(p.halted_by))
        check('and the code that halted it',
              p.halted_by[1] == 'POSTGAME_INPUT_DECLARED', str(p.halted_by))


# ========================================================= THE BYPASS HALF

def test_bypassing_the_guard_lets_the_leaking_stage_run():
    """If this does not change, the guard is not what stopped execution."""
    with guard_bypassed(MODULE, GUARD, returns=PASS_SHAPE):
        calls, (r1, r2) = _run(leak=True)
    check('bypassed, the leaking stage is no longer FAIL', r1.state != 'FAIL',
          f'{r1.state} {r1.code}')
    check('bypassed, the leaking stage function DOES run',
          _stages()[0] in calls, str(calls))
    check('bypassed, the later stage also runs', _stages()[1] in calls,
          str(calls))
    check('so the refusal came from the guard and nowhere else',
          calls == list(_stages()), str(calls))


def test_the_bypass_stub_matches_the_guards_pass_shape():
    """A stub of the wrong shape would prove nothing.

    The real guard returns Outcome.ok('INPUTS_ARE_PREGAME', ...). A stub
    returning None made an earlier bypass proof in this repository fail inside
    the caller rather than at the guard, which looks like a passing test and is
    not one.
    """
    real = PL.assert_no_postgame_inputs('feature_build', ['h_ewma'])
    check('the stub state matches the real pass state',
          PASS_SHAPE.state is real.state, f'{PASS_SHAPE.state} {real.state}')
    check('the stub code matches the real pass code',
          PASS_SHAPE.code == real.code, f'{PASS_SHAPE.code} {real.code}')


def test_the_bypass_target_exists():
    """A bypass pointed at a missing attribute would pass vacuously."""
    check(f'{MODULE}.{GUARD} exists', hasattr(PL, GUARD))
    try:
        with guard_bypassed(MODULE, 'assert_no_such_guard_exists',
                            returns=PASS_SHAPE):
            pass
        check('bypassing a missing guard raises', False, 'it did not raise')
    except AttributeError:
        check('bypassing a missing guard raises AttributeError', True)


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
