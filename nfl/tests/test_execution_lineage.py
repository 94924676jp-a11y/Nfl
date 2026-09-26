#!/usr/bin/env python3.12
"""A guard being correct on this branch does not mean anything executes it.

Scheduled workflows fire from the default branch only, but what each one RUNS
depends on its checkout: a `ref:` pointing at the automation branch runs this
code, a bare checkout runs the default branch, which is hundreds of commits
behind. Those two classes must stay separated, and the tool that separates them
must not understate a closure by missing an invocation shape.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nfl.tools import execution_lineage as L

ok = fail = 0
_INV = [None]


def check(label, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f'  FAIL {label} {detail}')


def inv():
    if _INV[0] is None:
        _INV[0] = L.inventory()
    return _INV[0]


def test_both_invocation_shapes_are_recognised():
    # The regression this test exists for: an earlier version matched only
    # `python3 foo.py` and so reported nfl-production-forecast as running two
    # test files and no forecast, because the forecast is invoked as
    # `python3 -m nfl.production.run_forecast`. A pattern that matches SOMETHING
    # is not a pattern that matches EVERYTHING.
    wf = inv()['workflows']
    f = wf.get('nfl-production-forecast.yml')
    check('forecast workflow present', f is not None)
    if f:
        check('module-form entry point found',
              'nfl/production/run_forecast.py' in f['entry_points'],
              f['entry_points'])
        check('script-form entry point also found',
              any(e.startswith('nfl/tests/') for e in f['entry_points']),
              f['entry_points'])


def test_the_two_checkout_classes_are_both_populated():
    wf = inv()['workflows']
    kinds = {w['checkout'] for w in wf.values()}
    check('both classes exist', kinds == {'BRANCH', 'DEFAULT'}, kinds)
    check('forecast runs the default branch',
          wf['nfl-production-forecast.yml']['checkout'] == 'DEFAULT')
    check('the board refresh runs this branch',
          wf['nfl-product-board.yml']['checkout'] == 'BRANCH')


def test_every_entry_point_exists_in_the_tree_its_workflow_checks_out():
    # Absent from main while the workflow checks out the branch is BY DESIGN and
    # must never be reported as a defect. Absent from the tree it actually runs
    # is a real one.
    missing = inv()['entry_points_absent_from_the_tree_they_run']
    check('no entry point missing from its own tree', not missing, missing)


def test_the_classes_are_disjoint_and_non_empty():
    i = inv()
    be, de = set(i['branch_executed']), set(i['default_executed_only'])
    check('disjoint', not (be & de), sorted(be & de)[:4])
    check('branch closure non-empty', len(be) > 20, len(be))
    check('counts agree with the lists',
          i['n_branch_executed'] == len(be)
          and i['n_default_executed_only'] == len(de))


def test_the_scheduled_board_refresh_reaches_the_forecast_engine():
    # This is the strongest positive lineage claim available in the repository:
    # a scheduled workflow, checking out this branch, whose import closure
    # reaches the football engine. If this ever stops holding, the participation
    # and containment guards stop being on any executing path.
    be = set(inv()['branch_executed'])
    for m in ('nfl/tools/refresh_boards.py', 'nfl/production/run_forecast.py',
              'nfl/production/nonqb/football_engine.py',
              'nfl/production/nonqb/layers.py'):
        check(f'branch-executed {m}', m in be)


def test_classify_covers_every_module_with_one_of_three_labels():
    i = inv()
    for m, want in (('nfl/production/run_forecast.py', 'BRANCH_EXECUTED'),
                    ('nfl/postgame/join_provenance.py', 'NOT_EXECUTED')):
        got = L.classify(i, m)
        check(f'{m} -> {want}', got == want, got)
    check('an invented path is NOT_EXECUTED',
          L.classify(i, 'nfl/does/not/exist.py') == 'NOT_EXECUTED')


def test_the_branch_is_diverged_from_the_default_branch():
    i = inv()
    check('divergence measured', isinstance(i['branch_only_commits'], int)
          and i['branch_only_commits'] > 0, i['branch_only_commits'])
    check('default-only measured', isinstance(i['default_only_commits'], int),
          i['default_only_commits'])


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_execution_lineage: {ok} ok, {fail} failed')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
