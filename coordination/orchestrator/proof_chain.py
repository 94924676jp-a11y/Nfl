#!/usr/bin/env python3.12
"""Prove the REPOSITORY-LEVEL event chain, without touching real state.

    python3.12 coordination/orchestrator/proof_chain.py

WHAT WAS STILL UNPROVEN, AND WHY A SUBPROCESS TEST COULD NOT PROVE IT

`test_orchestrator::test_m` runs three orchestration passes as three separate
processes and shows the state machine advances with nothing carried between
them but the repository. That is the STATE PLANE, and it is proven.

It says nothing about the EVENT PLANE: whether a `repository_dispatch` sent
with `GITHUB_TOKEN` actually causes GitHub to start another Actions run, with
the workflow definition on the default branch, checking out the automation
branch. Every part of that sentence is a property of GitHub, not of this code,
and the only way to establish it is to make it happen and read the run ids
back. Two assumptions in this area were already wrong:

  * push events from GITHUB_TOKEN do not start workflows at all;
  * a workflow only answers repository_dispatch if its definition is on the
    DEFAULT branch -- which this repository's was not.

Both looked fine in every test that did not cross a workflow boundary.

WHAT THIS SCRIPT DOES, AND WHAT IT DELIBERATELY DOES NOT

It runs ONE REAL orchestration pass -- the real `dispatch.next_action`, the
real workers, the real commit path -- against a THROWAWAY SANDBOX built inside
the runner. It then writes one proof-ledger row to the automation branch,
commits it, and asks GitHub for the next pass exactly as the production path
does.

So the event chain is real: real Actions runs, real commits, real dispatches,
real run ids. What is sandboxed is the PROJECT STATE. The real queues, returns
and handoff log are not read and not written, `autonomous_operation_enabled`
stays false, and no provider is ever called -- the sandbox runs in MOCK.

That split is the point. The chain being proven is the part nobody has
evidence for; the part that already has evidence is not re-run against live
state just to look thorough, because doing that would write fixture output
into ENG-001's own return path.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib as _pl
import shutil
import subprocess
import sys
import tempfile
import uuid

_sys_root = _pl.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_sys_root))

from coordination.orchestrator import github_runtime as G   # noqa: E402
from coordination.orchestrator import dispatch as D         # noqa: E402
from coordination.orchestrator import locks                 # noqa: E402
from coordination.orchestrator import main as M             # noqa: E402
from coordination.orchestrator import state as S            # noqa: E402

REPO = _sys_root
LEDGER_DIR = REPO / 'coordination' / 'runs' / '_proof'
MAX_PASSES = 3


def _say(*a):
    print(*a, flush=True)


def _run_url():
    base = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    rid = os.environ.get('GITHUB_RUN_ID', '')
    return f'{base}/{repo}/actions/runs/{rid}' if repo and rid else ''


def build_sandbox(root: _pl.Path, which_pass: int) -> _pl.Path:
    """A self-contained coordination tree, seeded for this pass.

    Seeded BY PASS NUMBER rather than carried forward, because each Actions
    run gets a clean runner and there is nowhere to carry a sandbox to. What
    IS carried forward is the thing under test: the dispatch event, and the
    proof ledger committed to the automation branch.
    """
    coord = root / 'coordination'
    for d in ('CLAUDE_RETURNS', 'PERPLEXITY_RETURNS', 'CHATGPT_OUTBOX',
              'orchestrator'):
        (coord / d).mkdir(parents=True, exist_ok=True)
    real = REPO / 'coordination'
    shutil.copy(real / 'validate_coordination.py', coord)
    shutil.copy(real / '__init__.py', coord)
    for f in sorted((real / 'orchestrator').glob('*.py')):
        shutil.copy(f, coord / 'orchestrator')
    shutil.copytree(real / 'orchestrator' / 'mocks',
                    coord / 'orchestrator' / 'mocks', dirs_exist_ok=True)

    policy = json.loads((real / 'AUTOMATION_POLICY.json').read_text())
    # ENABLED IN THE SANDBOX ONLY. The real policy file on the automation
    # branch is untouched and still reads false; this copy exists for the
    # length of one runner job and is thrown away with it.
    policy['autonomous_operation_enabled'] = True
    policy['branch_policy']['protected_branches'] = ['main']
    (coord / 'AUTOMATION_POLICY.json').write_text(json.dumps(policy, indent=1))
    shutil.copy(real / 'orchestrator' / 'MODELS.json', coord / 'orchestrator')

    (coord / 'PROJECT_STATE.json').write_text(json.dumps(
        {'schema': 'project_state', 'schema_version': '1.0.0',
         'project': 'event-chain proof sandbox', 'head_commit': None,
         'branch': 'proof'}, indent=1))
    (coord / 'OWNER_DECISIONS.md').write_text(
        '# Owner decisions\n\n## D-01 proof sandbox\n\nA decision does not '
        'expire.\n')
    (coord / 'HANDOFF_LOG.jsonl').write_text('')

    base = {'priority': 1, 'depends_on': [], 'created_by': 'owner',
            'result_path': None, 'commit_sha': None, 'blocks': [],
            'evidence': None,
            'acceptance_tests': ['the proof task is carried out',
                                 'evidence is recorded']}
    t1 = dict(base, task_id='PROOF-1', title='proof engineering task',
              objective='exercise the engineering worker', authorized=True,
              status='AUTHORIZED')
    t2 = dict(base, task_id='PROOF-2', title='the task after', priority=2,
              objective='exercise the next transition', authorized=False,
              status='DRAFT')
    # Pass 2 must find PROOF-1 RETURNED so the owner-review branch is what
    # runs. Pass 3 must find it COMPLETE and PROOF-2 authorized.
    if which_pass >= 2:
        t1 = dict(t1, status='RETURNED',
                  result_path='coordination/CLAUDE_RETURNS/PROOF-1.md')
    if which_pass >= 3:
        t1 = dict(t1, status='COMPLETE')
        t2 = dict(t2, status='AUTHORIZED', authorized=True)

    placeholder = [dict(base, task_id='RES-PLACEHOLDER', status='DRAFT',
                        authorized=False, title='placeholder',
                        objective='none', priority=999)]
    for name, tasks in (('ENGINEERING_QUEUE.json', [t1, t2]),
                        ('RESEARCH_QUEUE.json', placeholder)):
        (coord / name).write_text(json.dumps(
            {'schema': 'task_queue', 'schema_version': '1.0.0',
             'written_at_utc': '2026-09-23T00:00:00Z', 'written_by': 'proof',
             'status_vocabulary': ['DRAFT', 'AUTHORIZED', 'ACTIVE', 'BLOCKED',
                                   'RETURNED', 'COMPLETE', 'SUPERSEDED'],
             'execution_rule': 'authorized=true AND status=AUTHORIZED',
             'exclusive_active': name == 'ENGINEERING_QUEUE.json',
             'return_contract': 'coordination/CLAUDE_RETURNS/<task_id>.md',
             'tasks': tasks}, indent=1))

    mocks = coord / 'orchestrator' / 'mocks'
    for tid in ('PROOF-1', 'PROOF-2'):
        (mocks / f'anthropic.{tid}.json').write_text(json.dumps({'parsed': {
            'task_id': tid, 'status': 'COMPLETED',
            'implementation_summary': f'proof worker handled {tid}',
            'files_changed': [f'{tid.lower()}.txt'],
            'patches': [{'path': f'{tid.lower()}.txt',
                         'contents': 'proof\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'owner review'}}))
    (mocks / 'openai.PROOF-1.json').write_text(json.dumps({'parsed': {
        'task_id': 'PROOF-1', 'verdict': 'ACCEPT',
        'reasoning': 'both acceptance tests are evidenced in the return',
        'acceptance_test_verdicts': [
            {'test': t, 'satisfied': True, 'evidence': 'in the return'}
            for t in base['acceptance_tests']],
        'escalation_reason': None, 'next_task_id': 'PROOF-2',
        'new_task': None, 'research_request': None,
        'project_state_updates': {}, 'directive': None}}))

    if which_pass >= 2:
        (coord / 'CLAUDE_RETURNS' / 'PROOF-1.md').write_text(
            '# PROOF-1\n\nwork performed / evidence / tests / failures / '
            'changed files / commit sha / blockers / recommended next '
            'action\n')

    for cmd in (('git', 'init', '-q', '-b', 'proof'),
                ('git', 'config', 'user.email', 'proof@example.invalid'),
                ('git', 'config', 'user.name', 'proof'),
                ('git', 'add', '-A'),
                ('git', 'commit', '-q', '-m', 'proof sandbox')):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    if which_pass >= 2:
        sha = subprocess.run(('git', 'rev-parse', 'HEAD'), cwd=root,
                             capture_output=True, text=True).stdout.strip()
        q = json.loads((coord / 'ENGINEERING_QUEUE.json').read_text())
        for t in q['tasks']:
            if t['task_id'] == 'PROOF-1':
                t['commit_sha'] = sha
        (coord / 'ENGINEERING_QUEUE.json').write_text(json.dumps(q, indent=1))
        subprocess.run(('git', 'add', '-A'), cwd=root, capture_output=True)
        subprocess.run(('git', 'commit', '-q', '-m', 'seed sha'), cwd=root,
                       capture_output=True)
    return root


def main() -> int:
    which = int(os.environ.get('PROOF_PASS') or '1')
    chain_id = os.environ.get('PROOF_CHAIN_ID') or uuid.uuid4().hex[:12]
    branch = os.environ.get('AUTOMATION_BRANCH') or S.branch()
    _say(f'PROOF CHAIN {chain_id} -- pass {which} of {MAX_PASSES}')
    _say(f'  actions run: {_run_url() or "(not an Actions run)"}')

    if which > MAX_PASSES:
        _say('chain complete; not requesting another pass.')
        return 0

    tmp = _pl.Path(tempfile.mkdtemp(prefix=f'proof-{chain_id}-'))
    real_repo = S.REPO
    action_str, ok = '(none)', False
    try:
        build_sandbox(tmp, which)
        S.rebind(tmp)
        os.environ['AUTONOMY_MODE'] = 'MOCK'
        os.environ['ORCHESTRATOR_PUSH'] = '0'
        os.environ['ORCHESTRATOR_RUN_TESTS'] = '0'
        os.environ.pop('ORCHESTRATOR_DISPATCH_SINK', None)
        from coordination.orchestrator import providers as P
        P.MOCKS = tmp / 'coordination' / 'orchestrator' / 'mocks'

        snap = S.snapshot()
        action = D.next_action(snap)
        action_str = str(action)
        _say(f'  sandbox action: {action_str}')
        if action.kind == D.OWNER_REVIEW:
            ok, _e = M.do_owner_review(snap, action, S.head())
        elif action.kind == D.EXECUTE:
            ok, _e = M.do_execute(snap, action, S.head())
        else:
            ok = True
        _say(f'  sandbox pass ok={ok}')
    finally:
        S.rebind(real_repo)
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- the durable evidence, on the automation branch ------------------
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        'chain_id': chain_id,
        'pass': which,
        'recorded_at_utc': dt.datetime.now(dt.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
        'actions_run_id': os.environ.get('GITHUB_RUN_ID'),
        'actions_run_url': _run_url(),
        'triggered_by': ('repository_dispatch from the previous pass'
                         if which > 1 else 'a human workflow_dispatch'),
        'branch_checked_out': branch,
        'sandbox_action': action_str,
        'sandbox_pass_ok': ok,
        'note': ('Event-plane proof. The orchestration pass ran against a '
                 'throwaway sandbox inside the runner; the real queues, '
                 'returns and handoff log were not read or written, '
                 'autonomous_operation_enabled stayed false, and no provider '
                 'was called. What is real here is the Actions run, the '
                 'commit, and the dispatch that starts the next one.'),
    }
    p = LEDGER_DIR / f'{chain_id}-pass{which}.json'
    p.write_text(json.dumps(row, indent=1) + '\n')
    _say(f'  wrote {p.relative_to(REPO)}')

    head = S.head()
    try:
        G.commit_and_push(
            f'proof chain {chain_id}: pass {which} ran as Actions run '
            f'{row["actions_run_id"]}\n\n'
            f'{row["triggered_by"]}\n'
            f'sandbox action: {action_str}\n\n'
            f'Event-plane proof only -- real coordination state untouched, '
            f'autonomy still false, no provider called. [orchestrator-skip]',
            head, push=True)
        _say('  committed and pushed the proof row')
    except locks.Refusal as r:
        _say(f'  proof row not pushed: {r.code} {r.detail[:200]}')

    if which >= MAX_PASSES:
        _say(f'PROOF CHAIN {chain_id} COMPLETE after {MAX_PASSES} passes; '
             f'not requesting another.')
        return 0

    # ONE dispatch, not two. The first draft called the generic helper AND
    # _dispatch_with, which would have started two Actions runs per pass and
    # made the chain's own run count meaningless as evidence. The proof chain
    # needs `mode` and `proof_pass` in the payload, which the generic helper
    # does not carry, so it sends its own -- same endpoint, same event type,
    # same token, same allowlist on the receiving end.
    res = _dispatch_with({'mode': 'PROOF', 'chain_id': chain_id,
                          'proof_pass': which + 1}, branch)
    _say(f'  continuation for pass {which + 1}: {res}')
    return 0 if res.get('sent') else 6


def _dispatch_with(extra, branch) -> dict:
    """Send the proof continuation, carrying only routing fields."""
    import urllib.error
    import urllib.request
    repo = os.environ.get('GITHUB_REPOSITORY')
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not repo or not token:
        return {'sent': False, 'code': 'DISPATCH_UNAVAILABLE'}
    body = {'event_type': G.DISPATCH_EVENT,
            'client_payload': {'branch': branch,
                               'requested_by_run': os.environ.get(
                                   'GITHUB_RUN_ID'),
                               'chain_depth': extra['proof_pass'],
                               'reason': 'event-chain proof',
                               **extra}}
    req = urllib.request.Request(
        f'{G.GITHUB_API}/repos/{repo}/dispatches',
        data=json.dumps(body).encode(), method='POST',
        headers={'Accept': 'application/vnd.github+json',
                 'Authorization': f'Bearer {token}',
                 'X-GitHub-Api-Version': '2022-11-28',
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {'sent': True, 'code': f'DISPATCH_{r.status}'}
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', 'replace')[:400]
        except Exception:                                    # noqa: BLE001
            pass
        hint = (' -- needs permissions: contents: write AND actions: write'
                if exc.code == 403 else '')
        return {'sent': False, 'code': f'DISPATCH_HTTP_{exc.code}',
                'detail': detail + hint}
    except Exception as exc:                                 # noqa: BLE001
        return {'sent': False, 'code': 'DISPATCH_FAILED',
                'detail': f'{type(exc).__name__}: {exc}'}


if __name__ == '__main__':
    sys.exit(main())
