"""A scheduled workflow runs the DEFAULT BRANCH's copy of itself.

That one sentence is the whole reason this file exists, and it has now cost
this project twice.

GitHub starts a `schedule:` workflow from the default branch. The definition
executed is main's, not the maintained branch's. So a workflow edit committed
to the automation branch -- a checkout pin, a new guard, a fixed target -- is
INERT. It looks applied. The diff is right there. It changes nothing, because
nothing reads it.

Measured 2026-09-25, and this is the part worth remembering: the board pin
made under APPROVAL-004 is on the automation branch only, so the hourly board
run was still executing main's unpinned definition while the defect row said
FIX_DEPLOYED. The four-state lifecycle caught it, and it caught my own claim.

The same reading of main shows the cost is not theoretical. main's
capture_vintage.py is 708 lines behind and missing the commit titled "The
capture executor did not fail, it stopped, and nothing said so"; its
check_retention.py is 380 behind. The workflows running stale code are the
MONITORING ones -- the ones that would report the silence.

So these tests read origin/main, never the working tree, for anything they
claim about what runs. A test that read the working tree would have passed
happily through both incidents.
"""
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

WF_DIR = '.github/workflows'
DEFAULT_BRANCH = 'origin/main'

# Workflows deliberately left unpinned, each with the reason. A workflow may
# legitimately want the default branch -- but it has to SAY so, here, rather
# than be unpinned by omission. Omission is what produced every incident above.
INTENTIONALLY_DEFAULT_BRANCH = {
    'agent-orchestrator-dispatch.yml':
        'the trust boundary: it must run main\'s reviewed copy, then check out '
        'the automation branch itself',
    'agent-orchestrator-heartbeat.yml':
        'thin by design -- reads two policy fields and POSTs; runs no repo code',
}

from nfl.tests import remote_ref_freshness as F                  # noqa: E402

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


def _git(*args):
    return subprocess.run(['git', *args], cwd=_REPO, capture_output=True,
                          text=True, timeout=60).stdout


def _yaml(text):
    import yaml
    try:
        return yaml.safe_load(text)
    except Exception:                                        # noqa: BLE001
        return None


def _on(doc):
    if not isinstance(doc, dict):
        return {}
    return doc.get('on', doc.get(True, {})) or {}


def _default_branch_workflows():
    """The files that actually run on a timer, read from the default branch."""
    names = [n for n in _git('ls-tree', '-r', '--name-only', DEFAULT_BRANCH,
                             '--', WF_DIR).splitlines() if n.endswith(('.yml', '.yaml'))]
    out = {}
    for rel in names:
        text = _git('show', f'{DEFAULT_BRANCH}:{rel}')
        doc = _yaml(text)
        if isinstance(doc, dict) and _on(doc).get('schedule'):
            out[Path(rel).name] = (rel, text, doc)
    return out


def _checkout_refs(doc):
    """Every actions/checkout step's ref, None meaning 'the default branch'."""
    refs = []
    for job in (doc.get('jobs') or {}).values():
        for step in (job.get('steps') or []):
            uses = str(step.get('uses', ''))
            if uses.startswith('actions/checkout'):
                refs.append((step.get('with') or {}).get('ref'))
    return refs


def test_the_default_branch_ref_is_current():
    """Everything else in this file is read from origin/main. If that ref is
    behind, every verdict here is about a tree that no longer exists -- and it
    fails in the direction that looks like honest caution."""
    F.check_freshness(check)


def test_every_scheduled_workflow_on_main_pins_its_checkout():
    sched = _default_branch_workflows()
    check('scheduled workflows found on the default branch', bool(sched),
          'nothing to check -- suspicious in itself')
    for name, (rel, _text, doc) in sorted(sched.items()):
        refs = _checkout_refs(doc)
        if not refs:
            check(f'{name}: checks out no code', True)
            continue
        unpinned = [r for r in refs if not r]
        if name in INTENTIONALLY_DEFAULT_BRANCH:
            check(f'{name}: unpinned by declared intent', True)
            continue
        check(f'{name}: every checkout pins a ref', not unpinned,
              f'{len(unpinned)} of {len(refs)} checkout step(s) take the default '
              f'branch by omission, so this timer runs whatever main happens to '
              f'hold. Pin it, or declare it in INTENTIONALLY_DEFAULT_BRANCH '
              f'with a reason.')


def test_no_scheduled_workflow_fix_is_stranded_on_the_automation_branch():
    """THE INERT-FIX DETECTOR.

    If a scheduled workflow differs between the working branch and the default
    branch, the branch's version is not the one running. That is precisely the
    state the board pin was in while its defect row read FIX_DEPLOYED.
    """
    sched = _default_branch_workflows()
    stranded = []
    for name, (rel, text, _doc) in sorted(sched.items()):
        local = _REPO / rel
        if not local.exists():
            continue
        if local.read_text() != text:
            stranded.append(name)
    check('no scheduled workflow edit is stranded off the default branch',
          not stranded,
          f'{stranded} differ between this branch and {DEFAULT_BRANCH}. A '
          f'scheduled run executes the default-branch copy, so these edits are '
          f'INERT where they sit. Either deploy them or stop recording them as '
          f'deployed.')


def test_the_declared_exemptions_are_real_and_minimal():
    """An allowlist nobody prunes becomes a way to hide the defect."""
    known = {Path(n).name for n in
             _git('ls-tree', '-r', '--name-only', DEFAULT_BRANCH, '--', WF_DIR).splitlines()}
    known |= {p.name for p in (_REPO / WF_DIR).glob('*.y*ml')}
    for name in sorted(INTENTIONALLY_DEFAULT_BRANCH):
        check(f'exemption {name} names a real workflow',
              name in known,
              'exemption for a workflow that does not exist -- remove it')
        check(f'exemption {name} carries a reason',
              bool(INTENTIONALLY_DEFAULT_BRANCH[name].strip()))


def test_report_which_code_the_unpinned_timers_would_run():
    """Not a pass/fail gate: a standing measurement, so the cost of leaving
    this unfixed stays visible instead of being argued about."""
    sched = _default_branch_workflows()
    stale = []
    for name, (rel, _t, doc) in sorted(sched.items()):
        if name in INTENTIONALLY_DEFAULT_BRANCH:
            continue
        if any(r for r in _checkout_refs(doc)):
            continue
        text = _git('show', f'{DEFAULT_BRANCH}:{rel}')
        import re
        for script in sorted(set(re.findall(r'nfl/(?:tools|tests)/[a-z_0-9]+\.py', text))):
            m = _git('rev-parse', f'{DEFAULT_BRANCH}:{script}').strip()
            h = _git('rev-parse', f'HEAD:{script}').strip()
            if m and h and m != h:
                n = len(_git('log', '--oneline', f'{DEFAULT_BRANCH}..HEAD',
                             '--', script).splitlines())
                stale.append((name, script, n))
    check('stale-code survey completed', True)
    if stale:
        print('       unpinned timers would run code behind this branch:')
        for name, script, n in stale:
            print(f'         {name:<28} {script:<38} {n} commit(s) behind')
    else:
        print('       no unpinned scheduled timer runs stale code')


def test_no_scheduled_workflow_is_absent_from_the_default_branch():
    """A scheduled workflow that exists only on a feature branch NEVER FIRES.

    Not "fires with stale code" -- never fires at all. GitHub never registers
    it, so it has no runs, no failures and no alert. It is invisible rather
    than broken, which is worse.

    Measured 2026-09-25 against the Actions API: the repository has 11
    registered workflows and nfl-capture-liveness.yml is not among them,
    despite carrying `cron: 0 * * * *` on this branch. Its own header says it
    was written because earlier capture workflows "None of them ran again" --
    so the monitor built to detect silence has been silent since it was
    written, and could not have reported itself.
    """
    local = {}
    for p in sorted((_REPO / WF_DIR).glob('*.y*ml')):
        doc = _yaml(p.read_text())
        if isinstance(doc, dict) and _on(doc).get('schedule'):
            local[p.name] = p
    on_default = {Path(n).name for n in
                  _git('ls-tree', '-r', '--name-only', DEFAULT_BRANCH,
                       '--', WF_DIR).splitlines()}
    missing = sorted(n for n in local if n not in on_default)
    check('every scheduled workflow exists on the default branch', not missing,
          f'{missing} carry a cron but are absent from {DEFAULT_BRANCH}, so '
          f'GitHub never registers them and they have never fired once. '
          f'A timer on a feature branch is not a timer.')
