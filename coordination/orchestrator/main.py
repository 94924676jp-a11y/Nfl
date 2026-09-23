#!/usr/bin/env python3.12
"""The orchestration pass. Reads state, takes ONE action, records it, stops.

    python3.12 coordination/orchestrator/main.py            # one pass
    python3.12 coordination/orchestrator/main.py --plan     # decide, do nothing
    python3.12 coordination/orchestrator/main.py --max 3    # up to 3 transitions

WHY A PASS IS SHORT AND THE LOOP IS LONG

Each invocation takes at most `max_transitions_per_invocation` actions and
then exits, leaving a commit behind. The commit is a GitHub event; the event
starts the next pass. So the state machine advances across many short runs
rather than inside one long one, and every step of it is a reviewable commit
rather than a line in a log nobody reads.

That design costs a little latency and buys three things. A runaway cannot
exceed its budget without a human-visible commit per step. A crashed runner
loses at most one transition, because the state it was working from is on
disk. And the whole history of what the system did to itself is `git log`.

WHAT ONE PASS DOES

  snapshot -> decide (dispatch.next_action) -> act -> record -> commit -> stop

`act` is the only interesting part and it has exactly three shapes: run a
worker on a task, have the owner worker review a return, or stop. Everything
else -- budgets, locks, duplicate detection, protected paths -- has already
refused before we get here, which is why this file is short.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib as _pl
import sys as _sys

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import anthropic_engineer as ENG   # noqa: E402
from coordination.orchestrator import contracts as C              # noqa: E402
from coordination.orchestrator import dispatch as D               # noqa: E402
from coordination.orchestrator import github_runtime as G         # noqa: E402
from coordination.orchestrator import locks                       # noqa: E402
from coordination.orchestrator import openai_owner as OWN         # noqa: E402
from coordination.orchestrator import perplexity_research as RES  # noqa: E402
from coordination.orchestrator import providers as P              # noqa: E402
from coordination.orchestrator import state as S                  # noqa: E402

WORKER_MODULE = {C.Worker.ENGINEER: ENG, C.Worker.RESEARCH: RES,
                 C.Worker.OWNER: OWN}
MODEL_KEY = {C.Worker.ENGINEER: 'engineering_model',
             C.Worker.RESEARCH: 'research_model',
             C.Worker.OWNER: 'owner_model'}


def _say(*a):
    print(*a, flush=True)


def _relevant_files(task, repo=None, cap=12, max_bytes=60000):
    """The files a task's own record points at. NOT a guess.

    A worker given the wrong files writes the wrong code confidently, so this
    reads `relevant_files` / `evidence` off the task record rather than
    inferring from the title. If a task does not say what it touches, the
    worker gets nothing and says so -- which is the correct failure.
    """
    repo = repo or S.REPO     # resolved at call time; see apply_patches
    named = list(task.get('relevant_files') or [])
    if not named:
        for tok in str(task.get('evidence') or '').replace(',', ' ').split():
            if '/' in tok and tok.endswith(('.py', '.json', '.md', '.yml')):
                named.append(tok.strip())
    out, used = {}, 0
    for rel in named[:cap]:
        p = repo / rel
        if not p.exists() or not p.is_file():
            continue
        body = p.read_text(errors='replace')
        if used + len(body) > max_bytes:
            body = body[:max(0, max_bytes - used)] + '\n... [TRUNCATED]\n'
        out[rel] = body
        used += len(body)
        if used >= max_bytes:
            break
    return out


def _escalate(esc, title, body, *, commit=True, head=None):
    path = G.open_escalation_issue(esc, title, body)
    _say(f'ESCALATION {esc.value} -> {path}')
    G.append_log({'actor': 'orchestrator', 'event': 'ESCALATION',
                  'escalation': esc.value, 'artifact_path': path,
                  'note': title[:300]})
    if commit and head:
        try:
            G.commit_and_push(
                f'orchestrator: escalate {esc.value}\n\n{title}\n\n'
                f'The autonomous loop stopped here and did not retry. A human '
                f'changes something before it resumes.', head,
                push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
        except locks.Refusal as r:
            _say(f'  (escalation not committed: {r.code})')
    return path


# --------------------------------------------------------------- one call
def _call(snap, worker, task, system, user, attempt, head):
    """Build, guard, make and preserve one provider call."""
    cfg = snap.models[MODEL_KEY[worker]]
    call = C.WorkerCall(worker=worker, model=cfg['model'],
                        task_id=task['task_id'],
                        prompt_sha256=C.prompt_hash(system + user),
                        head_before=head, attempt=attempt)
    locks.require_not_duplicate(snap, call)

    # THE MODE IS DERIVED FROM THE PROTECTED POLICY IN THE SNAPSHOT, which was
    # read from the automation branch at the start of this pass. Not from the
    # event that woke us, and not from the environment alone. The environment
    # can only restrict.
    effective = P.resolve_mode(snap.policy, os.environ)
    if effective == P.MODE_LIVE:
        locks.require_secret(os.environ, P.SECRET_ENV[cfg['provider']], worker)

    rid = G.run_id(worker, task['task_id'], call.idempotency_key)
    _say(f'  calling {worker.value} ({cfg["model"]}) '
         f'requested={P.requested_mode()} policy={P.policy_mode(snap.policy)} '
         f'effective={effective} run={rid}')
    result = P.call_worker(call, worker, cfg, system, user,
                           task_id=task['task_id'],
                           effective_mode=effective)
    G.write_run(rid, call=call, result=result, system=system, user=user,
                head_before=head)
    return rid, call, result, cfg


def _record_failure(snap, rid, task, result, head):
    """A failed worker call is recorded as a failure. Never as a result."""
    _say(f'  WORKER_FAILED {result.code}: {result.detail[:300]}')
    G.append_log({'actor': 'orchestrator', 'run_id': rid,
                  'task_id': task['task_id'],
                  'idempotency_key': result.call.idempotency_key,
                  'event': 'WORKER_FAILED', 'code': result.code,
                  'note': result.detail[:500]})
    esc = result.escalation
    # A SPECIFIC DIAGNOSIS OUTRANKS THE GENERIC ONE. The retry budget being
    # spent says "this keeps failing"; PROVIDER_ACCESS_DENIED says "and here
    # is exactly why, and retrying will not help". Overwriting the second with
    # the first loses the only actionable fact in the failure.
    if esc in C.NEVER_AUTO_RETRY:
        pass
    elif snap.attempts(task['task_id']) > (
            snap.policy.get('limits') or {}).get('max_retries_per_task', 0):
        esc = C.Escalation.REPEATED_AGENT_FAILURE
    if esc:
        _escalate(esc, f'{task["task_id"]}: {result.code}',
                  result.detail, head=head)
    return esc


# ------------------------------------------------------------- the actions
def do_execute(snap, action, head) -> tuple:
    """Run the engineering or research worker on one authorized task."""
    task, qname, worker = action.task, action.queue_name, action.worker
    if worker is None or task is None:
        # A CALLER THAT PASSES A STOP HERE HAS A BUG, AND SAYS SO. The first
        # cut raised KeyError: None from a dict lookup, which names neither
        # the caller nor the mistake.
        raise locks.Refusal(
            'ACTION_NOT_EXECUTABLE',
            f'do_execute was given a {action.kind} action, which carries no '
            f'worker or task. Only EXECUTE actions are executable.',
            escalation=C.Escalation.STATE_CONTRADICTORY)
    mod = WORKER_MODULE[worker]
    attempt = snap.attempts(task['task_id'])

    if worker is C.Worker.ENGINEER:
        user = mod.build_prompt(
            task=task, directive=action.reason,
            project_state=snap.project_state, decisions=S.decisions_text(),
            files=_relevant_files(task), prior_return=action.prior_return)
    else:
        user = mod.build_prompt(task=task, directive=action.reason,
                                project_state=snap.project_state)

    if task.get('status') != 'ACTIVE':
        G.update_task(qname, task['task_id'], status='ACTIVE')
        G.append_log({'actor': 'orchestrator', 'task_id': task['task_id'],
                      'from_status': task.get('status'), 'to_status': 'ACTIVE',
                      'note': f'claimed by the orchestrator for {worker.value}'})

    rid, call, result, cfg = _call(snap, worker, task, mod.SYSTEM, user,
                                   attempt, head)
    if not result.ok:
        return False, _record_failure(snap, rid, task, result, head)

    ok, why = mod.validate_response(result.parsed, task['task_id'])
    if not ok:
        bad = C.WorkerResult.failure(call, 'WORKER_CONTRACT_VIOLATION', why,
                                     raw=result.raw)
        return False, _record_failure(snap, rid, task, bad, head)

    # ---- apply ----------------------------------------------------------
    written, tested, test_out = [], [], None
    if worker is C.Worker.ENGINEER:
        written = G.apply_patches(result.parsed.get('patches') or [], worker)
        _say(f'  wrote {len(written)} file(s)')
        tested = result.parsed.get('tests_run') or []
        if tested and os.environ.get('ORCHESTRATOR_RUN_TESTS', '1') == '1':
            passed, test_out = G.run_tests(
                tested, timeout=(snap.policy.get('limits') or {}).get(
                    'max_task_runtime_seconds', 1800))
            _say(f'  tests {"passed" if passed else "FAILED"}')
        normalized = mod.normalized_return(
            result.parsed, task=task, run_id=rid, model=cfg['model'],
            test_output=test_out)
    else:
        normalized = mod.normalized_return(result.parsed, task=task,
                                           run_id=rid, model=cfg['model'])
        reg = mod.source_registry(result.parsed, task_id=task['task_id'],
                                  run_id=rid, model=cfg['model'])
        (G.RUNS / rid / 'sources.json').write_text(
            json.dumps(reg, indent=1) + '\n')

    p = G.write_return(qname, task['task_id'], normalized)
    (G.RUNS / rid / 'normalized_return.md').write_text(normalized)

    G.update_task(qname, task['task_id'], status='RETURNED',
                  result_path=str(p.relative_to(S.REPO)))
    G.append_log({'actor': worker.value.lower(), 'run_id': rid,
                  'task_id': task['task_id'],
                  'idempotency_key': call.idempotency_key,
                  'from_status': 'ACTIVE', 'to_status': 'RETURNED',
                  'artifact_path': str(p.relative_to(S.REPO)),
                  'worker_status': result.parsed.get('status'),
                  'tokens': result.usage.get('total_tokens'),
                  'note': f'{worker.value} returned via the orchestrator'})

    sha = G.commit_and_push(
        f'{task["task_id"]}: {worker.value.lower()} worker return\n\n'
        f'{result.parsed.get("implementation_summary") or result.parsed.get("implications") or ""}'
        f'\n\nrun {rid}\nThe worker does not authorize its own next task; '
        f'this return goes to owner review.', head,
        push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    if sha:
        G.update_task(qname, task['task_id'], commit_sha=sha)
        _say(f'  committed {sha[:12]}')
    return True, None


def do_owner_review(snap, action, head) -> tuple:
    """The owner worker judges one RETURNED task and the queue moves."""
    task, qname = action.task, action.queue_name
    if task is None or qname is None:
        raise locks.Refusal(
            'ACTION_NOT_EXECUTABLE',
            f'do_owner_review was given a {action.kind} action, which carries '
            f'no task to review.',
            escalation=C.Escalation.STATE_CONTRADICTORY)
    rp = S.RETURNS[qname] / f'{task["task_id"]}.md'
    return_text = rp.read_text() if rp.exists() else None

    user = OWN.build_prompt(task=task, return_text=return_text,
                            project_state=snap.project_state,
                            decisions=S.decisions_text(),
                            queue_summary=D.summarize_queues(snap))
    rid, call, result, cfg = _call(snap, C.Worker.OWNER, task, OWN.SYSTEM,
                                   user, snap.attempts(task['task_id']), head)
    if not result.ok:
        return False, _record_failure(snap, rid, task, result, head)

    ok, why = OWN.validate_response(result.parsed, task['task_id'], task)
    if not ok:
        bad = C.WorkerResult.failure(call, 'WORKER_CONTRACT_VIOLATION', why,
                                     raw=result.raw)
        return False, _record_failure(snap, rid, task, bad, head)

    # THE MECHANICAL LIMIT, APPLIED TO WHAT IT PROPOSED, NOT TO WHAT IT SAID
    # IT WOULD DO.
    try:
        locks.enforce_reserved_decisions(OWN.proposal_text(result.parsed),
                                         'OPENAI owner')
    except locks.Refusal as r:
        _escalate(r.escalation, f'{task["task_id"]}: {r.code}', r.detail,
                  head=head)
        return False, r.escalation

    verdict = C.Verdict(result.parsed['verdict'])
    note = OWN.review_note(result.parsed, task=task, run_id=rid,
                           model=cfg['model'])
    (G.RUNS / rid / 'normalized_return.md').write_text(note)
    if rp.exists():
        rp.write_text(rp.read_text().rstrip() + '\n\n---\n\n' + note)

    new_status = {C.Verdict.ACCEPT: 'COMPLETE',
                  C.Verdict.RETURN_FOR_CORRECTION: 'AUTHORIZED',
                  C.Verdict.BLOCK: 'BLOCKED'}.get(verdict)
    if new_status:
        G.update_task(qname, task['task_id'], status=new_status)
    _say(f'  verdict {verdict.value} -> {new_status or "no status change"}')

    created = None
    if result.parsed.get('new_task'):
        nt = dict(result.parsed['new_task'])
        qn = ('ENGINEERING_QUEUE.json' if nt.pop('queue', '') == 'ENGINEERING'
              else 'RESEARCH_QUEUE.json')
        try:
            created = G.add_task(qn, nt)          # arrives DRAFT, never AUTHORIZED
            _say(f'  drafted {created["task_id"]} in {qn} (DRAFT, '
                 f'unauthorized -- a human authorizes it or it never runs)')
        except locks.Refusal as r:
            _say(f'  new_task refused: {r.code} {r.detail[:200]}')

    nid = result.parsed.get('next_task_id')
    if nid and nid not in OWN.NEVER_AUTHORIZE:
        _qn, nt = snap.by_id(nid)
        if nt is not None and nt.get('status') == 'DRAFT':
            # Only a task the OWNER already drafted may be flipped. A task the
            # worker invented in this same pass cannot be, because it was just
            # created by `add_task` and this snapshot predates it.
            G.update_task(_qn, nid, status='AUTHORIZED', authorized=True)
            _say(f'  authorized {nid} (was DRAFT, owner-created)')

    if result.parsed.get('directive'):
        d = result.parsed['directive']
        if d.get('filename') and d.get('body'):
            G.write_directive(d['filename'], d['body'])

    G.append_log({'actor': 'openai', 'run_id': rid, 'task_id': task['task_id'],
                  'idempotency_key': call.idempotency_key,
                  'from_status': 'RETURNED', 'to_status': new_status,
                  'event': 'OWNER_REVIEW', 'verdict': verdict.value,
                  'tokens': result.usage.get('total_tokens'),
                  'note': (result.parsed.get('reasoning') or '')[:400]})

    sha = G.commit_and_push(
        f'{task["task_id"]}: owner review -> {verdict.value}\n\n'
        f'{(result.parsed.get("reasoning") or "")[:900]}\n\nrun {rid}', head,
        push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    if sha:
        _say(f'  committed {sha[:12]}')

    if verdict is C.Verdict.ESCALATE:
        esc = C.Escalation(result.parsed['escalation_reason'])
        _escalate(esc, f'{task["task_id"]}: owner worker escalated',
                  result.parsed.get('reasoning') or '', head=S.head())
        return True, esc
    return True, None


# ------------------------------------------------------------------- pass
def one_pass(*, max_transitions=None, plan_only=False,
             require_autonomy=True) -> int:
    try:
        snap = S.snapshot()
    except S.StateError as exc:
        _say(f'STATE_UNREADABLE: {exc}')
        return 2

    cap = max_transitions if max_transitions is not None else \
        (snap.policy.get('limits') or {}).get(
            'max_transitions_per_invocation', 1)
    effective = P.resolve_mode(snap.policy, os.environ)
    _say(f'orchestrator: head {snap.head[:12]} on {snap.branch}, up to {cap} '
         f'transition(s)')
    _say(f'  mode: requested={P.requested_mode()} '
         f'policy={P.policy_mode(snap.policy)} -> EFFECTIVE={effective}')
    if P.requested_mode() == P.MODE_LIVE and effective != P.MODE_LIVE:
        # Said out loud rather than silently downgraded. An operator who asked
        # for LIVE and got MOCK must find out from the log, not from noticing
        # later that nothing was ever charged.
        _say('  LIVE was requested but the protected policy does not '
             'authorize it; running MOCK. Set autonomous_operation_enabled '
             'and execution_mode in AUTOMATION_POLICY.json to arm it.')

    used = 0
    committed_a_transition = False
    while used < cap:
        try:
            snap = S.snapshot()
        except S.StateError as exc:
            _say(f'STATE_UNREADABLE: {exc}')
            return 2
        action = D.next_action(snap, transitions_used=used,
                               require_autonomy=require_autonomy)
        _say(f'\n[{used + 1}/{cap}] {action}')
        if action.kind == D.STOP:
            if action.escalation and action.escalation not in C.BENIGN:
                _escalate(action.escalation, 'orchestration stopped',
                          action.reason, head=snap.head)
                return 4
            # A clean stop ends the chain. NOTHING_AUTHORIZED means the loop
            # reached the end of the work a human authorized, which is the
            # correct place to stop asking for more passes.
            return 0
        if plan_only:
            _say('  --plan: deciding only, nothing executed')
            return 0

        head = snap.head
        try:
            if action.kind == D.OWNER_REVIEW:
                ok, esc = do_owner_review(snap, action, head)
            else:
                ok, esc = do_execute(snap, action, head)
        except locks.Refusal as r:
            _say(f'  REFUSED {r.code}: {r.detail[:400]}')
            if r.escalation:
                _escalate(r.escalation, f'{action.task_id}: {r.code}',
                          r.detail, head=head)
                return 4
            return 0
        used += 1
        if esc:
            return 4
        if not ok:
            # A FAILED WORKER DOES NOT CHAIN. Asking for another pass after a
            # failure is how one broken task becomes an hour of broken tasks;
            # the retry budget, not the continuation, is what gives it another
            # go, and that happens on a pass a human or a schedule starts.
            return 5
        committed_a_transition = True
    _say(f'\ntransition budget of {cap} spent.')
    _continue_if_eligible(committed_a_transition)
    return 0


def _continue_if_eligible(committed_a_transition) -> None:
    """Ask GitHub for one more pass, if and only if one is warranted.

    THIS REPLACES PUSH RECURSION, WHICH DOES NOT WORK. GitHub will not start a
    workflow from a push made with GITHUB_TOKEN. repository_dispatch is one of
    the two documented exceptions, and it is the better mechanism anyway:
    continuation becomes a decision this pass makes, with its own budget and
    its own log row, rather than a side effect of having written a file.

    Four conditions, all required:
      1. this pass actually committed a transition -- otherwise there is
         nothing new for the next pass to read, and it would re-derive the
         same action and ask again, forever;
      2. the state, RE-READ, still offers a lawful next action;
      3. the continuation budget is not spent;
      4. autonomy is still enabled -- checked inside (2), so a kill switch
         flipped mid-pass stops the chain rather than being outrun.
    """
    if not committed_a_transition:
        _say('no transition was committed, so no continuation is requested: '
             'the next pass would read the same state and decide the same '
             'thing.')
        return
    try:
        snap = S.snapshot()
    except S.StateError as exc:
        _say(f'not continuing -- state unreadable: {exc}')
        return
    eligible, why = D.more_work_eligible(snap)
    if not eligible:
        _say(f'chain ends here: {why}')
        return
    try:
        locks.require_continuation_budget(snap)
    except locks.Refusal as r:
        _say(f'chain ends here: {r.code} -- {r.detail}')
        G.append_log({'actor': 'orchestrator', 'event': 'CONTINUATION_REFUSED',
                      'note': r.code})
        return

    depth = sum(1 for row in snap.log
                if row.get('event') == 'CONTINUATION_REQUESTED')
    res = G.request_continuation(why, chain_depth=depth + 1, head=snap.head)
    _say(f'continuation: {res.get("code")} '
         f'{"sent" if res.get("sent") else "NOT sent"} -- next: {why}')
    G.append_log({'actor': 'orchestrator', 'event': 'CONTINUATION_REQUESTED',
                  'note': f'{res.get("code")}: {why}'[:400],
                  'dispatch_sent': bool(res.get('sent'))})
    # The log row is itself a change, and it must reach the repository or the
    # budget it feeds is invisible to the next pass. Committed with a marker
    # so the push does not look like a transition to a reader.
    try:
        G.commit_and_push(
            f'orchestrator: request continuation [{res.get("code")}]\n\n'
            f'next action would be: {why}\n\n'
            f'Continuation is an explicit repository_dispatch, not push '
            f'recursion -- GITHUB_TOKEN pushes do not start workflows.',
            snap.head, push=os.environ.get('ORCHESTRATOR_PUSH', '1') == '1')
    except locks.Refusal as r:
        _say(f'  (continuation log not committed: {r.code})')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', action='store_true',
                    help='decide and print; execute nothing')
    ap.add_argument('--max', type=int, default=None,
                    help='override max transitions for this invocation')
    ap.add_argument('--ignore-switch', action='store_true',
                    help='for tests: proceed although autonomy is disabled')
    a = ap.parse_args(argv)
    return one_pass(max_transitions=a.max, plan_only=a.plan,
                    require_autonomy=not a.ignore_switch)


if __name__ == '__main__':
    _sys.exit(main())
