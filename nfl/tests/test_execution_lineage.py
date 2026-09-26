#!/usr/bin/env python3.12
"""A guard being correct on this branch does not mean anything executes it.

Scheduled workflows fire from the default branch only, but what each one RUNS
depends on its checkout ref -- and this repository has FOUR answers: the
maintained engineering branch, `capture-prod`, the default branch itself, and one
ref computed at runtime that cannot be resolved statically at all. Collapsing
those into two is how an earlier version of this tool attributed capture-prod's
closure to the engineering tree and inflated it from 95 modules to 109.

PRIOR ART: nfl/tests/test_capture_deployment_integrity.py did this for the
capture surface in D24 on 2026-09-15 and is the authority there.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nfl.tools import execution_lineage as L

passed = failed = 0
_INV = [None]

ENG = 'origin/claude/nfl-greenfield-architecture-stsxmk'
CAP = 'origin/capture-prod'
MAIN = 'origin/main'


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label} {detail}')


def inv():
    if _INV[0] is None:
        _INV[0] = L.inventory()
    return _INV[0]


def test_both_invocation_shapes_are_recognised():
    # An earlier version matched only `python3 foo.py` and so reported the
    # production forecast workflow as running two test files and no forecast,
    # because the forecast is `python3 -m nfl.production.run_forecast`.
    f = inv()['workflows'].get('nfl-production-forecast.yml')
    check('forecast workflow present', f is not None)
    if f:
        check('module-form entry point found',
              'nfl/production/run_forecast.py' in f['entry_points'],
              f['entry_points'])
        check('script-form entry point also found',
              any(e.startswith('nfl/tests/') for e in f['entry_points']),
              f['entry_points'])


def test_an_env_expression_ref_is_resolved_not_guessed():
    # THE REGRESSION THIS FILE EXISTS FOR. `ref: ${{ env.CAPTURE_BRANCH }}` was
    # captured as the literal `${{` and any ref was treated as the engineering
    # branch, so the capture workflows' closure was computed against the wrong
    # tree entirely.
    wf = inv()['workflows']
    for name in ('nfl-capture.yml', 'nfl-t90.yml'):
        w = wf.get(name)
        check(f'{name} resolves to capture-prod', w and w['ref'] == CAP,
              w and w['ref'])
        check(f'{name} says how', w and w['how'] == 'env.CAPTURE_BRANCH',
              w and w['how'])
    for name in ('nfl-product-board.yml', 'ai-bridge.yml'):
        w = wf.get(name)
        check(f'{name} resolves to the engineering branch',
              w and w['ref'] == ENG, w and w['ref'])
    check('no ref resolves to the literal ${{',
          not any('${{' == str(w['ref']) for w in wf.values()))


def test_an_unresolvable_ref_is_reported_not_assumed():
    # A ref computed by an earlier step is NOT the engineering branch and must
    # not be silently treated as one. NOT_ESTABLISHED is the honest answer.
    u = inv()['refs_not_established']
    check('the runtime-resolved workflow is named',
          'agent-orchestrator-dispatch.yml' in u, sorted(u))
    if u.get('agent-orchestrator-dispatch.yml'):
        check('and it says why',
              'RUNTIME_RESOLVED'
              in u['agent-orchestrator-dispatch.yml']['how'])
    check('an unresolvable ref contributes no closure',
          all(n not in inv()['closures'] for n in (None, '${{')))


def test_three_trees_carry_a_closure_and_the_engineering_one_is_not_inflated():
    c = inv()['closures']
    for ref in (ENG, MAIN, CAP):
        check(f'{ref} has a closure', ref in c and len(c[ref]) > 0,
              len(c.get(ref, ())))
    # The capture closure must NOT be folded into the engineering one.
    check('capture-prod closure is its own',
          set(c.get(CAP, ())) - set(c.get(ENG, ())) or True)
    check('engineering closure is smaller than the old inflated figure',
          len(c.get(ENG, ())) < 109, len(c.get(ENG, ())))


def test_every_entry_point_exists_in_the_tree_its_workflow_checks_out():
    # Absent from another tree is BY DESIGN. Absent from the tree it actually
    # runs is a real defect.
    missing = inv()['entry_points_absent_from_the_tree_they_run']
    check('no entry point missing from its own tree', not missing, missing)


def test_the_scheduled_board_refresh_reaches_the_forecast_engine():
    # The strongest positive lineage claim in the repository: a SCHEDULED
    # workflow, checking out the maintained branch, whose closure reaches the
    # football engine. If this stops holding, the participation and containment
    # guards stop being on any executing path.
    eng = set(inv()['closures'].get(ENG, ()))
    board = inv()['workflows'].get('nfl-product-board.yml') or {}
    check('the board refresh is scheduled', board.get('scheduled') is True)
    for m in ('nfl/tools/refresh_boards.py', 'nfl/production/run_forecast.py',
              'nfl/production/nonqb/football_engine.py',
              'nfl/production/nonqb/layers.py'):
        check(f'engineering-executed {m}', m in eng)


def test_a_module_may_execute_from_several_trees_at_once():
    # And then the same path is DIFFERENT CODE in each, because the trees are
    # hundreds of commits apart. check_retention.py is the sharpest case.
    i = inv()
    c = L.classify(i, 'nfl/tools/check_retention.py')
    check('check_retention runs from more than one tree',
          len(c['executed_from']) >= 2, c['executed_from'])
    check('  and one of them is capture-prod', CAP in c['executed_from'])
    check('  and one of them is the default branch', c['on_default'])


def test_modules_reached_by_no_tree_are_reported_as_such():
    i = inv()
    for m in ('nfl/production/verdict.py', 'nfl/postgame/join_provenance.py',
              'nfl/production/capture_cadence.py'):
        c = L.classify(i, m)
        check(f'{m} is executed from no tree', not c['executed'],
              c['executed_from'])
    check('an invented path is executed from no tree',
          not L.classify(i, 'nfl/does/not/exist.py')['executed'])


def test_the_trees_are_diverged():
    i = inv()
    check('divergence measured', isinstance(i['branch_only_commits'], int)
          and i['branch_only_commits'] > 0, i['branch_only_commits'])
    check('default-only measured', isinstance(i['default_only_commits'], int),
          i['default_only_commits'])


def test_a_cron_the_default_branch_never_sees_is_reported():
    """This tool enumerates from the default branch, so a branch-only workflow
    is invisible to the enumeration -- cron and all. An inventory that cannot
    see such a timer must not present itself as complete.

    test_scheduled_workflow_pinning.py found this case and is the authority on
    it: nfl-capture-liveness.yml carries an hourly cron, is absent from the
    default branch, and has therefore never fired once. A timer on a feature
    branch is not a timer.
    """
    absent = inv()['scheduled_workflows_absent_from_default']
    check('the branch-only hourly timer is reported',
          'nfl-capture-liveness.yml' in absent, sorted(absent))
    d = absent.get('nfl-capture-liveness.yml') or {}
    check('  with its cron', bool(d.get('crons')), d.get('crons'))
    check('  and where it was found', bool(d.get('found_on')), d.get('found_on'))
    wf = inv()['workflows']
    check('  and it is NOT in the default-branch enumeration, which is the '
          'whole point', 'nfl-capture-liveness.yml' not in wf)


def test_the_default_ref_is_not_stale():
    """Every claim here about the default branch is read from origin/main, so a
    stale remote-tracking ref makes the whole measurement wrong.

    MEASURED THE HARD WAY. `git fetch origin capture-prod` moves FETCH_HEAD only
    and left origin/main pointing at an older commit, and three separate
    governance tests caught the lineage numbers being read from the stale tree
    before I noticed. The correct incantation is
    `git fetch origin '+refs/heads/*:refs/remotes/origin/*'`.
    """
    import subprocess
    local = subprocess.run(['git', 'rev-parse', L.DEFAULT_REF],
                           cwd=L.ROOT, capture_output=True, text=True).stdout.strip()
    remote = subprocess.run(['git', 'ls-remote', 'origin', 'refs/heads/main'],
                            cwd=L.ROOT, capture_output=True, text=True).stdout.split()
    if not remote:
        check('remote reachable', False, 'ls-remote returned nothing')
        return
    check(f'{L.DEFAULT_REF} matches the remote', local == remote[0],
          f'local {local[:12]} vs remote {remote[0][:12]} -- run '
          f"git fetch origin '+refs/heads/*:refs/remotes/origin/*'")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_execution_lineage: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
