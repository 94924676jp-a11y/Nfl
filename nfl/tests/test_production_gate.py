#!/usr/bin/env python3.12
"""The production-critical gate is a declared, checkable list (owner OD-001, 2026-10-14, P0-B).

Every listed module exists and is discovered by the runner; every category has a module; nothing excluded for a reason
is quietly listed; every module reaches production code (it imports a file on the static call graph of a production
entrypoint); and the runner's --gate mode refuses to be combined with --modules. The gate's colour is measured by
`run_suite.py --gate`, not here."""
from __future__ import annotations

import ast
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = FAILED = 0
GATE = _REPO / 'nfl/tests/PRODUCTION_GATE.json'
REQUIRED = ('ELIGIBILITY', 'POINT_IN_TIME', 'RELEASE_AND_LOCK', 'LINEUP_RULES_AND_SELECTION', 'MARKET_AND_FC_FIREWALL')


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def _doc():
    return json.loads(GATE.read_text())


def test_the_list_is_well_formed():
    d = _doc()
    mods = [m['module'] for m in d['modules']]
    check(len(mods) == len(set(mods)) > 0, f'{len(mods)} distinct modules')
    missing = [m for m in mods if not (_REPO / 'nfl/tests' / f'{m}.py').is_file()]
    check(not missing, f'every gate module exists ({missing})')
    check(all(m['category'] in d['categories'] for m in d['modules']), 'every module names a declared category')
    for c in REQUIRED:
        check(any(m['category'] == c for m in d['modules']), f'category {c} has a module')
    both = sorted(set(mods) & set(d['excluded_with_reason']))
    check(not both, f'nothing excluded for a reason is also listed ({both})')
    check(d['IS_NOT'].startswith('a full-suite result'), 'the manifest says the gate IS_NOT a full-suite result')


def _prod_files():
    out = subprocess.run([sys.executable, str(_REPO / 'nfl/research/ledger/callgraph.py'), str(_REPO)],
                         capture_output=True, text=True, cwd=_REPO)
    cg = json.loads(out.stdout)
    return {f for v in cg['entrypoints'].values() for f in v['files']}


def _imports(path):
    hit = set()
    for n in ast.walk(ast.parse(path.read_text())):
        mods = []
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split('.')[0] in ('nfl', 'sportsplatform'):
            mods = [n.module] + [f'{n.module}.{a.name}' for a in n.names]
        elif isinstance(n, ast.Import):
            mods = [a.name for a in n.names]
        for m in mods:
            p = _REPO / m.replace('.', '/')
            for q in (p.with_suffix('.py'), p / '__init__.py'):
                if q.is_file():
                    hit.add(str(q.relative_to(_REPO)))
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith('nfl/') and n.value.endswith('.py'):
            hit.add(n.value)
    return hit


def test_every_gate_module_reaches_production_code():
    prod = _prod_files()
    check(len(prod) > 50, f'the production call graph is non-empty ({len(prod)} files)')
    exempt = {'GOVERNANCE_AND_HARNESS'}     # these guard the measurement itself, not a production file
    bare = [m['module'] for m in _doc()['modules'] if m['category'] not in exempt
            and not (_imports(_REPO / 'nfl/tests' / f"{m['module']}.py") & prod)]
    check(not bare, f'every non-harness gate module imports a production-call-graph file ({bare})')


def test_gate_mode_refuses_extra_modules():
    r = subprocess.run([sys.executable, str(_REPO / 'nfl/tests/run_suite.py'), '--gate', '--modules', 'test_issue_ledger'],
                       capture_output=True, text=True, cwd=_REPO)
    check(r.returncode == 2 and 'REFUSED' in r.stdout, f'--gate with --modules is refused (rc {r.returncode})')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for n, f in list(globals().items()):
        if n.startswith('test_') and callable(f):
            f()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
