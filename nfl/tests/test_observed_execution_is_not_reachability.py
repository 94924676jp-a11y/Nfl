#!/usr/bin/env python3.12
"""REACHABLE, INVOKED and OBSERVED are three things. Keep them three.

The execution-lineage work produced a closure figure, and a closure figure is
seductive: it looks like execution evidence and is not. `nfl/tests/run_suite.py`
sits in the engineering closure, which says nothing about whether any particular
test module ran -- in run 36268562488 the suite step ran ONE module and 276
checks in 7 seconds, against 14,406 checks in a full local run.

So observed-step evidence lives in its own artifact with its own rule: a row
needs a run id, the name of the step that did the work, and what was read out of
that step's log. This file enforces that rule, and asserts that absence is
recorded as a state rather than left silent.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
ART = _REPO / 'nfl/research/audit/OBSERVED_EXECUTION.json'
sys.path.insert(0, str(_REPO))

passed = failed = 0
LEVELS = ('OBSERVED', 'OBSERVED_PARTIAL')


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def art():
    return json.loads(ART.read_text())


def test_the_artifact_states_its_own_rule_and_the_three_levels():
    d = art()
    check('the rule is stated in the artifact, not only in a commit message',
          'run id' in d['rule'] and 'NOT evidence' in d['rule'], d['rule'][:70])
    for lvl in ('REACHABLE', 'INVOKED', 'OBSERVED'):
        check(f'{lvl} is defined', lvl in d['three_levels'])
    check('the closure caution is carried in the artifact',
          'closure is not a test report' in d['caution'], d['caution'][-60:])


def test_no_observation_may_exist_without_a_run_id_and_a_step():
    for o in art()['observations']:
        m = o.get('module')
        check(f'{m} names a run id', isinstance(o.get('run_id'), int),
              o.get('run_id'))
        check(f'{m} names the step that did the work',
              isinstance(o.get('step'), str) and o['step'].strip(), o.get('step'))
        check(f'{m} quotes what the log showed',
              isinstance(o.get('what_the_log_shows'), str)
              and len(o['what_the_log_shows']) > 20,
              o.get('what_the_log_shows'))
        check(f'{m} carries a level in {LEVELS}', o.get('level') in LEVELS,
              o.get('level'))


def test_every_observation_says_what_it_does_NOT_prove():
    """The half that stops an observation being over-read.

    Each row here was tempting to over-claim. The board refresh really executes
    the forecast closure -- and refused upstream of most of its guards, so those
    guards are not individually observed. Saying so is the point.
    """
    for o in art()['observations']:
        check(f"{o['module']} states what it does not prove",
              isinstance(o.get('does_not_prove'), str)
              and len(o['does_not_prove']) > 30, o.get('does_not_prove'))


def test_the_partial_observation_is_labelled_partial():
    """run_suite.py is the specific trap, so it is named specifically."""
    rows = {o['module']: o for o in art()['observations']}
    r = rows.get('nfl/tests/run_suite.py')
    check('run_suite.py has a row', r is not None)
    if r:
        check('  it is OBSERVED_PARTIAL, not OBSERVED',
              r['level'] == 'OBSERVED_PARTIAL', r['level'])
        check('  and it says the full suite does NOT run in CI',
              'full suite' in r['does_not_prove'], r['does_not_prove'][:60])


def test_absence_is_recorded_rather_than_silent():
    d = art()
    mods = d['not_observed']['modules']
    check('the not-observed list is non-empty', bool(mods), len(mods))
    # And it must agree with the lineage tool: a module listed as not observed
    # because nothing reaches it must actually be reached by nothing.
    from nfl.tools import execution_lineage as L
    inv = L.inventory()
    wrong = [m for m in mods if L.classify(inv, m)['executed']]
    check('every module listed as unreachable really is reached by no tree',
          not wrong, wrong)


def test_an_observed_module_is_at_least_reachable():
    """The weaker direction, and it must hold: you cannot observe a step running
    a module that no workflow reaches. If this fails, one of the two artifacts
    is wrong and the disagreement is the finding."""
    from nfl.tools import execution_lineage as L
    inv = L.inventory()
    for o in art()['observations']:
        m = o['module']
        check(f'{m} is reachable as well as observed',
              L.classify(inv, m)['executed'], 'observed but in no closure')


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_observed_execution_is_not_reachability: {passed} ok, '
          f'{failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
