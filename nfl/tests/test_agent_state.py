"""The execution-control layer: WORK_QUEUE.md, AGENT_STATE.json, HANDOFF.md.

Three files, one of which is written by hand. `WORK_QUEUE.md` holds decisions
-- priority, dependency, acceptance criteria -- and the other two are
GENERATED from it plus git by `nfl/tools/agent_state.py`.

The reason they are generated is the same reason P7 exists: two independent
statements of one truth drift, and the drift is invisible until someone reads
both. A hand-maintained AGENT_STATE would be a second place to record the HEAD
and the queue position, and the second place is always the one that is wrong.

What this file checks is that the generator refuses the two ways a queue stops
being honest: a status outside the vocabulary, and a BLOCKED item that names
no blocker. The second is the one that matters. `BLOCKED` with no stated cause
is where work goes to stop being looked at, and this project has already paid
for that once -- J1 was recorded blocked with cause NETWORK when it was simply
the other agent's to run.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

sys.path.insert(0, os.path.join(_ROOT, 'nfl', 'tools'))
import agent_state as AS                                          # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def _queue(body: str) -> str:
    d = tempfile.mkdtemp(prefix='queue_')
    p = pathlib.Path(d) / 'WORK_QUEUE.md'
    p.write_text(body)
    return str(p)


GOOD = """## ID: X1
- **priority**: 1
- **status**: ACTIVE
- **dependencies**: none
- **description**: do the thing
- **blocker**: none
- **acceptance criteria**:
  - the thing is done and the artifact is read back,
    across two lines
  - the suite is run
"""


def test_the_queue_parses_its_declared_fields():
    q = AS.parse_queue(_queue(GOOD))
    check('one item', len(q) == 1, str(len(q)))
    it = q[0]
    check('id, status and priority are read',
          it['id'] == 'X1' and it['status'] == 'ACTIVE'
          and it['priority'] == '1', str(it))
    check('two acceptance criteria, not one and not three',
          len(it['acceptance_criteria']) == 2,
          str(it['acceptance_criteria']))
    check('a criterion continued on a second line is joined, not truncated',
          'across two lines' in it['acceptance_criteria'][0],
          it['acceptance_criteria'][0])
    check('and no criterion text leaks into another field',
          'across two lines' not in it.get('blocker', ''), it.get('blocker'))


def test_a_status_outside_the_vocabulary_is_refused():
    bad = GOOD.replace('- **status**: ACTIVE', '- **status**: IN_PROGRESS')
    try:
        AS.parse_queue(_queue(bad))
        check('an unknown status is refused', False, 'no raise')
    except AS.QueueError as exc:
        check('an unknown status is refused, not coerced',
              'QUEUE_STATUS_UNKNOWN' in str(exc), str(exc)[:120])


def test_a_blocked_item_naming_no_blocker_is_refused():
    bad = GOOD.replace('- **status**: ACTIVE', '- **status**: BLOCKED')
    try:
        AS.parse_queue(_queue(bad))
        check('BLOCKED with blocker "none" is refused', False, 'no raise')
    except AS.QueueError as exc:
        check('BLOCKED with blocker "none" is refused',
              'BLOCKED_WITHOUT_BLOCKER' in str(exc), str(exc)[:140])
    empty = GOOD.replace('- **status**: ACTIVE', '- **status**: BLOCKED') \
                .replace('- **blocker**: none', '- **blocker**:')
    try:
        AS.parse_queue(_queue(empty))
        check('BLOCKED with an empty blocker is refused', False, 'no raise')
    except AS.QueueError as exc:
        check('BLOCKED with an empty blocker is refused',
              'BLOCKED_WITHOUT_BLOCKER' in str(exc), str(exc)[:140])


def test_the_real_queue_is_well_formed():
    q = AS.parse_queue()
    check('the committed queue parses', len(q) >= 8, str(len(q)))
    check('every item carries id, priority, status, description',
          all(all(k in it for k in
                  ('id', 'priority', 'status', 'description')) for it in q),
          str([it['id'] for it in q
               if not all(k in it for k in ('priority', 'status',
                                            'description'))]))
    check('every item carries acceptance criteria',
          all(it['acceptance_criteria'] for it in q),
          str([it['id'] for it in q if not it['acceptance_criteria']]))
    check('at most one item is ACTIVE at a time',
          sum(1 for it in q if it['status'] == 'ACTIVE') <= 1,
          str([it['id'] for it in q if it['status'] == 'ACTIVE']))
    ids = [it['id'] for it in q]
    check('ids are unique', len(ids) == len(set(ids)), str(ids))


def test_the_generated_state_is_generated_and_not_stale():
    p = pathlib.Path(_ROOT) / 'nfl' / 'AGENT_STATE.json'
    check('AGENT_STATE.json exists', p.exists(), str(p))
    if not p.exists():
        return
    on_disk = json.loads(p.read_text())
    live = AS.build()
    check('it names its generator',
          on_disk.get('generated_by') == AS.GENERATOR,
          str(on_disk.get('generated_by')))
    check('its queue matches a live parse of WORK_QUEUE.md',
          [q['id'] for q in on_disk['queue']]
          == [q['id'] for q in live['queue']],
          'regenerate: python3.12 nfl/tools/agent_state.py --write')
    check('its statuses match',
          [q['status'] for q in on_disk['queue']]
          == [q['status'] for q in live['queue']],
          'regenerate: python3.12 nfl/tools/agent_state.py --write')
    check('the next three eligible items come from the queue, not from prose',
          on_disk['next_three_eligible'] == live['next_three_eligible'],
          str(on_disk['next_three_eligible']))
    check('the suite classification is read from an artifact on disk',
          (on_disk['most_recent_suite_classification'].get('artifact')
           or '').endswith('.json'),
          str(on_disk['most_recent_suite_classification'].get('artifact')))


def test_the_state_records_v2_as_unearned_and_money_as_off():
    live = AS.build()
    pi = live['production_impact']
    check('real money is recorded NOT ENABLED', pi['real_money'] == 'NOT ENABLED')
    check('V2 is recorded NOT YET EARNED', pi['v2_status'] == 'NOT YET EARNED')


def test_the_handoff_names_the_active_task_and_the_next_action():
    p = pathlib.Path(_ROOT) / 'nfl' / 'HANDOFF.md'
    check('HANDOFF.md exists', p.exists(), str(p))
    if not p.exists():
        return
    txt = p.read_text()
    live = AS.build()
    check('it says it is generated and must not be hand-edited',
          'regenerate' in txt.lower() and AS.GENERATOR in txt)
    check('it names the current HEAD',
          live['git']['head_short'] in txt, live['git']['head_short'])
    check('it names the branch', live['git']['branch'] in txt)
    check('it states an exact next action', '## Exact next action' in txt)
    check('it lists every unresolved blocker',
          all(b['id'] in txt for b in live['unresolved_blockers']),
          str([b['id'] for b in live['unresolved_blockers']]))
    check('and it carries the resume commands',
          'nfl/tools/agent_state.py --write' in txt
          and 'nfl/tests/run_suite.py' in txt)


def test_a_blocker_that_is_only_mine_is_recorded_as_assigned():
    """`Blocked means blocked for both of us.` OUT-022C needs bytes from
    outside this checkout, so it is the other agent's to run, and the queue
    has to say that rather than filing it as a dead end."""
    q = {it['id']: it for it in AS.parse_queue()}
    out = q.get('OUT-022C')
    check('OUT-022C is in the queue', out is not None)
    if out is None:
        return
    check('and its blocker says it is assigned rather than dead',
          'assigned' in out['blocker'].lower(), out['blocker'][:160])
    check('and it still forbids inferring FanDuel salaries from DraftKings',
          any('DraftKings' in c for c in out['acceptance_criteria']),
          str(out['acceptance_criteria']))
