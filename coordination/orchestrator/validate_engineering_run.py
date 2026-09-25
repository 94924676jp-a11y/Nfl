#!/usr/bin/env python3.12
"""Independent pre-flight for the Claude Code engineering workflow.

    python3.12 coordination/orchestrator/validate_engineering_run.py \
        --task-id ENG-001 --expected-head <sha> [--emit-packet]

IF THIS REFUSES, CLAUDE NEVER RUNS. It is deliberately a separate script
rather than a step inside the workflow, for two reasons: it can be tested
without GitHub, and the workflow's job is then to call one thing and obey it
rather than to re-implement judgement in bash.

It re-derives everything from the CHECKED-OUT AUTOMATION BRANCH. The workflow
inputs say which task and which head to expect; they do not say whether the
task is authorized, which task is next, or whether the policy permits a pass.
Those all come from committed state, and an input that disagrees with
committed state is a refusal rather than an override -- that is the whole
authority boundary in one sentence.

Exit codes
    0   validated; the packet is written and the Action may run
    1   refused; the reason is printed and Claude must not run
    2   state unreadable
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib as _pl
import sys as _sys

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import claude_code_transport as T  # noqa: E402
from coordination.orchestrator import contracts as C              # noqa: E402
from coordination.orchestrator import dispatch as D               # noqa: E402
from coordination.orchestrator import locks                       # noqa: E402
from coordination.orchestrator import providers as P              # noqa: E402
from coordination.orchestrator import state as S                  # noqa: E402

ALLOWED_REPOS = ('94924676jp-a11y/Nfl',)
ALLOWED_BRANCHES = ('claude/nfl-greenfield-architecture-stsxmk',)


def refuse(code, detail):
    print(f'ENGINEERING_RUN_REFUSED {code}\n\n  {detail}', flush=True)
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--expected-head', default='')
    ap.add_argument('--repository', default=os.environ.get(
        'GITHUB_REPOSITORY', ''))
    ap.add_argument('--emit-packet', action='store_true')
    ap.add_argument('--run-id', default=os.environ.get('GITHUB_RUN_ID'))
    a = ap.parse_args(argv)

    # ---- 1. allowed repository and branch ------------------------------
    if a.repository and a.repository not in ALLOWED_REPOS:
        return refuse('REPOSITORY_NOT_ALLOWED',
                      f'{a.repository!r} is not in {ALLOWED_REPOS}.')
    branch = S.branch()
    if branch not in ALLOWED_BRANCHES:
        return refuse('BRANCH_NOT_ALLOWED',
                      f'checked out {branch!r}; engineering runs only on '
                      f'{ALLOWED_BRANCHES}.')

    # ---- 2. readable, self-consistent state ----------------------------
    try:
        snap = S.snapshot()
    except S.StateError as exc:
        print(f'STATE_UNREADABLE: {exc}')
        return 2
    if not snap.valid:
        return refuse('COORDINATION_INVALID', snap.validator_output)

    # ---- 3. policy permits a pass --------------------------------------
    if not snap.policy.get('autonomous_operation_enabled'):
        return refuse('AUTONOMY_DISABLED',
                      'AUTOMATION_POLICY.json has '
                      'autonomous_operation_enabled=false.')
    effective = P.resolve_mode(snap.policy, os.environ)
    print(f'  policy: enabled=yes execution_mode='
          f'{P.policy_mode(snap.policy)} -> effective={effective}')

    # ---- 4. the head has not moved -------------------------------------
    head = S.head()
    if a.expected_head and not head.startswith(a.expected_head[:12]):
        return refuse(
            'HEAD_MOVED',
            f'expected {a.expected_head[:12]}, checked out {head[:12]}. The '
            f'packet would describe a tree that no longer exists.')

    # ---- 5. the task exists, is authorized, and is THE next one --------
    qname, task = snap.by_id(a.task_id)
    if task is None:
        return refuse('TASK_NOT_FOUND', f'{a.task_id} is in no queue.')
    if qname != 'ENGINEERING_QUEUE.json':
        return refuse('TASK_NOT_ENGINEERING',
                      f'{a.task_id} lives in {qname}; this workflow runs '
                      f'engineering tasks only.')
    if not task.get('authorized'):
        return refuse('TASK_NOT_AUTHORIZED',
                      f'{a.task_id} has authorized=false.')
    if task.get('status') not in ('AUTHORIZED', 'ACTIVE'):
        return refuse('TASK_NOT_AUTHORIZED',
                      f'{a.task_id} is {task["status"]!r}.')

    # THE CHECK THAT STOPS AN INPUT CHOOSING THE WORK. A workflow input names
    # a task; canonical state decides which task is next. If they disagree,
    # the input loses -- otherwise anyone who can start this workflow picks
    # what the engineering worker does, and the queue is decoration.
    action = D.next_action(snap)
    if action.kind != D.EXECUTE or action.worker is not C.Worker.ENGINEER:
        return refuse(
            'NOT_THE_CURRENT_ACTION',
            f'canonical state says the next action is "{action}", not an '
            f'engineering execution. The input does not get to override it.')
    if action.task_id != a.task_id:
        return refuse(
            'NOT_THE_SELECTED_TASK',
            f'canonical state selects {action.task_id}, the input asked for '
            f'{a.task_id}. Refusing rather than letting an input choose.')

    # ---- 6. exactly one ACTIVE engineering task ------------------------
    try:
        locks.require_exclusive_active(snap, a.task_id)
    except locks.Refusal as r:
        return refuse(r.code, r.detail)

    # ---- 7. retry budget ------------------------------------------------
    try:
        locks.require_retry_budget(snap, a.task_id)
    except locks.Refusal as r:
        return refuse(r.code, r.detail)

    # ---- 8. the credential exists, WITHOUT reading its value ------------
    cfg = snap.models['engineering_model']
    transport = cfg.get('transport')
    if transport != C.Transport.CLAUDE_CODE_ACTION.value:
        return refuse('TRANSPORT_MISMATCH',
                      f'MODELS.json selects {transport!r}; this workflow '
                      f'implements {C.Transport.CLAUDE_CODE_ACTION.value}.')
    cred = cfg[transport]['credential_env']
    if effective == P.MODE_LIVE and not (os.environ.get(cred) or '').strip():
        # Named separately from SECRET_MISSING so the remedy is unambiguous:
        # `claude setup-token`, not an API console.
        return refuse(
            C.Escalation.CLAUDE_OAUTH_MISSING.value,
            f'{cred} is not set and the policy authorizes LIVE. Generate one '
            f'with `claude setup-token` on a trusted machine and add it as a '
            f'repository Actions secret. This transport does not fall back '
            f'to ANTHROPIC_API_KEY -- a silent fallback would move spending '
            f'from a subscription to metered billing with nobody deciding '
            f'to.')

    # ---- 9. build the packet -------------------------------------------
    prior = None
    rp = _pl.Path(S.REPO) / T.RETURN_DIR / a.task_id / T.RESULT_MD
    if rp.exists():
        prior = rp.read_text()[:20000]
    try:
        packet = T.build_packet(task, queue_name=qname, head=head, snap=snap,
                                prior_return=prior,
                                attempt=snap.attempts(a.task_id),
                                run_id=a.run_id)
    except T.PacketRefusal as r:
        return refuse(r.code, r.detail)

    if a.emit_packet:
        # CLEAR THE PREVIOUS ATTEMPT'S RETURN BEFORE THE WORKER STARTS.
        #
        # ingest reads coordination/CLAUDE_RETURNS/<task>/result.json IN
        # PREFERENCE to CLAUDE_STRUCTURED, and it commits whatever the worker
        # leaves behind -- so a second attempt at the same task checks out the
        # FIRST attempt's result.json and ingests that instead of the return
        # just produced. The head_before contract catches it, because the
        # stale result names the old packet's base, so it fails closed rather
        # than accepting stale work. But it fails closed FOREVER: every retry
        # reads the same stale file and refuses RESULT_OUT_OF_CONTRACT with a
        # message about the tree the work started from, which points at the
        # worker and not at the leftover file. A retry budget spent entirely
        # on a deadlock.
        #
        # Removing it here rather than teaching ingest to distrust it keeps
        # the rule simple: after the packet is emitted, anything in the return
        # directory belongs to this run.
        stale = (_pl.Path(S.REPO) / 'coordination' / 'CLAUDE_RETURNS' /
                 a.task_id / 'result.json')
        if stale.exists():
            stale.unlink()
            print(f'  cleared  {stale.relative_to(S.REPO)} '
                  f'(a previous attempt\'s return)')
        p = T.write_packet(packet)
        prompt = T.render_prompt(packet)
        T.assert_packet_is_clean(prompt)
        (_pl.Path(S.REPO) / T.PACKET_DIR / f'{a.task_id}.prompt.md').write_text(
            prompt)
        (_pl.Path(S.REPO) / T.PACKET_DIR / f'{a.task_id}.schema.json'
         ).write_text(json.dumps(T.json_schema(), indent=1) + '\n')
        print(f'  packet   {p.relative_to(S.REPO)}')
        print(f'  prompt   {T.PACKET_DIR}/{a.task_id}.prompt.md')
        print(f'  schema   {T.PACKET_DIR}/{a.task_id}.schema.json')

    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a') as fh:
            fh.write(f'validated=true\n')
            fh.write(f'task_id={a.task_id}\n')
            fh.write(f'head={head}\n')
            fh.write(f'effective_mode={effective}\n')
            fh.write(f'packet_sha256={packet["packet_sha256"]}\n')
    print(f'ENGINEERING_RUN_VALIDATED {a.task_id} at {head[:12]} '
          f'packet {packet["packet_sha256"][:16]}')
    return 0


if __name__ == '__main__':
    _sys.exit(main())
