#!/usr/bin/env python3.12
"""The owner/review worker. Decides; never writes code.

THE ASYMMETRY THAT DEFINES THIS MODULE

This worker is the most powerful in the runtime -- it accepts work, authorizes
the next task, and can create one -- and it is therefore the one whose limits
must be MECHANICAL rather than instructed. Telling a model "you may not
promote Q9" is a convention. Refusing, in code, to apply a state change that
promotes Q9 is a control. This module does the first because it helps; the
runtime does the second because the first is not enough.

Everything it may change is expressed as a small, closed set of PROPOSED state
changes, each validated before anything is written:

  ACCEPT                 a RETURNED task becomes COMPLETE
  RETURN_FOR_CORRECTION  back to AUTHORIZED, with the reason recorded
  BLOCK                  to BLOCKED, with the reason recorded
  ESCALATE               nothing changes; the loop stops and the owner is told

Authorizing a task is separate from all four and is deliberately narrower: it
may flip a task the OWNER already drafted from DRAFT to AUTHORIZED, and it may
draft a new one -- but a new task arrives as DRAFT, never AUTHORIZED, so no
work executes on a task no human has ever seen. That single rule is what keeps
a self-authorizing loop from existing.

WHAT IT MAY NEVER DO. Promote Q9. Authorize NFL-1. Declare V2 earned. Remove
an owner decision. Weaken a governance gate. Make sportsbook information
predictive. Treat UNKNOWN evidence as passing. Set the exposure cap. Enable
real money. These are checked in `locks.py` against the proposal itself, and
`OWNER_DECISIONS.md` is in `PROTECTED_PATHS` so no worker can edit it at all.
"""
from __future__ import annotations

import json

import pathlib as _pl, sys as _sys
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

from coordination.orchestrator import contracts as C

#: Task ids the owner worker may never move to AUTHORIZED, whatever it argues.
NEVER_AUTHORIZE = ('NFL-1',)

SYSTEM = """You are the OWNER/REVIEW worker on a governed NFL forecasting \
research repository. You review returned work and decide what happens next. \
You do NOT write code.

WHAT YOU MAY DO
- judge whether a return satisfied its acceptance tests, one by one
- ACCEPT, RETURN_FOR_CORRECTION, BLOCK, or ESCALATE a returned task
- authorize a task the owner already drafted (DRAFT -> AUTHORIZED)
- draft a NEW bounded task (it will be created as DRAFT, never AUTHORIZED)
- request external research
- propose a PROJECT_STATE update
- write a directive into CHATGPT_OUTBOX

WHAT YOU MAY NEVER DO — these are refused mechanically, so attempting one
stops the loop rather than achieving anything:
- promote Q9, or change its promotion state
- authorize NFL-1
- declare V2 earned, or move the version
- remove or weaken an owner decision or a governance gate
- make sportsbook information a predictive input
- treat UNKNOWN evidence as passing, or upgrade a claim's classification
- set the weekly exposure cap, or enable real money
- accept a return whose tests did not run

HOW TO JUDGE A RETURN
Acceptance is per-test and evidence-based. "Looks good" is not a verdict.
A test that did not RUN is not a test that passed: failure to reject a null is
not evidence of adequacy, and absence of a finding is not a pass. If a return
claims a result you cannot see evidence for in the return itself, that is
RETURN_FOR_CORRECTION, not ACCEPT.
If a decision in front of you is reserved to the human owner, ESCALATE. Do not
reason past it; the loop is not trying to win the argument.

Reply with ONE JSON object and nothing else:

{
  "task_id": "...",
  "verdict": "ACCEPT" | "RETURN_FOR_CORRECTION" | "BLOCK" | "ESCALATE",
  "reasoning": "plain language, per acceptance test",
  "acceptance_test_verdicts": [
     {"test": "...", "satisfied": true|false,
      "evidence": "what in the return shows this"}
  ],
  "escalation_reason": "one of the escalation codes, or null",
  "next_task_id": "an EXISTING task id to authorize next, or null",
  "new_task": null | {"task_id":"...","title":"...","objective":"...",
                      "acceptance_tests":["..."],"queue":"ENGINEERING|RESEARCH",
                      "priority": 5},
  "research_request": null | {"question":"...","why_it_matters":"..."},
  "project_state_updates": {},
  "directive": null | {"filename":"YYYY-MM-DD-NN-slug.md","body":"..."}
}"""


def build_prompt(*, task, return_text, project_state, decisions,
                 queue_summary) -> str:
    return ''.join([
        '# THE TASK UNDER REVIEW\n',
        json.dumps(task, indent=1, sort_keys=True),
        '\n\n# ITS ACCEPTANCE TESTS — judge each one separately\n',
        *(f'{i}. {a}\n' for i, a in
          enumerate(task.get('acceptance_tests') or [], 1)),
        '\n\n# THE RETURN THAT WAS SUBMITTED\n\n',
        return_text or '(NO RETURN ARTIFACT EXISTS — this alone is grounds to '
                       'refuse acceptance)',
        '\n\n# PROJECT STATE (measured)\n',
        json.dumps(project_state, indent=1, sort_keys=True),
        '\n\n# OWNER DECISIONS (all of them; a decision does not expire)\n',
        decisions,
        '\n\n# THE QUEUES, so you can name an EXISTING next task\n',
        queue_summary,
    ])


REQUIRED = ('task_id', 'verdict', 'reasoning', 'acceptance_test_verdicts')


def validate_response(parsed: dict, task_id: str, task: dict) -> tuple:
    """(ok, reason). Shape first; authority limits are enforced in locks.py."""
    missing = [k for k in REQUIRED if k not in parsed]
    if missing:
        return False, f'response lacks {missing}'
    if parsed.get('task_id') != task_id:
        return False, f'response reviews {parsed.get("task_id")!r}, not {task_id!r}'
    try:
        verdict = C.Verdict(parsed['verdict'])
    except ValueError:
        return False, (f'verdict {parsed.get("verdict")!r} is not one of '
                       f'{[v.value for v in C.Verdict]}')

    verdicts = parsed.get('acceptance_test_verdicts')
    if not isinstance(verdicts, list):
        return False, 'acceptance_test_verdicts must be a list'
    tests = task.get('acceptance_tests') or []
    if len(verdicts) != len(tests):
        # PER-TEST OR NOT AT ALL. A reviewer that judged four of seven tests
        # and accepted anyway has accepted three tests it never looked at, and
        # that is indistinguishable in the artifact from having judged them.
        return False, (f'{len(verdicts)} verdict(s) for {len(tests)} '
                       f'acceptance test(s). Every test is judged separately '
                       f'or the review is incomplete')
    for i, v in enumerate(verdicts, 1):
        if not isinstance(v, dict) or 'satisfied' not in v:
            return False, f'acceptance verdict {i} lacks `satisfied`'
        if not isinstance(v['satisfied'], bool):
            return False, f'acceptance verdict {i}.satisfied must be a boolean'

    if verdict is C.Verdict.ACCEPT:
        unmet = [v for v in verdicts if not v.get('satisfied')]
        if unmet:
            # ACCEPT WITH AN UNMET TEST IS A CONTRADICTION, NOT A JUDGEMENT
            # CALL. If the test should not have counted, the task record is
            # what is wrong, and changing that is the human's call.
            return False, (f'verdict ACCEPT while {len(unmet)} acceptance '
                           f'test(s) are marked unsatisfied. That is a '
                           f'contradiction; use RETURN_FOR_CORRECTION or '
                           f'escalate to have the task record changed')
    if verdict is C.Verdict.ESCALATE:
        code = parsed.get('escalation_reason')
        try:
            C.Escalation(code)
        except (ValueError, TypeError):
            return False, (f'ESCALATE needs escalation_reason from '
                           f'{[e.value for e in C.Escalation]}, got {code!r}')
    if verdict in (C.Verdict.BLOCK, C.Verdict.RETURN_FOR_CORRECTION):
        if not str(parsed.get('reasoning') or '').strip():
            return False, f'{verdict.value} without reasoning is not usable'

    nt = parsed.get('new_task')
    if nt is not None:
        if not isinstance(nt, dict):
            return False, 'new_task must be an object or null'
        if nt.get('queue') not in ('ENGINEERING', 'RESEARCH'):
            return False, "new_task.queue must be 'ENGINEERING' or 'RESEARCH'"
    nid = parsed.get('next_task_id')
    if nid and nid in NEVER_AUTHORIZE:
        return False, (f'{nid} may not be authorized by any worker. That is '
                       f'reserved to the human owner.')
    return True, ''


def proposal_text(parsed: dict) -> str:
    """Everything the worker proposed, flattened for the reserved-decision scan.

    Flattened deliberately: a reserved phrase buried in `reasoning` is just as
    much an attempt as one in `project_state_updates`, and scanning only the
    structured fields would miss the case where the model argues its way there
    in prose and then acts on it.
    """
    return json.dumps(parsed, sort_keys=True)


def review_note(parsed, *, task, run_id, model) -> str:
    """The reviewer's verdict, written into the handoff record."""
    lines = [f'## Owner review of {task["task_id"]} — '
             f'**{parsed.get("verdict")}**', '',
             f'*Autonomous owner worker ({model}), run `{run_id}`.*', '',
             (parsed.get('reasoning') or '').strip(), '',
             '| Acceptance test | Satisfied | Evidence |', '|---|---|---|']
    for v in (parsed.get('acceptance_test_verdicts') or []):
        ev = str(v.get('evidence') or '—').replace('|', '\\|')[:200]
        t = str(v.get('test') or '—').replace('|', '\\|')[:120]
        lines.append(f'| {t} | {"yes" if v.get("satisfied") else "NO"} | {ev} |')
    if parsed.get('escalation_reason'):
        lines += ['', f'**Escalated: `{parsed["escalation_reason"]}`.** The '
                      f'loop stops here and the owner decides.']
    return '\n'.join(lines) + '\n'


WORKER = C.Worker.OWNER
