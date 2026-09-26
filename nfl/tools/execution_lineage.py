#!/usr/bin/env python3.12
"""Which code the automation actually runs, and from which tree.

A guard being correct on the maintained branch does not establish that anything
executes it. GitHub fires `schedule:` and `repository_dispatch` only from the
DEFAULT branch, so all workflow DEFINITIONS live there -- but what each one RUNS
is decided by its checkout ref, and this repository has FOUR answers, not two:

    ref: ${{ env.BOARD_BRANCH }}      -> the maintained engineering branch
    ref: ${{ env.CAPTURE_BRANCH }}    -> capture-prod, a separate deployed tree
    no ref at all                     -> the default branch's own tree
    ref: ${{ steps.<id>.outputs.* }}  -> resolved at RUNTIME, not establishable

PRIOR ART, AND IT CAME FIRST. `nfl/tests/test_capture_deployment_integrity.py`
established this for the capture surface in D24 on 2026-09-15, including the
ref resolution and a content comparison of the deployed tree against the
validated contract. This tool generalises that reasoning to every workflow; it
does not replace that test, and where the two overlap the test is the authority
on the capture surface.

AN EARLIER VERSION OF THIS TOOL GOT IT WRONG IN TWO WAYS, both recorded because
both were the same mistake -- a pattern that matched SOMETHING was taken for a
pattern that matched EVERYTHING:

  1. It matched only `python3 foo.py` and missed
     `python3 -m nfl.production.run_forecast`, so it reported the production
     forecast workflow as running two test files and no forecast.
  2. It captured a ref of `${{ env.CAPTURE_BRANCH }}` as the literal `${{` and
     treated ANY ref as the engineering branch. That silently attributed the
     capture and T-90 closures to the engineering tree and inflated the
     engineering closure from 95 modules to 109.

So: an env-expression ref is resolved against the workflow's own `env:` block, a
ref this tool cannot resolve is reported NOT_ESTABLISHED rather than guessed,
and each closure is computed against the tree that workflow actually checks out.
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

# What a resolved ref means for the audit.
ENGINEERING = 'origin/claude/nfl-greenfield-architecture-stsxmk'


def _git(*a):
    return subprocess.run(('git',) + a, cwd=ROOT, capture_output=True,
                          text=True)


def show(ref: str, path: str):
    r = _git('show', f'{ref}:{path}')
    return r.stdout if r.returncode == 0 else None


def exists(ref, path) -> bool:
    if ref is None:
        return (ROOT / path).exists()
    return _git('cat-file', '-e', f'{ref}:{path}').returncode == 0


def read(ref, path):
    if ref is None:
        p = ROOT / path
        return p.read_text(errors='replace') if p.exists() else None
    return show(ref, path)


def entry_points(body: str) -> list:
    """Both invocation shapes. Missing either understates a closure."""
    out = set(re.findall(
        r'python3?(?:\.[0-9]+)? +([A-Za-z0-9_/.-]+\.py)', body))
    for mod in re.findall(r'python3?(?:\.[0-9]+)? +-m +([A-Za-z0-9_.]+)', body):
        if mod.startswith(PKG):
            out.add(mod.replace('.', '/') + '.py')
    return sorted(out)


def resolve_ref(body: str):
    """(ref, how). ref is None when it cannot be established statically."""
    env = dict(re.findall(r'^\s{2}([A-Z][A-Z0-9_]*):\s*(\S+)\s*$', body, re.M))
    m = re.search(r'actions/checkout@[^\n]*\n(?:.*\n){0,6}?\s*ref:\s*(.+)$',
                  body, re.M)
    if not m:
        return DEFAULT_REF, 'DEFAULT_CHECKOUT'
    raw = m.group(1).strip()
    e = re.fullmatch(r'\$\{\{\s*env\.([A-Z_]+)\s*\}\}', raw)
    if e and e.group(1) in env:
        return 'origin/' + env[e.group(1)], f'env.{e.group(1)}'
    if re.fullmatch(r'[A-Za-z0-9._/-]+', raw):
        return 'origin/' + raw, 'literal'
    # A ref computed by an earlier step. Guessing here is how the last version
    # of this tool attributed capture-prod's closure to the engineering tree.
    return None, f'RUNTIME_RESOLVED {raw}'


def workflows() -> dict:
    out = {}
    names = [l.split('/')[-1] for l in
             _git('ls-tree', '--name-only', DEFAULT_REF,
                  '.github/workflows/').stdout.split()]
    for n in names:
        body = show(DEFAULT_REF, f'.github/workflows/{n}') or ''
        ref, how = resolve_ref(body)
        out[n] = {'ref': ref, 'how': how, 'entry_points': entry_points(body),
                  'scheduled': bool(re.search(r'^\s*schedule:', body, re.M)),
                  'crons': re.findall(r"cron: *'([^']+)'", body)}
    return out


def closure(ref, entries) -> set:
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
    by_ref, unresolved, absent = {}, {}, {}
    for n, w in wf.items():
        if w['ref'] is None:
            unresolved[n] = {'how': w['how'],
                             'entry_points': w['entry_points']}
            continue
        by_ref.setdefault(w['ref'], set()).update(w['entry_points'])
        for e in w['entry_points']:
            # Absent from the tree its OWN workflow checks out is a defect.
            # Absent from some other tree is by design and is not one.
            if not exists(w['ref'], e):
                absent.setdefault(n, []).append(e)
    closures = {ref: sorted(closure(ref, sorted(ents)))
                for ref, ents in by_ref.items()}
    ahead = _git('rev-list', '--left-right', '--count',
                 f'{DEFAULT_REF}...HEAD').stdout.split()
    return {
        'spec_version': 'nfl-execution-lineage-2',
        'default_ref': DEFAULT_REF,
        'engineering_ref': ENGINEERING,
        'default_only_commits': int(ahead[0]) if len(ahead) == 2 else None,
        'branch_only_commits': int(ahead[1]) if len(ahead) == 2 else None,
        'workflows': wf,
        'closures': closures,
        'n_by_ref': {r: len(c) for r, c in closures.items()},
        'refs_not_established': unresolved,
        'entry_points_absent_from_the_tree_they_run': absent,
    }


def classify(inv: dict, module: str) -> dict:
    """Which trees execute this module, by the ref each workflow checks out.

    A module can be executed from several trees AT ONCE, and then the same path
    is different code in each, because the trees are hundreds of commits apart.
    That is the finding, not an artefact of reporting.
    """
    refs = sorted(r for r, c in inv['closures'].items() if module in c)
    return {'module': module, 'executed_from': refs,
            'executed': bool(refs),
            'on_engineering': inv['engineering_ref'] in refs,
            'on_default': inv['default_ref'] in refs}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    inv = inventory()
    if '--json' in argv:
        print(json.dumps(inv, indent=1))
        return 0
    print(f"{inv['default_ref']} has {inv['default_only_commits']} commits HEAD "
          f"does not; HEAD has {inv['branch_only_commits']} it does not\n")
    print(f"{'workflow':36s} {'runs the tree':50s} sched")
    for n, w in sorted(inv['workflows'].items()):
        print(f"  {n:34s} {str(w['ref']):48s} "
              f"{'yes' if w['scheduled'] else '-':4s} {w['how']}")
    if inv['refs_not_established']:
        print('\nREF NOT ESTABLISHED STATICALLY (not guessed):')
        for n, u in inv['refs_not_established'].items():
            print(f"  {n}: {u['how']}")
            print(f"    entry points: {u['entry_points']}")
    if inv['entry_points_absent_from_the_tree_they_run']:
        print('\nENTRY POINTS ABSENT FROM THE TREE THEIR WORKFLOW RUNS:')
        for n, es in inv['entry_points_absent_from_the_tree_they_run'].items():
            print(f'  {n}: {es}')
    else:
        print('\nevery workflow entry point exists in the tree it checks out')
    print('\nexecuted closure, per tree:')
    for ref, n in sorted(inv['n_by_ref'].items(), key=lambda x: -x[1]):
        print(f'  {ref:50s} {n:4d} modules')
    for m in [a for a in argv if a.endswith('.py')]:
        c = classify(inv, m)
        print(f"\n  {m}\n    executed from: {c['executed_from'] or 'NO TREE'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
