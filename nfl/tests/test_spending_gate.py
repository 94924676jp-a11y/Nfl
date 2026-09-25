"""The one step that costs money, and the condition that restrains it.

DEF-058 was not a bug in a function. Both halves were individually correct:
the pre-flight resolved the effective mode exactly right, and wrote it to
`effective_mode`. The workflow simply never read it, and the paid
`claude-code-action` step ran with no `if:` at all. A value produced and
consumed by nobody -- an ORPHANED_OUTPUT, and the orphan happened to be the
spending control.

Nothing on this branch could have caught it, and that is the second half of
the lesson. The workflow lives on the DEFAULT branch, because that is where
GitHub runs it from, so a test suite that reads the working tree does not
look at the file that executes. This file therefore reads origin/main, and
establishes that its copy of origin/main is current before believing a word
of it -- a stale ref would report the gate present long after someone removed
it, which is the failure direction nobody checks.

What is asserted is a PAIR, not a step: the paid worker and the mock worker
must carry complementary conditions, so that exactly one of them can run. A
gate on the expensive step with no cheap alternative would stall the loop
instead of protecting it, and an ungated cheap step beside a gated expensive
one would run both.
"""
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tests import remote_ref_freshness as F                  # noqa: E402

WF = '.github/workflows/claude-engineering-dispatch.yml'
DEFAULT_BRANCH = 'origin/main'
PAID_ACTION = 'anthropics/claude-code-action'
GATE = "steps.preflight.outputs.effective_mode == 'LIVE'"

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


def _deployed_text():
    r = subprocess.run(['git', 'show', f'{DEFAULT_BRANCH}:{WF}'], cwd=_REPO,
                       capture_output=True, text=True, timeout=30)
    return r.stdout if r.returncode == 0 else ''


def _steps():
    import yaml
    t = _deployed_text()
    if not t.strip():
        return []
    d = yaml.safe_load(t)
    out = []
    for job in (d.get('jobs') or {}).values():
        out.extend(job.get('steps') or [])
    return out


def _paid(steps):
    return [s for s in steps if PAID_ACTION in str(s.get('uses', ''))]


def _mock(steps):
    return [s for s in steps if 'mock_worker.py' in str(s.get('run', ''))]


def test_the_default_branch_ref_is_current():
    F.check_freshness(check)


def test_the_paid_step_runs_only_when_the_mode_is_really_live():
    steps = _steps()
    check('the deployed workflow was readable', bool(steps),
          f'could not read {DEFAULT_BRANCH}:{WF}')
    paid = _paid(steps)
    check('exactly one paid worker step exists', len(paid) == 1, len(paid))
    for s in paid:
        cond = str(s.get('if') or '')
        check('the paid step carries a condition', bool(cond),
              'NO `if:` -- this is DEF-058 exactly: the paid Action runs on '
              'every dispatched task whatever the mode')
        check('and the condition is the resolved effective mode',
              GATE in cond.replace('"', "'"), cond)


def test_a_non_paid_worker_covers_the_other_branch():
    """A gate with nothing on the other side stalls the loop rather than
    protecting it, and leaves no way to prove the transport without paying."""
    steps = _steps()
    mock = _mock(steps)
    check('a mock worker step exists', len(mock) == 1, len(mock))
    for s in mock:
        cond = str(s.get('if') or '').replace('"', "'")
        check('the mock step is the complement of the paid one',
              "effective_mode != 'LIVE'" in cond, cond)


def test_exactly_one_worker_can_run():
    """Belt and braces on the pair: the two conditions must be mutually
    exclusive AND exhaustive, so a task is never executed twice and never
    silently executed by nobody."""
    steps = _steps()
    paid, mock = _paid(steps), _mock(steps)
    if not (paid and mock):
        check('both worker steps present for the exclusivity check', False,
              f'paid={len(paid)} mock={len(mock)}')
        return
    p = str(paid[0].get('if') or '').replace('"', "'")
    m = str(mock[0].get('if') or '').replace('"', "'")
    check('paid is the == branch', "== 'LIVE'" in p, p)
    check('mock is the != branch', "!= 'LIVE'" in m, m)
    check('both read the same output', p.split('==')[0].strip() == m.split('!=')[0].strip(),
          f'{p!r} vs {m!r}')


def test_the_gate_reads_an_output_the_preflight_actually_writes():
    """The producer side. If validate_engineering_run stops writing
    effective_mode, the gate silently becomes `'' == 'LIVE'` -- permanently
    false, which fails safe, but would strand the loop with no explanation."""
    src = (_REPO / 'coordination' / 'orchestrator' /
           'validate_engineering_run.py').read_text()
    check('the pre-flight writes effective_mode to GITHUB_OUTPUT',
          re.search(r"effective_mode=\{?effective", src) is not None,
          'the gate would compare against an empty string')


def test_ingest_reads_whichever_worker_ran():
    """The consumer side. If ingest only reads the paid step's outputs, a MOCK
    pass hands it an empty conclusion and it treats a completed task as a
    worker that returned nothing."""
    t = _deployed_text()
    for key in ('conclusion', 'session_id', 'structured_output'):
        check(f'ingest falls back to the mock worker for {key}',
              re.search(rf'steps\.claude\.outputs\.{key}\s*\|\|\s*'
                        rf'steps\.mockworker\.outputs\.{key}', t) is not None,
              f'CLAUDE_{key.upper()} reads only the paid step')


def test_no_other_paid_action_slips_in_ungated():
    """The rule, not the instance: any step invoking the paid Action anywhere
    in this workflow must be gated."""
    ungated = [s for s in _paid(_steps()) if not str(s.get('if') or '').strip()]
    check('no ungated paid Action step anywhere in the workflow', not ungated,
          f'{len(ungated)} ungated step(s) invoking {PAID_ACTION}')
