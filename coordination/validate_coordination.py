#!/usr/bin/env python3.12
"""Refuse a coordination layer that is lying about its own state.

The queues govern what three agents may execute automatically, so a
malformed or self-contradictory queue is not an inconvenience -- it is an
authorization defect. Every check below exists because the failure it
catches would let work start that nobody approved, or let work be recorded
as finished with nothing behind it.

    python3.12 coordination/validate_coordination.py

Exit 0 clean, 1 on any violation. Prints every violation, not the first:
a validator that stops at one finding makes a reader fix them one commit at
a time.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

STATUSES = ('DRAFT', 'AUTHORIZED', 'ACTIVE', 'BLOCKED', 'RETURNED',
            'COMPLETE', 'SUPERSEDED')
#: A task in one of these has finished and owes evidence.
TERMINAL = ('RETURNED', 'COMPLETE')
REQUIRED_TASK_FIELDS = ('task_id', 'title', 'status', 'priority',
                        'authorized', 'depends_on', 'objective',
                        'acceptance_tests', 'created_by', 'result_path',
                        'commit_sha')

QUEUES = {
    'ENGINEERING_QUEUE.json': {'returns': 'CLAUDE_RETURNS',
                               'is_coding': True},
    'RESEARCH_QUEUE.json': {'returns': 'PERPLEXITY_RETURNS',
                            'is_coding': False},
}
DECISIONS = 'OWNER_DECISIONS.md'
LOG = 'HANDOFF_LOG.jsonl'

_v: list = []
#: What was measured, so the VALID line can say how much it looked at.
_n: dict = {}


def bad(code, detail):
    _v.append((code, detail))


def reset():
    """Clear the violation and count registers (for a caller running twice)."""
    _v.clear()
    _n.clear()


def _load(name):
    """Malformed queue JSON is a violation, not an exception."""
    p = HERE / name
    if not p.exists():
        bad('QUEUE_MISSING', f'{name} does not exist')
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:                                   # noqa: BLE001
        bad('QUEUE_MALFORMED', f'{name}: {type(e).__name__}: {e}')
        return None


def _all_task_ids():
    """Both queues. A research task waiting on an engineering task is the
    NORMAL case -- the engineering agent has no network and the research
    agent cannot land bytes the engineering slice has not asked for yet --
    so a dependency is resolved against the union, not against one file."""
    ids = set()
    for n in QUEUES:
        try:
            for t in (json.loads((HERE / n).read_text()).get('tasks') or ()):
                ids.add(t.get('task_id'))
        except Exception:                                    # noqa: BLE001
            pass
    return ids


def check_queue(name, cfg):
    q = _load(name)
    if q is None:
        return
    tasks = q.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        bad('QUEUE_EMPTY', f'{name} carries no tasks. An empty queue reads '
                           f'like "nothing to do" and is indistinguishable '
                           f'from a broken writer.')
        return
    _n['tasks'] = _n.get('tasks', 0) + len(tasks)
    seen, active = set(), []
    for t in tasks:
        tid = t.get('task_id', '<no id>')
        for f in REQUIRED_TASK_FIELDS:
            if f not in t:
                bad('TASK_FIELD_MISSING', f'{name}:{tid} has no {f!r}')
        if tid in seen:
            bad('TASK_ID_DUPLICATED', f'{name}:{tid} appears twice')
        seen.add(tid)

        st = t.get('status')
        if st not in STATUSES:
            bad('TASK_STATUS_UNKNOWN',
                f'{name}:{tid} status {st!r} is not one of {STATUSES}')

        # OWNER RULE 1 (2026-10-02): a task whose acceptance_tests is [] (or
        # not a list) passed every check here, because no check read it. An
        # acceptance list with nothing in it means the task cannot be judged
        # finished by anyone, so it is EMPTY_INPUT, refused by name.
        if 'acceptance_tests' in t:
            at = t.get('acceptance_tests')
            if not isinstance(at, list) or not at:
                bad('ACCEPTANCE_TESTS_EMPTY_INPUT',
                    f'{name}:{tid} acceptance_tests={at!r}: an empty or '
                    f'non-list acceptance set gives nothing to judge the '
                    f'task against, so it cannot be validated (cause '
                    f'EMPTY_INPUT)')

        auth = t.get('authorized')
        if not isinstance(auth, bool):
            bad('TASK_AUTHORIZED_NOT_BOOL',
                f'{name}:{tid} authorized={auth!r} is not a boolean. A '
                f'truthy string authorizes work nobody approved.')

        # 1. AN UNAUTHORIZED TASK MAY NOT BE ACTIVE.
        if st in ('ACTIVE', 'AUTHORIZED') and auth is not True:
            bad('UNAUTHORIZED_TASK_ACTIVE',
                f'{name}:{tid} is {st} with authorized={auth!r}. Only '
                f'authorized=true AND status=AUTHORIZED may be executed.')
        if st == 'ACTIVE':
            active.append(tid)

        # 2. A TERMINAL TASK OWES A RETURN ARTIFACT.
        if st in TERMINAL:
            rp = t.get('result_path')
            if not rp:
                bad('COMPLETED_TASK_NO_RETURN',
                    f'{name}:{tid} is {st} with no result_path. A task '
                    f'marked finished with no artifact is a claim.')
            elif not (REPO / rp).exists():
                bad('COMPLETED_TASK_RETURN_ABSENT',
                    f'{name}:{tid} names {rp}, which does not exist')
            else:
                want = HERE / cfg['returns'] / f'{tid}.md'
                if (REPO / rp).resolve() != want.resolve():
                    bad('RETURN_PATH_OFF_CONTRACT',
                        f'{name}:{tid} return is {rp}, contract is '
                        f'coordination/{cfg["returns"]}/{tid}.md')

            # 3. A COMPLETED CODING TASK OWES A COMMIT SHA.
            if cfg['is_coding']:
                sha = t.get('commit_sha')
                if not sha:
                    bad('COMPLETED_CODING_TASK_NO_SHA',
                        f'{name}:{tid} is {st} with no commit_sha')
                elif not re.fullmatch(r'[0-9a-f]{7,40}', str(sha)):
                    bad('COMMIT_SHA_MALFORMED',
                        f'{name}:{tid} commit_sha {sha!r} is not a sha')
                else:
                    r = subprocess.run(('git', 'cat-file', '-t', str(sha)),
                                       cwd=REPO, capture_output=True,
                                       text=True)
                    if r.stdout.strip() != 'commit':
                        bad('COMMIT_SHA_NOT_IN_REPO',
                            f'{name}:{tid} commit_sha {sha} does not resolve '
                            f'to a commit in this repository')

        for dep in t.get('depends_on') or ():
            if dep not in _all_task_ids():
                bad('DEPENDENCY_UNKNOWN',
                    f'{name}:{tid} depends on {dep!r}, which is in neither '
                    f'queue. A blocker nobody can look up is not a blocker.')

    # 4. EXCLUSIVE ACTIVE OWNERSHIP, WHERE THE QUEUE DECLARES IT.
    if q.get('exclusive_active') and len(active) > 1:
        bad('MULTIPLE_ACTIVE_TASKS',
            f'{name} declares exclusive_active and {len(active)} tasks are '
            f'ACTIVE: {active}. Three partially-implemented foundational '
            f'workstreams at once is the state this queue prevents.')


def check_decisions():
    """5. AN OWNER DECISION MAY NOT BE SILENTLY REMOVED.

    The headings are the record. A decision that vanishes without a
    SUPERSEDED note is indistinguishable from one that was never made, and
    an agent reading the file afterwards cannot tell.
    """
    p = HERE / DECISIONS
    if not p.exists():
        bad('DECISIONS_MISSING', f'{DECISIONS} does not exist')
        return
    txt = p.read_text()
    ids = set(re.findall(r'^##\s+(D-\d+)\b', txt, re.M))
    if not ids:
        bad('DECISIONS_UNREADABLE',
            f'{DECISIONS} carries no "## D-NN" headings, so removal cannot '
            f'be detected at all')
        return
    # THIS CHECK ONLY WORKS INSIDE THE REAL REPOSITORY, against the
    # COMMITTED version. That is a real limit and it is stated here rather
    # than discovered later: a copy of this directory somewhere else will
    # silently skip the check, because there is nothing to compare against.
    # Proven to fire in-repo: removing a D-NN heading and running this file
    # reports OWNER_DECISION_REMOVED and exits 1.
    prev = subprocess.run(('git', 'show', f'HEAD:coordination/{DECISIONS}'),
                          cwd=REPO, capture_output=True, text=True)
    if prev.returncode != 0:
        return                      # first commit of the file
    was = set(re.findall(r'^##\s+(D-\d+)\b', prev.stdout, re.M))
    gone = sorted(was - ids)
    for d in gone:
        if not re.search(rf'{d}\b.*SUPERSEDED', txt, re.I | re.S):
            bad('OWNER_DECISION_REMOVED',
                f'{d} was in the committed {DECISIONS} and is gone, with no '
                f'SUPERSEDED entry naming it')


def check_log():
    p = HERE / LOG
    if not p.exists():
        bad('LOG_MISSING', f'{LOG} does not exist')
        return
    n_rows = n_events = 0
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        n_rows += 1
        try:
            row = json.loads(line)
        except Exception as e:                               # noqa: BLE001
            bad('LOG_LINE_MALFORMED', f'{LOG}:{i}: {e}')
            continue
        if row.get('kind') == 'SCHEMA':
            continue
        n_events += 1
        for f in ('timestamp', 'actor', 'task_id', 'from_status',
                  'to_status'):
            if f not in row:
                bad('LOG_FIELD_MISSING', f'{LOG}:{i} has no {f!r}')
        for f in ('from_status', 'to_status'):
            v = row.get(f)
            if v is not None and v not in STATUSES:
                bad('LOG_STATUS_UNKNOWN', f'{LOG}:{i} {f}={v!r}')
    _n['log_rows'] = n_rows
    _n['log_events'] = n_events
    if n_rows == 0:
        # OWNER RULE 1 (2026-10-02): a HANDOFF_LOG.jsonl with no rows at all
        # passed this check -- the loop had nothing to refuse. A log that was
        # not parsed was not validated; reporting it VALID would make an
        # empty file and a verified log the same claim. EMPTY_INPUT, by name.
        # A log carrying its SCHEMA row and no events yet is a parsed, governed
        # log with a measured event count of zero, and is reported as such.
        bad('LOG_EMPTY_INPUT',
            f'{LOG} carries no rows: nothing was parsed, so the log was not '
            f'validated (cause EMPTY_INPUT). A new log starts with its SCHEMA '
            f'row.')


def check_mode():
    """OWNER RULE 3 (2026-10-02): the mode block, when present, must be one of the four modes and
    carry its provenance; a pinned mode_declared must be a mode. Absence is reported, not refused:
    the mode system reports NOT_EXECUTED on its own until the owner or an agent sets one."""
    try:
        import sys as _s
        _r = str(pathlib.Path(__file__).resolve().parents[1])
        if _r not in _s.path:
            _s.path.insert(0, _r)
        from coordination import mode as M
        sp = HERE / 'PROJECT_STATE.json'
        doc = json.loads(sp.read_text()) if sp.exists() else None
    except Exception as e:                                   # noqa: BLE001
        bad('MODE_UNREADABLE', f'{type(e).__name__}: {e}')
        return
    if not isinstance(doc, dict):
        # a sandbox or a checkout with no state file: the mode is unset, not invalid
        print('  mode: NONE (no PROJECT_STATE.json; boundary NOT_EXECUTED)')
        return
    for key in ('mode', 'mode_declared'):
        v = doc.get(key)
        if v is None:
            continue
        m = v.get('mode') if isinstance(v, dict) else v
        if m not in M.MODES:
            bad('MODE_UNKNOWN', f'PROJECT_STATE.{key} names {m!r}, not one of {M.MODES}')
        if key == 'mode' and isinstance(v, dict):
            for f in ('since_commit', 'since_utc', 'set_by', 'reason'):
                if not v.get(f):
                    bad('MODE_RECORD_INCOMPLETE', f'PROJECT_STATE.mode lacks {f}; a mode with no '
                                                  f'provenance is a label, not a state')
    cur = M.read(doc)
    print(f"  mode: {cur['mode'] or 'NONE (boundary NOT_EXECUTED)'}"
          + (f" (pinned by owner)" if cur['pinned'] else ''))


def main():
    for name, cfg in QUEUES.items():
        check_queue(name, cfg)
    check_decisions()
    check_log()
    check_mode()
    if _v:
        print(f'COORDINATION_INVALID: {len(_v)} violation(s)\n')
        for code, detail in _v:
            print(f'  {code}: {detail}')
        return 1
    print(f'COORDINATION_VALID: queues, decisions and handoff log are '
          f'internally consistent ({_n.get("tasks", 0)} task(s), '
          f'{_n.get("log_rows", 0)} log row(s) of which '
          f'{_n.get("log_events", 0)} event(s))')
    return 0


if __name__ == '__main__':
    sys.exit(main())
