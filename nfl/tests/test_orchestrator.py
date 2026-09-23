"""The complete mocked state machine, driven end to end before a cent is spent.

WHAT THIS PROVES, AND WHAT IT DOES NOT

It proves the STATE MACHINE: that an engineering task reaches the Anthropic
worker and a research task reaches the Perplexity worker, that a return wakes
the owner worker, that an owner verdict moves the queue and releases the next
task, and that ten separate conditions each STOP the loop rather than being
reasoned past.

It proves nothing about model quality, and it is not trying to. A mocked
provider says what the fixture says. What is under test is everything around
the model -- which is where every failure this runtime is designed against
actually lives.

HOW IT IS SANDBOXED, AND WHY THAT MATTERS MORE THAN USUAL

Every test builds a throwaway git repository with its own coordination layer
and calls `state.rebind()` onto it. The writes, commits and queue transitions
are REAL; only the provider is mocked. A test that stubbed the writes would
prove the decisions and nothing about the effects, and the effects are where a
protected path gets written or a task executes twice.

The real repository is never touched. `test_a_the_sandbox_is_a_sandbox`
asserts that first, because if it were false every other result here would be
a lie told against the live tree.

Run standalone:  python3.12 nfl/tests/test_orchestrator.py
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from coordination.orchestrator import contracts as C            # noqa: E402
from coordination.orchestrator import dispatch as D             # noqa: E402
from coordination.orchestrator import github_runtime as G       # noqa: E402
from coordination.orchestrator import locks                     # noqa: E402
from coordination.orchestrator import main as M                 # noqa: E402
from coordination.orchestrator import openai_owner as OWN       # noqa: E402
from coordination.orchestrator import providers as P            # noqa: E402
from coordination.orchestrator import state as S                # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []
REAL_REPO = pathlib.Path(__file__).resolve().parents[2]
REAL_HEAD_AT_START = subprocess.run(
    ('git', 'rev-parse', 'HEAD'), cwd=REAL_REPO,
    capture_output=True, text=True).stdout.strip()


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  NOT_EXECUTED {label}  {why}')


# ------------------------------------------------------------- the sandbox
ENG_TASK = {
    'task_id': 'ENG-X1', 'title': 'a bounded engineering task',
    'status': 'AUTHORIZED', 'priority': 1, 'authorized': True,
    'depends_on': [], 'objective': 'do the bounded thing',
    'acceptance_tests': ['the thing is done', 'evidence is recorded'],
    'created_by': 'owner', 'result_path': None, 'commit_sha': None,
    'blocks': [], 'evidence': None,
}
RES_TASK = {
    'task_id': 'RES-X1', 'title': 'a bounded research task',
    'status': 'AUTHORIZED', 'priority': 1, 'authorized': True,
    'depends_on': [], 'objective': 'find out the bounded thing',
    'acceptance_tests': ['the question is answered or declared UNKNOWN'],
    'created_by': 'owner', 'result_path': None, 'commit_sha': None,
    'blocks': [], 'evidence': None,
}


def build_sandbox(*, eng=None, res=None, autonomy=True, policy_over=None):
    """A real git repo with a real coordination layer. Caller removes it."""
    root = pathlib.Path(tempfile.mkdtemp(prefix='orch-sandbox-'))
    coord = root / 'coordination'
    for d in ('CLAUDE_RETURNS', 'PERPLEXITY_RETURNS', 'CHATGPT_OUTBOX',
              'orchestrator'):
        (coord / d).mkdir(parents=True, exist_ok=True)

    real = REAL_REPO / 'coordination'
    shutil.copy(real / 'validate_coordination.py', coord)
    shutil.copy(real / '__init__.py', coord)
    # THE WHOLE PACKAGE, not just the fixtures. A subprocess launched inside
    # the sandbox then resolves every path from its own __file__ and touches
    # nothing of the real repository -- which is what makes the multi-pass
    # proof a proof rather than a simulation with shared state.
    for f in sorted((real / 'orchestrator').glob('*.py')):
        shutil.copy(f, coord / 'orchestrator')
    shutil.copytree(real / 'orchestrator' / 'mocks',
                    coord / 'orchestrator' / 'mocks')

    policy = json.loads((real / 'AUTOMATION_POLICY.json').read_text())
    policy['autonomous_operation_enabled'] = autonomy
    policy['branch_policy']['protected_branches'] = ['main']
    for k, v in (policy_over or {}).items():
        if isinstance(v, dict):
            policy.setdefault(k, {}).update(v)
        else:
            policy[k] = v
    (coord / 'AUTOMATION_POLICY.json').write_text(json.dumps(policy, indent=1))
    shutil.copy(real / 'orchestrator' / 'MODELS.json', coord / 'orchestrator')

    (coord / 'PROJECT_STATE.json').write_text(json.dumps(
        {'schema': 'project_state', 'schema_version': '1.0.0',
         'project': 'sandbox', 'head_commit': None, 'branch': 'sandbox'},
        indent=1))
    (coord / 'OWNER_DECISIONS.md').write_text(
        '# Owner decisions\n\n## D-01 sandbox\n\nA decision does not expire.\n')
    (coord / 'HANDOFF_LOG.jsonl').write_text('')

    # BOTH queues are seeded. The validator refuses an empty queue -- "an
    # empty queue reads like nothing to do and is indistinguishable from a
    # broken writer" -- and it is right to, so the sandbox supplies a DRAFT
    # placeholder where a test did not. DRAFT is never executable, so routing
    # is unaffected by its presence.
    def _placeholder(prefix):
        return [{'task_id': f'{prefix}-PLACEHOLDER',
                 'title': 'placeholder so the queue is not empty',
                 'status': 'DRAFT', 'priority': 999, 'authorized': False,
                 'depends_on': [], 'objective': 'none',
                 'acceptance_tests': ['none'], 'created_by': 'test',
                 'result_path': None, 'commit_sha': None, 'blocks': [],
                 'evidence': None}]

    eng = eng if eng else _placeholder('ENG')
    res = res if res else _placeholder('RES')
    for name, tasks in (('ENGINEERING_QUEUE.json', eng),
                        ('RESEARCH_QUEUE.json', res)):
        (coord / name).write_text(json.dumps(
            {'schema': 'task_queue', 'schema_version': '1.0.0',
             'written_at_utc': '2026-09-23T00:00:00Z', 'written_by': 'test',
             'status_vocabulary': ['DRAFT', 'AUTHORIZED', 'ACTIVE', 'BLOCKED',
                                   'RETURNED', 'COMPLETE', 'SUPERSEDED'],
             'execution_rule': 'authorized=true AND status=AUTHORIZED',
             'exclusive_active': name == 'ENGINEERING_QUEUE.json',
             'return_contract': ('coordination/CLAUDE_RETURNS/<task_id>.md'
                                 if name == 'ENGINEERING_QUEUE.json'
                                 else 'coordination/PERPLEXITY_RETURNS/'
                                      '<task_id>.md'),
             'tasks': [dict(t) for t in (tasks or [])]}, indent=1))

    for cmd in (('git', 'init', '-q', '-b', 'sandbox'),
                ('git', 'config', 'user.email', 'test@example.invalid'),
                ('git', 'config', 'user.name', 'sandbox'),
                ('git', 'add', '-A'),
                ('git', 'commit', '-q', '-m', 'sandbox')):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    # THE VALIDATOR ALSO CHECKS THAT A RECORDED SHA RESOLVES, so a fixture
    # cannot use a made-up one. Any task seeded with the placeholder gets the
    # sandbox's real first commit instead. This is the validator doing its
    # job: "a completed coding task with no commit SHA" and a SHA that names
    # no commit are both things it exists to refuse.
    real_sha = subprocess.run(('git', 'rev-parse', 'HEAD'), cwd=root,
                              capture_output=True, text=True).stdout.strip()
    for name in ('ENGINEERING_QUEUE.json', 'RESEARCH_QUEUE.json'):
        q = json.loads((coord / name).read_text())
        touched = False
        for t in q['tasks']:
            if t.get('commit_sha') == '0' * 40:
                t['commit_sha'] = real_sha
                touched = True
        if touched:
            (coord / name).write_text(json.dumps(q, indent=1))
    if any(json.loads((coord / n).read_text()) for n in
           ('ENGINEERING_QUEUE.json',)):
        subprocess.run(('git', 'add', '-A'), cwd=root, capture_output=True)
        subprocess.run(('git', 'commit', '-q', '--allow-empty',
                        '-m', 'sandbox seed'), cwd=root, capture_output=True)
    S.rebind(root)
    return root


def teardown(root):
    S.rebind(REAL_REPO)
    shutil.rmtree(root, ignore_errors=True)


def _env(mode='MOCK'):
    os.environ['AUTONOMY_MODE'] = mode
    os.environ['ORCHESTRATOR_PUSH'] = '0'     # a sandbox has no remote
    os.environ['ORCHESTRATOR_RUN_TESTS'] = '0'


def _fixture(root, worker, task_id, payload):
    """A per-task fixture inside the sandbox's own mocks directory."""
    d = root / 'coordination' / 'orchestrator' / 'mocks'
    (d / f'{worker}.{task_id}.json').write_text(json.dumps(payload, indent=1))
    P.MOCKS = d


def _owner_fixture(root, task_id, task, verdict='ACCEPT', **over):
    parsed = {
        'task_id': task_id, 'verdict': verdict,
        'reasoning': 'mock owner reasoning',
        'acceptance_test_verdicts': [
            {'test': t, 'satisfied': verdict == 'ACCEPT',
             'evidence': 'present in the return'}
            for t in task['acceptance_tests']],
        'escalation_reason': None, 'next_task_id': None, 'new_task': None,
        'research_request': None, 'project_state_updates': {},
        'directive': None}
    parsed.update(over)
    _fixture(root, 'openai', task_id, {'parsed': parsed,
                                       'usage': {'total_tokens': 100}})


# ==========================================================================
def test_a_the_sandbox_is_a_sandbox():
    """Asserted FIRST. Every other result below depends on it."""
    print('\nA. the sandbox does not touch the real repository')
    root = build_sandbox(eng=[ENG_TASK])
    try:
        check('the runtime is rebound onto the sandbox',
              S.REPO == root.resolve(), f'{S.REPO}')
        check('  and HEAD read through the runtime is the sandbox HEAD',
              S.head() != REAL_HEAD_AT_START and len(S.head()) == 40)
        check('  and the sandbox validates',
              S.snapshot().valid, S.snapshot().validator_output[:200])
    finally:
        teardown(root)
    now = subprocess.run(('git', 'rev-parse', 'HEAD'), cwd=REAL_REPO,
                         capture_output=True, text=True).stdout.strip()
    check('the real repository HEAD is untouched', now == REAL_HEAD_AT_START,
          f'{now[:12]} vs {REAL_HEAD_AT_START[:12]}')
    check('  and the runtime is rebound back to it', S.REPO == REAL_REPO)


def test_a2_no_function_default_binds_a_rebindable_path():
    """The bug that leaked a sandbox file into the live tree, twice.

    `def f(..., repo=S.REPO)` evaluates S.REPO ONCE, at import. `rebind` then
    moves it and the function keeps the stale value -- so a sandboxed call
    writes to the real repository while every assertion about the sandbox
    still passes. It happened in `state.git`, was fixed, and then happened
    again in `apply_patches` and `_relevant_files`, which is what makes it
    worth a standing check rather than a comment.

    A default of `None` resolved at call time is the fix; this refuses the
    pattern outright so the next one is caught at test time rather than by
    noticing a stray file in `git status`.
    """
    print('\nA2. no function default captures a rebindable module path')
    import inspect
    offenders = []
    for mod in (S, G, M, D, locks, P):
        src = pathlib.Path(inspect.getfile(mod)).read_text()
        for i, line in enumerate(src.splitlines(), 1):
            t = line.strip()
            if not t.startswith('def ') and '(' not in t:
                continue
            for pat in ('=S.REPO', '= S.REPO', '=S.COORD', '= S.COORD',
                        '=REPO,', '=REPO)', '=COORD,', '=COORD)',
                        '=S.RUNS', '=RUNS,', '=RUNS)'):
                if pat in t and t.startswith('def '):
                    offenders.append(f'{pathlib.Path(mod.__file__).name}:{i}'
                                     f' {t[:90]}')
    check('no signature default captures a path that rebind() moves',
          not offenders, '; '.join(offenders))


def test_b_an_engineering_task_routes_to_the_anthropic_worker():
    print('\nB. ENGINEERING -> Anthropic, and the return lands on contract')
    _env()
    root = build_sandbox(eng=[ENG_TASK])
    try:
        snap = S.snapshot()
        a = D.next_action(snap)
        check('the dispatcher selects it', a.kind == D.EXECUTE, str(a))
        check('  and routes it to ANTHROPIC',
              a.worker is C.Worker.ENGINEER, str(a.worker))
        _fixture(root, 'anthropic', 'ENG-X1', {
            'usage': {'total_tokens': 10},
            'parsed': {
                'task_id': 'ENG-X1', 'status': 'COMPLETED',
                'implementation_summary': 'did the bounded thing',
                'files_changed': ['demo.txt'],
                'patches': [{'path': 'demo.txt', 'contents': 'real bytes\n'}],
                'tests_run': [], 'test_results': 'n/a', 'failures': [],
                'blockers': [], 'recommended_next_step': 'owner review',
                'confidence_notes': 'fixture'}})
        ok, esc = M.do_execute(snap, a, S.head())
        check('  the pass completes', ok and esc is None, f'{ok} {esc}')
        rp = root / 'coordination' / 'CLAUDE_RETURNS' / 'ENG-X1.md'
        check('  the return is written to CLAUDE_RETURNS/<task_id>.md',
              rp.exists())
        if rp.exists():
            body = rp.read_text().lower()
            miss = [s for s in C.ENGINEER_RETURN_SECTIONS if s not in body]
            check('  carrying all eight contract sections', not miss,
                  str(miss))
        check('  the worker actually wrote its file',
              (root / 'demo.txt').read_text() == 'real bytes\n')
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        t = q['tasks'][0]
        check('  the task is RETURNED, not COMPLETE',
              t['status'] == 'RETURNED', t['status'])
        check('  the worker did NOT mark its own work accepted',
              t['status'] != 'COMPLETE')
        check('  a commit sha was recorded', bool(t.get('commit_sha')))
        runs = list((root / 'coordination' / 'runs').glob('*'))
        check('  the raw response is preserved under runs/', len(runs) == 1)
        if runs:
            for f in ('request.json', 'response.json', 'metadata.json',
                      'normalized_return.md'):
                check(f'    runs/<id>/{f}', (runs[0] / f).exists())
            meta = json.loads((runs[0] / 'metadata.json').read_text())
            for k in ('provider', 'model', 'timestamp_utc', 'task_id',
                      'request_sha256', 'response_sha256', 'head_before',
                      'idempotency_key'):
                check(f'    metadata records {k}', bool(meta.get(k)))
    finally:
        teardown(root)


def test_c_a_research_task_routes_to_the_perplexity_worker():
    print('\nC. RESEARCH -> Perplexity, with a machine-readable source registry')
    _env()
    root = build_sandbox(res=[RES_TASK])
    try:
        snap = S.snapshot()
        a = D.next_action(snap)
        check('routed to PERPLEXITY', a.worker is C.Worker.RESEARCH, str(a))
        P.MOCKS = root / 'coordination' / 'orchestrator' / 'mocks'
        _fixture(root, 'perplexity', 'RES-X1', json.loads(
            (P.MOCKS / 'perplexity.default.json').read_text()
        ) | {'parsed': json.loads(
            (P.MOCKS / 'perplexity.default.json').read_text()
        )['parsed'] | {'task_id': 'RES-X1'}})
        ok, esc = M.do_execute(snap, a, S.head())
        check('  the pass completes', ok and esc is None, f'{ok} {esc}')
        rp = root / 'coordination' / 'PERPLEXITY_RETURNS' / 'RES-X1.md'
        check('  the return lands in PERPLEXITY_RETURNS/', rp.exists())
        if rp.exists():
            body = rp.read_text()
            check('    UNKNOWN is preserved as UNKNOWN, not upgraded',
                  'UNKNOWN' in body)
            check('    a null publication time stays NULL',
                  'NULL' in body)
        runs = list((root / 'coordination' / 'runs').glob('*'))
        check('  a sources.json registry is written',
              bool(runs) and (runs[0] / 'sources.json').exists())
        if runs and (runs[0] / 'sources.json').exists():
            reg = json.loads((runs[0] / 'sources.json').read_text())
            check('    with one record per claim',
                  len(reg['claims']) == 2, str(len(reg['claims'])))
    finally:
        teardown(root)


def test_d_a_return_wakes_the_owner_and_the_verdict_moves_the_queue():
    print('\nD. a RETURNED task wakes the owner worker; ACCEPT -> COMPLETE')
    _env()
    # A RETURNED task with no commit_sha is refused by the validator --
    # "a completed coding task has no commit SHA" is one of the six things it
    # was built to catch -- so the fixture carries one.
    t = dict(ENG_TASK, status='RETURNED', commit_sha='0' * 40,
             result_path='coordination/CLAUDE_RETURNS/ENG-X1.md')
    root = build_sandbox(eng=[t])
    try:
        (root / 'coordination' / 'CLAUDE_RETURNS' / 'ENG-X1.md').write_text(
            '# ENG-X1\n\nwork performed\nevidence\ntests\nfailures\n'
            'changed files\ncommit sha\nblockers\nrecommended next action\n')
        snap = S.snapshot()
        a = D.next_action(snap)
        check('the dispatcher chooses OWNER_REVIEW',
              a.kind == D.OWNER_REVIEW, str(a))
        check('  routed to OPENAI', a.worker is C.Worker.OWNER)
        _owner_fixture(root, 'ENG-X1', t, 'ACCEPT')
        ok, esc = M.do_owner_review(snap, a, S.head())
        check('  the review completes', ok and esc is None, f'{ok} {esc}')
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        check('  ACCEPT moved the task to COMPLETE',
              q['tasks'][0]['status'] == 'COMPLETE', q['tasks'][0]['status'])
        body = (root / 'coordination' / 'CLAUDE_RETURNS'
                / 'ENG-X1.md').read_text()
        check('  the verdict is appended to the return, not substituted for it',
              'work performed' in body and 'Owner review' in body)
    finally:
        teardown(root)


def test_e_owner_authorization_releases_the_next_task():
    """The handoff the whole system exists for."""
    print('\nE. owner ACCEPT + authorize -> the next task becomes runnable')
    _env()
    done = dict(ENG_TASK, status='RETURNED', commit_sha='0' * 40,
                result_path='coordination/CLAUDE_RETURNS/ENG-X1.md')
    nxt = dict(ENG_TASK, task_id='ENG-X2', title='the next one',
               status='DRAFT', authorized=False, priority=2)
    root = build_sandbox(eng=[done, nxt])
    try:
        (root / 'coordination' / 'CLAUDE_RETURNS' / 'ENG-X1.md').write_text(
            '# ENG-X1\n\nwork performed evidence tests failures changed files '
            'commit sha blockers recommended next action\n')
        snap = S.snapshot()
        check('ENG-X2 is NOT runnable while it is DRAFT',
              'ENG-X2' not in [t['task_id'] for _n, t in snap.executable()])
        _owner_fixture(root, 'ENG-X1', done, 'ACCEPT', next_task_id='ENG-X2')
        ok, esc = M.do_owner_review(snap, D.next_action(snap), S.head())
        check('  the review completes', ok and esc is None, f'{ok} {esc}')
        after = S.snapshot()
        ids = [t['task_id'] for _n, t in after.executable()]
        check('  ENG-X2 is now AUTHORIZED and runnable', 'ENG-X2' in ids,
              str(ids))
        a = D.next_action(after)
        check('  and the very next action dispatches it, with no human step',
              a.kind == D.EXECUTE and a.task_id == 'ENG-X2', str(a))
    finally:
        teardown(root)


def test_f_a_duplicate_event_does_not_execute_twice():
    print('\nF. the same call in the same state is made once')
    _env()
    root = build_sandbox(eng=[ENG_TASK])
    try:
        snap = S.snapshot()
        call = C.WorkerCall(worker=C.Worker.ENGINEER, model='m',
                            task_id='ENG-X1', prompt_sha256='p',
                            head_before=snap.head, attempt=0)
        check('a fresh key is not a duplicate',
              call.idempotency_key not in snap.idempotency_keys())
        G.append_log({'actor': 'test', 'run_id': 'r1', 'task_id': 'ENG-X1',
                      'idempotency_key': call.idempotency_key})
        snap2 = S.snapshot()
        try:
            locks.require_not_duplicate(snap2, call)
            check('the second identical call is refused', False,
                  'it was allowed through')
        except locks.Refusal as r:
            check('the second identical call is REFUSED by name',
                  r.code == 'DUPLICATE_RUN', r.code)
        other = C.WorkerCall(worker=C.Worker.ENGINEER, model='m',
                             task_id='ENG-X1', prompt_sha256='p',
                             head_before=snap.head, attempt=1)
        check('  but a genuine retry (attempt 1) has a different key',
              other.idempotency_key != call.idempotency_key)
    finally:
        teardown(root)


def test_g_a_racing_runner_loses_rather_than_clobbers():
    print('\nG. optimistic HEAD check: the loser abandons its write')
    _env()
    root = build_sandbox(eng=[ENG_TASK])
    try:
        observed = S.head()
        (root / 'raced.txt').write_text('another runner got here first\n')
        subprocess.run(('git', 'add', '-A'), cwd=root, capture_output=True)
        subprocess.run(('git', 'commit', '-q', '-m', 'raced'), cwd=root,
                       capture_output=True)
        check('HEAD moved under us', S.head() != observed)
        try:
            G.commit_and_push('would clobber', observed, push=False)
            check('the write is abandoned', False, 'it committed anyway')
        except locks.Refusal as r:
            check('the write is ABANDONED by name', r.code == 'HEAD_MOVED',
                  r.code)
    finally:
        teardown(root)


def test_h_every_stop_condition_actually_stops():
    """Ten conditions, each one asserted to halt the loop."""
    print('\nH. the stop conditions')
    _env()

    # 1. malformed state
    root = build_sandbox(eng=[ENG_TASK])
    try:
        (root / 'coordination' / 'ENGINEERING_QUEUE.json').write_text('{oops')
        try:
            snap = S.snapshot()
            a = D.next_action(snap)
            check('malformed queue stops', a.kind == D.STOP, str(a))
        except S.StateError:
            check('malformed queue stops (unreadable state raises)', True)
    finally:
        teardown(root)

    # 2. contradictory state -- two ACTIVE engineering tasks
    root = build_sandbox(eng=[dict(ENG_TASK, status='ACTIVE'),
                              dict(ENG_TASK, task_id='ENG-X2',
                                   status='ACTIVE', priority=2)])
    try:
        a = D.next_action(S.snapshot())
        check('two ACTIVE tasks stop the loop', a.kind == D.STOP, str(a))
        check('  as STATE_CONTRADICTORY',
              a.escalation is C.Escalation.STATE_CONTRADICTORY,
              str(a.escalation))
    finally:
        teardown(root)

    # 3. autonomy disabled
    root = build_sandbox(eng=[ENG_TASK], autonomy=False)
    try:
        a = D.next_action(S.snapshot())
        check('the kill switch stops the loop', a.kind == D.STOP, str(a))
    finally:
        teardown(root)

    # 4. nothing authorized
    root = build_sandbox(eng=[dict(ENG_TASK, status='DRAFT',
                                   authorized=False)])
    try:
        a = D.next_action(S.snapshot())
        check('nothing authorized stops, benignly', a.kind == D.STOP
              and a.escalation is C.Escalation.NOTHING_AUTHORIZED, str(a))
    finally:
        teardown(root)

    # 5. transition budget
    root = build_sandbox(eng=[ENG_TASK])
    try:
        a = D.next_action(S.snapshot(), transitions_used=3)
        check('the transition budget stops the loop',
              a.escalation is C.Escalation.TRANSITION_BUDGET_SPENT, str(a))
    finally:
        teardown(root)

    # 6. retry limit
    root = build_sandbox(eng=[ENG_TASK],
                         policy_over={'limits': {'max_retries_per_task': 1}})
    try:
        # An attempt is a KEYED worker call, not an ACTIVE transition -- see
        # Snapshot.attempts. The fixture has to look like the real thing.
        for i in range(3):
            G.append_log({'actor': 'test', 'task_id': 'ENG-X1',
                          'to_status': 'ACTIVE', 'run_id': f'r{i}',
                          'idempotency_key': f'k{i}' + '0' * 30})
        a = D.next_action(S.snapshot())
        check('the retry limit stops the loop', a.kind == D.STOP, str(a))
        check('  as REPEATED_AGENT_FAILURE',
              a.escalation is C.Escalation.REPEATED_AGENT_FAILURE,
              str(a.escalation))
    finally:
        teardown(root)

    # 7. rate limit
    root = build_sandbox(eng=[ENG_TASK],
                         policy_over={'limits': {'max_runs_per_hour': 1}})
    try:
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for i in range(2):
            G.append_log({'actor': 'test', 'run_id': f'q{i}',
                          'timestamp': now})
        a = D.next_action(S.snapshot())
        check('the hourly rate cap stops the loop',
              a.escalation is C.Escalation.COST_LIMIT_REACHED, str(a))
    finally:
        teardown(root)

    # 8. missing secret, in LIVE mode
    root = build_sandbox(eng=[ENG_TASK])
    try:
        env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}
        try:
            locks.require_secret(env, 'ANTHROPIC_API_KEY', C.Worker.ENGINEER)
            check('a missing secret stops', False, 'it returned a key')
        except locks.Refusal as r:
            check('a missing secret STOPS by name',
                  r.code == 'SECRET_MISSING', r.code)
            check('  and does NOT fall back to a mock',
                  r.escalation is C.Escalation.SECRET_MISSING)
    finally:
        teardown(root)

    # 9. an owner-only decision
    root = build_sandbox(eng=[ENG_TASK])
    try:
        for attempt in ('we should promote Q9 now',
                        'authorize NFL-1 next',
                        'V2 is earned by this result',
                        'enable real money for week 4'):
            try:
                locks.enforce_reserved_decisions(attempt, 'OPENAI owner')
                check(f'reserved decision refused: {attempt[:28]!r}', False,
                      'it was allowed')
            except locks.Refusal as r:
                check(f'reserved decision REFUSED: {attempt[:28]!r}',
                      r.code == 'RESERVED_DECISION_ATTEMPTED'
                      and r.escalation is C.Escalation.OWNER_DECISION_REQUIRED)
    finally:
        teardown(root)

    # 10. a protected path in a worker's diff
    root = build_sandbox(eng=[ENG_TASK])
    try:
        for path in ('coordination/OWNER_DECISIONS.md',
                     'coordination/ENGINEERING_QUEUE.json',
                     'nfl/production/review/gate.py',
                     '.github/workflows/agent-orchestrator.yml',
                     'coordination/AUTOMATION_POLICY.json'):
            try:
                G.apply_patches([{'path': path, 'contents': 'x'}],
                                C.Worker.ENGINEER)
                check(f'protected path refused: {path}', False, 'it wrote')
            except locks.Refusal as r:
                check(f'protected path REFUSED: {path}',
                      r.code == 'PROTECTED_PATH_WRITTEN')
        check('  and nothing was written before the refusal',
              not (root / 'coordination' / 'OWNER_DECISIONS.md'
                   ).read_text().startswith('x'))
    finally:
        teardown(root)


def test_i_a_worker_cannot_self_authorize():
    print('\nI. a created task arrives DRAFT, whatever the worker asked for')
    _env()
    root = build_sandbox(eng=[ENG_TASK])
    try:
        rec = G.add_task('ENGINEERING_QUEUE.json', {
            'task_id': 'ENG-NEW', 'title': 'invented',
            'objective': 'something', 'acceptance_tests': ['a test'],
            'status': 'AUTHORIZED', 'authorized': True, 'priority': 1})
        check('status is forced to DRAFT', rec['status'] == 'DRAFT',
              rec['status'])
        check('  and authorized is forced false',
              rec['authorized'] is False)
        check('  so it is not runnable',
              'ENG-NEW' not in [t['task_id']
                                for _n, t in S.snapshot().executable()])
        for bad in ({'task_id': 'X', 'title': 't', 'objective': 'o'},
                    {'task_id': 'Y', 'title': 't', 'objective': 'o',
                     'acceptance_tests': []}):
            try:
                locks.enforce_bounded_task(bad)
                check('an unbounded task is refused', False, str(bad))
            except locks.Refusal as r:
                check('an unbounded task is REFUSED',
                      r.code == 'TASK_NOT_BOUNDED')
    finally:
        teardown(root)


def test_j_a_failed_or_malformed_worker_call_is_never_a_success():
    print('\nJ. absent, empty and malformed responses are all failures')
    _env()
    # Four deliberate failures in a row, so the retry budget is raised for
    # this sandbox only. The budget itself is under test in H.
    root = build_sandbox(eng=[ENG_TASK],
                         policy_over={'limits': {'max_retries_per_task': 9}})
    try:
        snap = S.snapshot()
        a = D.next_action(snap)

        # a fixture that describes an API failure
        _fixture(root, 'anthropic', 'ENG-X1',
                 {'simulate_failure': True, 'code': 'API_TIMEOUT',
                  'detail': 'provider did not answer'})
        ok, esc = M.do_execute(snap, a, S.head())
        check('a timeout is recorded as a failure', not ok, f'{ok}')
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        check('  and the task is NOT marked RETURNED',
              q['tasks'][0]['status'] != 'RETURNED', q['tasks'][0]['status'])
        check('  the raw failure is still preserved',
              len(list((root / 'coordination' / 'runs').glob('*'))) == 1)

        # a structurally malformed return: claims a file it did not patch
        _fixture(root, 'anthropic', 'ENG-X1', {'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 's', 'files_changed': ['ghost.py'],
            'patches': [], 'tests_run': [], 'test_results': '',
            'failures': [], 'blockers': [], 'recommended_next_step': 'n'}})
        snap = S.snapshot()
        ok, esc = M.do_execute(snap, D.next_action(snap), S.head())
        check('a claimed change with no bytes is a failure', not ok)
        check('  and ghost.py was not created',
              not (root / 'ghost.py').exists())

        # an empty response
        _fixture(root, 'anthropic', 'ENG-X1', {'parsed': {}})
        snap = S.snapshot()
        ok, esc = M.do_execute(snap, D.next_action(snap), S.head())
        check('an empty parsed body is a failure', not ok)

        # a missing fixture is not an empty success either
        (root / 'coordination' / 'orchestrator' / 'mocks'
         / 'anthropic.ENG-X1.json').unlink()
        (root / 'coordination' / 'orchestrator' / 'mocks'
         / 'anthropic.default.json').unlink()
        snap = S.snapshot()
        ok, esc = M.do_execute(snap, D.next_action(snap), S.head())
        check('a missing fixture is a failure, not a blank pass', not ok)
    finally:
        teardown(root)


def test_k_the_owner_cannot_accept_what_it_did_not_judge():
    print('\nK. owner review contract')
    _env()
    t = dict(ENG_TASK, status='RETURNED', commit_sha='0' * 40,
             result_path='coordination/CLAUDE_RETURNS/ENG-X1.md')
    root = build_sandbox(eng=[t])
    try:
        (root / 'coordination' / 'CLAUDE_RETURNS' / 'ENG-X1.md').write_text('x')
        snap = S.snapshot()
        a = D.next_action(snap)

        _owner_fixture(root, 'ENG-X1', t, 'ACCEPT',
                       acceptance_test_verdicts=[
                           {'test': 'the thing is done', 'satisfied': True,
                            'evidence': 'e'}])
        ok, _e = M.do_owner_review(snap, a, S.head())
        check('ACCEPT judging 1 of 2 tests is refused', not ok)

        _owner_fixture(root, 'ENG-X1', t, 'ACCEPT')
        parsed = json.loads((root / 'coordination' / 'orchestrator' / 'mocks'
                             / 'openai.ENG-X1.json').read_text())
        parsed['parsed']['acceptance_test_verdicts'][0]['satisfied'] = False
        (root / 'coordination' / 'orchestrator' / 'mocks'
         / 'openai.ENG-X1.json').write_text(json.dumps(parsed))
        snap = S.snapshot()
        ok, _e = M.do_owner_review(snap, D.next_action(snap), S.head())
        check('ACCEPT with an unsatisfied test is refused', not ok)

        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        check('  and the task never reached COMPLETE',
              q['tasks'][0]['status'] != 'COMPLETE', q['tasks'][0]['status'])

        # RETURN_FOR_CORRECTION puts it back in the queue, not in the bin.
        _owner_fixture(root, 'ENG-X1', t, 'RETURN_FOR_CORRECTION')
        snap = S.snapshot()
        ok, _e = M.do_owner_review(snap, D.next_action(snap), S.head())
        check('RETURN_FOR_CORRECTION is accepted as a verdict', ok)
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        check('  and the task goes back to AUTHORIZED',
              q['tasks'][0]['status'] == 'AUTHORIZED', q['tasks'][0]['status'])
    finally:
        teardown(root)


def test_l_the_full_chain_runs_with_no_human_step():
    """THE SUCCESS CONDITION, asserted rather than described.

    research -> owner review -> engineering -> owner review -> next task,
    with the only inputs being repository state and fixtures.
    """
    print('\nL. the whole chain, end to end, no human in the middle')
    _env()
    res = dict(RES_TASK, priority=1)
    eng = dict(ENG_TASK, status='DRAFT', authorized=False, priority=2)
    nxt = dict(ENG_TASK, task_id='ENG-X2', title='the one after',
               status='DRAFT', authorized=False, priority=3)
    root = build_sandbox(res=[res], eng=[eng, nxt])
    try:
        P.MOCKS = root / 'coordination' / 'orchestrator' / 'mocks'
        base = json.loads((P.MOCKS / 'perplexity.default.json').read_text())
        base['parsed']['task_id'] = 'RES-X1'
        _fixture(root, 'perplexity', 'RES-X1', base)
        _owner_fixture(root, 'RES-X1', res, 'ACCEPT', next_task_id='ENG-X1')
        _fixture(root, 'anthropic', 'ENG-X1', {'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 'implemented it',
            'files_changed': ['chain.txt'],
            'patches': [{'path': 'chain.txt', 'contents': 'chain\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'review'}})
        _owner_fixture(root, 'ENG-X1', eng, 'ACCEPT', next_task_id='ENG-X2')

        seen = []
        for step in range(5):
            snap = S.snapshot()
            a = D.next_action(snap)
            if a.kind == D.STOP:
                seen.append(('STOP', str(a.escalation)))
                break
            seen.append((a.kind, a.worker.value, a.task_id))
            if a.kind == D.OWNER_REVIEW:
                ok, _e = M.do_owner_review(snap, a, S.head())
            else:
                ok, _e = M.do_execute(snap, a, S.head())
            if not ok:
                seen.append(('FAILED', a.task_id))
                break

        for s in seen:
            print(f'       {s}')
        expected = [
            ('EXECUTE', 'PERPLEXITY', 'RES-X1'),
            ('OWNER_REVIEW', 'OPENAI', 'RES-X1'),
            ('EXECUTE', 'ANTHROPIC', 'ENG-X1'),
            ('OWNER_REVIEW', 'OPENAI', 'ENG-X1'),
            ('EXECUTE', 'ANTHROPIC', 'ENG-X2'),
        ]
        check('research -> owner -> engineering -> owner -> next task',
              seen[:5] == expected, f'{seen}')
        check('  every transition came from repository state alone',
              len(seen) >= 5)
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        by = {t['task_id']: t['status'] for t in q['tasks']}
        check('  ENG-X1 ended COMPLETE', by.get('ENG-X1') == 'COMPLETE',
              str(by))
        n_commits = int(subprocess.run(
            ('git', 'rev-list', '--count', 'HEAD'), cwd=root,
            capture_output=True, text=True).stdout.strip() or 0)
        check('  and each transition left its own commit', n_commits >= 5,
              f'{n_commits} commit(s)')
    finally:
        teardown(root)


def test_m_the_chain_continues_by_explicit_dispatch_across_fresh_passes():
    """THE LIVE-READINESS PROOF. Three passes, three processes, no human.

    WHY THIS TEST HAD TO EXIST. The runtime originally assumed the loop would
    sustain itself through push events: commit, push, push event, next run.
    GitHub does not start a workflow from a push made with GITHUB_TOKEN --
    documented behaviour, specifically to stop workflows recursing. The chain
    would have run ONCE and stopped, and every in-process test would still
    have passed, because in-process tests never cross a workflow boundary.

    So this test crosses one. Each pass is a SEPARATE PYTHON PROCESS launched
    inside the sandbox checkout, sharing nothing with the last but the
    repository. Between passes the only thing carried forward is a dispatch
    request the previous pass wrote -- exactly what repository_dispatch
    delivers. If a pass does not ask for a successor, the chain stops, and the
    test would see it stop.

    Pass 1  engineering task executes, commits, asks for a continuation
    Pass 2  owner review executes, commits, asks for a continuation
    Pass 3  the next authorized task is selected

    Nothing triggers a pass except the previous pass's request.
    """
    print('\nM. multi-pass continuation, one process per pass')
    _env()
    eng = dict(ENG_TASK)
    nxt = dict(ENG_TASK, task_id='ENG-X2', title='the one after',
               status='DRAFT', authorized=False, priority=2)
    root = build_sandbox(eng=[eng, nxt])
    sink = root / '_dispatch'
    try:
        mocks = root / 'coordination' / 'orchestrator' / 'mocks'
        (mocks / 'anthropic.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 'implemented it',
            'files_changed': ['chain.txt'],
            'patches': [{'path': 'chain.txt', 'contents': 'chain\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'review'}}))
        (mocks / 'openai.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'verdict': 'ACCEPT',
            'reasoning': 'both acceptance tests are evidenced in the return',
            'acceptance_test_verdicts': [
                {'test': t, 'satisfied': True, 'evidence': 'in the return'}
                for t in eng['acceptance_tests']],
            'escalation_reason': None, 'next_task_id': 'ENG-X2',
            'new_task': None, 'research_request': None,
            'project_state_updates': {}, 'directive': None}}))
        (mocks / 'anthropic.ENG-X2.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X2', 'status': 'COMPLETED',
            'implementation_summary': 'the one after',
            'files_changed': ['chain2.txt'],
            'patches': [{'path': 'chain2.txt', 'contents': 'chain2\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'review'}}))

        env = dict(os.environ,
                   AUTONOMY_MODE='MOCK', ORCHESTRATOR_PUSH='0',
                   ORCHESTRATOR_RUN_TESTS='0',
                   ORCHESTRATOR_DISPATCH_SINK=str(sink),
                   PYTHONPATH=str(root))

        passes, triggered_by = [], 'the test, once'
        for n in range(1, 4):
            before = set(p.name for p in sink.glob('*.json')) \
                if sink.exists() else set()
            r = subprocess.run(
                ('python3.12', 'coordination/orchestrator/main.py', '--max', '1'),
                cwd=root, env=env, capture_output=True, text=True, timeout=180)
            out = r.stdout + r.stderr
            line = [ln for ln in out.splitlines() if ln.startswith('[1/')]
            passes.append({'n': n, 'rc': r.returncode,
                           'action': line[0] if line else '(no action line)',
                           'triggered_by': triggered_by,
                           'continued': 'continuation:' in out})
            print(f'       pass {n} (triggered by {triggered_by}): '
                  f'{passes[-1]["action"][:92]}')
            new_dispatch = (set(p.name for p in sink.glob('*.json')) - before) \
                if sink.exists() else set()
            if not new_dispatch:
                print(f'       pass {n} requested NO continuation -- '
                      f'chain ends')
                break
            d = json.loads((sink / sorted(new_dispatch)[-1]).read_text())
            check(f'pass {n} emitted a repository_dispatch',
                  d['event_type'] == 'agent-orchestrator-continue',
                  d['event_type'])
            cp = d['client_payload']
            check(f'  its payload carries no project state',
                  set(cp) == {'branch', 'requested_by_run', 'observed_head',
                              'chain_depth', 'reason', 'task_id', 'note'},
                  str(sorted(cp)))
            # THE PROPERTY, STATED PRECISELY. My first cut grepped the
            # payload for words like "authorized" and fired on the `reason`
            # sentence -- "the highest-priority authorized executable task" --
            # which is a human-readable trace string and is meant to be there.
            # What actually matters is that nothing STRUCTURED rides along:
            # no task record, no queue fragment, no nested object the next
            # pass could mistake for state. Every value is a flat scalar.
            nested = {k: type(v).__name__ for k, v in cp.items()
                      if isinstance(v, (dict, list))}
            check(f'  every payload value is a flat scalar -- no record '
                  f'travels with the event', not nested, str(nested))
            check(f'  and the reason is a trace string, not a decision',
                  isinstance(cp.get('reason'), str)
                  and len(cp['reason']) <= 200)
            triggered_by = f'pass {n}\'s dispatch'

        for pdata in passes:
            print(f'       -> {pdata}')
        check('three passes ran', len(passes) == 3, str(len(passes)))
        if len(passes) < 3:
            return
        check('  pass 1 executed the engineering task via ANTHROPIC',
              'EXECUTE ENG-X1 via ANTHROPIC' in passes[0]['action'],
              passes[0]['action'])
        check('  pass 1 asked for the next pass', passes[0]['continued'])
        check('  pass 2 was triggered by that dispatch, not by a human',
              passes[1]['triggered_by'] == "pass 1's dispatch")
        check('  pass 2 ran the OWNER review',
              'OWNER_REVIEW ENG-X1 via OPENAI' in passes[1]['action'],
              passes[1]['action'])
        check('  pass 2 asked for the next pass', passes[1]['continued'])
        check('  pass 3 was triggered by that dispatch, not by a human',
              passes[2]['triggered_by'] == "pass 2's dispatch")
        check('  pass 3 selected the NEXT authorized task',
              'ENG-X2' in passes[2]['action'], passes[2]['action'])
        check('  no manual trigger occurred after the first',
              [p['triggered_by'] for p in passes[1:]]
              == ["pass 1's dispatch", "pass 2's dispatch"])

        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        by = {t['task_id']: t['status'] for t in q['tasks']}
        check('  ENG-X1 reached COMPLETE through the chain',
              by.get('ENG-X1') == 'COMPLETE', str(by))
        check('  and ENG-X2 was authorized by the owner worker, not by itself',
              by.get('ENG-X2') in ('ACTIVE', 'RETURNED'), str(by))
    finally:
        teardown(root)


def test_n_a_pass_that_changed_nothing_does_not_ask_for_another():
    """The condition that stops a dispatch chain spinning on itself."""
    print('\nN. no committed transition -> no continuation')
    _env()
    root = build_sandbox(eng=[dict(ENG_TASK, status='DRAFT',
                                   authorized=False)])
    sink = root / '_dispatch'
    try:
        env = dict(os.environ, AUTONOMY_MODE='MOCK', ORCHESTRATOR_PUSH='0',
                   ORCHESTRATOR_RUN_TESTS='0',
                   ORCHESTRATOR_DISPATCH_SINK=str(sink),
                   PYTHONPATH=str(root))
        r = subprocess.run(
            ('python3.12', 'coordination/orchestrator/main.py'),
            cwd=root, env=env, capture_output=True, text=True, timeout=120)
        check('the pass stops on NOTHING_AUTHORIZED',
              'NOTHING_AUTHORIZED' in (r.stdout + r.stderr), r.stdout[-300:])
        check('  and emitted no dispatch',
              not sink.exists() or not list(sink.glob('*.json')))

        # And the kill switch: armed state, but autonomy off.
        teardown(root)
        root2 = build_sandbox(eng=[ENG_TASK], autonomy=False)
        env['PYTHONPATH'] = str(root2)
        sink2 = root2 / '_dispatch'
        env['ORCHESTRATOR_DISPATCH_SINK'] = str(sink2)
        r2 = subprocess.run(
            ('python3.12', 'coordination/orchestrator/main.py'),
            cwd=root2, env=env, capture_output=True, text=True, timeout=120)
        check('a disabled kill switch stops the pass',
              'autonomous_operation_enabled=false' in (r2.stdout + r2.stderr))
        check('  and emits no dispatch',
              not sink2.exists() or not list(sink2.glob('*.json')))
        teardown(root2)
        root = None
    finally:
        if root is not None:
            teardown(root)


def test_o_the_continuation_budget_ends_the_chain():
    print('\nO. the continuation chain is bounded from the LOG')
    _env()
    root = build_sandbox(eng=[ENG_TASK],
                         policy_over={'limits':
                                      {'max_continuations_per_hour': 2}})
    try:
        for i in range(2):
            G.append_log({'actor': 'orchestrator',
                          'event': 'CONTINUATION_REQUESTED',
                          'note': f'prior chain link {i}'})
        snap = S.snapshot()
        try:
            locks.require_continuation_budget(snap)
            check('the continuation budget refuses', False, 'it allowed one')
        except locks.Refusal as r:
            check('the continuation budget REFUSES by name',
                  r.code == 'CONTINUATION_BUDGET_SPENT', r.code)
            check('  as a cost escalation',
                  r.escalation is C.Escalation.COST_LIMIT_REACHED)
            check('  counted from the log, not from a payload',
                  r.evidence.get('used') == 2, str(r.evidence))
    finally:
        teardown(root)


def test_p_the_transport_sends_only_parameters_each_model_accepts():
    """The defect no mock could have found.

    Both current flagship reasoning models REJECT sampling parameters rather
    than ignoring them: claude-opus-5 removed temperature/top_p/top_k, and
    gpt-5.6-sol returns 400 "Only the default (1) value is supported". The
    first transport hard-coded temperature=0 for all three providers and
    max_tokens for the two chat-completions ones, so every live call would
    have failed on its first request while the entire mocked suite stayed
    green. A fixture answers whatever it is told to.
    """
    print('\nP. per-model request parameters')
    models = json.loads((REAL_REPO / 'coordination' / 'orchestrator'
                         / 'MODELS.json').read_text())
    for key, provider, must, forbidden in (
            ('owner_model', 'openai',
             ('max_completion_tokens',), ('temperature', 'max_tokens')),
            ('engineering_model', 'anthropic',
             ('max_tokens', 'system'), ('temperature', 'top_p', 'top_k')),
            ('research_model', 'perplexity', ('max_tokens',), ())):
        cfg = models[key]
        body = P._request_body(cfg['provider'], cfg, 'SYS', 'USER')
        check(f'{cfg["model"]} is on the {provider} provider',
              cfg['provider'] == provider, cfg['provider'])
        for k in must:
            check(f'  sends {k}', k in body, str(sorted(body)))
        for k in forbidden:
            check(f'  does NOT send {k} (the API rejects it)',
                  k not in body, f'{k} present -> guaranteed HTTP 400')
    check('the owner model id is the verified flagship',
          models['owner_model']['model'] == 'gpt-5.6-sol',
          models['owner_model']['model'])
    check('the engineering model id carries no date suffix',
          models['engineering_model']['model'] == 'claude-opus-5',
          models['engineering_model']['model'])
    check('an unknown endpoint refuses rather than guessing',
          'chat_completions' in P.ENDPOINTS and 'messages' in P.ENDPOINTS)


#: Obviously-fake placeholders. LIVE checks that a key is PRESENT before it
#: calls, which is correct -- a missing key must stop a LIVE pass rather than
#: silently fall back to a fixture. To exercise everything after that gate the
#: test must satisfy it, so it supplies values that are unmistakably not
#: credentials. They never leave the process: `providers.SPY` intercepts
#: before the request is built into a connection, so nothing is ever sent
#: anywhere, and no real secret exists in this repository to leak.
FAKE_KEYS = {'ANTHROPIC_API_KEY': 'not-a-real-key-test-only',
             'OPENAI_API_KEY': 'not-a-real-key-test-only',
             'PERPLEXITY_API_KEY': 'not-a-real-key-test-only'}


def _with_fake_keys():
    os.environ.update(FAKE_KEYS)


def _without_fake_keys():
    for k in FAKE_KEYS:
        os.environ.pop(k, None)


def _spy_pass(root, which, policy_over=None):
    """One orchestration pass with provider calls RECORDED, never sent.

    Returns (list of intended LIVE calls, the action string). The policy is
    re-read from disk each time, exactly as a fresh workflow pass would.
    """
    import copy
    coord = root / 'coordination'
    if policy_over:
        pol = json.loads((coord / 'AUTOMATION_POLICY.json').read_text())
        pol.update(policy_over)
        (coord / 'AUTOMATION_POLICY.json').write_text(json.dumps(pol, indent=1))
    snap = S.snapshot()
    action = D.next_action(snap)
    P.SPY = []
    try:
        if action.kind == D.OWNER_REVIEW:
            M.do_owner_review(snap, action, S.head())
        elif action.kind == D.EXECUTE:
            M.do_execute(snap, action, S.head())
        spied = copy.deepcopy(P.SPY)
    finally:
        P.SPY = None
    return spied, str(action)


def test_q_live_authority_comes_from_protected_policy_not_the_payload():
    """THE MODE-AUTHORITY PROOF. No money is spent to run it.

    WHAT WAS WRONG. The dispatcher let a human pick LIVE at startup and then
    downgraded every continuation to MOCK, because trusting the event payload
    would let anyone who can open a dispatch spend money. The refusal was
    right and the LOCATION was wrong: it also meant LIVE could not survive its
    own first continuation, so the system proved autonomous EVENT continuation
    and not autonomous LIVE continuation.

    Authority now lives in AUTOMATION_POLICY.json on the automation branch --
    a protected path no worker may write. LIVE requires
    autonomous_operation_enabled AND execution_mode=LIVE AND a LIVE request;
    the request can only restrict, never escalate, and no payload field
    appears anywhere in that decision.

    `providers.SPY` records what WOULD have been sent and returns the fixture,
    so three passes of real LIVE semantics cost nothing.
    """
    print('\nQ. LIVE persists across continuations, and only policy grants it')
    _env()
    eng = dict(ENG_TASK)
    nxt = dict(ENG_TASK, task_id='ENG-X2', title='the one after',
               status='DRAFT', authorized=False, priority=2)
    root = build_sandbox(eng=[eng, nxt],
                         policy_over={'execution_mode': 'LIVE'})
    try:
        P.MOCKS = root / 'coordination' / 'orchestrator' / 'mocks'
        mocks = P.MOCKS
        (mocks / 'anthropic.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 'did it', 'files_changed': ['q.txt'],
            'patches': [{'path': 'q.txt', 'contents': 'q\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'review'}}))
        (mocks / 'openai.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'verdict': 'ACCEPT',
            'reasoning': 'evidenced',
            'acceptance_test_verdicts': [
                {'test': t, 'satisfied': True, 'evidence': 'e'}
                for t in eng['acceptance_tests']],
            'escalation_reason': None, 'next_task_id': 'ENG-X2',
            'new_task': None, 'research_request': None,
            'project_state_updates': {}, 'directive': None}}))
        (mocks / 'anthropic.ENG-X2.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X2', 'status': 'COMPLETED',
            'implementation_summary': 'the one after',
            'files_changed': ['q2.txt'],
            'patches': [{'path': 'q2.txt', 'contents': 'q2\n'}],
            'tests_run': [], 'test_results': 'n/a', 'failures': [],
            'blockers': [], 'recommended_next_step': 'review'}}))

        # The runtime is asked for LIVE, as the dispatcher would after reading
        # the policy. No payload is involved anywhere in this test.
        os.environ['AUTONOMY_MODE'] = 'LIVE'

        # THE SECRET GATE COMES FIRST, and that ordering is itself a property
        # worth pinning: an armed LIVE policy with no key must stop, not fall
        # back to a fixture and look like it worked.
        _without_fake_keys()
        try:
            _spy_pass(root, 0)
            check('armed LIVE with no API key refuses', False, 'it proceeded')
        except locks.Refusal as r:
            check('armed LIVE with no API key REFUSES by name',
                  r.code == 'SECRET_MISSING', r.code)
        _with_fake_keys()

        expect = [('ANTHROPIC', 'claude-opus-5'),
                  ('OPENAI', 'gpt-5.6-sol'),
                  ('ANTHROPIC', 'claude-opus-5')]
        for i, (want_worker, want_model) in enumerate(expect, 1):
            spied, action = _spy_pass(root, i)
            print(f'       pass {i}: {action[:78]}')
            check(f'pass {i} would make exactly one LIVE provider call',
                  len(spied) == 1, f'{len(spied)}: {spied}')
            if not spied:
                return
            check(f'  to {want_worker}', spied[0]['worker'] == want_worker,
                  spied[0]['worker'])
            check(f'  on {want_model}', spied[0]['model'] == want_model,
                  spied[0]['model'])
            check('  recorded as LIVE', spied[0]['mode'] == 'LIVE')
            print(f'         -> WOULD CALL {spied[0]["worker"]} '
                  f'{spied[0]["model"]} LIVE, body '
                  f'{spied[0]["body_keys"]}')
        check('LIVE survived two continuations with no human action',
              True)
    finally:
        os.environ['AUTONOMY_MODE'] = 'MOCK'
        _without_fake_keys()
        teardown(root)


def test_r_a_payload_cannot_escalate_mock_or_off_to_live():
    """The security property, asserted from both directions."""
    print('\nR. nothing outside the protected policy can grant LIVE')
    _env()

    # The decision function itself, exhaustively.
    for pol, env, want, why in (
            ({'autonomous_operation_enabled': True,
              'execution_mode': 'LIVE'}, 'LIVE', 'LIVE',
             'armed and requested'),
            ({'autonomous_operation_enabled': True,
              'execution_mode': 'MOCK'}, 'LIVE', 'MOCK',
             'policy says MOCK -- a LIVE request cannot raise it'),
            ({'autonomous_operation_enabled': False,
              'execution_mode': 'LIVE'}, 'LIVE', 'MOCK',
             'autonomy off -- execution_mode alone is not enough'),
            ({'autonomous_operation_enabled': True,
              'execution_mode': 'LIVE'}, 'MOCK', 'MOCK',
             'the request may restrict'),
            ({'autonomous_operation_enabled': True}, 'LIVE', 'MOCK',
             'an absent execution_mode reads as MOCK, never as permissive'),
            ({}, 'LIVE', 'MOCK', 'an empty policy grants nothing'),
    ):
        got = P.resolve_mode(pol, {'AUTONOMY_MODE': env})
        check(f'{why} -> {want}', got == want, f'got {got}')

    # And end to end: policy MOCK, the runtime asked for LIVE anyway.
    root = build_sandbox(eng=[ENG_TASK],
                         policy_over={'execution_mode': 'MOCK'})
    try:
        P.MOCKS = root / 'coordination' / 'orchestrator' / 'mocks'
        (P.MOCKS / 'anthropic.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 's', 'files_changed': ['r.txt'],
            'patches': [{'path': 'r.txt', 'contents': 'r\n'}],
            'tests_run': [], 'test_results': '', 'failures': [],
            'blockers': [], 'recommended_next_step': 'n'}}))
        # KEYS PRESENT ON PURPOSE. If the key were missing, a refusal would
        # prove nothing about the policy -- the absent credential would be
        # doing the work. The policy has to be the only thing standing here.
        _with_fake_keys()
        os.environ['AUTONOMY_MODE'] = 'LIVE'
        spied, action = _spy_pass(root, 1)
        check('a pass ran, with valid-looking keys available', 
              'EXECUTE' in action, action)
        check('  and made NO live provider call', spied == [],
              f'{spied} -- money would have been spent')
    finally:
        os.environ['AUTONOMY_MODE'] = 'MOCK'
        _without_fake_keys()
        teardown(root)

    # The startup guard refuses by name rather than downgrading in silence.
    root = build_sandbox(eng=[ENG_TASK], policy_over={'execution_mode': 'MOCK'})
    try:
        snap = S.snapshot()
        try:
            locks.require_live_authorized(snap, P.MODE_LIVE)
            check('an unauthorized LIVE startup refuses', False, 'it allowed')
        except locks.Refusal as r:
            check('an unauthorized LIVE startup REFUSES by name',
                  r.code == 'LIVE_NOT_AUTHORIZED', r.code)
    finally:
        teardown(root)


def test_s_both_kill_switches_stop_spending():
    print('\nS. either protected field alone stops a paid call')
    _env()

    # 1. autonomous_operation_enabled = false -> the pass never reaches a
    #    worker at all.
    root = build_sandbox(eng=[ENG_TASK], autonomy=False,
                         policy_over={'execution_mode': 'LIVE'})
    try:
        os.environ['AUTONOMY_MODE'] = 'LIVE'
        snap = S.snapshot()
        a = D.next_action(snap)
        check('autonomy off stops the pass before any worker',
              a.kind == D.STOP, str(a))
        P.SPY = []
        try:
            check('  and no provider call was even attempted', P.SPY == [])
        finally:
            P.SPY = None
        check('  effective mode is MOCK regardless of the request',
              P.resolve_mode(snap.policy, os.environ) == P.MODE_MOCK)
    finally:
        os.environ['AUTONOMY_MODE'] = 'MOCK'
        teardown(root)

    # 2. execution_mode = MOCK -> the pass RUNS, and pays nothing.
    root = build_sandbox(eng=[ENG_TASK], policy_over={'execution_mode': 'MOCK'})
    try:
        P.MOCKS = root / 'coordination' / 'orchestrator' / 'mocks'
        (P.MOCKS / 'anthropic.ENG-X1.json').write_text(json.dumps({'parsed': {
            'task_id': 'ENG-X1', 'status': 'COMPLETED',
            'implementation_summary': 's', 'files_changed': ['s.txt'],
            'patches': [{'path': 's.txt', 'contents': 's\n'}],
            'tests_run': [], 'test_results': '', 'failures': [],
            'blockers': [], 'recommended_next_step': 'n'}}))
        _with_fake_keys()
        os.environ['AUTONOMY_MODE'] = 'LIVE'
        spied, action = _spy_pass(root, 1)
        check('execution_mode MOCK still lets the pass do its work',
              'EXECUTE' in action, action)
        check('  while making no paid call', spied == [], str(spied))
        q = json.loads((root / 'coordination'
                        / 'ENGINEERING_QUEUE.json').read_text())
        check('  and the transition still happened',
              q['tasks'][0]['status'] == 'RETURNED', q['tasks'][0]['status'])
    finally:
        os.environ['AUTONOMY_MODE'] = 'MOCK'
        _without_fake_keys()
        teardown(root)


def test_t_the_committed_policy_is_off_and_mock():
    """The production file itself, not a sandbox copy of it."""
    print('\nT. the real policy on this branch is disarmed')
    pol = json.loads((REAL_REPO / 'coordination'
                      / 'AUTOMATION_POLICY.json').read_text())
    check('autonomous_operation_enabled is false',
          pol.get('autonomous_operation_enabled') is False,
          str(pol.get('autonomous_operation_enabled')))
    check('execution_mode is MOCK', pol.get('execution_mode') == 'MOCK',
          str(pol.get('execution_mode')))
    check('  so nothing on this branch can reach a provider',
          P.resolve_mode(pol, {'AUTONOMY_MODE': 'LIVE'}) == P.MODE_MOCK)
    check('the vocabulary is closed',
          pol.get('execution_mode_vocabulary') == ['MOCK', 'LIVE'],
          str(pol.get('execution_mode_vocabulary')))


TESTS = [v for k, v in sorted(globals().items()) if k.startswith('test_')]

if __name__ == '__main__':
    for fn in TESTS:
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed, {len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
