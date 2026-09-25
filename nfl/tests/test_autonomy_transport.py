"""Does a pass ever START without a human?

Every other test in the orchestrator suite asks whether a pass, once started,
behaves. None asks what starts one. That gap is the whole defect: seven
orchestrator runs exist, all on 2026-09-23, the last two failed, and nothing
has run since -- while nine AUTHORIZED tasks sit in a queue with no ACTIVE
lock. The system was not refusing to work. Nothing was asking it to.

So these tests are about TRANSPORT, not behaviour:

  * is there a timer anywhere that re-enters the chain (cold start),
  * does the event a starter emits match what a receiver accepts, and
  * is the starter deployed where GitHub will actually run it.

The third is why this file refuses to be quietly green. A heartbeat committed
to the automation branch fires NEVER -- `schedule:` runs only from the default
branch -- so a test that merely checked the file exists would pass while the
loop stayed just as dead. That is precisely the defect class this audit was
built to catch, and it would be embarrassing to rebuild it here. The
deployment check therefore FAILS with DEPLOYMENT_PENDING rather than passing.
"""
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

WF = _REPO / '.github' / 'workflows'
HEARTBEAT = WF / 'agent-orchestrator-heartbeat.yml'
HB_REL = '.github/workflows/agent-orchestrator-heartbeat.yml'
RECEIVER_REL = '.github/workflows/agent-orchestrator-dispatch.yml'
DEFAULT_BRANCH = 'origin/main'

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


def _yaml(src):
    import yaml
    return yaml.safe_load(src.read_text() if isinstance(src, Path) else src)


def _on(doc):
    """`on:` parses as the boolean True under YAML 1.1. Handle both."""
    if not isinstance(doc, dict):
        return {}
    return doc.get('on', doc.get(True, {})) or {}


def _from_default(rel):
    try:
        return subprocess.run(['git', 'show', f'{DEFAULT_BRANCH}:{rel}'],
                              cwd=_REPO, capture_output=True, text=True,
                              timeout=30).stdout
    except Exception:                                        # noqa: BLE001
        return ''


def test_heartbeat_exists_and_carries_a_timer():
    check('heartbeat workflow exists', HEARTBEAT.exists(),
          'the chain has no cold start at all')
    if not HEARTBEAT.exists():
        return
    sched = _on(_yaml(HEARTBEAT)).get('schedule')
    check('heartbeat declares a schedule', bool(sched),
          'without schedule: it cannot start itself')
    crons = [s.get('cron') for s in (sched or [])]
    check('cron fields well formed',
          all(isinstance(c, str) and len(c.split()) == 5 for c in crons),
          f'malformed: {crons}')
    print(f'       cold-start timer: {crons}')


def test_emitted_event_type_is_accepted_by_the_receiver():
    """A POST whose event_type no workflow lists is a silent 204 into nothing.

    Both sides are READ, never hardcoded -- a test asserting the literal
    string would keep passing after someone renamed one side of the pair.
    """
    from coordination.orchestrator.github_runtime import DISPATCH_EVENT

    recv = _from_default(RECEIVER_REL)
    check(f'receiver present on {DEFAULT_BRANCH}', bool(recv.strip()),
          'repository_dispatch can never start a pass without it')
    if not recv.strip():
        return
    accepted = _on(_yaml(recv)).get('repository_dispatch', {}).get('types', [])
    check('orchestrator event_type is accepted by the receiver',
          DISPATCH_EVENT in accepted,
          f'emits {DISPATCH_EVENT!r}, receiver accepts {accepted}')

    if HEARTBEAT.exists():
        emitted = set(re.findall(r'event_type\\?"\s*:\s*\\?"([a-z-]+)',
                                 HEARTBEAT.read_text()))
        check('heartbeat POSTs an event_type', bool(emitted),
              'no event_type found in the dispatch body')
        check('heartbeat emits only accepted event types',
              not (emitted - set(accepted)),
              f'unaccepted: {emitted - set(accepted)}')


def test_heartbeat_can_actually_post_a_dispatch():
    """Missing `actions: write` makes the POST a 403 -- the exact failure the
    receiver's own comment records the chain having died of once already."""
    if not HEARTBEAT.exists():
        check('heartbeat permissions', False, 'no heartbeat')
        return
    perms = _yaml(HEARTBEAT).get('permissions', {})
    check('heartbeat has actions: write', perms.get('actions') == 'write',
          f'actions={perms.get("actions")!r}: POST /dispatches would 403')


def test_heartbeat_grants_no_authority():
    """It may ASK for a pass. It must not become a fourth place the mode is
    decided. Authority is AUTOMATION_POLICY.json on the automation branch,
    re-derived after checkout and again in-process before any provider call."""
    if not HEARTBEAT.exists():
        check('heartbeat authority', False, 'no heartbeat')
        return
    txt = HEARTBEAT.read_text()
    check('does not set execution_mode LIVE',
          not re.search(r'execution_mode\s*[:=]\s*["\']?LIVE', txt))
    check('does not write AUTOMATION_POLICY.json',
          not re.search(r'(>>|>|tee|sed -i|curl -X (PUT|PATCH)).{0,80}AUTOMATION_POLICY',
                        txt))
    check('does not arm autonomous_operation_enabled',
          not re.search(r'autonomous_operation_enabled\s*["\']?\s*[:=]\s*true', txt))
    check('consults the policy before dispatching', 'enabled' in txt)


def test_heartbeat_is_silent_when_disarmed():
    """A disarmed system must not emit a dispatch every hour forever."""
    if not HEARTBEAT.exists():
        check('heartbeat gating', False, 'no heartbeat')
        return
    steps = _yaml(HEARTBEAT)['jobs']['heartbeat']['steps']
    posting = [s for s in steps if 'dispatches' in str(s.get('run', ''))]
    check('a step POSTs a dispatch', bool(posting))
    ungated = [s for s in posting if "== 'true'" not in str(s.get('if', ''))]
    check('every dispatch step is gated on the policy flag', not ungated,
          f'{len(ungated)} ungated dispatch step(s)')


def test_cold_start_is_deployed_or_explicitly_pending():
    """THE ONE THAT MUST NOT QUIETLY PASS.

    `schedule:` fires only from the default branch. A heartbeat living only on
    the automation branch is inert, and a green test here would assert a loop
    that cannot start.
    """
    # A stale origin/main reads as "not deployed", which is the answer you
    # expect while deploying and therefore the one nobody questions. Establish
    # the ref is current before believing anything it says.
    if F.check_freshness(check) != F.FRESH:
        print('       (deployment verdict below is unverified)')
    on_default = _from_default(HB_REL)
    if on_default.strip():
        sched = _on(_yaml(on_default)).get('schedule')
        check(f'cold start DEPLOYED on {DEFAULT_BRANCH}', bool(sched),
              'present on default branch but carries no schedule')
        print(f'       deployed cron: {[s.get("cron") for s in (sched or [])]}')
        return
    check('cold start deployed where schedule: fires', False,
          'DEPLOYMENT_PENDING -- the heartbeat is written on the automation '
          'branch, where `schedule:` never fires. It starts nothing until it '
          'is placed on the default branch. The loop remains cold.')


def test_no_existing_scheduled_workflow_already_starts_the_orchestrator():
    """Measures the claim rather than asserting it: six timers exist and none
    reaches the agent loop. If that ever changes, this test says so."""
    from coordination.orchestrator.github_runtime import DISPATCH_EVENT
    scheduled, starters = [], []
    for f in sorted(WF.glob('*.yml')):
        try:
            doc = _yaml(f)
        except Exception:                                    # noqa: BLE001
            continue
        if not _on(doc).get('schedule'):
            continue
        scheduled.append(f.name)
        if f.name == HEARTBEAT.name:
            continue
        txt = f.read_text()
        if DISPATCH_EVENT in txt or 'orchestrator' in txt.lower():
            starters.append(f.name)
    check('scheduled workflows were enumerated', bool(scheduled))
    print(f'       {len(scheduled)} scheduled: {scheduled}')
    print(f'       pre-existing orchestrator starters (excl. heartbeat): '
          f'{starters or "NONE -- this was the defect"}')
