#!/usr/bin/env python3.12
"""The arming summary must read the flag, not assert it. DEF-078.

The Summary step of `.github/workflows/agent-orchestrator.yml` used to end with
two unconditional echoes:

    Autonomy is armed in `coordination/AUTOMATION_POLICY.json`.
    To stop it immediately, set `autonomous_operation_enabled` to false and push.

Neither consulted the file. `autonomous_operation_enabled` is false, so every run
published a summary asserting the loop was ARMED while the orchestrator printed
the opposite eight lines above it in the same job log -- run 36268562488, job
108477993914:

    [1/3] STOP: AUTOMATION_POLICY.json has autonomous_operation_enabled=false.
    This is the default and the kill switch; set it true to arm the loop.

No control was weakened: the kill switch is load-bearing and was observed
refusing in that very run. The cost is to the reader. A governance status string
that is a constant cannot be told apart from one that measured something, and an
owner who had just disarmed and saw this summary would conclude the disarm
failed.

This test extracts the snippet from the workflow and runs it against five states,
including the two that must report NOT ESTABLISHED rather than guessing.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
WF = _REPO / '.github/workflows/agent-orchestrator.yml'
POLICY = _REPO / 'coordination/AUTOMATION_POLICY.json'

passed = failed = 0


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def snippet():
    """The summary's own arming logic, lifted out of the workflow verbatim."""
    y = WF.read_text()
    m = re.search(r"python3\.12 - <<'PY'\n(.*?)\n\s*PY", y, re.S)
    if not m:
        return None
    return '\n'.join(l[10:] if l.startswith(' ' * 10) else l
                     for l in m.group(1).splitlines())


def run_against(state):
    """Run the snippet in a throwaway tree holding `state` as the policy."""
    snip = snippet()
    if snip is None:
        return None
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'coordination'), exist_ok=True)
    dest = os.path.join(d, 'coordination', 'AUTOMATION_POLICY.json')
    if state is None:
        shutil.copy(POLICY, dest)
    elif isinstance(state, str):
        pathlib.Path(dest).write_text(state)
    else:
        pathlib.Path(dest).write_text(json.dumps(state))
    r = subprocess.run([sys.executable, '-c', snip], cwd=d,
                       capture_output=True, text=True)
    return r.stdout.strip()


def test_the_workflow_no_longer_asserts_armedness():
    y = WF.read_text()
    check('the unconditional "Autonomy is armed in" echo is gone',
          'echo "Autonomy is armed in' not in y)
    check('the summary reads the policy file instead',
          'AUTOMATION_POLICY.json' in y and 'autonomous_operation_enabled' in y)
    check('and the arming logic is extractable, so this test tests the real '
          'thing rather than a copy', snippet() is not None)


def test_each_arming_state_is_reported_as_itself():
    cases = [
        ({'autonomous_operation_enabled': True, 'execution_mode': 'MOCK'},
         'ARMED', 'NOT ARMED'),
        ({'autonomous_operation_enabled': False, 'execution_mode': 'MOCK'},
         'NOT ARMED', None),
        ({'execution_mode': 'MOCK'}, 'NOT ESTABLISHED', None),
        ({'autonomous_operation_enabled': 'true'}, 'NOT ESTABLISHED', None),
        ('{ not json', 'NOT ESTABLISHED', None),
    ]
    for state, must, must_not in cases:
        out = run_against(state)
        label = (state if isinstance(state, str) else
                 state.get('autonomous_operation_enabled', '<absent>'))
        check(f'{label!r} -> reports {must}', out is not None and must in out,
              out)
        if must_not:
            check(f'  and does not also say {must_not}',
                  out is not None and must_not not in out.replace(must, ''),
                  out)


def test_the_live_state_is_reported_truthfully():
    """Against the repository's actual policy file, whatever it currently says."""
    live = json.loads(POLICY.read_text())
    armed = live.get('autonomous_operation_enabled')
    out = run_against(None)
    check('the live policy is readable', out is not None, out)
    if out is None:
        return
    if armed is True:
        check('live state reports ARMED', 'ARMED' in out and 'NOT ARMED'
              not in out, out)
    elif armed is False:
        check('live state reports NOT ARMED', 'NOT ARMED' in out, out)
        check('  and names the kill switch rather than just a boolean',
              'kill switch' in out, out)
        check('  and says plainly that this is not a failure',
              'not a failure' in out, out)
    else:
        check('live state reports NOT ESTABLISHED', 'NOT ESTABLISHED' in out,
              out)


def test_the_kill_switch_itself_is_unchanged_by_this_fix():
    """A reporting fix must not touch the control it reports on."""
    live = json.loads(POLICY.read_text())
    check('autonomous_operation_enabled is still a real boolean',
          isinstance(live.get('autonomous_operation_enabled'), bool),
          repr(live.get('autonomous_operation_enabled')))
    check('execution_mode is still declared',
          isinstance(live.get('execution_mode'), str),
          repr(live.get('execution_mode')))


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_arming_summary_reads_the_flag: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
