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
from coordination.orchestrator import contracts as C               # noqa: E402
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

    # THE HEAD THE WORKER REPORTS IS THE PACKET'S BASE, NOT THE CHECKED-OUT
    # HEAD, AND THOSE ARE ROUTINELY DIFFERENT.
    #
    # The orchestrator builds the packet at H0, recording commits.base = H0,
    # then COMMITS the packet, producing H1, and dispatches with
    # expected_head = H1. The worker job checks out H1, so the workflow's
    # `steps.before.outputs.sha` is H1 -- while validate_result compares the
    # reported head_before against the packet's base, H0.
    #
    # The real Claude worker gets this right by accident of construction: the
    # rendered prompt shows it `packet['commits']['base']` and it copies that
    # back. A mock worker handed the checked-out head would report H1 and be
    # refused RESULT_OUT_OF_CONTRACT on every single return -- "the work
    # started from a different tree than was authorized" -- which is a true
    # sentence about a false premise, and would have looked like a governance
    # failure rather than a wiring bug.
    #
    # Caught by rehearsing the chain locally before arming it. Reading the
    # code did not show it; the two values are equal in every unit test
    # because no commit happens in between.
    pkt_path = root / T.packet_path(task_id)
    if not pkt_path.exists():
        raise MockRefusal('MOCK_PACKET_ABSENT',
                          f'no packet at {T.packet_path(task_id)}; the worker '
                          f'cannot report the base it was authorized from')
    packet = json.loads(pkt_path.read_text())
    authorized_base = packet['commits']['base']

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
        f'- checked_out_head: {head_before}\n'
        f'- authorized_base (reported as head_before): {authorized_base}\n'
        f'- effective_mode: {mode}\n'
        f'- written_at_utc: {stamp}\n'
        f'- fixture: {fx.get("name", "claude_code.default")}\n\n'
        f'It is inert by design: nothing in the forecast path reads\n'
        f'{MOCK_DIR}/.\n')
    # THE NARRATIVE RETURN, which ingest requires separately from the
    # structured one: at least 400 characters and carrying every section in
    # contracts.ENGINEER_RETURN_SECTIONS. The headings are DERIVED from that
    # constant rather than typed here, so a section added to the contract does
    # not silently start failing every mock return with RETURN_MD_MISSING_OR_
    # STUB -- a message that points at the worker and not at the drift.
    rdir = root / T.RETURN_DIR / task_id
    rdir.mkdir(parents=True, exist_ok=True)
    body = [f'# {task_id} - MOCK return', '',
            'Produced by the MOCK worker. No model was called, nothing was',
            'assessed, and no money was spent. This file exists so the real',
            'ingest, the real containment check and the real commit all run',
            'against a return of the right shape.', '']
    said = {
        'work performed': 'Wrote one inert note under coordination/MOCK_RUNS/. '
                          'No engineering was attempted.',
        'evidence': f'{note.relative_to(root)}, and this file.',
        'tests': 'None run. A mock worker running the suite would be reporting '
                 'the suite, not the task.',
        'failures': 'None. That is a statement about the transport, not about '
                    'the task, which was not attempted.',
        'changed files': str(note.relative_to(root)),
        'commit sha': f'base {authorized_base[:12]}; ingest makes the commit.',
        'blockers': 'The task itself remains unstarted and still AUTHORIZED '
                    'work for a real worker.',
        'recommended next action': 'Treat this return as transport evidence '
                                   'only. Re-run the task under LIVE when the '
                                   'loop is armed for it.',
    }
    for section in C.ENGINEER_RETURN_SECTIONS:
        body.append(f'## {section.title()}')
        body.append(said.get(section, 'Not applicable to a MOCK return.'))
        body.append('')
    (rdir / T.RESULT_MD).write_text('\n'.join(body))

    changed = [str(note.relative_to(root)),
               str((rdir / T.RESULT_MD).relative_to(root))]

    result = {
        'task_id': task_id,
        'worker': fx.get('worker', 'ANTHROPIC'),
        'transport': 'CLAUDE_CODE_ACTION',
        'head_before': authorized_base,
        'changed_paths': changed,
        'commands_run': fx.get('commands_run', []),
        'tests': fx.get('tests', []),
        # ONE JUDGEMENT PER CRITERION, because the contract requires every
        # criterion judged separately and refuses COMPLETED otherwise -- a
        # worker that judged some and not others would be reporting a partial
        # result as a whole one.
        #
        # `satisfied` is true so the chain can complete and the transport can
        # be proven end to end. The evidence string says, in every entry, that
        # nothing was actually assessed. That combination is deliberate: the
        # mock is allowed to move the state machine, and is not allowed to be
        # mistaken for engineering. governance_checks.model_called is false,
        # executed_by is MOCK_WORKER, and the uncertainties say the same.
        'acceptance_criteria_results': fx.get('acceptance_criteria_results') or [
            {'criterion': c, 'satisfied': True,
             'evidence': 'MOCK_WORKER: transport proof only. This criterion '
                         'was NOT assessed and no model examined it.'}
            for c in (packet.get('acceptance_criteria') or [])],
        'uncertainties': fx.get('uncertainties', [
            'This return was produced by the MOCK worker. It demonstrates '
            'transport, containment and ingest. It demonstrates nothing about '
            'the engineering task itself.']),
        'refusals': fx.get('refusals', []),
        # DERIVED FROM THE CONTRACT, never copied. validate_result refuses a
        # return missing any GOVERNANCE_CHECKS key, and a hardcoded list here
        # would rot silently the first time one is added -- the mock would
        # start failing for a reason that looks like governance.
        #
        # True is accurate, not convenient: this worker wrote one inert note
        # under MOCK_RUNS and did nothing else, so it genuinely edited no
        # policy, promoted nothing, authorized nothing and used no price as an
        # input. The two MOCK markers are added on top so no reader can mistake
        # the attestation for one a model made.
        # MERGED, not replaced. An earlier version let a fixture's
        # governance_checks stand in for the whole object, and a three-key
        # fixture then produced a return missing eleven required keys -- the
        # fixture silently shadowed the contract. The contract keys are always
        # present; a fixture layers on top, and may set one False on purpose to
        # exercise the breach path, which validate_result treats as a refusal
        # to accept rather than a malformed file.
        'governance_checks': {
            **{k: True for k in T.GOVERNANCE_CHECKS},
            # POSITIVE ASSERTIONS ONLY, and this is a real constraint rather
            # than a style note. validate_result treats ANY false value in
            # this object as the worker confessing a breach -- not a shape
            # error, a refusal -- so a `model_called: False` marker, which
            # reads as obviously true prose, is parsed as "the worker reported
            # breaching model_called" and the task does not advance. The
            # existing keys are all phrased did_not_ / created_no_ / used_no_
            # for exactly this reason; these follow.
            'called_no_model': True,
            'touched_no_protected_paths': True,
            'executed_by': 'MOCK_WORKER',      # a string, so not a breach flag
            **(fx.get('governance_checks') or {})},
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
