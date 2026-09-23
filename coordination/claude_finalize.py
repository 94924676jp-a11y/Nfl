#!/usr/bin/env python3.12
"""Close an ACTIVE engineering task, but only against evidence.

    python3.12 coordination/claude_finalize.py <task_id> <commit_sha> \
        coordination/CLAUDE_RETURNS/<task_id>.md

A RETURN WITHOUT EVIDENCE IS NOT ALLOWED. Three things are verified before
anything moves, and each refusal is named:

  the commit resolves in THIS repository  (not a plausible-looking hex string)
  the return file exists and is not a stub
  the return path is the one the contract names

Then, and only then: ACTIVE -> RETURNED, `result_path` and `commit_sha` are
written, one line is appended to HANDOFF_LOG.jsonl, and
validate_coordination.py runs. If validation refuses the result, so does this
script -- a finalize that leaves the queue invalid has not finalized anything.

It does not mark COMPLETE. That is the owner's move: an agent that can both
do the work and declare it accepted is grading its own exam.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import datetime as dt

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
QUEUE = HERE / 'ENGINEERING_QUEUE.json'
LOG = HERE / 'HANDOFF_LOG.jsonl'
#: A return shorter than this is a stub, and a stub is not evidence. The
#: contract asks for eight sections; nothing real fits in 400 bytes.
MIN_RETURN_BYTES = 400
REQUIRED_SECTIONS = ('work performed', 'evidence', 'tests', 'failures',
                     'changed files', 'commit', 'blocker', 'next')


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def refuse(code, msg, rc=1):
    print(f'FINALIZE_REFUSED {code}\n\n  {msg}')
    return rc


def main(argv):
    if len(argv) != 3:
        return refuse('USAGE', 'claude_finalize.py <task_id> <commit_sha> '
                               '<return_path>', 2)
    tid, sha, rel = argv
    rel = rel.replace('\\', '/')

    try:
        q = json.loads(QUEUE.read_text())
    except Exception as e:                                   # noqa: BLE001
        return refuse('QUEUE_UNREADABLE', f'{QUEUE}: {e}', 2)
    task = next((t for t in q.get('tasks') or [] if t['task_id'] == tid), None)
    if task is None:
        return refuse('TASK_UNKNOWN',
                      f'{tid} is not in ENGINEERING_QUEUE.json. A return for '
                      f'a task nobody queued is not a return.')
    if task.get('status') != 'ACTIVE':
        return refuse('TASK_NOT_ACTIVE',
                      f'{tid} is {task.get("status")!r}, not ACTIVE. Claim it '
                      f'with claude_dispatch.py before finalizing it.')

    # 1. THE COMMIT MUST EXIST HERE.
    if not re.fullmatch(r'[0-9a-f]{7,40}', sha):
        return refuse('COMMIT_SHA_MALFORMED', f'{sha!r} is not a sha')
    r = subprocess.run(('git', 'cat-file', '-t', sha), cwd=REPO,
                       capture_output=True, text=True)
    if r.stdout.strip() != 'commit':
        return refuse('COMMIT_NOT_IN_REPO',
                      f'{sha} does not resolve to a commit in this '
                      f'repository. A sha nobody can check out is a claim.')

    # 2. THE RETURN MUST EXIST, BE ON CONTRACT, AND SAY SOMETHING.
    want = f'coordination/CLAUDE_RETURNS/{tid}.md'
    if rel != want:
        return refuse('RETURN_PATH_OFF_CONTRACT',
                      f'return is {rel}, contract is {want}')
    p = REPO / rel
    if not p.exists():
        return refuse('RETURN_ABSENT', f'{rel} does not exist')
    body = p.read_text()
    if len(body.encode()) < MIN_RETURN_BYTES:
        return refuse('RETURN_IS_A_STUB',
                      f'{rel} is {len(body.encode())} bytes. The contract '
                      f'asks for eight sections; a stub is not evidence.')
    low = body.lower()
    missing = [s for s in REQUIRED_SECTIONS if s not in low]
    if missing:
        return refuse('RETURN_INCOMPLETE',
                      f'{rel} does not mention: {missing}. The eight sections '
                      f'are the contract, not a suggestion.')
    if sha[:7] not in body:
        return refuse('RETURN_DOES_NOT_NAME_THE_COMMIT',
                      f'{rel} never mentions {sha[:7]}. A return that does '
                      f'not name its own commit cannot be checked against it.')

    prev = task['status']
    task['status'] = 'RETURNED'
    task['result_path'] = rel
    task['commit_sha'] = sha
    QUEUE.write_text(json.dumps(q, indent=1) + '\n')
    with LOG.open('a') as fh:
        fh.write(json.dumps({
            'timestamp': _now(), 'actor': 'claude', 'task_id': tid,
            'from_status': prev, 'to_status': 'RETURNED',
            'commit_sha': sha, 'artifact_path': rel,
            'note': 'finalized by claude_finalize.py; COMPLETE is the '
                    'owner\'s move'}) + '\n')

    r = subprocess.run(('python3.12', str(HERE / 'validate_coordination.py')),
                       capture_output=True, text=True)
    if r.returncode != 0:                                    # pragma: no cover
        return refuse('FINALIZE_BROKE_VALIDATION',
                      'the queue is invalid after this write; revert it.\n\n'
                      + (r.stdout or '').strip(), 2)

    print(f'FINALIZE_OK {tid}\n')
    print(f'  status       {prev} -> RETURNED')
    print(f'  commit_sha   {sha}')
    print(f'  result_path  {rel}')
    print(f'  {r.stdout.strip()}')
    print('\n  COMPLETE is the owner\'s move, not this script\'s.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
