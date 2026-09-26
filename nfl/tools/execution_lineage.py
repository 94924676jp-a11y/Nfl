#!/usr/bin/env python3.12
"""Which code the automation actually runs, and from which branch.

A guard being correct on the maintained branch does not establish that anything
executes it. Scheduled and dispatched workflows live on the DEFAULT branch,
because GitHub only fires `schedule:` and `repository_dispatch` from there --
but what each one RUNS depends on its checkout:

    ref: <automation branch>   runs the maintained engineering code
    bare `actions/checkout`    runs the DEFAULT branch's code

The engineering branch is 652 commits ahead of main and 33 behind. So those two
classes execute materially different trees, and a workflow's NAME says nothing
about which. `nfl-production-forecast.yml` checks out main.

THE THREE CLASSES A MODULE CAN BE IN, and the audit needs all three separated:

  BRANCH_EXECUTED   reachable from a branch-checkout workflow, so the code the
                    audit reads is the code that runs
  MAIN_EXECUTED     reachable only from a default-checkout workflow, so a fix on
                    the branch does NOT change what executes until main moves
  NOT_EXECUTED      reachable from no workflow at all; a fix here is correct and
                    inert until something invokes it

WHY THIS IS NOT THE SAME AS THE GUARD CENSUS. That census asked whether a
guard's caller is mentioned in any yml or md -- a text match, on the branch, over
files that may not be the ones that run. This resolves imports transitively from
the entry points each workflow actually invokes, against the tree that workflow
actually checks out. The first is a proxy; this is the lineage.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_REF = 'origin/main'
PKG = ('nfl.', 'sportsplatform.', 'coordination.')


def _git(*a):
    return subprocess.run(('git',) + a, cwd=ROOT, capture_output=True,
                          text=True)


def show(ref: str, path: str):
    r = _git('show', f'{ref}:{path}')
    return r.stdout if r.returncode == 0 else None


def exists(ref: str, path: str) -> bool:
    if ref is None:
        return (ROOT / path).exists()
    return _git('cat-file', '-e', f'{ref}:{path}').returncode == 0


def read(ref, path):
    if ref is None:
        p = ROOT / path
        return p.read_text(errors='replace') if p.exists() else None
    return show(ref, path)


def workflows() -> dict:
    """name -> {checkout, ref, entry_points} read from the DEFAULT branch.

    The workflow DEFINITIONS are always read from the default branch, because
    that is the only place a schedule or dispatch can fire from. What they RUN
    is a separate question, answered by the checkout ref.
    """
    out = {}
    names = [l.split('/')[-1] for l in
             _git('ls-tree', '--name-only', DEFAULT_REF,
                  '.github/workflows/').stdout.split()]
    for n in names:
        body = show(DEFAULT_REF, f'.github/workflows/{n}') or ''
        m = re.search(r'actions/checkout@[^\n]*\n(?:.*\n){0,6}?\s*ref:\s*(\S+)',
                      body)
        ref_expr = m.group(1) if m else None
        # A ref that interpolates the automation-branch env var, or names a
        # branch outright, means the workflow runs the BRANCH.
        runs_branch = bool(ref_expr)
        # Two invocation shapes, and missing either understates the closure.
        # `python3 -m nfl.production.run_forecast` was missed by an earlier
        # version of this tool, which then reported nfl-production-forecast as
        # running two test files and no forecast. A regex that matches
        # SOMETHING is not a regex that matches EVERYTHING.
        entries = set(re.findall(
            r'python3?(?:\.[0-9]+)? +([A-Za-z0-9_/.-]+\.py)', body))
        for mod in re.findall(
                r'python3?(?:\.[0-9]+)? +-m +([A-Za-z0-9_.]+)', body):
            if mod.startswith(PKG):
                entries.add(mod.replace('.', '/') + '.py')
        entries = sorted(entries)
        out[n] = {'checkout': 'BRANCH' if runs_branch else 'DEFAULT',
                  'ref_expr': ref_expr, 'entry_points': entries}
    return out


def closure(ref, entries) -> set:
    """Transitive first-party import closure of `entries` against one tree."""
    seen = {e for e in entries if exists(ref, e)}
    frontier = list(seen)
    while frontier:
        nxt = []
        for f in frontier:
            src = read(ref, f)
            if not src:
                continue
            try:
                t = ast.parse(src)
            except SyntaxError:
                continue
            for n in ast.walk(t):
                mods = []
                if isinstance(n, ast.ImportFrom) and n.module:
                    mods += [n.module] + [f'{n.module}.{a.name}'
                                          for a in n.names]
                elif isinstance(n, ast.Import):
                    mods += [a.name for a in n.names]
                for m in mods:
                    if not m.startswith(PKG):
                        continue
                    p = m.replace('.', '/') + '.py'
                    if p not in seen and exists(ref, p):
                        seen.add(p)
                        nxt.append(p)
        frontier = nxt
    return seen


def inventory() -> dict:
    wf = workflows()
    branch_entries, default_entries, absent = [], [], {}
    for n, w in wf.items():
        for e in w['entry_points']:
            (branch_entries if w['checkout'] == 'BRANCH'
             else default_entries).append(e)
            # An entry point absent from the tree its workflow checks out would
            # be a real defect. Absent from MAIN while the workflow checks out
            # the BRANCH is by design and must not be reported as one.
            tree = None if w['checkout'] == 'BRANCH' else DEFAULT_REF
            if not exists(tree, e):
                absent.setdefault(n, []).append(e)
    bc = closure(None, sorted(set(branch_entries)))
    dc = closure(DEFAULT_REF, sorted(set(default_entries)))
    ahead = _git('rev-list', '--left-right', '--count',
                 f'{DEFAULT_REF}...HEAD').stdout.split()
    return {
        'spec_version': 'nfl-execution-lineage-1',
        'default_ref': DEFAULT_REF,
        'default_only_commits': int(ahead[0]) if len(ahead) == 2 else None,
        'branch_only_commits': int(ahead[1]) if len(ahead) == 2 else None,
        'workflows': wf,
        'entry_points_absent_from_the_tree_they_run': absent,
        'branch_executed': sorted(bc),
        'default_executed_only': sorted(dc - bc),
        'n_branch_executed': len(bc),
        'n_default_executed_only': len(dc - bc),
    }


def classify(inv: dict, module: str) -> str:
    if module in inv['branch_executed']:
        return 'BRANCH_EXECUTED'
    if module in inv['default_executed_only']:
        return 'MAIN_EXECUTED'
    return 'NOT_EXECUTED'


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    inv = inventory()
    if '--json' in argv:
        print(json.dumps(inv, indent=1))
        return 0
    print(f"default branch {inv['default_ref']}: "
          f"{inv['default_only_commits']} commits it has that HEAD does not; "
          f"HEAD has {inv['branch_only_commits']} it does not\n")
    print(f"{'workflow':38s} {'runs':8s} entry points")
    for n, w in sorted(inv['workflows'].items()):
        print(f"  {n:36s} {w['checkout']:8s} {len(w['entry_points'])}")
    if inv['entry_points_absent_from_the_tree_they_run']:
        print('\nENTRY POINTS ABSENT FROM THE TREE THEIR WORKFLOW RUNS:')
        for n, es in inv['entry_points_absent_from_the_tree_they_run'].items():
            print(f'  {n}: {es}')
    else:
        print('\nevery workflow entry point exists in the tree that workflow '
              'checks out')
    print(f"\nbranch-executed closure      {inv['n_branch_executed']:4d} modules")
    print(f"default-executed-only        {inv['n_default_executed_only']:4d} modules")
    for m in argv:
        if m.endswith('.py'):
            print(f'  {classify(inv, m):16s} {m}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
