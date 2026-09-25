"""Is the loop continuously autonomous? Answer it from evidence, per stage.

THE POINT OF THIS FILE IS THAT I DO NOT GET TO NARRATE THE ANSWER.

"Autonomous" has been claimed for this system before while it performed zero
passes for two days. The claim was not a lie; it was an unmeasured assertion
about a chain nobody had watched end to end. So the acceptance test gets a
reader that names each stage, finds the row or run that proves it, and says
NOT_ESTABLISHED when there is none -- never PASS by default, and never PASS
because the stage before it passed.

THE DISTINCTION THAT MATTERS MOST, and the one already got wrong once: a
heartbeat that RAN is not a heartbeat that ENTERED THE CHAIN. While autonomy
is disarmed the heartbeat fires, reads the policy, skips its dispatch step and
exits success. That is the refusal branch working correctly, and it proves
nothing whatever about the loop. Stage 1 and stage 2 are therefore separate,
and stage 2 requires the dispatch step to have CONCLUDED SUCCESS rather than
been skipped.

Stages 3, 5, 6 and 7 are read from coordination/HANDOFF_LOG.jsonl, which the
orchestrator commits, so they are auditable after the fact by anyone with the
repository. Stages 1, 2 and 8 are facts about GitHub Actions runs and cannot be
read from the tree; pass them in with --runs as JSON from the Actions API.
Without that file they report NOT_ESTABLISHED, which is the honest answer, not
a failure of this tool.

Usage:
    python3.12 nfl/tools/autonomy_acceptance.py [--runs runs.json] [--json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
LOG = _REPO / 'coordination' / 'HANDOFF_LOG.jsonl'
MOCK_RUNS = _REPO / 'coordination' / 'MOCK_RUNS'

PROVEN = 'PROVEN'
NOT_ESTABLISHED = 'NOT_ESTABLISHED'
CONTRADICTED = 'CONTRADICTED'

#: The owner's acceptance test, in his order, one stage per sentence.
STAGES = (
    ('1_HEARTBEAT_FIRES_ON_SCHEDULE',
     'a heartbeat run exists whose event is `schedule`, not a manual dispatch'),
    ('2_HEARTBEAT_ENTERS_THE_CHAIN',
     'that run\'s "Re-enter the chain" step CONCLUDED SUCCESS rather than '
     'being skipped -- a disarmed heartbeat fires and skips, which proves '
     'nothing'),
    ('3_ORCHESTRATOR_SELECTS_A_TASK',
     'a DELEGATED row names an authorized task'),
    ('4_WORKER_EXECUTES',
     'the worker left a trace: a MOCK_RUNS note, or an ingested return whose '
     'governance_checks say who executed it'),
    ('5_RESULT_IS_INGESTED',
     'the delegated task moved status after its DELEGATED row, by ingest '
     'rather than by hand'),
    ('6_CONTINUATION_CHAINS',
     'a CONTINUATION_REQUESTED row was actually sent (dispatch_sent true), '
     'not merely logged'),
    ('7_NEXT_TASK_SELECTED_AUTOMATICALLY',
     'a later DELEGATED row names a DIFFERENT task after that continuation'),
    ('8_KILLED_PASS_IS_RESTARTED',
     'a pass failed or was cancelled, and a later scheduled heartbeat entered '
     'the chain again with no human-triggered run in between'),
)

HUMAN_EVENTS = {'workflow_dispatch', 'push', 'issues', 'issue_comment'}


def _rows() -> list:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _runs(path) -> list:
    """Actions runs as JSON. Accepts the API's own shape or a bare list."""
    if not path:
        return []
    p = pathlib.Path(path)
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    if isinstance(d, dict):
        return d.get('workflow_runs') or d.get('runs') or []
    return d if isinstance(d, list) else []


def assess(rows, runs) -> dict:
    """One verdict per stage, each with the evidence or the reason there is none."""
    v = {k: {'state': NOT_ESTABLISHED, 'why': 'no evidence found', 'what': what}
         for k, what in STAGES}

    def mark(key, state, why):
        v[key]['state'], v[key]['why'] = state, why

    hb = [r for r in runs
          if 'heartbeat' in str(r.get('path', '')) or
             'heartbeat' in str(r.get('name', '')).lower()]
    if not runs:
        for k in ('1_HEARTBEAT_FIRES_ON_SCHEDULE', '2_HEARTBEAT_ENTERS_THE_CHAIN',
                  '8_KILLED_PASS_IS_RESTARTED'):
            mark(k, NOT_ESTABLISHED,
                 'no --runs file; these are facts about Actions runs and cannot '
                 'be read from the repository')
    else:
        sched = [r for r in hb if r.get('event') == 'schedule']
        if sched:
            mark('1_HEARTBEAT_FIRES_ON_SCHEDULE', PROVEN,
                 f'run {sched[0].get("id")} event=schedule '
                 f'conclusion={sched[0].get("conclusion")} '
                 f'at {sched[0].get("run_started_at")}')
        else:
            mark('1_HEARTBEAT_FIRES_ON_SCHEDULE', NOT_ESTABLISHED,
                 f'{len(hb)} heartbeat run(s), none with event=schedule')

        entered = [r for r in hb if _entered_chain(r)]
        if entered:
            mark('2_HEARTBEAT_ENTERS_THE_CHAIN', PROVEN,
                 f'run {entered[0].get("id")} ran its dispatch step to success')
        elif hb:
            mark('2_HEARTBEAT_ENTERS_THE_CHAIN', NOT_ESTABLISHED,
                 f'{len(hb)} heartbeat run(s), every one SKIPPED the dispatch '
                 f'step. That is the disarmed refusal branch, not the loop.')

    delegated = [r for r in rows if r.get('event') == 'DELEGATED']
    if delegated:
        mark('3_ORCHESTRATOR_SELECTS_A_TASK', PROVEN,
             f'{len(delegated)} DELEGATED row(s); latest {delegated[-1].get("task_id")} '
             f'at {delegated[-1].get("timestamp")}')

    notes = sorted(MOCK_RUNS.glob('*.md')) if MOCK_RUNS.exists() else []
    executed = [r for r in rows
                if str(r.get('note', '')).find('MOCK_WORKER') >= 0
                or r.get('event') == 'WORKER_FAILED']
    if notes:
        mark('4_WORKER_EXECUTES', PROVEN,
             f'{len(notes)} MOCK_RUNS note(s); latest {notes[-1].name}')
    elif executed:
        mark('4_WORKER_EXECUTES', NOT_ESTABLISHED,
             f'{len(executed)} worker row(s) but no MOCK_RUNS note. Latest: '
             f'{executed[-1].get("event")} {executed[-1].get("code", "")}')

    if delegated:
        last = delegated[-1]
        after = [r for r in rows
                 if r.get('task_id') == last.get('task_id')
                 and str(r.get('timestamp', '')) > str(last.get('timestamp', ''))
                 and r.get('to_status') not in (None, 'None', '')]
        if after:
            mark('5_RESULT_IS_INGESTED', PROVEN,
                 f'{last.get("task_id")} -> {after[-1].get("to_status")} '
                 f'at {after[-1].get("timestamp")}')
        else:
            mark('5_RESULT_IS_INGESTED', NOT_ESTABLISHED,
                 f'{last.get("task_id")} was DELEGATED and never moved again. '
                 f'ACTIVE reads like work in progress and is actually a stall.')

    sent = [r for r in rows
            if r.get('event') == 'CONTINUATION_REQUESTED' and r.get('dispatch_sent')]
    if sent:
        mark('6_CONTINUATION_CHAINS', PROVEN,
             f'{len(sent)} continuation(s) sent; latest {sent[-1].get("timestamp")}')
    else:
        logged = [r for r in rows if r.get('event') == 'CONTINUATION_REQUESTED']
        if logged:
            mark('6_CONTINUATION_CHAINS', NOT_ESTABLISHED,
                 f'{len(logged)} CONTINUATION_REQUESTED row(s), none with '
                 f'dispatch_sent true -- logged, not sent')

    if sent and delegated:
        t = sent[-1].get('timestamp', '')
        later = [r for r in delegated
                 if str(r.get('timestamp', '')) > str(t)]
        prior_ids = {r.get('task_id') for r in delegated
                     if str(r.get('timestamp', '')) <= str(t)}
        fresh = [r for r in later if r.get('task_id') not in prior_ids]
        if fresh:
            mark('7_NEXT_TASK_SELECTED_AUTOMATICALLY', PROVEN,
                 f'{fresh[0].get("task_id")} delegated at '
                 f'{fresh[0].get("timestamp")}, after the continuation')
        else:
            mark('7_NEXT_TASK_SELECTED_AUTOMATICALLY', NOT_ESTABLISHED,
                 'no DELEGATED row for a new task after the last sent '
                 'continuation')

    if runs:
        dead = [r for r in runs if r.get('conclusion') in ('failure', 'cancelled')]
        if dead:
            t = max(str(r.get('run_started_at') or '') for r in dead)
            revived = [r for r in runs
                       if r.get('event') == 'schedule' and _entered_chain(r)
                       and str(r.get('run_started_at') or '') > t]
            between = [r for r in runs
                       if r.get('event') in HUMAN_EVENTS
                       and t < str(r.get('run_started_at') or '')
                       and (not revived or str(r.get('run_started_at') or '')
                            < min(str(x.get('run_started_at') or '') for x in revived))]
            if revived and not between:
                mark('8_KILLED_PASS_IS_RESTARTED', PROVEN,
                     f'pass died at {t}; scheduled run '
                     f'{revived[0].get("id")} re-entered the chain with no '
                     f'human-triggered run in between')
            elif revived and between:
                mark('8_KILLED_PASS_IS_RESTARTED', CONTRADICTED,
                     f'a scheduled run followed the failure, but {len(between)} '
                     f'human-triggered run(s) came first: the restart cannot be '
                     f'attributed to the heartbeat')
            else:
                mark('8_KILLED_PASS_IS_RESTARTED', NOT_ESTABLISHED,
                     f'pass died at {t} and no later scheduled run entered the '
                     f'chain')
        else:
            mark('8_KILLED_PASS_IS_RESTARTED', NOT_ESTABLISHED,
                 'no failed or cancelled pass to recover from yet')
    return v


def _entered_chain(run) -> bool:
    """Did this heartbeat run actually dispatch?

    Requires per-step data. A run's own success is NOT sufficient and treating
    it as such is the exact error this file exists to prevent: the disarmed
    heartbeat succeeds every time while dispatching nothing.
    """
    for job in (run.get('jobs') or []):
        for step in (job.get('steps') or []):
            if 'Re-enter the chain' in str(step.get('name', '')):
                return step.get('conclusion') == 'success'
    return bool(run.get('entered_chain'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runs', default=None,
                    help='JSON of Actions runs, ideally with per-step jobs')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(argv)
    v = assess(_rows(), _runs(a.runs))
    if a.json:
        print(json.dumps(v, indent=1))
    else:
        proven = sum(1 for s in v.values() if s['state'] == PROVEN)
        print(f'AUTONOMY ACCEPTANCE: {proven}/{len(STAGES)} stage(s) proven\n')
        for k, _ in STAGES:
            s = v[k]
            print(f'  [{s["state"]:<16}] {k}')
            print(f'        needs: {s["what"]}')
            print(f'        {s["why"]}')
        print('\nThe system may be called continuously autonomous only when '
              'every stage reads PROVEN.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
