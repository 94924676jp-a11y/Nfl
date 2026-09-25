#!/usr/bin/env python3.12
"""The loop: read the approval queue, park that branch, take the next task.

    python3.12 nfl/tools/autonomy.py state        # the derived summary
    python3.12 nfl/tools/autonomy.py next         # highest-priority authorized
    python3.12 nfl/tools/autonomy.py queue        # open work, severity order
    python3.12 nfl/tools/autonomy.py approvals    # the owner's queue
    python3.12 nfl/tools/autonomy.py escalations  # what earns an interruption
    python3.12 nfl/tools/autonomy.py mark-escalated APPROVAL-001

The whole operating rule, as code rather than as a habit:

    if a task needs approval and approval is absent:
        mark ONLY that branch WAITING_OWNER, set it aside
    take the next highest-priority authorized task
    repeat until there is literally no authorized work left

`state` prints `global_stop_required`, which is computed from counts. While
`valid_next_actions` is above zero, stopping is a choice and not a state.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve()
                       .parents[2]))

from nfl.governance import ledgers as L                        # noqa: E402


def _fmt(d: dict) -> str:
    return (f"  {d['id']:<9} {d['severity']:<8} {d['subsystem']:<14} "
            f"{d['status']:<16} {d['defect'][:74]}")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else 'state'
    rows, apps = L.defects(), L.approvals()

    if cmd == 'state':
        s = L.write_state()
        print(json.dumps({k: v for k, v in s.items()
                          if k not in ('reading',)}, indent=1, sort_keys=True))
        if not s['global_stop_required']:
            print(f"\n-> authorized work remains ({s['valid_next_actions']}); "
                  f"next is {s['next_action']}")
        else:
            print('\n-> STOP: ' + '; '.join(s['global_stop_reasons']))
        return 0

    if cmd == 'next':
        n = L.next_action(rows)
        if not n:
            print('no authorized task available')
            return 0
        print(f"{n['id']}  [{n['severity']}] {n['subsystem']}")
        print(f"  defect        {n['defect']}")
        print(f"  reproduction  {n['reproduction']}")
        print(f"  next action   {n['next_action']}")
        print(f"  affected      {n['affected']}")
        if n['prospective_validation_needed']:
            print('  NOTE          prospective validation required before '
                  'this counts as an improvement')
        return 0

    if cmd == 'queue':
        for d in L.actionable(rows):
            print(_fmt(d))
        parked = [d for d in rows if d['status'] in
                  (L.WAITING_OWNER, L.EXTERNAL_BLOCKED)]
        if parked:
            print('\nparked (does NOT stop other work):')
            for d in parked:
                print(_fmt(d) + f"   <- {d['blocked_by']}")
        return 0

    if cmd == 'approvals':
        for a in apps:
            blocked = L.blocked_by(a['id'], rows)
            print(f"{a['id']}  {a['status']}  urgency={a['urgency']}"
                  + (f"  deadline={a['deadline']}" if a.get('deadline') else ''))
            print(f"  {a['decision_required']}")
            print(f"  why owner      {a['why_owner_approval']}")
            print(f"  options        {' | '.join(a['options'])}")
            print(f"  recommended    {a['recommended_default']}")
            print(f"  blocks         {blocked or 'nothing'}")
            print(f"  continues      {a['work_that_continues_regardless']}\n")
        return 0

    if cmd == 'escalations':
        due = [(a, L.should_escalate(a, rows)) for a in apps]
        due = [(a, r) for a, r in due if r]
        if not due:
            print('nothing earns an interruption. Open approvals wait in the '
                  'queue; "still open" is not a reason to ping.')
            return 0
        for a, r in due:
            print(f"{a['id']}: {r}")
        return 0

    if cmd == 'mark-escalated':
        if len(argv) < 2:
            print('usage: mark-escalated <APPROVAL-ID>')
            return 2
        target = argv[1]
        for a in apps:
            if a['id'] == target:
                a['last_escalated_at'] = dt.datetime.now(
                    dt.timezone.utc).isoformat()
                a['blocked_ids_at_last_escalation'] = L.blocked_by(
                    target, rows)
                L._write(L.APPROVAL_QUEUE, apps)
                print(f'{target} marked escalated; it will not be raised '
                      f'again unless urgency changes, a deadline nears, more '
                      f'work becomes blocked by it, or it is the last blocker')
                return 0
        print(f'{target} not found')
        return 2

    print(__doc__)
    return 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # `autonomy.py queue | head` is the normal way to read this. Without
        # this the tool dies with a traceback on a perfectly good invocation.
        import os
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise SystemExit(0)
