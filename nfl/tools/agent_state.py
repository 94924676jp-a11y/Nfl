#!/usr/bin/env python3.12
"""Generate `nfl/AGENT_STATE.json` and `nfl/HANDOFF.md` from repository state.

    python3.12 nfl/tools/agent_state.py            # print, write nothing
    python3.12 nfl/tools/agent_state.py --write    # write both files

WHY THIS IS A GENERATOR AND NOT THREE HAND-KEPT FILES

`nfl/WORK_QUEUE.md` is the only hand-authored one of the three, because item
text, priority, dependency and acceptance criteria are decisions rather than
measurements. Everything else here -- the HEAD, the branch, the dirty paths,
the queue positions, the last suite classification, the next eligible items --
is read from git and from artifacts on disk at the moment of generation.

The alternative was three prose files maintained in parallel. That is the same
defect P7 exists to repair: two independent statements of one truth drift, and
the drift is invisible until someone reads both. If a number in AGENT_STATE is
wrong here, it is wrong because the repository is in that state, which is a
useful thing for it to be wrong about.

WHAT IT REFUSES

A queue item whose status is not in the declared vocabulary, and a `BLOCKED`
item that states no blocker. A blocked item with no named blocker is how
"blocked" becomes a place work goes to stop being looked at.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import pathlib
import re
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
QUEUE = _REPO / 'nfl' / 'WORK_QUEUE.md'
STATE = _REPO / 'nfl' / 'AGENT_STATE.json'
HANDOFF = _REPO / 'nfl' / 'HANDOFF.md'

STATUSES = ('QUEUED', 'ACTIVE', 'BLOCKED', 'DONE', 'SUPERSEDED')
GENERATOR = 'nfl/tools/agent_state.py'


class QueueError(RuntimeError):
    pass


def _git(*args) -> str:
    try:
        return subprocess.run(['git'] + list(args), cwd=_REPO,
                              capture_output=True, text=True,
                              timeout=60).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return ''


def parse_queue(path=None) -> list:
    """The queue items, in file order, with their declared fields."""
    path = pathlib.Path(path or QUEUE)
    if not path.exists():
        raise QueueError(f'QUEUE_MISSING: {path}')
    items, cur, field, in_ac = [], None, None, False
    for line in path.read_text().splitlines():
        m = re.match(r'^## ID:\s*(\S+)\s*$', line)
        if m:
            cur = {'id': m.group(1), 'acceptance_criteria': []}
            items.append(cur)
            field, in_ac = None, False
            continue
        if cur is None:
            continue
        # `[\w ]+` because the field is written `**acceptance criteria**`,
        # with a space. A `\w+` pattern silently did not match it, so the
        # criteria fell through to the continuation branch and were glued onto
        # `blocker`. The queue file read correctly and the generated state did
        # not, which is the failure mode this generator exists to remove.
        m = re.match(r'^-\s+\*\*([\w ]+)\*\*:\s*(.*)$', line)
        if m:
            field, val = m.group(1).strip().replace(' ', '_'), m.group(2).strip()
            if field in ('acceptance_criteria', 'acceptance'):
                field, in_ac = 'acceptance_criteria', True
                continue
            in_ac = False
            cur[field] = val
            continue
        m = re.match(r'^\s+-\s+(.*)$', line)
        if m and in_ac:
            cur['acceptance_criteria'].append(m.group(1).strip())
            continue
        if not line.strip():
            continue
        # A CONTINUATION LINE BELONGS TO WHAT IT CONTINUES, not to whatever
        # field was set last. A first version appended every indented line to
        # `field`, so the tail of the last acceptance bullet ended up glued
        # onto `blocker` -- a blocker that read as a sentence about a sample
        # size. Wrong text in a blocker is worse than no text.
        if line.startswith('  '):
            if in_ac and cur['acceptance_criteria']:
                cur['acceptance_criteria'][-1] += ' ' + line.strip()
            elif field:
                cur[field] = (cur.get(field, '') + ' ' + line.strip()).strip()
    for it in items:
        it['acceptance_criteria'] = [
            re.sub(r'\s+', ' ', c).strip().rstrip(';') for c in
            it['acceptance_criteria']]
    bad = [i for i in items if i.get('status') not in STATUSES]
    if bad:
        raise QueueError(
            f'QUEUE_STATUS_UNKNOWN: {[(i["id"], i.get("status")) for i in bad]}'
            f' -- the vocabulary is {STATUSES}')
    silent = [i['id'] for i in items
              if i.get('status') == 'BLOCKED'
              and (i.get('blocker') or '').strip().lower() in ('', 'none')]
    if silent:
        raise QueueError(
            f'BLOCKED_WITHOUT_BLOCKER: {silent} -- a blocked item that names '
            f'no blocker is where work goes to stop being looked at.')
    return items


def last_suite_classification() -> dict:
    """The newest suite attribution artifact, read rather than recalled."""
    fs = sorted(glob.glob(str(
        _REPO / 'nfl' / 'research' / 'suite_attribution'
        / 'SUITE_ATTRIBUTION_*.json')))
    if not fs:
        return {'artifact': None,
                'note': 'no suite attribution artifact on disk'}
    p = pathlib.Path(fs[-1])
    d = json.loads(p.read_text())
    rows = d.get('rows') or []
    counts: dict = {}
    for r in rows:
        counts[r.get('classification', '?')] = counts.get(
            r.get('classification', '?'), 0) + 1
    return {'artifact': str(p.relative_to(_REPO)),
            'baseline': d.get('baseline_commit') or d.get('baseline'),
            'current': d.get('current_commit') or d.get('current'),
            'totals': d.get('totals'),
            'classification_counts': counts}


def build(path=None) -> dict:
    items = parse_queue(path)
    by_status: dict = {}
    for i, it in enumerate(items):
        it['queue_position'] = i + 1
        by_status.setdefault(it['status'], []).append(it['id'])
    active = [it for it in items if it['status'] == 'ACTIVE']
    eligible = [it['id'] for it in items if it['status'] == 'QUEUED']
    # `XY PATH`: the code is two columns wide and either may be blank,
    # so the path starts after column 2 and is found by stripping, not
    # by a fixed slice. A fixed [3:] ate the first character of a path
    # whose code was `M ` rather than ` M`.
    dirty = [ln[2:].strip() for ln in
             _git('status', '--porcelain').splitlines() if ln.strip()]
    return {
        'generated_by': GENERATOR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'git': {
            'head': _git('rev-parse', 'HEAD'),
            'head_short': _git('rev-parse', '--short', 'HEAD'),
            'branch': _git('rev-parse', '--abbrev-ref', 'HEAD'),
            'head_subject': _git('log', '-1', '--pretty=%s'),
            'remote_head': _git('rev-parse', '--short',
                                '@{upstream}') or 'NO_UPSTREAM',
            'dirty_paths': dirty,
            'is_clean': not dirty,
        },
        'active_task': (active[0]['id'] if active else None),
        'active_task_position': (active[0]['queue_position']
                                 if active else None),
        'n_active': len(active),
        'last_completed_task': (by_status.get('DONE') or [None])[-1],
        'queue': [{k: v for k, v in it.items()} for it in items],
        'queue_by_status': by_status,
        'unresolved_blockers': [
            {'id': it['id'], 'blocker': it.get('blocker')}
            for it in items if it['status'] == 'BLOCKED'],
        'next_three_eligible': eligible[:3],
        'most_recent_suite_classification': last_suite_classification(),
        'production_impact': {
            'real_money': 'NOT ENABLED',
            'v2_status': 'NOT YET EARNED',
            'note': 'No change in this session has been promoted to a '
                    'production forecast path. Read this field from the '
                    'commit under review, never from this line alone.',
        },
    }


def handoff(state: dict) -> str:
    g = state['git']
    act = next((q for q in state['queue']
                if q['id'] == state['active_task']), None)
    blockers = state['unresolved_blockers']
    lines = [
        '# HANDOFF',
        '',
        f'Generated by `{GENERATOR}` at {state["generated_at"]}. '
        f'Do not hand-edit: regenerate.',
        '',
        '## Current objective',
        '',
        'Produce NFL player-prop and DFS forecasts that discriminate between '
        'games materially better than the current baseline, with honest '
        'calibration and a fully auditable research process. Market data may '
        'evaluate a forecast and may never feed one. **V2 NOT YET EARNED.**',
        '',
        '## Where the repository is',
        '',
        f'- branch `{g["branch"]}` at `{g["head_short"]}` — {g["head_subject"]}',
        f'- working tree: '
        + ('clean' if g['is_clean']
           else f'{len(g["dirty_paths"])} uncommitted path(s): '
                + ', '.join(g['dirty_paths'][:8])),
        '',
        '## Active task',
        '',
    ]
    if act:
        lines += [f'**{act["id"]}** (queue position {act["queue_position"]}) '
                  f'— {act.get("description", "")}', '']
        if act.get('acceptance_criteria'):
            lines.append('Acceptance criteria not yet all met:')
            lines += [f'- {c}' for c in act['acceptance_criteria']]
            lines.append('')
    else:
        lines += ['None marked ACTIVE. Select the highest-priority `QUEUED` '
                  'item.', '']
    lines += [
        '## Exact next action',
        '',
        f'Select `{(state["next_three_eligible"] or ["<none eligible>"])[0]}`'
        if not act else
        f'Finish `{act["id"]}`, then select '
        f'`{(state["next_three_eligible"] or ["<none eligible>"])[0]}`.',
        '',
        '## Blockers',
        '',
    ]
    lines += ([f'- **{b["id"]}**: {b["blocker"]}' for b in blockers]
              or ['- none'])
    lines += [
        '',
        '## Commands to resume',
        '',
        '```',
        'cd /home/user/nfl',
        'git log --oneline -3',
        'python3.12 nfl/tools/agent_state.py --write   # refresh this file',
        'python3.12 nfl/tests/run_suite.py             # full suite, ~45 min',
        'python3.12 nfl/production/pipeline.py --audit-reads',
        '```',
        '',
        'Write files through `cat <<\'EOF\' | python3.12 nfl/tools/nflwrite.py '
        '<path>`; it refuses a write outside this repository. `python3.12` '
        'only. Stage selectively, never a broad `git add`.',
        '',
    ]
    return '\n'.join(lines)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    state = build()
    if '--write' in argv:
        STATE.write_text(json.dumps(state, indent=1) + '\n')
        HANDOFF.write_text(handoff(state))
        print(f'wrote {STATE.relative_to(_REPO)} and '
              f'{HANDOFF.relative_to(_REPO)}')
    else:
        print(json.dumps(state, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
