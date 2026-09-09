"""OWN-9 Part 0: the repository write guard, and the OWN-9 artifacts.

The guard exists because three times in one session a compound shell command
of the form `cd repo && job & ; cat > FILE` wrote FILE into the OTHER
repository -- everything after `&` runs in the original working directory. A
convention did not stop it; this is the engineering guard that does.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
GUARD = os.path.join(_ROOT, 'nfl', 'tools', 'nflwrite.py')

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _run(args, payload=b'x', cwd='/tmp'):
    return subprocess.run([sys.executable, GUARD] + args, input=payload,
                          capture_output=True, cwd=cwd)


def test_A_guard_resolves_the_root_without_the_cwd():
    print('\nA. the root comes from the guard file, not the shell')
    r = _run(['--check'], b'', cwd='/tmp')
    check('it resolves from an unrelated cwd', r.returncode == 0,
          r.stderr.decode()[:160])
    check('and names the NFL root', b'/nfl' in r.stdout,
          r.stdout.decode()[:120])


def test_B_guard_refuses_every_escape():
    print('\nB. destinations outside the repository are refused')
    for label, dest in (
            ('an absolute path in another repo',
             '/home/user/mlb-prop-system-v7/STRAY.md'),
            ('a .. traversal', '../mlb-prop-system-v7/STRAY.md'),
            ('a bare parent escape', '../../etc/STRAY.md')):
        r = _run([dest])
        check(f'{label} is refused', r.returncode != 0,
              f'exit {r.returncode}')
        check(f'{label} is refused BY NAME',
              b'NFLWRITE_DESTINATION_OUTSIDE_REPO' in r.stderr,
              r.stderr.decode()[:120])


def test_C_guard_refuses_an_empty_write():
    print('\nC. an empty payload is refused')
    r = _run(['nfl/research/own9/_guard_probe.txt'], b'')
    check('zero bytes is refused, because that is what a failed heredoc looks '
          'like when it succeeds', r.returncode != 0)
    check('by name', b'NFLWRITE_EMPTY_PAYLOAD' in r.stderr,
          r.stderr.decode()[:120])


def test_D_guard_permits_a_legitimate_write_from_a_wrong_cwd():
    print('\nD. a legitimate write still works from the wrong directory')
    probe = os.path.join(_ROOT, 'nfl', 'research', 'own9', '_guard_probe.txt')
    try:
        r = _run(['nfl/research/own9/_guard_probe.txt'], b'guard probe\n')
        check('it writes', r.returncode == 0, r.stderr.decode()[:160])
        check('inside the NFL repo', os.path.exists(probe))
        check('with the payload intact',
              open(probe).read() == 'guard probe\n' if os.path.exists(probe)
              else False)
    finally:
        if os.path.exists(probe):
            os.remove(probe)


def test_E_own9_artifacts_are_present_and_honest():
    print('\nE. the OWN-9 artifacts')
    p = os.path.join(_ROOT, 'nfl', 'research', 'own9', 'own9_results.json')
    if not os.path.exists(p):
        check('no results artifact yet -- nothing claimed', True)
        return
    d = json.load(open(p))
    check('it records the pre-registration it ran under',
          d.get('predeclaration_sha256', '').startswith('90f6ecc3'),
          str(d.get('predeclaration_sha256'))[:16])
    check('it is research-only and unpromoted',
          d.get('research_only') is True and d.get('promoted') is False)
    check('it states that both arms were given the same oracled budgets',
          d.get('budgets_oracled_identically_for_both_arms') is True)
    dc = d.get('frozen_category_closure_in_the_DATA') or {}
    check('the frozen categories close in the DATA before any model runs',
          dc.get('exact') == dc.get('n') and dc.get('max_abs') == 0, str(dc))
    inv = d.get('per_draw_invariants') or {}
    if 'A1' in inv:
        check('A1 closes in EVERY draw',
              inv['A1'].get('closure_violations') == 0, str(inv['A1']))
        check('A1 allocates nothing negative',
              inv['A1'].get('negative') == 0)
        check('A1 never lets designed QB rush exceed its budget',
              inv['A1'].get('designed_qb_exceeds_budget') == 0)
    if 'A0' in inv:
        check('A0 does NOT close -- that is the defect under test',
              inv['A0'].get('closure_violations', 0) > 0,
              str(inv['A0'].get('closure_violations')))


def test_zz_every_check_passed():
    print(f'\n{PASSED} passed, {FAILED} failed')
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
