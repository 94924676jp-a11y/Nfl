#!/usr/bin/env python3.12
"""Decide the ONE next action from repository state. Decides; never acts.

The event loop is a function of state, not a script. Given a snapshot this
module returns a single `Action` saying what should happen and why, and
`main.py` carries it out. Separating them is what makes the state machine
testable without a provider, a network or a commit -- the whole mocked suite
in `test_orchestrator.py` drives THIS function and asserts on its answers.

PRECEDENCE, AND WHY IT IS THIS ORDER

  1. state invalid            -> stop. Never reason past a contradiction.
  2. autonomy disabled        -> stop. The default and the kill switch.
  3. budget spent             -> stop.
  4. a RETURNED task exists   -> OWNER REVIEW. Reviewing finished work comes
                                 before starting more, because unreviewed
                                 returns are the thing that piles up.
  5. an ACTIVE task exists    -> continue THAT task. One at a time.
  6. an executable task       -> route by queue and dispatch it.
  7. otherwise                -> stop, NOTHING_AUTHORIZED. A clean finish.

Point 4 above the others is deliberate. A loop that always prefers new work
accumulates a backlog of unjudged returns and eventually authorizes its next
task on the strength of work nobody checked.
"""
from __future__ import annotations

import dataclasses

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C
from coordination.orchestrator import locks


@dataclasses.dataclass
class Action:
    """What to do next, and the reason, in one object."""

    kind: str                      # see KINDS below
    reason: str
    worker: C.Worker | None = None
    queue_name: str | None = None
    task: dict | None = None
    escalation: C.Escalation | None = None
    prior_return: str | None = None

    @property
    def task_id(self):
        return (self.task or {}).get('task_id')

    def __str__(self):
        t = f' {self.task_id}' if self.task else ''
        w = f' via {self.worker.value}' if self.worker else ''
        e = f' [{self.escalation.value}]' if self.escalation else ''
        return f'{self.kind}{t}{w}{e}: {self.reason}'


STOP = 'STOP'
OWNER_REVIEW = 'OWNER_REVIEW'
EXECUTE = 'EXECUTE'
KINDS = (STOP, OWNER_REVIEW, EXECUTE)


def _stop(reason, escalation=None):
    return Action(kind=STOP, reason=reason, escalation=escalation)


def next_action(snap, *, transitions_used=0, require_autonomy=True) -> Action:
    """The single next action. Pure: reads the snapshot, writes nothing."""
    # ---- 1. a contradictory state is never reasoned past -----------------
    try:
        locks.require_valid_state(snap)
    except locks.Refusal as r:
        return _stop(r.detail, r.escalation)

    # ---- 2. the kill switch ---------------------------------------------
    if require_autonomy:
        try:
            locks.require_autonomy_enabled(snap)
        except locks.Refusal as r:
            return _stop(r.detail, r.escalation)

    # ---- 3. budgets ------------------------------------------------------
    limits = snap.policy.get('limits') or {}
    cap = limits.get('max_transitions_per_invocation', 1)
    if transitions_used >= cap:
        return _stop(
            f'{transitions_used} transition(s) used against a cap of {cap}. '
            f'Stopping cleanly; the next GitHub event continues the state '
            f'machine from here.',
            C.Escalation.TRANSITION_BUDGET_SPENT)
    try:
        locks.require_rate_budget(snap)
        locks.require_branch_allowed(snap)
    except locks.Refusal as r:
        return _stop(r.detail, r.escalation)

    # ---- 4. unreviewed returns come first --------------------------------
    returned = snap.returned()
    if returned:
        qname, task = returned[0]
        return Action(kind=OWNER_REVIEW, worker=C.Worker.OWNER,
                      queue_name=qname, task=task,
                      reason=f'{task["task_id"]} is RETURNED and awaiting an '
                             f'owner verdict. Unreviewed work is judged '
                             f'before new work is started.')

    # ---- 5. one ACTIVE task at a time ------------------------------------
    active = snap.active()
    if len(active) > 1:
        ids = [t['task_id'] for _n, t in active]
        return _stop(f'{ids} are all ACTIVE. Exactly one task may hold the '
                     f'lock; two means a prior run did not finish cleanly.',
                     C.Escalation.STATE_CONTRADICTORY)
    if active:
        qname, task = active[0]
        worker = C.ROUTING[qname]
        try:
            locks.require_retry_budget(snap, task['task_id'])
        except locks.Refusal as r:
            return _stop(r.detail, r.escalation)
        return Action(kind=EXECUTE, worker=worker, queue_name=qname,
                      task=task,
                      reason=f'{task["task_id"]} is already ACTIVE; a pass '
                             f'resumes the task in flight rather than '
                             f'starting another.',
                      prior_return=_prior_return(qname, task))

    # ---- 6. select and route ---------------------------------------------
    runnable = snap.executable()
    if not runnable:
        return _stop(
            'No task is AUTHORIZED with its dependencies satisfied. That is '
            'a correct outcome, not a failure: the loop has reached the end '
            'of the work a human has authorized.',
            C.Escalation.NOTHING_AUTHORIZED)

    qname, task = runnable[0]
    worker = C.ROUTING[qname]
    for gate in (lambda: locks.require_exclusive_active(snap,
                                                        task['task_id']),
                 lambda: locks.require_retry_budget(snap, task['task_id'])):
        try:
            gate()
        except locks.Refusal as r:
            return _stop(r.detail, r.escalation)

    return Action(kind=EXECUTE, worker=worker, queue_name=qname, task=task,
                  reason=f'{task["task_id"]} is the highest-priority '
                         f'authorized executable task (priority '
                         f'{task.get("priority")}), routed to '
                         f'{worker.value} by its queue.',
                  prior_return=_prior_return(qname, task))


def _prior_return(queue_name, task):
    """The previous return, when this is a correction round.

    Passed to the worker so a correction can see the criticism it is
    answering. Without it a second attempt is a first attempt with a different
    random seed.
    """
    from coordination.orchestrator import state as S
    p = S.RETURNS[queue_name] / f'{task["task_id"]}.md'
    return p.read_text() if p.exists() else None


def task_branch(task_id: str) -> str:
    """The branch name a per-task branch policy would use."""
    return f'agent/{task_id.lower()}'


def summarize_queues(snap) -> str:
    """A compact queue view for the owner worker's prompt."""
    lines = []
    for name, q in sorted(snap.queues.items()):
        lines.append(f'## {name}')
        for t in q.get('tasks') or []:
            lines.append(
                f'  {t.get("task_id"):<10} {t.get("status"):<11} '
                f'p{t.get("priority"):<4} auth={str(t.get("authorized")):<5} '
                f'deps={t.get("depends_on") or []} :: {t.get("title", "")}')
    return '\n'.join(lines)


if __name__ == '__main__':
    import sys
    from coordination.orchestrator import state as S
    try:
        snap = S.snapshot()
    except S.StateError as exc:
        print(f'STATE_UNREADABLE: {exc}')
        sys.exit(2)
    a = next_action(snap, require_autonomy=('--ignore-switch' not in sys.argv))
    print(a)
    sys.exit(0 if a.kind != STOP else 3)
