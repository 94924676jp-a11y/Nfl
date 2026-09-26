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
from coordination.orchestrator import contracts as C                # noqa: E402
from coordination.orchestrator import providers as P                # noqa: E402

BASE = 'aaaaaaaaaaaabbbbbbbbbbbbccccccccccccdddd'


def _packet(root, task_id='ENG-001', criteria=3, base=BASE):
    """A packet of the shape the orchestrator writes.

    The worker reads its authorized base and its criteria FROM HERE, which is
    the whole point: handing it the checked-out head instead produced a return
    refused RESULT_OUT_OF_CONTRACT on every attempt.
    """
    d = Path(root) / T.PACKET_DIR
    d.mkdir(parents=True, exist_ok=True)
    pkt = {'task_id': task_id, 'worker': 'ANTHROPIC',
           'transport': 'CLAUDE_CODE_ACTION',
           'commits': {'base': base, 'expected_head': base},
           'acceptance_criteria': [f'criterion {i}' for i in range(criteria)],
           'directive': 'd', 'title': 't'}
    (d / f'{task_id}.json').write_text(json.dumps(pkt))
    return pkt

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
        _packet(d)
        out = M.run('ENG-001', 'abc123def456', mode='MOCK', repo=d)
        check('conclusion is success', out['conclusion'] == 'success', out['conclusion'])
        check('session id is marked as a mock', out['session_id'].startswith('mock-'))
        r = json.loads(out['structured_output'])
        missing = [k for k in T.json_schema()['required'] if k not in r]
        check('every required field present', not missing, f'missing {missing}')
        check('transport named correctly', r['transport'] == 'CLAUDE_CODE_ACTION')
        check('head_before is the PACKET BASE, not the checked-out head',
              r['head_before'] == BASE,
              f'{r["head_before"]!r} -- reporting the checked-out head is '
              f'refused RESULT_OUT_OF_CONTRACT on every return')
        check('task id carried through', r['task_id'] == 'ENG-001')


def test_the_return_says_plainly_that_no_model_ran():
    """An artifact that cannot be told apart from a real one is the failure
    mode this whole project keeps naming. The mock must be legible as a mock."""
    with tempfile.TemporaryDirectory() as d:
        _packet(d)
        r = json.loads(M.run('ENG-001', 'h', mode='MOCK', repo=d)['structured_output'])
        check('governance_checks records that no model ran',
              r['governance_checks'].get('called_no_model') is True,
              r['governance_checks'])
        check('no false value anywhere in governance_checks',
              not [k for k, v in r['governance_checks'].items() if v is False],
              'a false value is read as the worker CONFESSING a breach, and '
              'the return is refused')
        check('governance_checks names the executor',
              r['governance_checks'].get('executed_by') == 'MOCK_WORKER')
        check('uncertainties disclaim the engineering result',
              any('MOCK' in str(u) for u in r['uncertainties']), r['uncertainties'])


def test_it_writes_a_real_change_for_the_real_ingest():
    with tempfile.TemporaryDirectory() as d:
        _packet(d)
        r = json.loads(M.run('ENG-001', 'h', mode='MOCK', repo=d)['structured_output'])
        paths = r['changed_paths']
        check('both the note and the narrative return are reported',
              len(paths) == 2, paths)
        for rel in paths:
            check(f'{rel} exists on disk', (Path(d) / rel).exists())
        check('one lands under MOCK_RUNS',
              any(x.startswith(M.MOCK_DIR) for x in paths), paths)
        note = next(Path(d).joinpath(x) for x in paths if x.startswith(M.MOCK_DIR))
        check('the note says no money was spent',
              'no money was spent' in note.read_text())


def test_the_change_is_one_containment_allows():
    """If the mock wrote to a protected path every proof run would refuse, and
    the refusal would look like a containment success."""
    from coordination.orchestrator import locks, contracts as C
    with tempfile.TemporaryDirectory() as d:
        _packet(d)
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
        (tmp / 'engineer.default.json').write_text(json.dumps(
            {'simulate_failure': True, 'code': 'API_TIMEOUT', 'detail': 'x'}))
        M.FIXTURES = tmp
        with tempfile.TemporaryDirectory() as d:
            _packet(d)
            out = M.run('ENG-001', 'h', mode='MOCK', repo=d)
        check('conclusion is failure', out['conclusion'] == 'failure', out['conclusion'])
        check('the code is carried', out.get('code') == 'API_TIMEOUT')
        check('no structured output on failure', out['structured_output'] == '')
    finally:
        M.FIXTURES = original


def test_the_shipped_fixture_is_present_and_parses():
    """The workflow depends on it at runtime; an unparseable fixture would
    surface as a confusing worker failure inside Actions."""
    p = M.FIXTURES / 'engineer.default.json'
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
        _packet(d)
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


def test_the_return_satisfies_the_real_contract():
    """THE ONE THAT WOULD HAVE CAUGHT ALL OF IT.

    Five separate defects in this worker were found by rehearsing the chain by
    hand -- the reported head, the criteria count, the governance keys being
    shadowed by the fixture, a false marker read as a breach confession, and a
    missing return.md. Every one of them would have refused the FIRST armed
    run, each with a message pointing somewhere other than the cause.

    None of them needed a rehearsal to find. They needed this assertion:
    run the worker, then put its return through the same validate_result the
    real ingest uses.
    """
    with tempfile.TemporaryDirectory() as d:
        pkt = _packet(d, criteria=7)
        out = M.run('ENG-001', 'a-different-head', mode='MOCK', repo=d)
        parsed = json.loads(out['structured_output'])
        ok, why = T.validate_result(parsed, pkt)
        check('the mock return passes the real contract', ok, why)
        check('one judgement per criterion',
              len(parsed['acceptance_criteria_results']) == 7,
              len(parsed['acceptance_criteria_results']))
        check('every contract governance key is present',
              not [k for k in T.GOVERNANCE_CHECKS
                   if k not in parsed['governance_checks']])


def test_the_narrative_return_carries_every_required_section():
    """ingest checks return.md separately: 400 characters and every section in
    ENGINEER_RETURN_SECTIONS, or RETURN_MD_MISSING_OR_STUB."""
    with tempfile.TemporaryDirectory() as d:
        _packet(d)
        M.run('ENG-001', 'h', mode='MOCK', repo=d)
        rmd = Path(d) / T.RETURN_DIR / 'ENG-001' / T.RESULT_MD
        check('return.md written', rmd.exists(), str(rmd))
        body = rmd.read_text()
        check('long enough to be a return', len(body) >= 400, len(body))
        missing = [s for s in C.ENGINEER_RETURN_SECTIONS if s not in body.lower()]
        check('every required section present', not missing, missing)
        check('it says plainly that nothing was assessed',
              'no model was called' in body.lower())
