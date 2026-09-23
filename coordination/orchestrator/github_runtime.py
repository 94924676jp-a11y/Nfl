#!/usr/bin/env python3.12
"""The only module that writes, commits or pushes. Everything else is pure.

Keeping writes in one file is not tidiness. It means the question "what can
this runtime change?" has ONE answer that fits on a screen, and that a reviewer
checking whether an autonomous agent can touch a protected path reads this
module rather than auditing nine.

THE RAW/NORMALIZED SPLIT, AND WHY RAW IS NOT STATE

Every provider call writes four files under `coordination/runs/<run_id>/`:
request.json, response.json, metadata.json, normalized_return.md. The raw
response is EVIDENCE -- it is what the provider actually said, hashed, with
the repository HEAD before and after. It is deliberately NOT canonical project
state: state lives in the queues and PROJECT_STATE.json, which are small,
diffable and reviewed. A runtime that reads its own past model output as
authority is a runtime that will eventually believe something no human wrote.

WHY THE HEAD CHECK IS HERE AND NOT IN THE CALLER. The gap between deciding to
write and writing is where a racing runner slips in. The check belongs
immediately before the write, in the same function, or it is checking a
different moment than the one that matters.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import subprocess

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C
from coordination.orchestrator import locks
from coordination.orchestrator import state as S

RUNS = S.COORD / 'runs'
ATTRIBUTION = (
    'Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n'
    'Claude-Session: https://claude.ai/code/session_01AhzzzJvfv5ysCRfLvXou8X')


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(text) -> str:
    if isinstance(text, (dict, list)):
        text = json.dumps(text, sort_keys=True)
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()


def run_id(worker, task_id, key) -> str:
    """Stable, sortable, and carries its own idempotency key.

    The key is IN the directory name so that a duplicate run is visible by
    listing a directory, without parsing anything.
    """
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return f'{stamp}-{worker.value.lower()}-{task_id}-{key[:12]}'


# ------------------------------------------------------- raw preservation
def write_run(rid, *, call, result, system, user, head_before,
              head_after=None, normalized=None, extra=None) -> pathlib.Path:
    """Preserve the call and its response, whatever happened.

    WRITTEN ON FAILURE TOO, and that is the point. A run that errored is the
    run you most need to read later; discarding it because `ok` is False would
    throw away the only record of what the provider actually said.
    """
    d = RUNS / rid
    d.mkdir(parents=True, exist_ok=True)
    request = {'worker': call.worker.value, 'model': call.model,
               'task_id': call.task_id, 'attempt': call.attempt,
               'system': system, 'user': user}
    (d / 'request.json').write_text(json.dumps(request, indent=1) + '\n')
    (d / 'response.json').write_text(
        json.dumps(result.raw or {}, indent=1, default=str) + '\n')
    meta = {
        'run_id': rid,
        'provider': call.worker.value,
        'model': call.model,
        'timestamp_utc': now(),
        'task_id': call.task_id,
        'attempt': call.attempt,
        'idempotency_key': call.idempotency_key,
        'request_sha256': sha(request),
        'response_sha256': sha(result.raw or {}),
        'prompt_sha256': call.prompt_sha256,
        'head_before': head_before,
        'head_after': head_after,
        'ok': result.ok,
        'code': result.code,
        'detail': result.detail[:4000],
        'usage': result.usage,
        'escalation': result.escalation.value if result.escalation else None,
        'mode': os.environ.get('AUTONOMY_MODE', 'MOCK').upper(),
        'note': ('Raw provider output. EVIDENCE, not project state. The '
                 'queues and PROJECT_STATE.json are canonical.'),
    }
    if extra:
        meta.update(extra)
    (d / 'metadata.json').write_text(json.dumps(meta, indent=1) + '\n')
    if normalized is not None:
        (d / 'normalized_return.md').write_text(normalized)
    return d


# ------------------------------------------------------------- the writes
def write_return(queue_name, task_id, text) -> pathlib.Path:
    d = S.RETURNS[queue_name]
    d.mkdir(parents=True, exist_ok=True)
    p = d / f'{task_id}.md'
    p.write_text(text)
    return p


def apply_patches(patches, worker, *, repo=None) -> list:
    """Write a worker's files, AFTER refusing any protected path.

    The refusal happens before ANY file is written, so a diff containing one
    forbidden path applies none of itself. A partial apply would leave the
    repository in a state no review covered and no rollback describes.
    """
    raw = [str(p.get('path') or '') for p in patches]
    # NORMALISE, THEN REFUSE. An earlier cut of this used `.lstrip('./')`,
    # which strips a CHARACTER SET rather than a prefix: '../escape.py' became
    # 'escape.py' and the traversal check downstream then found nothing wrong.
    # Quietly rewriting a hostile path into a benign one is worse than either
    # accepting or refusing it, because the log records a path nobody sent.
    paths, bad = [], []
    for r in raw:
        if not r.strip() or r.startswith('/') or '\\' in r:
            bad.append(r)
            continue
        rel = os.path.normpath(r)
        if rel.startswith('..') or os.path.isabs(rel) or rel == '.':
            bad.append(r)
            continue
        try:
            (S.REPO / rel).resolve().relative_to(S.REPO.resolve())
        except ValueError:
            bad.append(r)
            continue
        paths.append(rel)
    if bad:
        raise locks.Refusal(
            'PATCH_PATH_UNSAFE',
            f'{bad} escape the repository, are absolute, or are empty. '
            f'Refused whole, and not rewritten into something acceptable.',
            escalation=C.Escalation.DESTRUCTIVE_ACTION_REQUIRED, paths=bad)
    locks.enforce_protected_paths(paths, worker)

    # `repo=S.REPO` AS A DEFAULT ARGUMENT BOUND THE REAL REPOSITORY AT DEF
    # TIME, so a sandboxed test wrote its fixture files into the live tree --
    # and it did, twice, before this was caught. Python evaluates a default
    # once, at definition; `state.rebind` then moved S.REPO and this function
    # kept the old value. Resolved at call time now, and
    # test_orchestrator::test_a asserts the real tree is untouched.
    repo = repo or S.REPO
    written = []
    for patch, rel in zip(patches, paths):
        target = (repo / rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(patch['contents'])
        written.append(rel)
    return written


#: Keys `validate_coordination.check_log` requires on every row. They must be
#: PRESENT; null is a legal value for the two status fields.
LOG_REQUIRED = ('timestamp', 'actor', 'task_id', 'from_status', 'to_status')


def append_log(row: dict) -> None:
    """One line, appended, and schema-complete by construction.

    THE RUNTIME MUST NOT BE ABLE TO WRITE A ROW THAT HALTS THE RUNTIME. The
    first cut of this wrote whatever the caller passed, and several callers --
    the WORKER_FAILED and ESCALATION paths especially -- had no natural
    from_status/to_status. The validator then refused the log on the NEXT
    pass, so a single worker timeout would have bricked the loop into
    STATE_CONTRADICTORY and required a human to clean up a file the system
    wrote itself. Found by the mocked suite, which is what it is for.

    Normalising here rather than at each call site means a new caller cannot
    reintroduce it by forgetting.
    """
    row = {'timestamp': now(), **row}
    for k in LOG_REQUIRED:
        row.setdefault(k, None)
    for k in ('from_status', 'to_status'):
        # A status outside the vocabulary is a defect, not a label. Better to
        # record None than to write a word the validator will reject forever.
        if row[k] is not None and row[k] not in (
                'DRAFT', 'AUTHORIZED', 'ACTIVE', 'BLOCKED', 'RETURNED',
                'COMPLETE', 'SUPERSEDED'):
            row[k] = None
    ordered = {k: row.pop(k) for k in LOG_REQUIRED}
    with S.LOG.open('a') as fh:
        fh.write(json.dumps({**ordered, **row}, sort_keys=False) + '\n')


def update_task(queue_name, task_id, **fields) -> dict:
    """Change named fields on one task record. Nothing else is touched."""
    p = S.COORD / queue_name
    q = json.loads(p.read_text())
    hit = None
    for t in q.get('tasks') or []:
        if t.get('task_id') == task_id:
            hit = t
            t.update(fields)
            break
    if hit is None:
        raise locks.Refusal('TASK_NOT_FOUND',
                            f'{task_id} is not in {queue_name}',
                            escalation=C.Escalation.STATE_CONTRADICTORY)
    p.write_text(json.dumps(q, indent=1) + '\n')
    return hit


def add_task(queue_name, task: dict) -> dict:
    """Add a task as DRAFT. NEVER as AUTHORIZED.

    This is the hinge the whole design turns on. A worker that could create a
    task and authorize it in one step is a worker that authorizes itself, and
    every limit downstream becomes advisory. So a created task arrives DRAFT
    and waits for a human, whatever the creating worker asked for.
    """
    locks.enforce_bounded_task(task)
    p = S.COORD / queue_name
    q = json.loads(p.read_text())
    if any(t.get('task_id') == task['task_id'] for t in q.get('tasks') or []):
        raise locks.Refusal('TASK_ID_TAKEN',
                            f'{task["task_id"]} already exists in '
                            f'{queue_name}',
                            escalation=C.Escalation.STATE_CONTRADICTORY)
    record = {
        'task_id': task['task_id'],
        'title': task['title'],
        'status': 'DRAFT',
        'priority': int(task.get('priority', 50)),
        'authorized': False,
        'depends_on': list(task.get('depends_on') or []),
        'objective': task['objective'],
        'acceptance_tests': list(task['acceptance_tests']),
        'created_by': 'autonomous_owner_worker',
        'result_path': None,
        'commit_sha': None,
        'blocks': [],
        'evidence': task.get('evidence'),
        'created_note': ('Drafted by the autonomous owner worker. It arrives '
                         'DRAFT and unauthorized by construction; a human '
                         'authorizes it or it never runs.'),
    }
    q.setdefault('tasks', []).append(record)
    p.write_text(json.dumps(q, indent=1) + '\n')
    return record


def write_directive(filename, body) -> pathlib.Path:
    d = S.COORD / 'CHATGPT_OUTBOX'
    d.mkdir(parents=True, exist_ok=True)
    p = d / filename
    p.write_text(body)
    return p


# ------------------------------------------------------------ git, guarded
def _git(*args, check=True):
    r = subprocess.run(('git',) + args, cwd=S.REPO, capture_output=True,
                       text=True)
    if check and r.returncode != 0:
        raise locks.Refusal('GIT_FAILED',
                            f'git {" ".join(args)}: {r.stderr.strip()}')
    return (r.stdout or '').strip()


def changed_paths() -> list:
    out = _git('status', '--porcelain')
    return [ln[3:].strip() for ln in out.splitlines() if ln.strip()]


def commit_and_push(message, head_before, *, push=True, paths=None) -> str:
    """Commit, verify nobody raced us, push. Returns the new sha.

    The head check sits between staging and committing rather than at the top
    of the caller, because that is the only window that matters: everything
    before it can be redone for free.
    """
    locks.require_head_unmoved(head_before)
    if paths:
        _git('add', '--', *paths)
    else:
        _git('add', '-A')
    if not _git('diff', '--cached', '--name-only'):
        return ''                     # nothing to commit is not a failure
    body = message.rstrip() + '\n\n' + ATTRIBUTION + '\n'
    tmp = S.REPO / '.git' / 'ORCHESTRATOR_COMMIT_MSG'
    tmp.write_text(body)
    _git('commit', '-q', '-F', str(tmp))
    tmp.unlink(missing_ok=True)
    new = S.head()
    if push:
        br = S.branch()
        bp = S.policy().get('branch_policy') or {}
        if br in (bp.get('protected_branches') or []):
            raise locks.Refusal(
                'BRANCH_PROTECTED',
                f'refusing to push to protected branch {br}',
                escalation=C.Escalation.DESTRUCTIVE_ACTION_REQUIRED)
        for delay in (0, 2, 4, 8, 16):
            if delay:
                import time
                time.sleep(delay)
            r = subprocess.run(('git', 'push', '-u', 'origin', br),
                               cwd=S.REPO, capture_output=True, text=True)
            if r.returncode == 0:
                break
        else:
            raise locks.Refusal('PUSH_FAILED',
                                'git push failed after 5 attempts')
    return new


def run_tests(commands, *, timeout=1800) -> tuple:
    """Run the repo's own checks. (all_passed, combined_output).

    A non-zero exit is a failure and is REPORTED AS ONE. There is no branch
    here that decides a failing test was probably fine.
    """
    chunks, ok = [], True
    for cmd in commands or []:
        try:
            r = subprocess.run(cmd, shell=True, cwd=S.REPO,
                               capture_output=True, text=True, timeout=timeout)
            out = ((r.stdout or '') + (r.stderr or ''))[-8000:]
            chunks.append(f'$ {cmd}\n{out}\n[exit {r.returncode}]')
            ok = ok and r.returncode == 0
        except subprocess.TimeoutExpired:
            chunks.append(f'$ {cmd}\n[TIMED OUT after {timeout}s]')
            ok = False
    return ok, '\n\n'.join(chunks)


# ------------------------------------------------- the continuation event
#
# WHY THIS EXISTS, AND WHY THE ORIGINAL DESIGN WAS WRONG.
#
# The first cut assumed: orchestrator commits -> git push -> push event ->
# next orchestrator run. GitHub does not work that way. Its documented
# behaviour is that "when you use the repository's GITHUB_TOKEN to perform
# tasks, events triggered by the GITHUB_TOKEN will not create a new workflow
# run" -- specifically so that a workflow pushing code cannot recurse. So the
# loop would have run exactly once and stopped, silently, looking fine.
#
# The same documentation names the exceptions: workflow_dispatch and
# repository_dispatch "always create workflow runs", because they are explicit
# calls rather than side effects. That is the mechanism this uses, and it is
# better than the accident it replaces: continuation becomes a DELIBERATE act
# the orchestrator takes only when it has decided more work is eligible,
# rather than a side effect of having written a file.
#
# WHAT THE PAYLOAD MAY CARRY. Branch, the run that asked, an observed HEAD for
# tracing, a chain depth and a reason. NOT project state, not a task record,
# not a decision. The next pass re-reads everything from the repository. A
# payload that carried authoritative state would be a second source of truth
# that no validator checks and no reviewer sees -- and unlike the repository,
# it arrives from outside.
DISPATCH_EVENT = 'agent-orchestrator-continue'
GITHUB_API = 'https://api.github.com'


def _dispatch_sink():
    """Where a continuation goes when this is not a real Actions run.

    Tests point this at a directory and read what would have been sent. There
    is deliberately no path where a sink write is reported as a real dispatch.
    """
    return os.environ.get('ORCHESTRATOR_DISPATCH_SINK') or ''


def request_continuation(reason, *, chain_depth, head, task_id=None) -> dict:
    """Ask GitHub to start one more orchestrator pass. Returns what happened.

    Never raises for transport trouble: a continuation that could not be sent
    is a FACT about this run and belongs in the log, not in a traceback. It is
    also not fatal -- the work is committed, and a human or a schedule can
    resume the chain.
    """
    payload = {
        'event_type': DISPATCH_EVENT,
        'client_payload': {
            'branch': S.branch(),
            'requested_by_run': os.environ.get('GITHUB_RUN_ID'),
            'observed_head': head,
            'chain_depth': chain_depth,
            'reason': str(reason)[:200],
            'task_id': task_id,
            'note': ('tracing only -- the next pass re-reads all state from '
                     'the repository and trusts nothing in this payload'),
        },
    }
    sink = _dispatch_sink()
    if sink:
        d = pathlib.Path(sink)
        d.mkdir(parents=True, exist_ok=True)
        f = d / f'{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")}.json'
        f.write_text(json.dumps(payload, indent=1) + '\n')
        return {'sent': False, 'sink': str(f), 'code': 'DISPATCH_TO_SINK'}

    repo = os.environ.get('GITHUB_REPOSITORY')
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not repo or not token:
        # NOT AN ERROR, AND NOT A SUCCESS EITHER. Outside Actions there is
        # nothing to dispatch to; say so plainly rather than pretending.
        return {'sent': False, 'code': 'DISPATCH_UNAVAILABLE',
                'detail': 'GITHUB_REPOSITORY/GITHUB_TOKEN are unset, so this '
                          'is not a GitHub Actions run. Nothing was sent.'}
    import urllib.error
    import urllib.request
    req = urllib.request.Request(
        f'{GITHUB_API}/repos/{repo}/dispatches',
        data=json.dumps(payload).encode(), method='POST',
        headers={'Accept': 'application/vnd.github+json',
                 'Authorization': f'Bearer {token}',
                 'X-GitHub-Api-Version': '2022-11-28',
                 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {'sent': True, 'code': f'DISPATCH_{r.status}',
                    'status': r.status}
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', 'replace')[:600]
        except Exception:                                    # noqa: BLE001
            pass
        hint = ''
        if exc.code == 403:
            # The one failure worth naming, because the remedy is a one-line
            # workflow change and the message alone does not say so.
            hint = (' -- the workflow needs `permissions: contents: write` '
                    'AND `actions: write` for the GITHUB_TOKEN to create a '
                    'repository_dispatch. If the org forces read-only '
                    'workflow permissions, a GitHub App installation token is '
                    'the next option; see AUTONOMY_SETUP.md.')
        return {'sent': False, 'code': f'DISPATCH_HTTP_{exc.code}',
                'detail': detail + hint}
    except Exception as exc:                                 # noqa: BLE001
        return {'sent': False, 'code': 'DISPATCH_FAILED',
                'detail': f'{type(exc).__name__}: {exc}'}


def open_escalation_issue(escalation, title, body) -> str:
    """Record an escalation. Returns where it went.

    The FILE is written unconditionally; the GitHub issue is best effort. An
    escalation that exists only as an API call nobody watched is an escalation
    that did not happen, so the durable record is a committed file and the
    issue is the notification on top of it.
    """
    d = S.COORD / 'ESCALATIONS'
    d.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    p = d / f'{stamp}-{escalation.value}.md'
    p.write_text(f'# {escalation.value}\n\n{title}\n\n{body}\n\n'
                 f'*The autonomous loop stopped here. It will not retry this '
                 f'on its own; a human changes something first.*\n')
    return str(p.relative_to(S.REPO))
