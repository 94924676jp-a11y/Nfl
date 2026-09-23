#!/usr/bin/env python3.12
"""Select the ONE engineering task Claude is allowed to execute next.

    python3.12 coordination/claude_dispatch.py            # select and claim
    python3.12 coordination/claude_dispatch.py --dry-run  # select, claim nothing

THERE IS NO FREEFORM NEXT-TASK SELECTION. An agent that picks its own next
piece of work drifts toward whatever is interesting, and this project has
three partially-implemented foundational workstreams in its history to show
for it. The queue decides; this script reads the queue.

IT FAILS CLOSED, EVERY TIME:

  malformed or invalid coordination  -> refuse, exit 2
  a task already ACTIVE              -> return THAT task, claim nothing
  no task authorized and unblocked   -> refuse, exit 3
  a required owner directive absent  -> refuse, exit 4

Refusing is a correct outcome. An agent that is told "nothing is authorized"
and stops has behaved properly; one that finds something to do anyway has not.

THIS IS NOT A SECOND SOURCE OF TRUTH. It reads ENGINEERING_QUEUE.json, writes
back the one field it is allowed to change (`status`), and appends one line to
HANDOFF_LOG.jsonl. It never edits OWNER_DECISIONS.md, never authorizes a task,
and never invents one.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import datetime as dt

HERE = pathlib.Path(__file__).resolve().parent
QUEUE = HERE / 'ENGINEERING_QUEUE.json'
LOG = HERE / 'HANDOFF_LOG.jsonl'
OUTBOX = HERE / 'CHATGPT_OUTBOX'
DONE = ('RETURNED', 'COMPLETE', 'SUPERSEDED')


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _refuse(code, msg, exit_code):
    print(f'DISPATCH_REFUSED {code}\n\n  {msg}')
    return exit_code


def _validate():
    r = subprocess.run(('python3.12', str(HERE / 'validate_coordination.py')),
                       capture_output=True, text=True)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def _directive_present(task) -> tuple:
    """Some tasks may not start until an owner directive exists on disk.

    A task declares this with `requires_directive: "<filename-fragment>"`.
    Absence is a REFUSAL, not a shrug: the point of the field is that the
    work is not authorized by the queue row alone.
    """
    frag = task.get('requires_directive')
    if not frag:
        return True, None
    if not OUTBOX.exists():
        return False, f'{OUTBOX} does not exist'
    hits = [p.name for p in sorted(OUTBOX.glob('*.md'))
            if frag.lower() in p.name.lower()]
    return bool(hits), (hits[0] if hits else
                        f'no file in CHATGPT_OUTBOX/ matching {frag!r}')


def main():
    dry = '--dry-run' in sys.argv

    rc, out = _validate()
    if rc != 0:
        return _refuse('COORDINATION_INVALID',
                       'validate_coordination.py refuses the current state, '
                       'so nothing may be dispatched. Fix the coordination '
                       f'defect first.\n\n{out.strip()}', 2)
    try:
        q = json.loads(QUEUE.read_text())
    except Exception as e:                                   # noqa: BLE001
        return _refuse('QUEUE_UNREADABLE', f'{QUEUE}: {e}', 2)

    tasks = q.get('tasks') or []
    by_id = {t['task_id']: t for t in tasks}

    # ALREADY CLAIMED. Report it and change nothing -- re-running dispatch
    # must be safe, and a second ACTIVE task is exactly what the queue's
    # exclusive_active flag exists to prevent.
    active = [t for t in tasks if t.get('status') == 'ACTIVE']
    if active:
        t = active[0]
        print(f'DISPATCH_ALREADY_ACTIVE {t["task_id"]}\n')
        _print_task(t)
        print('\n  Nothing was claimed. Finish or release this task first:\n'
              f'    python3.12 coordination/claude_finalize.py '
              f'{t["task_id"]} <sha> coordination/CLAUDE_RETURNS/'
              f'{t["task_id"]}.md')
        return 0

    ready, why_not = [], []
    for t in sorted(tasks, key=lambda x: x.get('priority', 10 ** 6)):
        tid = t['task_id']
        if t.get('status') in DONE:
            continue
        if t.get('authorized') is not True or t.get('status') != 'AUTHORIZED':
            why_not.append(f'{tid}: authorized={t.get("authorized")!r} '
                           f'status={t.get("status")!r}')
            continue
        unmet = [d for d in (t.get('depends_on') or ())
                 if (by_id.get(d) or {}).get('status') not in DONE]
        if unmet:
            why_not.append(f'{tid}: waiting on {unmet}')
            continue
        okd, detail = _directive_present(t)
        if not okd:
            why_not.append(f'{tid}: {detail}')
            continue
        ready.append((t, detail))

    if not ready:
        return _refuse(
            'NO_TASK_AUTHORIZED',
            'no engineering task is both authorized and unblocked. This is a '
            'correct outcome and the right response is to stop, not to find '
            'something to do.\n\n  ' + '\n  '.join(why_not[:12]), 3)

    task, directive = ready[0]
    if dry:
        print(f'DISPATCH_DRY_RUN {task["task_id"]}\n')
        _print_task(task, directive)
        return 0

    prev = task['status']
    task['status'] = 'ACTIVE'
    QUEUE.write_text(json.dumps(q, indent=1) + '\n')
    with LOG.open('a') as fh:
        fh.write(json.dumps({
            'timestamp': _now(), 'actor': 'claude',
            'task_id': task['task_id'], 'from_status': prev,
            'to_status': 'ACTIVE',
            'artifact_path': f'coordination/CLAUDE_RETURNS/'
                             f'{task["task_id"]}.md',
            'note': 'claimed by claude_dispatch.py'}) + '\n')

    rc, out = _validate()
    if rc != 0:                                              # pragma: no cover
        return _refuse('CLAIM_BROKE_VALIDATION',
                       'the claim left coordination invalid; revert it.\n\n'
                       + out.strip(), 2)

    print(f'DISPATCH_CLAIMED {task["task_id"]}\n')
    _print_task(task, directive)
    print('\n  When finished:\n'
          f'    python3.12 coordination/claude_finalize.py '
          f'{task["task_id"]} <commit-sha> '
          f'coordination/CLAUDE_RETURNS/{task["task_id"]}.md')
    return 0


def _print_task(t, directive=None):
    print(f'  {t["task_id"]}  priority {t.get("priority")}  '
          f'{t.get("title")}')
    print(f'\n  OBJECTIVE\n    {t.get("objective")}')
    print('\n  ACCEPTANCE TESTS')
    for a in t.get('acceptance_tests') or ():
        print(f'    - {a}')
    for k in ('caution', 'note', 'constraint', 'evidence', 'blocks'):
        if t.get(k):
            print(f'\n  {k.upper()}\n    {t[k]}')
    if directive:
        print(f'\n  OWNER DIRECTIVE\n    CHATGPT_OUTBOX/{directive}')
    print(f'\n  RETURN TO\n    coordination/CLAUDE_RETURNS/'
          f'{t["task_id"]}.md')


if __name__ == '__main__':
    sys.exit(main())
