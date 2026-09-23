#!/usr/bin/env python3.12
"""The CLAUDE_CODE_ACTION transport: a bounded packet out, a governed return in.

WHY THIS IS NOT A BRANCH INSIDE `call_worker`

Every other worker is a synchronous HTTP call: build a prompt, POST, parse,
return. The Claude Code Action is a SEPARATE GITHUB JOB that edits the working
tree and reports back through `structured_output` and files on disk. Pretending
that is an HTTP call would mean a function that sometimes returns a response
and sometimes returns a promise that a different job will keep.

So this transport DELEGATES rather than CALLS. The orchestrator decides the
task, emits a bounded execution packet, hands off, and later ingests a
committed return. That is the same shape it already uses for the owner worker
across a `repository_dispatch` boundary.

THE PACKET IS THE CONTROL SURFACE, AND IT IS DELIBERATELY NARROW

"Work on the repo" is not a task. A packet names one authorized task, the
commit it starts from, the files it may read, the paths it may not touch, the
tests it must run, and the artifacts it must produce. Everything Claude Code
is allowed to know arrives in it, and everything it produces is checked
against it afterwards.

The packet is committed evidence. It therefore NEVER contains a credential --
`assert_packet_is_clean` refuses one, and it runs before the packet is written
rather than after.

WHAT STOPS THIS BEING A PROMPT THAT ASKS NICELY. Nothing in the packet is a
control by itself. The controls are mechanical and they run on the way back:
`locks.enforce_protected_paths` against the real diff, the queue's own
authorization, the exclusive ACTIVE lock, and the owner review that alone can
mark a task COMPLETE. The packet's prose exists so a capable worker does not
have to guess what it may do; the checks exist because prose is not a control.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib as _pl
import re
import sys as _sys

_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C          # noqa: E402
from coordination.orchestrator import state as S              # noqa: E402

SPEC_VERSION = 'claude_code_transport/1.0.0'
PACKET_DIR = 'coordination/ENGINEERING_PACKETS'
RETURN_DIR = 'coordination/CLAUDE_RETURNS'

#: Files the worker must produce. The machine-readable one is what the owner
#: review and the validator read; the human one is what a person reads. Both,
#: not either: a JSON blob nobody reads and prose nothing can check are the
#: two ways this goes wrong.
RESULT_JSON = 'result.json'
RESULT_MD = 'return.md'

#: Every key `result.json` must carry. Absent -> the return is malformed and
#: the task does not advance.
RESULT_REQUIRED = (
    'task_id', 'worker', 'transport', 'head_before', 'changed_paths',
    'commands_run', 'tests', 'acceptance_criteria_results', 'uncertainties',
    'refusals', 'governance_checks', 'result_status',
)
RESULT_STATUSES = ('COMPLETED', 'PARTIAL', 'BLOCKED', 'REFUSED')

#: The governance statements the worker must echo back a verdict on. Asking
#: for a verdict per item is not a control -- the mechanical checks are -- but
#: it makes a worker that was about to do one of these say so first.
GOVERNANCE_CHECKS = (
    'executed_only_the_authorized_task',
    'created_no_new_authority',
    'modified_no_owner_decisions',
    'edited_no_automation_policy',
    'authorized_no_other_task',
    'did_not_promote_q9',
    'did_not_authorize_nfl_1',
    'did_not_declare_v2_earned',
    'used_no_sportsbook_price_as_a_predictive_football_input',
    'preserved_uncertainty_rather_than_narrowing_it',
    'failed_closed_where_required_evidence_was_missing',
)

#: Patterns that look like a credential. Checked against the packet before it
#: is written, because a packet is committed and a commit is forever.
_SECRET_SHAPES = re.compile(
    r'(sk-ant-[A-Za-z0-9_\-]{8,}|sk-proj-[A-Za-z0-9_\-]{8,}'
    r'|pplx-[A-Za-z0-9]{8,}|gh[pousr]_[A-Za-z0-9]{20,}'
    r'|CLAUDE_CODE_OAUTH_TOKEN\s*[:=]\s*\S+'
    r'|ANTHROPIC_API_KEY\s*[:=]\s*\S+'
    r'|OPENAI_API_KEY\s*[:=]\s*\S+)')


class PacketRefusal(Exception):
    """A packet that cannot be built safely is not built."""

    def __init__(self, code, detail, **evidence):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail
        self.evidence = evidence


def assert_packet_is_clean(text) -> None:
    """No credential may enter a committed packet. Checked before writing."""
    hit = _SECRET_SHAPES.search(text)
    if hit:
        raise PacketRefusal(
            'PACKET_CONTAINS_SECRET',
            f'the packet contains something shaped like a credential '
            f'({hit.group(0)[:12]}...). A packet is committed evidence; a '
            f'secret in one is published, not stored.')


def relevant_files(task, repo=None, cap=14, max_bytes=100_000) -> list:
    """The files the TASK RECORD names. Never a guess.

    A worker pointed at the wrong files writes the wrong code confidently. If
    the record names nothing, the packet says so and the worker is told to
    report that rather than go looking -- an unbounded search is how a task
    stops being one task.
    """
    repo = repo or S.REPO
    named = list(task.get('relevant_files') or [])
    if not named:
        for tok in str(task.get('evidence') or '').replace(',', ' ').split():
            if '/' in tok and tok.endswith(('.py', '.json', '.md', '.yml')):
                named.append(tok.strip())
    out, used = [], 0
    for rel in named[:cap]:
        p = repo / rel
        if not p.exists() or not p.is_file():
            continue
        size = p.stat().st_size
        if used + size > max_bytes:
            break
        out.append(rel)
        used += size
    return out


def build_packet(task, *, queue_name, head, snap, prior_return=None,
                 attempt=0, run_id=None) -> dict:
    """The complete, bounded description of one authorized unit of work."""
    if task.get('status') not in ('AUTHORIZED', 'ACTIVE'):
        raise PacketRefusal(
            'TASK_NOT_AUTHORIZED',
            f'{task.get("task_id")} is {task.get("status")!r}. A packet is '
            f'only ever built from a task the queue already authorized.',
            task_id=task.get('task_id'), status=task.get('status'))
    if not task.get('authorized'):
        raise PacketRefusal(
            'TASK_NOT_AUTHORIZED',
            f'{task.get("task_id")} has authorized=false.',
            task_id=task.get('task_id'))

    tid = task['task_id']
    packet = {
        'spec_version': SPEC_VERSION,
        'task_id': tid,
        'authorization': {
            'queue': queue_name,
            'status': task['status'],
            'authorized': True,
            'authorized_by': task.get('created_by'),
            'note': ('Authority comes from this committed queue record. It '
                     'does not come from the event that started the run, and '
                     'it cannot be granted by anything in a workflow input.'),
        },
        'commits': {'base': head, 'expected_head': head,
                    'note': 'A head that has moved invalidates this packet.'},
        'directive': task.get('objective'),
        'title': task.get('title'),
        'acceptance_criteria': list(task.get('acceptance_tests') or []),
        'relevant_files': relevant_files(task),
        'forbidden_paths': sorted(set(C.PROTECTED_PATHS)
                                  | set(C.ENGINEER_FORBIDDEN_PATHS)),
        'protected_paths': sorted(C.PROTECTED_PATHS),
        'required_tests': [
            f'python3.12 nfl/tests/run_suite.py --only {t}'
            for t in (task.get('required_test_modules') or [])
        ] or ['python3.12 nfl/tests/run_suite.py --only <the module you '
              'changed or added>'],
        'governance_constraints': {
            'must_not': [
                'create new authority of any kind',
                'modify coordination/OWNER_DECISIONS.md',
                'modify coordination/AUTOMATION_POLICY.json',
                'modify any file under .github/workflows/',
                'modify any queue file, PROJECT_STATE.json, '
                'CHATGPT_OUTBOX/ or HANDOFF_LOG.jsonl',
                'authorize, create or start another task',
                'promote Q9 or change its promotion state',
                'authorize NFL-1',
                'declare V2 earned',
                'use sportsbook prices as predictive football inputs',
                'weaken, skip, disable or quarantine a test to reach green',
                'report a step as succeeded without reading its output',
            ],
            'must': [
                'execute ONLY the task named above',
                'run the required tests through run_suite and report the '
                'counts the runner printed',
                'report failures you did not fix, including pre-existing ones',
                'preserve uncertainty rather than narrowing it to look '
                'finished -- an UNKNOWN is a real answer',
                'fail closed and say so when evidence you need is absent, '
                'rather than inferring it',
            ],
            'checks_to_return': list(GOVERNANCE_CHECKS),
        },
        'limits': {
            'max_turns': 30,
            'max_runtime_seconds': 1800,
            'note': 'Enforced by the workflow, not by this text.',
        },
        'required_output_paths': {
            'result_json': f'{RETURN_DIR}/{tid}/{RESULT_JSON}',
            'return_md': f'{RETURN_DIR}/{tid}/{RESULT_MD}',
        },
        'prior_return': prior_return,
        'attempt': attempt,
        'run_id': run_id,
        'built_at_utc': dt.datetime.now(dt.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ'),
    }
    body = json.dumps(packet, indent=1, sort_keys=True)
    assert_packet_is_clean(body)
    packet['packet_sha256'] = hashlib.sha256(body.encode()).hexdigest()
    return packet


def packet_path(task_id) -> str:
    return f'{PACKET_DIR}/{task_id}.json'


def write_packet(packet, repo=None) -> _pl.Path:
    repo = repo or S.REPO
    p = repo / packet_path(packet['task_id'])
    p.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(packet, indent=1, sort_keys=True) + '\n'
    assert_packet_is_clean(body)
    p.write_text(body)
    return p


def render_prompt(packet) -> str:
    """The text the Action receives. The packet, plus how to answer.

    Deterministic: the same packet renders the same bytes, because the prompt
    hash feeds the idempotency key and a clock in here would make every retry
    look like new work.
    """
    g = packet['governance_constraints']
    lines = [
        'You are the ENGINEERING worker on a governed NFL forecasting '
        'research repository, running under an orchestrator that has already '
        'authorized exactly one task.',
        '',
        f'# YOUR TASK: {packet["task_id"]} — {packet.get("title") or ""}',
        '',
        packet.get('directive') or '(no objective recorded)',
        '',
        '# ACCEPTANCE CRITERIA — address every one explicitly',
    ]
    for i, a in enumerate(packet['acceptance_criteria'], 1):
        lines.append(f'{i}. {a}')
    lines += ['', '# FILES THIS TASK IS ABOUT']
    if packet['relevant_files']:
        lines += [f'- {f}' for f in packet['relevant_files']]
    else:
        lines.append('(the task record names none — if you cannot proceed '
                     'without knowing, say so and return BLOCKED rather than '
                     'searching the repository for something to change)')
    lines += ['', '# YOU MUST NOT'] + [f'- {x}' for x in g['must_not']]
    lines += ['', '# YOU MUST'] + [f'- {x}' for x in g['must']]
    lines += ['', '# PATHS YOU MAY NOT WRITE',
              'Any diff touching these is refused whole and your work is '
              'discarded, so do not edit them even to "fix" something:']
    lines += [f'- {p}' for p in packet['forbidden_paths']]
    lines += ['', '# TESTS'] + [f'- {t}' for t in packet['required_tests']]
    lines += ['',
              '`run_suite` is the authoritative execution path. A zero exit '
              'code from invoking a module directly is NOT a test result.']
    if packet.get('prior_return'):
        lines += ['', '# THIS IS A CORRECTION ROUND',
                  'Read what was wrong before writing anything.', '',
                  packet['prior_return']]
    out = packet['required_output_paths']
    lines += [
        '', '# WHAT YOU MUST LEAVE BEHIND', '',
        f'Write `{out["result_json"]}` as a JSON object with exactly these '
        f'keys:', '',
        '```json',
        json.dumps({
            'task_id': packet['task_id'],
            'worker': 'ANTHROPIC', 'transport': 'CLAUDE_CODE_ACTION',
            'head_before': packet['commits']['base'],
            'changed_paths': ['...'],
            'commands_run': ['...'],
            'tests': [{'command': '...', 'passed': 0, 'failed': 0,
                       'output_tail': '...'}],
            'acceptance_criteria_results': [
                {'criterion': '...', 'satisfied': True, 'evidence': '...'}],
            'uncertainties': ['what you are not sure of'],
            'refusals': ['anything you declined to do, and why'],
            'governance_checks': {k: True for k in GOVERNANCE_CHECKS},
            'result_status': 'COMPLETED | PARTIAL | BLOCKED | REFUSED',
        }, indent=1),
        '```', '',
        f'and `{out["return_md"]}` as a human-readable report with these '
        f'eight headings, in this order:', '',
    ]
    lines += [f'{i}. {s}' for i, s in
              enumerate(C.ENGINEER_RETURN_SECTIONS, 1)]
    lines += [
        '',
        'One acceptance-criteria entry per criterion above — judging four of '
        'seven and calling it done is three criteria nobody looked at.',
        '',
        'Do not commit. The workflow commits what you leave in the working '
        'tree, after checking it against the paths above.',
        '',
        'If you cannot complete the task, return what you have with '
        '`result_status` BLOCKED and the blocker named. A partial honest '
        'return is worth more than a confident empty one.',
    ]
    return '\n'.join(lines)


def json_schema() -> dict:
    """The schema handed to `claude_args: --json-schema`.

    This is what turns the Action's answer into something checkable rather
    than something to be read hopefully. `structured_output` then carries
    these fields and a missing one is a malformed return, not a judgement
    call.
    """
    return {
        'type': 'object',
        'required': list(RESULT_REQUIRED),
        'additionalProperties': True,
        'properties': {
            'task_id': {'type': 'string'},
            'worker': {'type': 'string'},
            'transport': {'type': 'string'},
            'head_before': {'type': 'string'},
            'changed_paths': {'type': 'array', 'items': {'type': 'string'}},
            'commands_run': {'type': 'array', 'items': {'type': 'string'}},
            'tests': {'type': 'array'},
            'acceptance_criteria_results': {'type': 'array'},
            'uncertainties': {'type': 'array'},
            'refusals': {'type': 'array'},
            'governance_checks': {'type': 'object'},
            'result_status': {'type': 'string', 'enum': list(RESULT_STATUSES)},
        },
    }


# ------------------------------------------------------------- the return
def validate_result(parsed, packet) -> tuple:
    """(ok, reason). The same discipline the API transport's return gets.

    A shape violation is a failed call. There is deliberately no branch that
    accepts a return because it looks like it tried.
    """
    if not isinstance(parsed, dict):
        return False, f'result.json is a {type(parsed).__name__}, not an object'
    missing = [k for k in RESULT_REQUIRED if k not in parsed]
    if missing:
        return False, f'result.json lacks {missing}'
    if parsed.get('task_id') != packet['task_id']:
        return False, (f'result is for {parsed.get("task_id")!r}, not '
                       f'{packet["task_id"]!r} -- a worker answering about a '
                       f'different task is not a usable return')
    if parsed.get('transport') != C.Transport.CLAUDE_CODE_ACTION.value:
        return False, (f'transport {parsed.get("transport")!r} does not match '
                       f'the transport that ran')
    if parsed.get('result_status') not in RESULT_STATUSES:
        return False, (f'result_status {parsed.get("result_status")!r} not in '
                       f'{RESULT_STATUSES}')
    if parsed.get('head_before') != packet['commits']['base']:
        return False, (f'head_before {str(parsed.get("head_before"))[:12]!r} '
                       f'is not the packet\'s base '
                       f'{packet["commits"]["base"][:12]!r} -- the work '
                       f'started from a different tree than was authorized')

    crit = parsed.get('acceptance_criteria_results')
    if not isinstance(crit, list):
        return False, 'acceptance_criteria_results must be a list'
    want = len(packet['acceptance_criteria'])
    if parsed['result_status'] == 'COMPLETED' and len(crit) != want:
        return False, (f'{len(crit)} criteria judged against {want} required. '
                       f'Every criterion is judged separately or the return '
                       f'is incomplete')
    for i, c in enumerate(crit, 1):
        if not isinstance(c, dict) or 'satisfied' not in c:
            return False, f'criterion {i} lacks `satisfied`'
        if not isinstance(c['satisfied'], bool):
            return False, f'criterion {i}.satisfied must be a boolean'
    if parsed['result_status'] == 'COMPLETED' \
            and any(not c['satisfied'] for c in crit):
        return False, ('result_status COMPLETED with an unsatisfied '
                       'criterion is a contradiction; use PARTIAL or BLOCKED')

    checks = parsed.get('governance_checks')
    if not isinstance(checks, dict):
        return False, 'governance_checks must be an object'
    absent = [k for k in GOVERNANCE_CHECKS if k not in checks]
    if absent:
        return False, f'governance_checks lacks {absent}'
    denied = sorted(k for k, v in checks.items() if v is False)
    if denied:
        # NOT a shape error. The worker is SAYING it breached something, and
        # that is a refusal to accept, not a malformed file.
        return False, (f'the worker reported breaching {denied}. The return '
                       f'is refused and the task does not advance.')

    if parsed['result_status'] == 'COMPLETED' \
            and not (parsed.get('changed_paths') or []):
        return False, ('COMPLETED with no changed paths. If nothing needed '
                       'changing that is BLOCKED or PARTIAL with the reason '
                       'stated, not a silent completion')
    return True, ''


def parse_result(text):
    """`structured_output` or a result.json file body -> (obj, why)."""
    from coordination.orchestrator import providers as P
    return P.parse_structured(text or '')


WORKER = C.Worker.ENGINEER
TRANSPORT = C.Transport.CLAUDE_CODE_ACTION
