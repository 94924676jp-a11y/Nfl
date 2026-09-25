"""The cheap worker, held to the expensive one's standard.

A mock exists to make a real thing provable. It stops being worth having the
moment it is easier to pass than the thing it stands in for -- then it proves
only that the mock works.

So the properties here are mostly refusals: MOCK cannot be reached while the
effective mode is LIVE, a missing fixture is a failure rather than a blank
success, and the change it writes must be one the real containment check
actually allows. The last one matters because the whole point of the mock
worker is that everything downstream of it stays real -- the real diff, the
real protected-path enforcement, the real commit.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from coordination.orchestrator import mock_worker as M              # noqa: E402
from coordination.orchestrator import claude_code_transport as T    # noqa: E402
from coordination.orchestrator import providers as P                # noqa: E402

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                          # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def test_mock_run_returns_a_schema_valid_structured_result():
    with tempfile.TemporaryDirectory() as d:
        out = M.run('ENG-001', 'abc123def456', mode='MOCK', repo=d)
        check('conclusion is success', out['conclusion'] == 'success', out['conclusion'])
        check('session id is marked as a mock', out['session_id'].startswith('mock-'))
        r = json.loads(out['structured_output'])
        missing = [k for k in T.json_schema()['required'] if k not in r]
        check('every required field present', not missing, f'missing {missing}')
        check('transport named correctly', r['transport'] == 'CLAUDE_CODE_ACTION')
        check('head_before carried through', r['head_before'] == 'abc123def456')
        check('task id carried through', r['task_id'] == 'ENG-001')


def test_the_return_says_plainly_that_no_model_ran():
    """An artifact that cannot be told apart from a real one is the failure
    mode this whole project keeps naming. The mock must be legible as a mock."""
    with tempfile.TemporaryDirectory() as d:
        r = json.loads(M.run('ENG-001', 'h', mode='MOCK', repo=d)['structured_output'])
        check('governance_checks records no model call',
              r['governance_checks'].get('model_called') is False)
        check('governance_checks names the executor',
              r['governance_checks'].get('executed_by') == 'MOCK_WORKER')
        check('uncertainties disclaim the engineering result',
              any('MOCK' in str(u) for u in r['uncertainties']), r['uncertainties'])


def test_it_writes_a_real_change_for_the_real_ingest():
    with tempfile.TemporaryDirectory() as d:
        r = json.loads(M.run('ENG-001', 'h', mode='MOCK', repo=d)['structured_output'])
        paths = r['changed_paths']
        check('exactly one path changed', len(paths) == 1, paths)
        p = Path(d) / paths[0]
        check('the file exists on disk', p.exists(), str(p))
        check('it lands under MOCK_RUNS', paths[0].startswith(M.MOCK_DIR), paths[0])
        body = p.read_text()
        check('the note says no money was spent', 'no money was spent' in body)


def test_the_change_is_one_containment_allows():
    """If the mock wrote to a protected path every proof run would refuse, and
    the refusal would look like a containment success."""
    from coordination.orchestrator import locks, contracts as C
    with tempfile.TemporaryDirectory() as d:
        r = json.loads(M.run('ENG-001', 'h', mode='MOCK', repo=d)['structured_output'])
        try:
            locks.enforce_protected_paths(r['changed_paths'], C.Worker.ENGINEER)
            check('mock change passes the real containment check', True)
        except locks.Refusal as exc:
            check('mock change passes the real containment check', False, exc.code)


def test_it_refuses_to_stand_in_for_a_live_run():
    """Reaching here in LIVE means the caller's gating is wrong. Running the
    cheap thing in place of the expensive one would hide exactly that."""
    ok, why = raised(M.MockRefusal,
                     lambda: M.run('ENG-001', 'h', mode=P.MODE_LIVE),
                     'MOCK_WORKER_REACHED_IN_LIVE')
    check('LIVE is refused, not silently substituted', ok, why)


def test_a_missing_fixture_is_a_failure_not_an_empty_success():
    original = M.FIXTURES
    try:
        M.FIXTURES = Path(tempfile.mkdtemp())
        ok, why = raised(M.MockRefusal, lambda: M.fixture_for('ENG-001'),
                         'MOCK_FIXTURE_ABSENT')
        check('absent fixture refuses', ok, why)
    finally:
        M.FIXTURES = original


def test_a_fixture_may_describe_a_failure():
    """The failure paths need exercising too, and this is how, without
    breaking anything real."""
    original = M.FIXTURES
    try:
        tmp = Path(tempfile.mkdtemp())
        (tmp / 'claude_code.default.json').write_text(json.dumps(
            {'simulate_failure': True, 'code': 'API_TIMEOUT', 'detail': 'x'}))
        M.FIXTURES = tmp
        with tempfile.TemporaryDirectory() as d:
            out = M.run('ENG-001', 'h', mode='MOCK', repo=d)
        check('conclusion is failure', out['conclusion'] == 'failure', out['conclusion'])
        check('the code is carried', out.get('code') == 'API_TIMEOUT')
        check('no structured output on failure', out['structured_output'] == '')
    finally:
        M.FIXTURES = original


def test_the_shipped_fixture_is_present_and_parses():
    """The workflow depends on it at runtime; an unparseable fixture would
    surface as a confusing worker failure inside Actions."""
    p = M.FIXTURES / 'claude_code.default.json'
    check('shipped fixture exists', p.exists(), str(p))
    if p.exists():
        try:
            fx = json.loads(p.read_text())
            check('shipped fixture parses', True)
            check('it does not simulate failure by default',
                  not fx.get('simulate_failure'))
        except json.JSONDecodeError as e:
            check('shipped fixture parses', False, str(e))


def test_cli_writes_the_three_outputs_the_workflow_reads():
    """The workflow wires these into ingest as CLAUDE_CONCLUSION,
    CLAUDE_SESSION_ID and CLAUDE_STRUCTURED. A missing key there is a silent
    empty env var, which ingest would read as a worker that returned nothing."""
    with tempfile.TemporaryDirectory() as d:
        gh = Path(d) / 'gh_output'
        gh.write_text('')
        prev_out, prev_repo = os.environ.get('GITHUB_OUTPUT'), M.S.REPO
        try:
            os.environ['GITHUB_OUTPUT'] = str(gh)
            M.S.REPO = Path(d)
            rc = M.main(['--task-id', 'ENG-001', '--head-before', 'abc123',
                         '--mode', 'MOCK'])
        finally:
            M.S.REPO = prev_repo
            if prev_out is None:
                os.environ.pop('GITHUB_OUTPUT', None)
            else:
                os.environ['GITHUB_OUTPUT'] = prev_out
        check('exit 0', rc == 0, rc)
        keys = {ln.split('=', 1)[0] for ln in gh.read_text().splitlines() if '=' in ln}
        for k in ('conclusion', 'session_id', 'structured_output'):
            check(f'output {k} written', k in keys, sorted(keys))
        for ln in gh.read_text().splitlines():
            if ln.startswith('structured_output='):
                check('structured output is a single line, unclosable by content',
                      ln.count('\n') == 0 and len(ln) > 40)
