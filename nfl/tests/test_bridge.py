#!/usr/bin/env python3.12
"""The bridge gate and the owner-review continuation.

WHAT THIS PROVES AND WHAT IT CANNOT. It proves the gate's decisions against
synthetic GitHub event payloads, and it proves that exactly one bounded
continuation is requested after a successful ingest and none after a refused
one. It does NOT prove that GitHub delivers the payload shape assumed here,
and it does not invoke the Claude Code Action -- no test in this file opens a
socket or spends anything.

THE ONE PROOF THIS FILE CANNOT PERFORM, STATED PLAINLY RATHER THAN FAKED:
a real issue opened by a different GitHub account. This session authenticates
as the owner, so a non-owner issue cannot be created to test against. What is
checked instead is the decision function, against a payload carrying another
login -- which is the same code the workflow runs, fed the same field GitHub
would set. The workflow's job-level `if:` is checked separately, as text, in
test_orchestrator's workflow test.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import bridge as B                 # noqa: E402
from coordination.orchestrator import github_runtime as G         # noqa: E402

PASSED = FAILED = 0
REPO = pathlib.Path(__file__).resolve().parents[2]


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def event(login=B.OWNER_LOGIN, title='[AI-BRIDGE] a question', body='',
          number=7):
    return {'action': 'opened',
            'issue': {'number': number, 'title': title, 'body': body,
                      'user': {'login': login}}}


def refusal_code(fn, *a, **kw):
    try:
        fn(*a, **kw)
    except B.Refusal as r:
        return r.code
    return None


# --------------------------------------------------------------- the gate
def test_a_only_the_owner_may_wake_claude():
    print('\nA. the identity gate')
    check('the owner is authorized', B.authorize(event())['login']
          == B.OWNER_LOGIN)
    # THE CHECK THE PUBLIC REPOSITORY MAKES NECESSARY.
    for stranger in ('mallory', 'MALLORY', '94924676jp-a11y2',
                     'x94924676jp-a11y', '', 'github-actions[bot]'):
        check(f'  {stranger!r} is refused',
              refusal_code(B.authorize, event(login=stranger))
              == 'BRIDGE_REQUESTER_NOT_OWNER')
    # A near-miss login is the interesting case: a substring or casefold
    # comparison would admit at least one of the six above.
    check('the comparison is exact, not a substring or a casefold',
          refusal_code(B.authorize, event(login='94924676JP-A11Y'))
          == 'BRIDGE_REQUESTER_NOT_OWNER')


def test_b_the_title_marker_is_anchored():
    print('\nB. the title marker')
    check('a marked title passes',
          B.authorize(event(title='[AI-BRIDGE] hello'))['number'] == 7)
    for bad in ('hello', 'why does [AI-BRIDGE] fail', ' [AI-BRIDGE] x',
                '[ai-bridge] x', 'AI-BRIDGE x'):
        check(f'  {bad!r} is refused',
              refusal_code(B.authorize, event(title=bad))
              == 'BRIDGE_TITLE_NOT_MARKED')


def test_c_an_unaddressable_request_is_refused():
    print('\nC. the reply must have somewhere to go')
    ev = event()
    del ev['issue']['number']
    check('an issue with no number is refused',
          refusal_code(B.authorize, ev) == 'BRIDGE_EVENT_MALFORMED')


# ----------------------------------------------------------- the two modes
def test_d_mode_defaults_to_the_harmless_one():
    print('\nD. classification')
    check('a plain request is a conversation',
          B.classify(B.authorize(event(body='what does gamesim do?')))
          == (B.MODE_CONVERSATION, None))
    # PROSE MUST NOT SELECT THE MODE. If wording decided, this body would
    # start an engineering run while asking for the opposite.
    check('  prose about engineering is still a conversation',
          B.classify(B.authorize(event(
              body='do not run any engineering task yet, just explain '
                   'the engineering queue')))[0] == B.MODE_CONVERSATION)
    m, t = B.classify(B.authorize(event(
        body='Mode: engineering\nTask: ENG-001\nplease run it')))
    check('an explicit declaration selects engineering',
          m == B.MODE_ENGINEERING and t == 'ENG-001')
    check('  the marker is case-insensitive',
          B.classify(B.authorize(event(
              body='MODE: ENGINEERING\nTASK: ENG-004')))
          == (B.MODE_ENGINEERING, 'ENG-004'))


def test_e_the_bridge_never_chooses_the_task():
    print('\nE. no freeform task selection')
    check('engineering without a task id is refused',
          refusal_code(B.classify, B.authorize(event(
              body='mode: engineering\nrun whatever is next')))
          == 'BRIDGE_TASK_NOT_NAMED')
    # And the id it does read is carried, not obeyed: the engineering
    # pre-flight still refuses NOT_THE_SELECTED_TASK if canonical state
    # disagrees. That is asserted in validate_engineering_run's own tests;
    # here we only check the bridge does not substitute its own choice.
    _, t = B.classify(B.authorize(event(
        body='mode: engineering\ntask: ENG-999-not-real')))
    check('  an unknown id is passed through, not corrected', t
          == 'ENG-999-not-real')


# ------------------------------------------------------- the policy gate
def test_f_policy_stops_an_authorized_request():
    print('\nF. the policy gate')

    class Snap:
        def __init__(self, enabled, mode):
            self.policy = {'autonomous_operation_enabled': enabled,
                           'execution_mode': mode}
            self.head = 'deadbeef'

    check('disabled autonomy refuses',
          refusal_code(B.check_policy, Snap(False, 'LIVE'))
          == 'BRIDGE_AUTONOMY_DISABLED')
    check('MOCK refuses even when enabled',
          refusal_code(B.check_policy, Snap(True, 'MOCK'))
          == 'BRIDGE_NOT_LIVE')
    check('the bridge has no switch of its own',
          'bridge' not in json.dumps(
              json.loads((REPO / 'coordination'
                          / 'AUTOMATION_POLICY.json').read_text())).lower())


def test_g_end_to_end_refusal_against_the_real_policy():
    print('\nG. the gate, run as the workflow runs it')
    # THE PROOF THE OWNER ASKED FOR: an owner-authored, correctly marked
    # request reaches the point immediately before Claude and stops, because
    # production policy is disarmed. Run as a subprocess so it is the real
    # entry point and the real exit code, not an imported function.
    with tempfile.TemporaryDirectory() as d:
        ep = pathlib.Path(d) / 'event.json'
        ep.write_text(json.dumps(event(body='what is the bullpen defect?')))
        out = pathlib.Path(d) / 'contract.md'
        r = subprocess.run(
            (sys.executable, 'coordination/orchestrator/bridge.py',
             '--event', str(ep), '--out', str(out)),
            cwd=REPO, capture_output=True, text=True)
        check('it exits 1, so the Claude step is never reached',
              r.returncode == 1, f'rc={r.returncode} {r.stdout[:200]}')
        check('  and names the policy as the reason',
              'BRIDGE_AUTONOMY_DISABLED' in r.stdout, r.stdout[:200])
        check('  and still emits the contract', out.exists())
        if out.exists():
            body = out.read_text()
            check('  carrying every contract key',
                  all(f'"{k}"' in body for k in B.CONTRACT_KEYS))
            check('  and marking the result REFUSED', '"REFUSED"' in body)

    # A stranger's request does not even get that far.
    with tempfile.TemporaryDirectory() as d:
        ep = pathlib.Path(d) / 'event.json'
        ep.write_text(json.dumps(event(login='mallory')))
        r = subprocess.run(
            (sys.executable, 'coordination/orchestrator/bridge.py',
             '--event', str(ep)),
            cwd=REPO, capture_output=True, text=True)
        check('a stranger is refused by the script too',
              r.returncode == 1
              and 'BRIDGE_REQUESTER_NOT_OWNER' in r.stdout, r.stdout[:200])
        check('  and no contract claims authorization',
              'AUTHORIZED' not in r.stdout)


# ------------------------------------------------- the continuation fix
def test_h_exactly_one_continuation_and_only_on_success():
    print('\nH. the owner-review continuation')
    from coordination.orchestrator import ingest_engineering_return as I

    src = (REPO / 'coordination' / 'orchestrator'
           / 'ingest_engineering_return.py').read_text()
    # STRUCTURE, NOT A SUBSTRING. The point is not that the call appears
    # somewhere; it is that it appears after the accept and never inside a
    # refusal. _refuse returns before reaching it.
    check('the continuation is requested from the success path',
          'ENGINEERING_RETURN_ACCEPTED' in src
          and src.index('ENGINEERING_RETURN_ACCEPTED')
          < src.index('_request_owner_review(rid, tid)'))
    ref_body = src[src.index('def _refuse'):src.index('def main')]
    check('  and never from the refusal path',
          '_request_owner_review' not in ref_body)
    check('it reuses request_continuation rather than a new dispatcher',
          'G.request_continuation(' in src)
    check('  with the same event type the orchestrator uses',
          G.DISPATCH_EVENT == 'agent-orchestrator-continue')
    check('  and asks the existing budget first',
          src.index('locks.require_continuation_budget')
          < src.index('G.request_continuation('))

    # WHAT WOULD HAVE BEEN SENT, without sending it. The sink exists for
    # exactly this and refuses to report itself as a real dispatch.
    with tempfile.TemporaryDirectory() as d:
        os.environ['ORCHESTRATOR_DISPATCH_SINK'] = d
        try:
            res = G.request_continuation('t', chain_depth=1, head='abc',
                                         task_id='ENG-001')
        finally:
            os.environ.pop('ORCHESTRATOR_DISPATCH_SINK', None)
        files = sorted(pathlib.Path(d).glob('*.json'))
        check('one request produces exactly one dispatch', len(files) == 1,
              str(files))
        check('  reported as NOT sent, because a sink is not GitHub',
              res.get('sent') is False and res.get('code')
              == 'DISPATCH_TO_SINK')
        payload = json.loads(files[0].read_text())
        check('  addressed to the orchestrator continue event',
              payload['event_type'] == 'agent-orchestrator-continue')
        check('  carrying the task it concerns',
              payload['client_payload']['task_id'] == 'ENG-001')
        check('  and carrying no authority',
              'authorized' not in json.dumps(payload).lower()
              and 'execution_mode' not in json.dumps(payload))


def test_i_the_reply_is_written_on_every_outcome():
    print('\nI. the reply')
    from coordination.orchestrator import bridge_reply as R
    import tempfile as _tf

    with _tf.TemporaryDirectory() as d:
        (pathlib.Path(d) / R.REASON_FILE).write_text(
            'BRIDGE_REFUSED BRIDGE_AUTONOMY_DISABLED')
        (pathlib.Path(d) / R.STATUS_FILE).write_text('{"result_status": "REFUSED"}')
        body = R.build({'GATE_OUTCOME': 'failure', 'GITHUB_RUN_ID': '1'},
                       root=d)['body']
        check('a refusal still produces a comment', bool(body.strip()))
        check('  naming the refusal code', 'BRIDGE_AUTONOMY_DISABLED' in body)
        check('  and saying nothing was spent',
              'no subscription usage was consumed' in body)
        check('  and carrying the contract', 'REFUSED' in body)

    with _tf.TemporaryDirectory() as d:
        body = R.build({'GATE_OUTCOME': 'success', 'MODE': 'ENGINEERING',
                        'TASK_ID': 'ENG-001', 'HANDOFF_HTTP': '204'},
                       root=d)['body']
        check('an engineering handoff says it did not authorize anything',
              'does not authorize anything' in body and 'ENG-001' in body)

    with _tf.TemporaryDirectory() as d:
        # AN EMPTY CONCLUSION IS NOT SUCCESS. Run 35897771719 produced exactly
        # this, and the reply must not read as though Claude answered.
        body = R.build({'GATE_OUTCOME': 'success', 'MODE': 'CONVERSATION',
                        'CLAUDE_CONCLUSION': ''}, root=d)['body']
        check('an empty Claude conclusion is reported as empty',
              '(empty)' in body and 'not the same as success' in body)

    with _tf.TemporaryDirectory() as d:
        body = R.build({'GATE_OUTCOME': 'failure'}, root=d)['body']
        check('a gate that printed nothing is called out, not glossed',
              'itself a defect' in body)


def test_j_the_workflow_carries_the_same_gate():
    print('\nJ. the workflow on the default branch')
    r = subprocess.run(
        ('git', 'show', 'origin/main:.github/workflows/ai-bridge.yml'),
        cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        print('  NOT_EXECUTED  ai-bridge.yml not on origin/main yet')
        return
    wf = r.stdout
    # THE JOB-LEVEL GATE, which is what stops a runner starting at all.
    check('the job gate names the owner login',
          f"github.event.issue.user.login == '{B.OWNER_LOGIN}'" in wf)
    check('  and anchors the title with startsWith, not contains',
          f"startsWith(github.event.issue.title, '{B.TITLE_PREFIX}')" in wf)
    # PARSED, NOT GREPPED. The first version of these two checks searched
    # the raw text and failed on the file's own COMMENTS -- the header says
    # "NO issue_comment TRIGGER" and explains why id-token is withheld, and
    # both checks matched the explanation instead of the configuration. That
    # is the fourth time in this repository a substring has stood in for
    # structure. A comment naming a trigger is not a trigger.
    try:
        import yaml
    except ImportError:                                   # pragma: no cover
        print('  NOT_EXECUTED  trigger/permissions shape needs PyYAML')
    else:
        w = yaml.safe_load(wf)
        on = w[True]          # bare `on:` parses as the boolean True
        check('the trigger is issues:opened and nothing else',
              on == {'issues': {'types': ['opened']}}, repr(on))
        check('  so no comment on a public issue can start a run',
              'issue_comment' not in on)
        check('no id-token is granted',
              'id-token' not in w['permissions'], repr(w['permissions']))
        check('  and contents stays read: the bridge does not commit',
              w['permissions']['contents'] == 'read')
    check('the Action is given github_token, so no OIDC path',
          'github_token: ${{ secrets.GITHUB_TOKEN }}' in wf)
    check('the gate runs before the Action',
          wf.index('bridge.py') < wf.index('uses: anthropics/claude-code-action@v1'))
    check('every Claude step is conditioned on the gate succeeding',
          wf.count("steps.gate.outcome == 'success'") >= 2)
    check('conversation mode is restricted to read tools',
          '--allowed-tools Read,Grep,Glob' in wf)
    check('engineering is handed off, not executed here',
          'claude-engineering-dispatch.yml' in wf)


TESTS = [v for k, v in sorted(globals().items()) if k.startswith('test_')]

if __name__ == '__main__':
    for fn in TESTS:
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
