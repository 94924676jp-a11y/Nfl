#!/usr/bin/env python3.12
"""Read the repository's coordination state. Read ONLY -- nothing here writes.

The split matters. `state.py` answers "what is true right now"; `dispatch.py`
decides what to do about it; `github_runtime.py` is the only module that
writes, commits or pushes. Mixing those is how a reader acquires a side effect
nobody expected, and a state machine whose observation step mutates state
cannot be reasoned about at all.

Everything here is derived from files on disk at the current HEAD. There is no
cache and no memory between invocations -- the repository IS the memory, which
is the whole premise of the coordination layer and the reason two agents that
never speak can still agree.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import subprocess

HERE = pathlib.Path(__file__).resolve().parent
COORD = HERE.parent
REPO = COORD.parent

POLICY = COORD / 'AUTOMATION_POLICY.json'
MODELS = HERE / 'MODELS.json'
PROJECT_STATE = COORD / 'PROJECT_STATE.json'
DECISIONS = COORD / 'OWNER_DECISIONS.md'
LOG = COORD / 'HANDOFF_LOG.jsonl'
RUNS = COORD / 'runs'

ENGINEERING_QUEUE = COORD / 'ENGINEERING_QUEUE.json'
RESEARCH_QUEUE = COORD / 'RESEARCH_QUEUE.json'
RETURNS = {'ENGINEERING_QUEUE.json': COORD / 'CLAUDE_RETURNS',
           'RESEARCH_QUEUE.json': COORD / 'PERPLEXITY_RETURNS'}


def rebind(repo_root) -> None:
    """Point every path at another repository. FOR TESTS ONLY.

    The mocked state machine has to drive real writes, real commits and real
    queue transitions, because a test that stubs the writes proves the
    decisions and nothing about the effects. So it builds a throwaway git
    repository and rebinds the runtime onto it.

    This is an explicit function rather than an environment variable read at
    import time, for one reason: an env var would mean a mis-set variable in
    CI could silently point the LIVE runtime at the wrong tree. A function
    that only the test calls cannot be reached by forgetting something.
    """
    global REPO, COORD, POLICY, MODELS, PROJECT_STATE, DECISIONS, LOG, RUNS
    global ENGINEERING_QUEUE, RESEARCH_QUEUE, RETURNS
    REPO = pathlib.Path(repo_root).resolve()
    COORD = REPO / 'coordination'
    POLICY = COORD / 'AUTOMATION_POLICY.json'
    MODELS = COORD / 'orchestrator' / 'MODELS.json'
    PROJECT_STATE = COORD / 'PROJECT_STATE.json'
    DECISIONS = COORD / 'OWNER_DECISIONS.md'
    LOG = COORD / 'HANDOFF_LOG.jsonl'
    RUNS = COORD / 'runs'
    ENGINEERING_QUEUE = COORD / 'ENGINEERING_QUEUE.json'
    RESEARCH_QUEUE = COORD / 'RESEARCH_QUEUE.json'
    RETURNS = {'ENGINEERING_QUEUE.json': COORD / 'CLAUDE_RETURNS',
               'RESEARCH_QUEUE.json': COORD / 'PERPLEXITY_RETURNS'}
    # github_runtime caches RUNS at import; keep the two in step.
    try:
        from coordination.orchestrator import github_runtime as _G
        _G.RUNS = RUNS
    except ImportError:
        pass


class StateError(Exception):
    """Malformed or missing state. NEVER defaulted around."""


def git(*args, cwd=None) -> str:
    # `cwd=REPO` as a DEFAULT ARGUMENT would bind the path at def time and
    # survive `rebind`, so a sandboxed test would silently read the real
    # repository's HEAD. Resolved at call time instead.
    r = subprocess.run(('git',) + args, cwd=cwd or REPO, capture_output=True,
                       text=True)
    return (r.stdout or '').strip()


def head() -> str:
    return git('rev-parse', 'HEAD')


def branch() -> str:
    return git('rev-parse', '--abbrev-ref', 'HEAD')


def _read_json(path, what):
    """Load or raise. A missing policy file is not an empty policy.

    Returning {} here would make every limit read as absent and therefore
    unlimited, which is the most expensive possible interpretation of a
    missing file.
    """
    if not path.exists():
        raise StateError(f'{what} is absent at {path}. The orchestrator will '
                         f'not run without it; an absent policy is not a '
                         f'permissive one.')
    try:
        return json.loads(path.read_text())
    except ValueError as exc:
        raise StateError(f'{what} at {path} is not valid JSON: {exc}') from exc


def policy() -> dict:
    return _read_json(POLICY, 'AUTOMATION_POLICY.json')


def models() -> dict:
    return _read_json(MODELS, 'MODELS.json')


def project_state() -> dict:
    return _read_json(PROJECT_STATE, 'PROJECT_STATE.json')


def decisions_text() -> str:
    if not DECISIONS.exists():
        raise StateError('OWNER_DECISIONS.md is absent. A runtime that cannot '
                         'read the owner\'s rulings must not act on their '
                         'behalf.')
    return DECISIONS.read_text()


def queue(name: str) -> dict:
    return _read_json(COORD / name, name)


def queues() -> dict:
    return {n: queue(n) for n in ('ENGINEERING_QUEUE.json',
                                  'RESEARCH_QUEUE.json')}


def log_lines() -> list:
    """Every handoff ever recorded. A malformed line RAISES."""
    if not LOG.exists():
        return []
    out = []
    for i, line in enumerate(LOG.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            raise StateError(f'HANDOFF_LOG.jsonl line {i} is not JSON: {exc}. '
                             f'A log the runtime cannot read is a log it '
                             f'cannot use to detect a duplicate run.')
    return out


def validate() -> tuple:
    """Run the existing validator. Its verdict is the runtime's gate.

    This shells out rather than importing, deliberately: the validator is the
    contract the human-operated path already uses, and a second in-process
    implementation of it would be a second source of truth about validity.
    """
    r = subprocess.run(('python3.12', str(COORD / 'validate_coordination.py')),
                       capture_output=True, text=True, cwd=REPO)
    return r.returncode, ((r.stdout or '') + (r.stderr or '')).strip()


# ------------------------------------------------------------- the view
@dataclasses.dataclass
class Snapshot:
    """Everything one orchestration pass is allowed to decide from."""

    head: str
    branch: str
    valid: bool
    validator_output: str
    policy: dict
    models: dict
    project_state: dict
    queues: dict
    log: list

    # --------------------------------------------------------- queries
    def tasks(self, queue_name=None) -> list:
        """(queue_name, task) pairs, optionally for one queue."""
        out = []
        for name, q in self.queues.items():
            if queue_name and name != queue_name:
                continue
            for t in q.get('tasks') or []:
                out.append((name, t))
        return out

    def by_id(self, task_id):
        for name, t in self.tasks():
            if t.get('task_id') == task_id:
                return name, t
        return None, None

    def active(self, queue_name=None) -> list:
        return [(n, t) for n, t in self.tasks(queue_name)
                if t.get('status') == 'ACTIVE']

    def returned(self) -> list:
        """Returns awaiting owner review, oldest queue order first."""
        return [(n, t) for n, t in self.tasks()
                if t.get('status') == 'RETURNED']

    def executable(self, queue_name=None) -> list:
        """AUTHORIZED, authorized=true, dependencies satisfied.

        Sorted by priority then task_id, so two runners that race reach the
        SAME task rather than two different ones -- determinism here is what
        makes the exclusive lock sufficient.
        """
        done = {t.get('task_id') for _n, t in self.tasks()
                if t.get('status') in ('RETURNED', 'COMPLETE', 'SUPERSEDED')}
        out = []
        for n, t in self.tasks(queue_name):
            if t.get('status') != 'AUTHORIZED' or not t.get('authorized'):
                continue
            if [d for d in (t.get('depends_on') or []) if d not in done]:
                continue
            out.append((n, t))
        return sorted(out, key=lambda p: (p[1].get('priority', 9999),
                                          p[1].get('task_id', '')))

    def runs_in_last_hour(self, now=None) -> int:
        """From the log, so two racing runners count the same runs."""
        import datetime as dt
        now = now or dt.datetime.now(dt.timezone.utc)
        cut = now - dt.timedelta(hours=1)
        n = 0
        for row in self.log:
            ts = row.get('timestamp')
            if not ts or not row.get('run_id'):
                continue
            try:
                when = dt.datetime.fromisoformat(
                    str(ts).replace('Z', '+00:00'))
            except ValueError:
                continue
            if when >= cut:
                n += 1
        return n

    def attempts(self, task_id: str) -> int:
        """How many WORKER CALLS this task has already had.

        COUNTED FROM CALLS, NOT FROM `ACTIVE` TRANSITIONS, and the difference
        is load-bearing. A task that is already ACTIVE is not re-marked ACTIVE
        on a retry, so counting transitions left `attempt` pinned at 0 -- and
        since `attempt` feeds the idempotency key, a legitimate retry after a
        recorded failure derived the SAME key as the failed call and was
        refused as a duplicate. The retry budget existed and could never be
        used.

        Counting keyed rows separates the two cases properly:

          two runners racing    -> same log, same attempt, SAME key -> blocked
          a retry after failure -> the failure row is now in the log, so
                                   attempt is one higher and the key differs
                                   -> allowed, and bounded by
                                   max_retries_per_task

        Found by test_j in the mocked suite, which drove three calls in a row
        and had the third refused.
        """
        return sum(1 for r in self.log
                   if r.get('task_id') == task_id and r.get('idempotency_key'))

    def run_ids(self) -> set:
        return {r['run_id'] for r in self.log if r.get('run_id')}

    def idempotency_keys(self) -> set:
        return {r['idempotency_key'] for r in self.log
                if r.get('idempotency_key')}


def snapshot() -> Snapshot:
    """Read everything once. Raises StateError rather than guessing."""
    rc, out = validate()
    return Snapshot(head=head(), branch=branch(), valid=(rc == 0),
                    validator_output=out, policy=policy(), models=models(),
                    project_state=project_state(), queues=queues(),
                    log=log_lines())


if __name__ == '__main__':
    import sys
    try:
        s = snapshot()
    except StateError as exc:
        print(f'STATE_UNREADABLE: {exc}')
        sys.exit(2)
    print(f'head      {s.head[:12]} on {s.branch}')
    print(f'valid     {s.valid}  ({s.validator_output.splitlines()[0]})')
    print(f'autonomy  {s.policy.get("autonomous_operation_enabled")}')
    print(f'active    {[t["task_id"] for _n, t in s.active()]}')
    print(f'returned  {[t["task_id"] for _n, t in s.returned()]}')
    print(f'runnable  {[t["task_id"] for _n, t in s.executable()][:6]}')
    print(f'runs/hour {s.runs_in_last_hour()}')
