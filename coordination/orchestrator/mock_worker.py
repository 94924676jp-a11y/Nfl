"""The worker that costs nothing, so the loop can be proven before it spends.

WHY THIS EXISTS. `providers` has a proper mock provider: a separate provider,
reachable only by asking for MOCK by name, refusing with MOCK_FIXTURE_ABSENT
rather than returning a blank success. The CLAUDE_CODE_ACTION transport had no
equivalent. Its workflow ran `anthropics/claude-code-action@v1` with no `if:`,
so the effective mode -- computed correctly by the pre-flight and written to
GITHUB_OUTPUT -- restrained nothing. MOCK was a word the worker never read.

That left no non-paid path through the worker at all, which is why the
end-to-end loop could never be demonstrated without billing for it.

WHAT IT MUST DO, AND WHAT IT MUST NOT. Downstream does not care how the
working tree came to look the way it does: `ingest_engineering_return` reads
the real diff, runs the real containment check, and commits. So a mock worker
earns its keep only by producing a REAL working-tree change and a schema-valid
structured return, and then letting every governed step run for real. A mock
that also stubbed ingest would prove nothing about the thing being proven.

It must never be reachable by accident. Same rule as the fixture provider:
MOCK is asked for by name, a missing fixture is a failure rather than an empty
success, and nothing here falls back to a mock because a credential is absent.
A fabricated result wearing a real one's clothes is worse than no result.

The change it writes is deliberately inert -- a note under
coordination/MOCK_RUNS/ -- so a proof run leaves an auditable trace and
touches nothing a forecast reads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from coordination.orchestrator import claude_code_transport as T   # noqa: E402
from coordination.orchestrator import providers as P               # noqa: E402
from coordination.orchestrator import state as S                   # noqa: E402

MOCK_DIR = 'coordination/MOCK_RUNS'
FIXTURES = _HERE / 'mocks'


class MockRefusal(Exception):
    def __init__(self, code, detail):
        super().__init__(f'{code}: {detail}')
        self.code, self.detail = code, detail


def fixture_for(task_id: str) -> dict:
    """`claude_code.<task>.json` if present, else `claude_code.default.json`.

    Absent is a refusal. The mock path is only worth having if it is held to
    the same standard as the live one.
    """
    specific = FIXTURES / f'claude_code.{task_id}.json'
    path = specific if specific.exists() else FIXTURES / 'claude_code.default.json'
    if not path.exists():
        # Displayed relative when it is inside the repo, absolute otherwise.
        # Building the refusal must never itself raise -- an exception while
        # explaining a refusal loses the refusal.
        try:
            shown = path.relative_to(_REPO)
        except ValueError:
            shown = path
        raise MockRefusal('MOCK_FIXTURE_ABSENT',
                          f'no fixture at {shown}; a mock worker with no '
                          f'fixture would be inventing a result')
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise MockRefusal('MOCK_FIXTURE_UNREADABLE', f'{path.name}: {exc}')


def run(task_id: str, head_before: str, *, mode: str, repo=None) -> dict:
    """Apply the fixture's change and return the structured result.

    `mode` is the EFFECTIVE mode the pre-flight computed. Anything but MOCK is
    refused here rather than quietly accepted: if LIVE reached this function
    the caller's gating is wrong, and running the cheap thing in place of the
    expensive one would hide that.
    """
    if str(mode).upper() == P.MODE_LIVE:
        raise MockRefusal('MOCK_WORKER_REACHED_IN_LIVE',
                          'effective mode is LIVE; the real Action should have '
                          'run. Refusing rather than silently substituting.')
    root = pathlib.Path(repo or S.REPO)
    fx = fixture_for(task_id)

    if fx.get('simulate_failure'):
        return {'conclusion': 'failure',
                'session_id': f'mock-{task_id}',
                'structured_output': '',
                'code': fx.get('code', 'MOCK_SIMULATED_FAILURE'),
                'detail': fx.get('detail', '')}

    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    note = root / MOCK_DIR / f'{task_id}-{stamp}.md'
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(
        f'# MOCK worker run for {task_id}\n\n'
        f'No model was called and no money was spent. This file exists so a\n'
        f'proof run leaves a real working-tree change for the real ingest,\n'
        f'containment check and commit to act on.\n\n'
        f'- head_before: {head_before}\n'
        f'- effective_mode: {mode}\n'
        f'- written_at_utc: {stamp}\n'
        f'- fixture: {fx.get("name", "claude_code.default")}\n\n'
        f'It is inert by design: nothing in the forecast path reads\n'
        f'{MOCK_DIR}/.\n')
    changed = [str(note.relative_to(root))]

    result = {
        'task_id': task_id,
        'worker': fx.get('worker', 'ANTHROPIC'),
        'transport': 'CLAUDE_CODE_ACTION',
        'head_before': head_before,
        'changed_paths': changed,
        'commands_run': fx.get('commands_run', []),
        'tests': fx.get('tests', []),
        'acceptance_criteria_results': fx.get('acceptance_criteria_results', []),
        'uncertainties': fx.get('uncertainties', [
            'This return was produced by the MOCK worker. It demonstrates '
            'transport, containment and ingest. It demonstrates nothing about '
            'the engineering task itself.']),
        'refusals': fx.get('refusals', []),
        'governance_checks': fx.get('governance_checks', {
            'executed_by': 'MOCK_WORKER', 'model_called': False}),
        'result_status': fx.get('result_status', 'COMPLETED'),
    }
    return {'conclusion': 'success',
            'session_id': f'mock-{task_id}-{stamp}',
            'structured_output': json.dumps(result)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--head-before', required=True)
    ap.add_argument('--mode', default=os.environ.get('EFFECTIVE_MODE', P.MODE_MOCK))
    a = ap.parse_args(argv)
    try:
        out = run(a.task_id, a.head_before, mode=a.mode)
    except MockRefusal as r:
        print(f'MOCK_WORKER_REFUSED {r.code}: {r.detail}')
        return 1
    gh = os.environ.get('GITHUB_OUTPUT')
    if gh:
        with open(gh, 'a', encoding='utf-8') as fh:
            fh.write(f'conclusion={out["conclusion"]}\n')
            fh.write(f'session_id={out["session_id"]}\n')
            # Single line: the schema has no newlines in it, and a delimiter
            # block would let fixture content close it early.
            fh.write('structured_output='
                     f'{out["structured_output"]}\n')
    print(f'MOCK worker: {out["conclusion"]} for {a.task_id} '
          f'({len(out["structured_output"])} bytes of structured output)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
