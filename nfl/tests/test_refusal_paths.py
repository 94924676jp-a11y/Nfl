"""The refusal branches AUDIT-0 found nobody had exercised.

WHY THIS MODULE EXISTS

`trace_execution_path` measured the test suite against the real ATL @ GB run
and found that eleven of fourteen stages had their code named somewhere in
nfl/tests/ -- but only ONE of those matches was on an actual refusal code.
Ten matched on a success code such as QB_LAYER_OK, which shows the happy path
ran and says nothing about whether the branch that stops a bad run has ever
fired. Three stages had no test naming their code at all:
`team_environment`, `joint_reconciliation`, `scoring`.

So the suite was largely proving the system works on good input rather than
that it refuses bad input. This module works on that gap from the refusal
vocabulary upward, which is the layer that can be exercised without running a
471-second forecast.

WHAT IT ASSERTS
===============
1. AN UNDECLARED REFUSAL CODE IS REFUSED. Inventing a code at the call site is
   how a whole category of failure becomes invisible, and `refuse` already
   guards it; this pins that guard.
2. EVERY REFUSAL CODE A STAGE CAN EMIT IS DECLARED. The two codes
   `joint_reconciliation` can raise are checked against REFUSALS by name, so a
   future edit that adds a third gets caught here rather than at 3am on a
   Sunday slate.
3. A REFUSAL IS A RESULT, NOT AN ABSENCE. It carries its code, its stage, its
   run id and a timestamp, and it is BLOCKED with cause GOVERNANCE rather than
   a bare failure.
4. EVERY DECLARED CODE HAS A HUMAN EXPLANATION, because a code nobody can
   read is only marginally better than a silent failure.
5. THE VOCABULARY COVERS THE STAGES THE TRACE NAMED, and where it does not the
   test says which stage is still unrepresented rather than passing quietly.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.production import refusal as RF  # noqa: E402
from sportsplatform.governance.outcome import Cause, State  # noqa: E402

PASSED = FAILED = BLOCKED = 0

#: The codes each previously-untested stage can emit, read out of
#: run_forecast rather than guessed.
STAGE_REFUSALS = {
    'joint_reconciliation': ('JOINT_RECONCILIATION_FAILURE',
                             'INCOMPLETE_PLAYER_ACCOUNTING'),
    'artifact_sealing': ('ARTIFACT_SEALING_FAILURE',
                         'EMPTY_FORECAST_ARTIFACT'),
    'capture_validation': ('SOURCE_MISSING', 'SOURCE_TOO_LATE',
                           'RAW_HASH_MISMATCH',
                           'REQUIRED_SOURCE_NOT_DECLARED',
                           'DECLARED_CAPTURES_UNVERIFIED'),
    'identity_resolution': ('IDENTITY_UNRESOLVED',),
    'publication': ('NFL1_NOT_AUTHORIZED',),
}


def chk(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def test_an_undeclared_refusal_code_is_refused():
    out = RF.refuse('TOTALLY_MADE_UP_CODE', 'joint_reconciliation',
                    'something went wrong', 'run-1')
    chk('it does not produce a refusal', out.state is State.FAIL,
        out.state.name)
    chk('it is named UNKNOWN_REFUSAL_CODE',
        out.code == 'UNKNOWN_REFUSAL_CODE', out.code)
    chk('and says why inventing one is dangerous',
        'becomes invisible' in out.detail)
    chk('carrying the offending code for a human to fix',
        out.evidence.get('offending_code') == 'TOTALLY_MADE_UP_CODE')


def test_every_code_a_stage_can_emit_is_declared():
    for stage, codes in sorted(STAGE_REFUSALS.items()):
        for code in codes:
            chk(f'{stage} -> {code} is declared', code in RF.REFUSALS)


def test_a_refusal_is_a_result_not_an_absence():
    out = RF.refuse('JOINT_RECONCILIATION_FAILURE', 'joint_reconciliation',
                    'team totals could not be reconciled', 'run-42')
    chk('it is BLOCKED, not FAIL', out.state is State.BLOCKED, out.state.name)
    chk('the cause is GOVERNANCE', out.evidence.get('cause') == Cause.GOVERNANCE
        or getattr(out, 'cause', None) == Cause.GOVERNANCE
        or 'GOVERNANCE' in str(out.as_dict()),
        str(out.as_dict())[:120])
    chk('the code is carried', out.code == 'JOINT_RECONCILIATION_FAILURE')
    rec = out.evidence.get('refusal') or {}
    chk('a persisted record is attached', bool(rec))
    for field in ('code', 'stage', 'detail', 'run_id', 'at'):
        chk(f'the record carries {field}', bool(rec.get(field)),
            str(rec.get(field)))
    chk('the stage is named in the record',
        rec.get('stage') == 'joint_reconciliation')
    chk('and the run id', rec.get('run_id') == 'run-42')
    chk('the detail reaches the human-readable message',
        'could not be reconciled' in out.detail)


def test_the_second_joint_branch_is_distinguishable():
    """The two joint failures are different facts and must not collapse."""
    a = RF.refuse('JOINT_RECONCILIATION_FAILURE', 'joint_reconciliation',
                  'team totals could not be reconciled', 'r')
    b = RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'joint_reconciliation',
                  'team and player totals do not reconcile', 'r')
    chk('the two codes differ', a.code != b.code)
    chk('and their declared meanings differ',
        RF.REFUSALS[a.code] != RF.REFUSALS[b.code])
    chk('a physically invalid joint draw is not an accounting mismatch',
        'physically valid' in RF.REFUSALS['JOINT_RECONCILIATION_FAILURE']
        and 'reconcile' in RF.REFUSALS['INCOMPLETE_PLAYER_ACCOUNTING'])


def test_every_declared_code_has_a_human_explanation():
    chk('the vocabulary is non-empty', len(RF.REFUSALS) >= 15,
        str(len(RF.REFUSALS)))
    bare = [c for c, why in RF.REFUSALS.items() if len(str(why)) < 20]
    chk('no code carries a stub explanation', not bare, str(bare))
    shouty = [c for c in RF.REFUSALS if c != c.upper()]
    chk('every code is a stable upper-case token', not shouty, str(shouty))


def test_structured_evidence_reaches_the_outcome_only():
    out = RF.refuse('INCOMPLETE_PLAYER_ACCOUNTING', 'joint_reconciliation',
                    'team and player totals do not reconcile', 'r',
                    team_total=41.0, player_total=38.5)
    chk('structured evidence is on the Outcome',
        out.evidence.get('team_total') == 41.0)
    rec = out.evidence.get('refusal') or {}
    chk('but the persisted record keeps its five fields',
        set(rec) == {'code', 'stage', 'detail', 'run_id', 'at'}, str(sorted(rec)))


def test_the_trace_named_stages_are_covered_or_reported():
    """Say which stages still lack a declared refusal rather than pass quietly."""
    from_trace = ('team_environment', 'joint_reconciliation', 'scoring')
    covered = [s for s in from_trace if s in STAGE_REFUSALS]
    uncovered = [s for s in from_trace if s not in STAGE_REFUSALS]
    chk('joint_reconciliation now has declared refusal codes under test',
        'joint_reconciliation' in covered)
    print(f'       still without a declared refusal vocabulary: {uncovered}')
    chk('and the ones still uncovered are named rather than hidden',
        set(uncovered) == {'team_environment', 'scoring'}, str(uncovered))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
