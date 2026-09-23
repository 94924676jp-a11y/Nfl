#!/usr/bin/env python3.12
"""Ingest what the Claude Code Action left behind, check it, and commit it.

    python3.12 coordination/orchestrator/ingest_engineering_return.py \
        --task-id ENG-001 --head-before <sha> --branch <automation branch>

THE ACTION'S OWN CONCLUSION IS NOT THE VERDICT. A run can report success and
still leave a malformed return, an empty return, or a diff touching a path no
worker may write. Each of those must stop the task advancing, and each is
checked here against artefacts on disk rather than against what the run said
about itself.

WHAT THIS ENFORCES, IN ORDER

  1. the diff. `locks.enforce_protected_paths` against the real changed
     files, BEFORE anything is committed, so a diff containing one forbidden
     path applies none of itself;
  2. the machine-readable result, against the packet that authorized the work;
  3. the human return, against the eight-section contract the manual path
     already uses -- one standard, not two;
  4. the commit, with the run's evidence preserved either way.

WHAT IT DELIBERATELY DOES NOT DO. Mark the task COMPLETE. The worker's return
moves the task to RETURNED and no further. Only the owner reviewer decides a
governed transition, which is the same rule the API transport lives under and
the reason a worker cannot accept its own work.

Exit codes
    0   return accepted, committed, task RETURNED
    2   state unreadable
    3   refused -- malformed, out of contract, or forbidden diff
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
from coordination.orchestrator import github_runtime as G         # noqa: E402
from coordination.orchestrator import locks                       # noqa: E402
from coordination.orchestrator import state as S                  # noqa: E402


def _say(*a):
    print(*a, flush=True)


def _refuse(rid, task_id, code, detail, head, escalation=None) -> int:
    """Record the refusal as evidence, never as a silent no-op."""
    _say(f'ENGINEERING_RETURN_REFUSED {code}\n\n  {detail}')
    G.append_log({'actor': 'anthropic', 'run_id': rid, 'task_id': task_id,
                  'event': 'WORKER_FAILED', 'code': code,
                  'note': str(detail)[:500],
                  'transport': C.Transport.CLAUDE_CODE_ACTION.value})
    if escalation:
        path = G.open_escalation_issue(escalation, f'{task_id}: {code}',
                                       str(detail))
        _say(f'  escalation -> {path}')
    try:
        G.commit_and_push(
            f'{task_id}: engineering return REFUSED [{code}]\n\n'
            f'{str(detail)[:900]}\n\n'
            f'The task is left where it was. A refused return is recorded '
            f'rather than discarded, because the run that failed is the one '
            f'most worth reading. [orchestrator-skip]',
            head, push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    except locks.Refusal as r:
        _say(f'  (refusal not committed: {r.code})')
    return 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--head-before', required=True)
    ap.add_argument('--branch', default='')
    a = ap.parse_args(argv)
    tid = a.task_id
    rid = os.environ.get('GITHUB_RUN_ID') or 'local'
    conclusion = os.environ.get('CLAUDE_CONCLUSION') or 'unknown'
    session = os.environ.get('CLAUDE_SESSION_ID') or None

    try:
        snap = S.snapshot()
    except S.StateError as exc:
        _say(f'STATE_UNREADABLE: {exc}')
        return 2

    qname, task = snap.by_id(tid)
    if task is None:
        _say(f'TASK_NOT_FOUND: {tid}')
        return 2

    pkt_path = _pl.Path(S.REPO) / T.packet_path(tid)
    if not pkt_path.exists():
        return _refuse(rid, tid, 'PACKET_ABSENT',
                       f'{T.packet_path(tid)} is missing, so there is nothing '
                       f'to check the return against.', a.head_before)
    packet = json.loads(pkt_path.read_text())

    # ---- 1. THE DIFF, before anything is committed ----------------------
    changed = [p for p in G.changed_paths()
               if not p.startswith(T.PACKET_DIR)]
    _say(f'  changed paths: {len(changed)}')
    try:
        locks.enforce_protected_paths(changed, C.Worker.ENGINEER)
    except locks.Refusal as r:
        # Refuse the change WHOLE. Reverting here rather than committing is
        # the difference between "the worker was stopped" and "the worker was
        # stopped after we kept some of it".
        G._git('reset', '--hard', 'HEAD', check=False)
        G._git('clean', '-fd', check=False)
        return _refuse(rid, tid, r.code, r.detail, a.head_before,
                       escalation=r.escalation)

    # ---- 2. the machine-readable result --------------------------------
    rdir = _pl.Path(S.REPO) / T.RETURN_DIR / tid
    rjson = rdir / T.RESULT_JSON
    structured = os.environ.get('CLAUDE_STRUCTURED') or ''
    parsed, why = (None, 'no source')
    if rjson.exists():
        parsed, why = T.parse_result(rjson.read_text())
        src = str(rjson.relative_to(S.REPO))
    elif structured.strip():
        # The Action's `structured_output` is a fallback source, not a
        # substitute: a committed file is evidence a reviewer can read at
        # leisure, a step output lives as long as the run does.
        parsed, why = T.parse_result(structured)
        src = 'structured_output'
        if parsed:
            rdir.mkdir(parents=True, exist_ok=True)
            rjson.write_text(json.dumps(parsed, indent=1) + '\n')
    else:
        src = 'nothing'
    if parsed is None:
        return _refuse(
            rid, tid, 'RESULT_MALFORMED',
            f'no usable result.json ({src}: {why}). The Action reported '
            f'conclusion={conclusion!r}, which is not a substitute: a run can '
            f'succeed and still leave nothing checkable.', a.head_before)
    _say(f'  result parsed from {src}')

    ok, why = T.validate_result(parsed, packet)
    if not ok:
        return _refuse(rid, tid, 'RESULT_OUT_OF_CONTRACT', why, a.head_before)

    # ---- 3. the human return, same contract as the manual path ---------
    rmd = rdir / T.RESULT_MD
    if not rmd.exists() or len(rmd.read_text()) < 400:
        return _refuse(rid, tid, 'RETURN_MD_MISSING_OR_STUB',
                       f'{T.RETURN_DIR}/{tid}/{T.RESULT_MD} is absent or too '
                       f'short to be a return.', a.head_before)
    body = rmd.read_text().lower()
    absent = [s for s in C.ENGINEER_RETURN_SECTIONS if s not in body]
    if absent:
        return _refuse(rid, tid, 'RETURN_MD_INCOMPLETE',
                       f'the return is missing {absent}.', a.head_before)

    # ---- 4. record, commit, and move the task to RETURNED --------------
    meta = {
        'task_id': tid, 'worker': C.Worker.ENGINEER.value,
        'transport': C.Transport.CLAUDE_CODE_ACTION.value,
        'action': 'anthropics/claude-code-action@v1',
        'session_id': session, 'action_conclusion': conclusion,
        'actions_run_id': rid, 'head_before': a.head_before,
        'packet_sha256': packet.get('packet_sha256'),
        'changed_paths': changed,
        'result_status': parsed.get('result_status'),
        'note': ('No credential appears here or anywhere in the return. The '
                 'OAuth token is consumed by the Action and never read, '
                 'logged or written by this runtime.'),
    }
    (rdir / 'transport_metadata.json').write_text(
        json.dumps(meta, indent=1) + '\n')

    G.update_task(qname, tid, status='RETURNED',
                  result_path=str(rmd.relative_to(S.REPO)))
    G.append_log({'actor': 'anthropic', 'run_id': rid, 'task_id': tid,
                  'from_status': task.get('status'), 'to_status': 'RETURNED',
                  'artifact_path': str(rmd.relative_to(S.REPO)),
                  'transport': C.Transport.CLAUDE_CODE_ACTION.value,
                  'worker_status': parsed.get('result_status'),
                  'note': 'Claude Code Action return, checked and committed'})

    sha = G.commit_and_push(
        f'{tid}: engineering return via Claude Code Action\n\n'
        f'{(parsed.get("result_status") or "")} — '
        f'{len(changed)} changed path(s), '
        f'{len(parsed.get("acceptance_criteria_results") or [])} criteria '
        f'judged.\n\nrun {rid}\n\n'
        f'The worker does not accept its own work: this moves the task to '
        f'RETURNED. Only the owner reviewer decides COMPLETE.',
        a.head_before, push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    if sha:
        G.update_task(qname, tid, commit_sha=sha)
        _say(f'  committed {sha[:12]}')
    _say(f'ENGINEERING_RETURN_ACCEPTED {tid} status={parsed["result_status"]}'
         f' -> task RETURNED (owner review decides COMPLETE)')

    # ---- 5. wake the owner reviewer, and ONLY from here ----------------
    _request_owner_review(rid, tid)
    return 0


def _request_owner_review(rid, tid) -> dict:
    """Ask for one orchestrator pass so the OpenAI owner worker reviews this.

    THE GAP THIS CLOSES. Before this, a successful ingest set the task to
    RETURNED, committed, and stopped. Nothing dispatched the orchestrator, so
    the owner-review half of the loop never woke and the chain ended at
    RETURNED -- which looks like a finished run and is actually a stall. The
    engineering worker cannot accept its own work, so a return nobody reviews
    is a return that goes nowhere.

    IT IS REACHED ONLY FROM THE SUCCESS PATH. Every refusal returns through
    _refuse, which does not come here. A malformed return, a diff touching a
    protected path, an unreadable state -- none of them may wake a reviewer,
    because there is nothing lawful to review and the pass would burn a
    continuation to discover that.

    NOT A SECOND MECHANISM. This calls the same
    github_runtime.request_continuation the orchestrator calls, carrying the
    same event type, and it asks locks.require_continuation_budget first so
    it is bounded by the same limits.max_continuations_per_hour. A separate
    dispatcher with its own bound would be a second thing to reason about and
    a second thing to forget to cap.
    """
    try:
        snap = S.snapshot()
    except S.StateError as exc:
        # Not fatal. The return is committed; what is lost is the wake-up,
        # and saying so is better than raising over work already accepted.
        _say(f'  owner review NOT requested -- state unreadable: {exc}')
        return {'sent': False, 'code': 'STATE_UNREADABLE'}
    try:
        locks.require_continuation_budget(snap)
    except locks.Refusal as r:
        _say(f'  owner review NOT requested: {r.code} -- {r.detail}')
        G.append_log({'actor': 'anthropic', 'run_id': rid, 'task_id': tid,
                      'event': 'CONTINUATION_REFUSED', 'note': r.code})
        return {'sent': False, 'code': r.code}

    depth = sum(1 for row in snap.log
                if row.get('event') == 'CONTINUATION_REQUESTED')
    why = f'{tid} is RETURNED and awaits owner review'
    res = G.request_continuation(why, chain_depth=depth + 1, head=snap.head,
                                 task_id=tid)
    _say(f'  owner review: {res.get("code")} '
         f'{"sent" if res.get("sent") else "NOT sent"}')
    G.append_log({'actor': 'anthropic', 'run_id': rid, 'task_id': tid,
                  'event': 'CONTINUATION_REQUESTED',
                  'note': f'{res.get("code")}: {why}'[:400],
                  'dispatch_sent': bool(res.get('sent'))})
    try:
        G.commit_and_push(
            f'{tid}: request owner review [{res.get("code")}]\n\n'
            f'The engineering return is committed and the task is RETURNED. '
            f'This row records the continuation request that wakes the owner '
            f'reviewer, and it is what the next pass counts against '
            f'limits.max_continuations_per_hour.',
            snap.head, push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    except Exception as exc:                      # noqa: BLE001
        _say(f'  continuation log not pushed: {exc}')
    return res


if __name__ == '__main__':
    _sys.exit(main())
