#!/usr/bin/env python3.12
"""Every reason the runtime refuses to act. Each one fails CLOSED.

WHAT THIS MODULE IS DEFENDING AGAINST, CONCRETELY

Two GitHub Actions runs fire microseconds apart on the same push. Both read
the queue, both see ENG-001 AUTHORIZED, both call a worker, both spend money,
and both commit. The task executed twice and the second commit silently
overwrote the first. Nothing in the queue's design prevents that, because a
JSON file has no notion of who is holding it.

Three mechanisms stop it here, and they are deliberately independent so that
one of them being wrong does not open the gate:

  1. WORKFLOW CONCURRENCY. GitHub cancels a second orchestrator run on the
     same branch. This is the cheapest and the least trustworthy -- it does
     not cover a manual invocation, a self-hosted runner, or a run on a
     different ref.
  2. THE EXCLUSIVE ACTIVE LOCK. At most one ACTIVE engineering task, checked
     from the committed queue. If one is ACTIVE, no new task is dispatched.
  3. THE IDEMPOTENCY KEY. Derived from (worker, model, task, prompt, HEAD,
     attempt). If a run with that key is already in HANDOFF_LOG.jsonl, the
     call is not made. This is the one that survives a race, because both
     runners derive the SAME key from the same state, and the loser's commit
     is rejected by the optimistic HEAD check below.

WHY THERE IS AN OPTIMISTIC HEAD CHECK AS WELL. Between reading state and
writing a result, another runner may have committed. Writing anyway would
clobber it. So the head observed at the start is carried through and verified
before the write; a mismatch abandons the write and lets the next event
re-derive from the new state. Losing a race costs one wasted API call. Not
detecting one costs a corrupted queue.
"""
from __future__ import annotations

import fnmatch
import re

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C
from coordination.orchestrator import state as S


class Refusal(Exception):
    """A named, non-negotiable stop. Carries an Escalation where one fits."""

    def __init__(self, code, detail, escalation=None, **evidence):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail
        self.escalation = escalation
        self.evidence = evidence


# ------------------------------------------------------------ the gates
def require_valid_state(snap) -> None:
    """A contradictory queue stops the loop. It is never reasoned past."""
    if not snap.valid:
        raise Refusal(
            'COORDINATION_INVALID',
            f'validate_coordination.py refused:\n{snap.validator_output}',
            escalation=C.Escalation.STATE_CONTRADICTORY)


def require_autonomy_enabled(snap) -> None:
    if not snap.policy.get('autonomous_operation_enabled'):
        raise Refusal(
            'AUTONOMY_DISABLED',
            'AUTOMATION_POLICY.json has autonomous_operation_enabled=false. '
            'This is the default and the kill switch; set it true to arm the '
            'loop.',
            escalation=None)


def require_live_authorized(snap, requested) -> None:
    """LIVE needs the PROTECTED POLICY to say so. Nothing else grants it.

    Called when a human explicitly asks for LIVE at startup, so the refusal
    arrives immediately and by name instead of being silently downgraded and
    discovered later from a bill that never came.
    """
    from coordination.orchestrator import providers as _P
    if requested != _P.MODE_LIVE:
        return
    if not snap.policy.get('autonomous_operation_enabled'):
        raise Refusal(
            'LIVE_NOT_AUTHORIZED',
            'LIVE was requested but AUTOMATION_POLICY.json has '
            'autonomous_operation_enabled=false. Arming is a deliberate edit '
            'to a protected file on the automation branch, not a workflow '
            'input.',
            escalation=None)
    if _P.policy_mode(snap.policy) != _P.MODE_LIVE:
        raise Refusal(
            'LIVE_NOT_AUTHORIZED',
            f'LIVE was requested but AUTOMATION_POLICY.json has '
            f'execution_mode='
            f'{snap.policy.get("execution_mode", "(absent)")!r}. Both fields '
            f'must say so; an absent field reads as MOCK, because the whole '
            f'point of a committed policy is that spending requires someone '
            f'to have written the word LIVE into it.',
            escalation=None)


def require_secret(env: dict, name: str, worker) -> str:
    """A missing key STOPS. It is never worked around with a mock.

    Silently falling back to a mock when a real key is absent would produce a
    fabricated return that looks exactly like a real one, which is the single
    worst outcome this runtime can produce.
    """
    val = (env.get(name) or '').strip()
    if not val:
        raise Refusal(
            'SECRET_MISSING',
            f'{name} is not set, so the {worker.value} worker cannot be '
            f'called. See coordination/AUTONOMY_SETUP.md. The runtime will '
            f'not substitute a mock for a missing key.',
            escalation=C.Escalation.SECRET_MISSING, secret=name)
    return val


def require_branch_allowed(snap) -> None:
    bp = snap.policy.get('branch_policy') or {}
    protected = tuple(bp.get('protected_branches') or ())
    if snap.branch in protected and not bp.get('may_push_to_default_branch'):
        raise Refusal(
            'BRANCH_PROTECTED',
            f'{snap.branch} is a protected branch and '
            f'may_push_to_default_branch is false. Autonomous commits go to '
            f'{bp.get("automation_branch")!r}.',
            escalation=C.Escalation.DESTRUCTIVE_ACTION_REQUIRED,
            branch=snap.branch)


def require_rate_budget(snap) -> None:
    cap = (snap.policy.get('limits') or {}).get('max_runs_per_hour')
    if cap is None:
        raise Refusal('POLICY_INCOMPLETE',
                      'limits.max_runs_per_hour is absent; an absent limit is '
                      'not an unlimited one.',
                      escalation=C.Escalation.STATE_CONTRADICTORY)
    used = snap.runs_in_last_hour()
    if used >= cap:
        raise Refusal(
            'RATE_LIMIT', f'{used} run(s) in the last hour against a cap of '
                          f'{cap}.',
            escalation=C.Escalation.COST_LIMIT_REACHED, used=used, cap=cap)


def require_exclusive_active(snap, task_id) -> None:
    """At most one ACTIVE engineering task, and it must be this one."""
    act = snap.active('ENGINEERING_QUEUE.json')
    ids = [t['task_id'] for _n, t in act]
    if len(ids) > 1:
        raise Refusal(
            'EXCLUSIVE_ACTIVE_VIOLATED',
            f'{ids} are all ACTIVE. Exactly one engineering task may hold the '
            f'lock; two means a previous run did not finish cleanly and the '
            f'state needs a human.',
            escalation=C.Escalation.STATE_CONTRADICTORY, active=ids)
    if ids and ids[0] != task_id:
        raise Refusal(
            'LOCK_HELD', f'{ids[0]} is ACTIVE, so {task_id} may not start.',
            escalation=None, holder=ids[0])


def require_retry_budget(snap, task_id) -> None:
    lim = (snap.policy.get('limits') or {}).get('max_retries_per_task', 0)
    n = snap.attempts(task_id)
    # `attempts` counts dispatches; the first is not a retry.
    if n > lim:
        raise Refusal(
            'RETRY_BUDGET_SPENT',
            f'{task_id} has been dispatched {n} time(s) against a retry limit '
            f'of {lim}. Something about this task is not working and another '
            f'attempt is unlikely to be the answer.',
            escalation=C.Escalation.REPEATED_AGENT_FAILURE,
            task_id=task_id, attempts=n, limit=lim)


def require_not_duplicate(snap, call) -> None:
    """The same call, in the same state, is not made twice."""
    if call.idempotency_key in snap.idempotency_keys():
        raise Refusal(
            'DUPLICATE_RUN',
            f'a run with idempotency key {call.idempotency_key} is already in '
            f'HANDOFF_LOG.jsonl. Two workflows raced, or an event was '
            f'redelivered; either way the work is already done.',
            escalation=None, key=call.idempotency_key)


def require_head_unmoved(observed_head: str) -> None:
    """Optimistic concurrency. Lose the race rather than clobber the winner."""
    now = S.head()
    if now != observed_head:
        raise Refusal(
            'HEAD_MOVED',
            f'HEAD was {observed_head[:12]} when this pass began and is now '
            f'{now[:12]}. Another runner committed first. Abandoning this '
            f'write; the next event will re-derive from the new state.',
            escalation=None, observed=observed_head, actual=now)


def require_continuation_budget(snap) -> None:
    """Bound the dispatch chain, from the LOG rather than from the payload.

    The continuation payload carries a chain depth, and it would be easier to
    enforce on that. It would also be wrong: the depth is chosen by the sender,
    and the sender is the thing being bounded. Counting committed log rows
    means two runners that race, or a redelivered dispatch, see the same
    number -- and means the bound survives a payload nobody validated.
    """
    import datetime as _dt
    cap = (snap.policy.get('limits') or {}).get(
        'max_continuations_per_hour')
    if cap is None:
        raise Refusal('POLICY_INCOMPLETE',
                      'limits.max_continuations_per_hour is absent; an absent '
                      'limit is not an unlimited one.',
                      escalation=C.Escalation.STATE_CONTRADICTORY)
    cut = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)
    n = 0
    for row in snap.log:
        if row.get('event') != 'CONTINUATION_REQUESTED':
            continue
        try:
            when = _dt.datetime.fromisoformat(
                str(row.get('timestamp')).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue
        if when >= cut:
            n += 1
    if n >= cap:
        raise Refusal(
            'CONTINUATION_BUDGET_SPENT',
            f'{n} continuation(s) requested in the last hour against a cap of '
            f'{cap}. The chain stops here; a human or the next scheduled '
            f'event restarts it.',
            escalation=C.Escalation.COST_LIMIT_REACHED, used=n, cap=cap)


def require_token_budget(snap, spent: int, per: str) -> None:
    cap = (snap.policy.get('limits') or {}).get(per)
    if cap is not None and spent >= cap:
        raise Refusal(
            'TOKEN_BUDGET_SPENT',
            f'{spent} token(s) against {per}={cap}.',
            escalation=C.Escalation.COST_LIMIT_REACHED, spent=spent, cap=cap)


# ----------------------------------------------- what a worker may write
def _match(path: str, pattern: str) -> bool:
    return path == pattern or path.startswith(pattern.rstrip('/') + '/') \
        or fnmatch.fnmatch(path, pattern)


def enforce_protected_paths(changed, worker) -> None:
    """Refuse a diff that touches a path the worker may not write.

    CHECKED AGAINST THE DIFF, NOT AGAINST THE MODEL'S CLAIM. A worker that is
    asked "did you modify the governance gate?" can answer no and be wrong,
    or answer no and be lying, and there is no way to tell them apart. The
    diff cannot do either.
    """
    forbidden = list(C.PROTECTED_PATHS)
    if worker is C.Worker.ENGINEER:
        forbidden += list(C.ENGINEER_FORBIDDEN_PATHS)
    hits = sorted({p for p in changed
                   for f in forbidden if _match(p, f)})
    if hits:
        raise Refusal(
            'PROTECTED_PATH_WRITTEN',
            f'the {worker.value} worker modified {hits}, which it may not. '
            f'The change is refused whole -- a partial apply would leave the '
            f'repository in a state no review covered.',
            escalation=C.Escalation.GOVERNANCE_CONFLICT, paths=hits)


#: Phrases that, appearing in a worker's PROPOSED state change, mean it has
#: reached for a decision reserved to the owner. Matched on the worker's
#: structured output, never used as the only control -- the mechanical checks
#: above are what actually hold.
_RESERVED_RE = re.compile(
    r'\b(promote\s+q9|q9[_\s-]*promot|authorize\s+nfl-1|nfl-1\s+authoriz'
    r'|v2\s+(is\s+)?earned|declare\s+v2|enable\s+real[_\s-]*money'
    r'|weekly[_\s-]*exposure[_\s-]*cap)\b', re.I)


def enforce_reserved_decisions(proposal: str, who) -> None:
    hit = _RESERVED_RE.search(proposal or '')
    if hit:
        raise Refusal(
            'RESERVED_DECISION_ATTEMPTED',
            f'the {who} worker proposed {hit.group(0)!r}. That decision is '
            f'reserved to the owner and no model output can make it. The '
            f'proposal is recorded and the loop stops.',
            escalation=C.Escalation.OWNER_DECISION_REQUIRED,
            matched=hit.group(0))


def enforce_owner_decisions_intact(before: str, after: str) -> None:
    """An owner decision may be APPENDED to. It may never be removed."""
    ids_before = set(re.findall(r'^#+\s*(D-\d+)', before, re.M))
    ids_after = set(re.findall(r'^#+\s*(D-\d+)', after, re.M))
    lost = sorted(ids_before - ids_after)
    if lost:
        raise Refusal(
            'OWNER_DECISION_REMOVED',
            f'{lost} disappeared from OWNER_DECISIONS.md. Decisions are '
            f'appended to and superseded in place, never deleted -- the '
            f'struck-through record is the useful one.',
            escalation=C.Escalation.GOVERNANCE_CONFLICT, lost=lost)


def enforce_bounded_task(task: dict) -> None:
    """A newly created task must be bounded before anything may run it."""
    missing = [k for k in ('task_id', 'title', 'objective', 'acceptance_tests')
               if not task.get(k)]
    if missing:
        raise Refusal(
            'TASK_NOT_BOUNDED',
            f'a proposed task lacks {missing}. A task without an objective '
            f'and acceptance tests cannot be judged done, so it cannot be '
            f'authorized.',
            escalation=C.Escalation.OWNER_DECISION_REQUIRED, missing=missing)
    if not isinstance(task.get('acceptance_tests'), list) \
            or not task['acceptance_tests']:
        raise Refusal(
            'TASK_NOT_BOUNDED',
            'acceptance_tests must be a non-empty list.',
            escalation=C.Escalation.OWNER_DECISION_REQUIRED)
