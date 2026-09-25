"""The reader that decides whether we may say "autonomous", held to its word.

This test exists because the tool it tests is the thing standing between a
measured claim and a comfortable one. If it can be fooled, it is worse than
nothing: it launders an assertion into a verdict.

The two properties that carry the weight:

  * a heartbeat run that SUCCEEDED while SKIPPING its dispatch step must not
    prove the chain was entered. That is the disarmed refusal branch, it will
    be the common case for as long as autonomy is off, and it looks like a
    green run in every list; and

  * a restart that followed a human-triggered run must be CONTRADICTED rather
    than PROVEN, because the acceptance test is specifically that the system
    wakes itself with no message from the owner. If I trigger a run and then
    count the recovery, I have proven the opposite of the claim.
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import autonomy_acceptance as A                   # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def _hb(event='schedule', dispatch='skipped', started='2026-09-25T17:48:49Z',
        conclusion='success', rid=1):
    return {'id': rid, 'path': '.github/workflows/agent-orchestrator-heartbeat.yml',
            'event': event, 'conclusion': conclusion, 'run_started_at': started,
            'jobs': [{'steps': [
                {'name': 'Read the policy from the automation branch',
                 'conclusion': 'success'},
                {'name': 'Re-enter the chain', 'conclusion': dispatch}]}]}


def test_nothing_is_proven_by_default():
    v = A.assess([], [])
    states = {k: s['state'] for k, s in v.items()}
    check('every stage starts NOT_ESTABLISHED',
          set(states.values()) == {A.NOT_ESTABLISHED}, states)
    check('all eight stages are reported', len(v) == 8, len(v))


def test_a_skipped_dispatch_does_not_prove_the_chain_was_entered():
    """THE ONE THAT MATTERS. A green run that dispatched nothing is the
    disarmed default, and it must never read as the loop working."""
    v = A.assess([], [_hb(dispatch='skipped')])
    check('firing on schedule is proven',
          v['1_HEARTBEAT_FIRES_ON_SCHEDULE']['state'] == A.PROVEN)
    check('entering the chain is NOT proven by a skipped dispatch',
          v['2_HEARTBEAT_ENTERS_THE_CHAIN']['state'] == A.NOT_ESTABLISHED,
          v['2_HEARTBEAT_ENTERS_THE_CHAIN'])
    check('and it says why in those terms',
          'refusal branch' in v['2_HEARTBEAT_ENTERS_THE_CHAIN']['why'])


def test_a_successful_dispatch_does_prove_it():
    v = A.assess([], [_hb(dispatch='success')])
    check('chain entry proven when the dispatch step succeeded',
          v['2_HEARTBEAT_ENTERS_THE_CHAIN']['state'] == A.PROVEN,
          v['2_HEARTBEAT_ENTERS_THE_CHAIN'])


def test_a_manual_trigger_does_not_prove_the_timer():
    v = A.assess([], [_hb(event='workflow_dispatch', dispatch='success')])
    check('workflow_dispatch does not prove the schedule fires',
          v['1_HEARTBEAT_FIRES_ON_SCHEDULE']['state'] == A.NOT_ESTABLISHED,
          v['1_HEARTBEAT_FIRES_ON_SCHEDULE'])


def test_a_logged_continuation_is_not_a_sent_one():
    logged = [{'event': 'CONTINUATION_REQUESTED', 'timestamp': 't1',
               'dispatch_sent': False}]
    v = A.assess(logged, [])
    check('logged but unsent continuation is NOT_ESTABLISHED',
          v['6_CONTINUATION_CHAINS']['state'] == A.NOT_ESTABLISHED,
          v['6_CONTINUATION_CHAINS'])
    check('and it says logged, not sent',
          'not sent' in v['6_CONTINUATION_CHAINS']['why'])
    sent = [{'event': 'CONTINUATION_REQUESTED', 'timestamp': 't1',
             'dispatch_sent': True}]
    check('a sent continuation is proven',
          A.assess(sent, [])['6_CONTINUATION_CHAINS']['state'] == A.PROVEN)


def test_a_delegated_task_that_never_moves_is_a_stall_not_an_ingest():
    rows = [{'event': 'DELEGATED', 'task_id': 'ENG-001', 'timestamp': 't1'}]
    v = A.assess(rows, [])
    check('selection proven', v['3_ORCHESTRATOR_SELECTS_A_TASK']['state'] == A.PROVEN)
    check('ingest not proven', v['5_RESULT_IS_INGESTED']['state'] == A.NOT_ESTABLISHED)
    check('and it names the stall',
          'stall' in v['5_RESULT_IS_INGESTED']['why'],
          v['5_RESULT_IS_INGESTED']['why'])
    rows.append({'task_id': 'ENG-001', 'timestamp': 't2', 'to_status': 'RETURNED'})
    check('ingest proven once the task moves',
          A.assess(rows, [])['5_RESULT_IS_INGESTED']['state'] == A.PROVEN)


def test_the_next_task_must_be_a_different_task():
    rows = [{'event': 'CONTINUATION_REQUESTED', 'timestamp': 't2', 'dispatch_sent': True},
            {'event': 'DELEGATED', 'task_id': 'ENG-001', 'timestamp': 't1'},
            {'event': 'DELEGATED', 'task_id': 'ENG-001', 'timestamp': 't3'}]
    v = A.assess(rows, [])
    check('re-delegating the SAME task is not progress',
          v['7_NEXT_TASK_SELECTED_AUTOMATICALLY']['state'] == A.NOT_ESTABLISHED,
          v['7_NEXT_TASK_SELECTED_AUTOMATICALLY'])
    rows.append({'event': 'DELEGATED', 'task_id': 'ENG-002', 'timestamp': 't4'})
    check('a new task after the continuation is progress',
          A.assess(rows, [])['7_NEXT_TASK_SELECTED_AUTOMATICALLY']['state'] == A.PROVEN)


def test_a_restart_a_human_caused_is_contradicted_not_proven():
    """If I trigger the run that recovers it, I have proven the opposite."""
    runs = [_hb(event='schedule', dispatch='success', conclusion='failure',
                started='2026-09-25T10:00:00Z', rid=1),
            {'id': 2, 'name': 'x', 'event': 'workflow_dispatch', 'conclusion': 'success',
             'run_started_at': '2026-09-25T10:30:00Z'},
            _hb(event='schedule', dispatch='success',
                started='2026-09-25T11:00:00Z', rid=3)]
    v = A.assess([], runs)
    check('a human-triggered run between failure and recovery contradicts it',
          v['8_KILLED_PASS_IS_RESTARTED']['state'] == A.CONTRADICTED,
          v['8_KILLED_PASS_IS_RESTARTED'])
    clean = [runs[0], runs[2]]
    check('without one, the restart is proven',
          A.assess([], clean)['8_KILLED_PASS_IS_RESTARTED']['state'] == A.PROVEN,
          A.assess([], clean)['8_KILLED_PASS_IS_RESTARTED'])
