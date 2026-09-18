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
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

QUEUE = _REPO / 'nfl' / 'WORK_QUEUE.md'
STATE = _REPO / 'nfl' / 'AGENT_STATE.json'
HANDOFF = _REPO / 'nfl' / 'HANDOFF.md'

STATUSES = ('QUEUED', 'ACTIVE', 'BLOCKED', 'DONE', 'SUPERSEDED')
GENERATOR = 'nfl/tools/agent_state.py'


class QueueError(RuntimeError):
    pass


def worktree_state() -> dict:
    """Working-tree dirtiness, FROM THE MODULE THAT OWNS IT.

    `nfl/identity/` is the only place in this repository permitted to ask git
    about working-tree state; `test_determinism_proof` sweeps every source
    module for a `--porcelain` call and fails on any other. A first version of
    this generator ran `git status --porcelain` itself and joined
    `commit_claim.py` on that offender list.

    The rule is right here for a second reason, which is this control layer's
    own reason for existing: an independently computed view of "what is dirty"
    is a second truth, and the two drift. So the repair is a call into
    `code_identity`, not an exemption from the rule.

    `n_dirty_tree_entries_observed` is carried as a DIAGNOSTIC. The identity
    module keeps it out of `ident` deliberately, because anything reading
    generated artifact state that reaches a sealed body changes a forecast id
    for byte-identical draws -- measured, in the Q9 dry run. `AGENT_STATE.json`
    and `SYSTEM_STATE.json` are not sealed forecast artifacts and nothing
    hashes them into one, which is why it is lawful to record it here and
    would not be there.
    """
    from sportsplatform.governance.outcome import State
    from nfl.identity import code_identity as CI
    o = CI.code_identity()
    if o.state is not State.PASS:
        return {'state': 'NOT_MEASURED', 'why': f'{o.code}: {o.detail}'[:300]}
    v = o.value
    return {
        'commit': v['commit'],
        'code_version': v['code_version'],
        'source_scope_clean': v['source_scope_clean'],
        'dirty_source_files': [e['path'] for e in v['dirty_source_files']],
        'n_dirty_source_files': v['n_dirty_source_files'],
        'n_dirty_tree_entries_observed':
            o.evidence.get('n_dirty_tree_entries_observed'),
        'scope_note':
            'dirty_source_files is SOURCE scope only -- the .py files the '
            'identity contract hashes. A changed .md or .json is counted in '
            'n_dirty_tree_entries_observed and is not listed.',
    }


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

    def _prio(it):
        # BY PRIORITY, NOT BY FILE ORDER. A first version returned the queue's
        # own order, so a newly ranked priority-2 item appeared BELOW a
        # priority-12 one that happened to be written earlier in the file --
        # and "next three eligible" is the line a fresh session reads to decide
        # what to do. An unparseable priority sorts last rather than first, so
        # a malformed entry cannot jump the queue.
        try:
            return (0, int(str(it.get('priority')).strip()))
        except (TypeError, ValueError):
            return (1, 0)
    eligible = [it['id'] for it in sorted(
        (x for x in items if x['status'] == 'QUEUED'), key=_prio)]
    wt = worktree_state()
    dirty = wt.get('dirty_source_files', [])
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
            'dirty_source_files': dirty,
            'worktree': wt,
            'is_clean': bool(wt.get('source_scope_clean')),
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
        f'- source scope: '
        + ('clean' if g['is_clean']
           else f'{len(g["dirty_source_files"])} dirty source file(s): '
                + ', '.join(g['dirty_source_files'][:8]))
        + f' ({g["worktree"].get("n_dirty_tree_entries_observed")} dirty tree '
          f'entries in total, source and not)',
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
