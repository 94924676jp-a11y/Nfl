"""Attribute every current suite result against a baseline run. Machine-readable.

WHY THIS EXISTS. A suite with 62 failing checks is not information. "62 failing
checks, 61 of which also failed before I touched anything, and here is the one
that did not" is. Without the second form there is no way to tell a repository
that has always been red from one a change just broke, and the temptation is to
fix whatever is red to get a green number -- which is how a real regression gets
buried under nineteen unrelated repairs.

THE GRAMMAR IT PARSES is `run_suite.main`'s own output, not a guess at it:

  modules N  test functions N  checks N  FAILING CHECKS N  RAISED N
      ZERO-CHECK FUNCTIONS N  BLOCKED FUNCTIONS N
  blocked (declared, not a pass, not a failure):
    <file>::<fn>
  IMPORT <file>            + traceback
  RAISED <file>::<fn>      + traceback
  CHECKS <file>: N failing check(s)
    FAIL <label>: <detail>
  VACUOUS <file>: ... ZERO checks ...
  ZERO-CHECK FUNCTIONS: N test function(s) ...
    <file>::<fn>
  SUITE FAIL|PASS

FIVE CLASSES, and the last one is the honest escape hatch rather than a
dustbin:

  PRE_EXISTING            present at baseline, present now
  NEWLY_INTRODUCED        absent at baseline, present now
  RESOLVED_SINCE_BASELINE present at baseline, absent now
  CHANGED_CLASSIFICATION  present in both but the KIND or the magnitude moved
  ENVIRONMENTAL           the detail names a network refusal, a live fetch or
                          a capture this executor cannot make. Classified only
                          on that evidence, never because an item is
                          inconvenient.

IDENTITY OF A FAILING CHECK. A FAIL line's text carries measured numbers that
move between runs, so the key is the line with digit runs collapsed. The raw
text is kept beside it, and when two runs share a key but differ in raw text
the item is CHANGED_CLASSIFICATION rather than PRE_EXISTING -- the check still
fails, but it fails differently, and that is worth seeing.

A MODULE THAT DID NOT EXIST AT BASELINE is marked `new_module`. Its failures
are NEWLY_INTRODUCED by construction, which is true and useless on its own, so
the flag travels with them.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

SPEC_VERSION = 'suite-diff-1'

PRE_EXISTING = 'PRE_EXISTING'
NEWLY_INTRODUCED = 'NEWLY_INTRODUCED'
RESOLVED = 'RESOLVED_SINCE_BASELINE'
CHANGED = 'CHANGED_CLASSIFICATION'
ENVIRONMENTAL = 'ENVIRONMENTAL'
CLASSES = (PRE_EXISTING, NEWLY_INTRODUCED, RESOLVED, CHANGED, ENVIRONMENTAL)

#: Evidence that an item is about this executor's environment rather than the
#: code. Matched against the raw detail, case-insensitively.
ENV_MARKERS = ('connect', '403', 'network', 'live fetch', 'live source',
               'cannot be proven here', 'egress', 'urlerror', 'timed out',
               'name resolution', 'unreachable')

_NUM = re.compile(r'\d[\d,]*(?:\.\d+)?(?:e[+-]?\d+)?', re.I)
_HEX = re.compile(r'\b[0-9a-f]{7,}\b', re.I)

HEADER = re.compile(
    r'modules (\d+)\s+test functions (\d+)\s+checks (\d+)\s+'
    r'FAILING CHECKS (\d+)\s+RAISED (\d+)\s+ZERO-CHECK FUNCTIONS (\d+)\s+'
    r'BLOCKED FUNCTIONS (\d+)')


#: Checkout roots collapsed to <ROOT> before keying. A suite run from a
#: worktree prints that worktree's absolute path, so a check whose detail
#: quotes a path would otherwise key differently in the two runs and appear as
#: one RESOLVED plus one NEWLY_INTRODUCED -- a phantom regression AND a
#: phantom repair, from the same unchanged check. Measured: this happened to
#: four items on the first pass.
ROOTS: list = []


def norm(text: str) -> str:
    """Collapse run-varying detail so the same check keys the same."""
    t = text
    for r in sorted(ROOTS, key=len, reverse=True):
        if r:
            t = t.replace(r.rstrip('/'), '<ROOT>')
    t = _HEX.sub('<hex>', t)
    t = _NUM.sub('#', t)
    return ' '.join(t.split())


def _is_env(*texts) -> bool:
    blob = ' '.join(t for t in texts if t).lower()
    return any(m in blob for m in ENV_MARKERS)


def parse(path) -> dict:
    """run_suite output -> {totals, items}. Items are keyed, not positional."""
    raw = pathlib.Path(path).read_text(errors='replace')
    lines = raw.splitlines()
    out = {'path': str(path), 'totals': None, 'verdict': None, 'items': {}}
    for ln in lines:
        m = HEADER.search(ln)
        if m:
            k = ('modules', 'test_functions', 'checks', 'failing_checks',
                 'raised', 'zero_check_functions', 'blocked_functions')
            out['totals'] = dict(zip(k, (int(x) for x in m.groups())))
        if ln.strip() in ('SUITE FAIL', 'SUITE PASS'):
            out['verdict'] = ln.strip()

    def add(kind, module, ident, detail, extra=None):
        key = f'{kind}|{module}|{ident}'
        out['items'][key] = {'kind': kind, 'module': module, 'ident': ident,
                             'detail': detail, **(extra or {})}

    i = 0
    in_blocked = False
    in_zero = False
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith('blocked (declared'):
            in_blocked, in_zero = True, False
            i += 1
            continue
        if s.startswith('ZERO-CHECK FUNCTIONS:'):
            in_zero, in_blocked = True, False
            i += 1
            continue
        if in_blocked or in_zero:
            if '::' in s and not s.startswith(('CHECKS', 'RAISED', 'IMPORT',
                                               'VACUOUS')):
                mod, fn = s.split('::', 1)
                add('BLOCKED_FUNCTION' if in_blocked else 'ZERO_CHECK_FUNCTION',
                    mod.strip(), fn.strip(), s)
                i += 1
                continue
            if s:
                in_blocked = in_zero = False
            else:
                i += 1
                continue
        if s.startswith('RAISED ') and '::' in s:
            body = s[len('RAISED '):]
            mod, fn = body.split('::', 1)
            tb = []
            j = i + 1
            while j < len(lines) and lines[j].strip() and \
                    not lines[j].lstrip().startswith(
                        ('RAISED ', 'CHECKS ', 'IMPORT ', 'VACUOUS ')):
                tb.append(lines[j])
                j += 1
            last = next((x.strip() for x in reversed(tb) if x.strip()), '')
            add('RAISED', mod.strip(), fn.strip(), last,
                {'exception': last})
            i = j
            continue
        if s.startswith('IMPORT '):
            mod = s[len('IMPORT '):].strip()
            tb = []
            j = i + 1
            while j < len(lines) and lines[j].strip():
                tb.append(lines[j])
                j += 1
            last = next((x.strip() for x in reversed(tb) if x.strip()), '')
            add('IMPORT_ERROR', mod, 'module', last, {'exception': last})
            i = j
            continue
        if s.startswith('VACUOUS '):
            mod = s[len('VACUOUS '):].split(':', 1)[0].strip()
            add('VACUOUS_MODULE', mod, 'module', s)
            i += 1
            continue
        if s.startswith('CHECKS ') and ':' in s:
            head = s[len('CHECKS '):]
            mod, rest = head.split(':', 1)
            mod = mod.strip()
            n = re.search(r'(\d+) failing check', rest)
            add('MODULE_FAILING', mod, 'count',
                rest.strip(), {'n_failing': int(n.group(1)) if n else None})
            j = i + 1
            while j < len(lines):
                t = lines[j].strip()
                if not t:
                    break
                if t.startswith(('CHECKS ', 'RAISED ', 'IMPORT ', 'VACUOUS ')):
                    break
                if t.startswith('FAIL'):
                    add('FAILING_CHECK', mod, norm(t), t, {'raw': t})
                j += 1
            i = j
            continue
        i += 1
    return out


def self_check(parsed: dict) -> dict:
    """Parsed items must reconcile with the runner's own header totals.

    A parser that silently drops items produces a diff that silently
    understates a regression, which is the failure mode this whole exercise
    exists to avoid. The one legitimate shortfall is the runner's own
    `lines[:20]` truncation of FAIL lines per module; it is detected from the
    module counts rather than assumed, and reported.
    """
    t = parsed['totals'] or {}
    items = parsed['items'].values()
    got = {
        'failing_checks': sum(1 for v in items if v['kind'] == 'FAILING_CHECK'),
        'raised': sum(1 for v in items
                      if v['kind'] in ('RAISED', 'IMPORT_ERROR')),
        'zero_check_functions': sum(1 for v in items
                                    if v['kind'] == 'ZERO_CHECK_FUNCTION'),
        'blocked_functions': sum(1 for v in items
                                 if v['kind'] == 'BLOCKED_FUNCTION'),
    }
    truncated = sorted(v['module'] for v in items
                       if v['kind'] == 'MODULE_FAILING'
                       and (v.get('n_failing') or 0) > 20)
    problems = []
    for k, n in got.items():
        want = t.get(k)
        if want is None:
            continue
        if n == want:
            continue
        if k == 'failing_checks' and truncated and n < want:
            continue                      # explained by the runner's cap
        problems.append({'field': k, 'header': want, 'parsed': n})
    return {'reconciled': not problems, 'parsed_counts': got,
            'header_counts': {k: t.get(k) for k in got},
            'modules_over_the_20_line_cap': truncated,
            'problems': problems}


def classify(base: dict, cur: dict, baseline_files=None) -> dict:
    b, c = base['items'], cur['items']
    # `existed_at_baseline` is asked of GIT, not inferred from whether the
    # module produced a problem. A module that passed at baseline produces no
    # items, and calling that "new" would excuse a real regression as the
    # arrival of new code. The first pass of this tool did exactly that.
    base_files = set(baseline_files or ())
    rows = []
    for key, v in sorted(c.items()):
        env = _is_env(v.get('detail'), v.get('exception'))
        if key in b:
            same_raw = norm(b[key].get('raw') or b[key].get('detail') or '') \
                == norm(v.get('raw') or v.get('detail') or '')
            cls = PRE_EXISTING if same_raw else CHANGED
            if v['kind'] == 'MODULE_FAILING' and \
                    b[key].get('n_failing') != v.get('n_failing'):
                cls = CHANGED
        else:
            cls = NEWLY_INTRODUCED
        if env:
            cls = ENVIRONMENTAL
        rows.append({**v, 'key': key, 'classification': cls,
                     'baseline_detail': (b.get(key) or {}).get('detail'),
                     'baseline_n_failing': (b.get(key) or {}).get('n_failing'),
                     'module_existed_at_baseline':
                         (v['module'] in base_files) if base_files else None,
                     'new_module': (v['module'] not in base_files)
                     if base_files else None})
    for key, v in sorted(b.items()):
        if key not in c:
            rows.append({**v, 'key': key, 'classification': RESOLVED,
                         'baseline_detail': v.get('detail'),
                         'module_existed_at_baseline': True,
                         'new_module': False})
    counts = {}
    for r in rows:
        counts.setdefault(r['classification'], 0)
        counts[r['classification']] += 1
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r['kind'], {}).setdefault(r['classification'], 0)
        by_kind[r['kind']][r['classification']] += 1
    delta = {}
    if base['totals'] and cur['totals']:
        delta = {k: cur['totals'][k] - base['totals'][k]
                 for k in cur['totals']}
    return {
        'spec_version': SPEC_VERSION,
        'baseline': {'log': base['path'], 'totals': base['totals'],
                     'verdict': base['verdict']},
        'current': {'log': cur['path'], 'totals': cur['totals'],
                    'verdict': cur['verdict']},
        'delta_totals': delta,
        'counts_by_classification': counts,
        'counts_by_kind': by_kind,
        'newly_introduced': [r for r in rows
                             if r['classification'] == NEWLY_INTRODUCED],
        'changed': [r for r in rows if r['classification'] == CHANGED],
        'resolved': [r for r in rows if r['classification'] == RESOLVED],
        'environmental': [r for r in rows
                          if r['classification'] == ENVIRONMENTAL],
        'rows': rows,
        'roots_collapsed': list(ROOTS),
        'identity_rule': (
            'a failing check is keyed by its FAIL line with digit runs '
            'collapsed, so the same check keys the same across runs; the raw '
            'text is kept and a key match with different raw text is '
            'CHANGED_CLASSIFICATION rather than PRE_EXISTING'),
        'environmental_rule': (
            'classified ENVIRONMENTAL only when the detail names a network '
            'refusal, a live fetch or a capture this executor cannot make. '
            f'Markers: {list(ENV_MARKERS)}'),
        'not_a_licence_to_fix': (
            'PRE_EXISTING is a classification, not a task. Repairing '
            'unrelated red to obtain a green number is what this diff exists '
            'to make unnecessary.'),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--current', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--roots', default='',
                    help='comma-separated checkout roots to collapse to '
                         '<ROOT> before keying; without them a worktree path '
                         'difference reads as a regression')
    ap.add_argument('--baseline-commit', default='',
                    help='commit whose tree decides whether a module is new; '
                         'without it "new module" is left null rather than '
                         'guessed')
    ap.add_argument('--repo', default='.')
    a = ap.parse_args(argv)
    ROOTS.extend([r for r in a.roots.split(',') if r.strip()])
    base_files = None
    if a.baseline_commit:
        import subprocess
        r = subprocess.run(['git', 'ls-tree', '-r', '--name-only',
                            a.baseline_commit],
                           capture_output=True, text=True, cwd=a.repo)
        if r.returncode == 0:
            base_files = set(r.stdout.split())
        else:
            print('REFUSING: could not list the baseline commit tree; '
                  '"new module" would then be a guess.')
            return 1
    base, cur = parse(a.baseline), parse(a.current)
    if not base['totals'] or not cur['totals']:
        print('REFUSING: one of the logs has no totals line. An unfinished '
              'run cannot be diffed, and diffing it would understate the '
              'side that did not finish.')
        return 1
    for label, parsed in (('baseline', base), ('current', cur)):
        sc = self_check(parsed)
        if not sc['reconciled']:
            print(f'REFUSING: the {label} parse does not reconcile with the '
                  f"runner's own totals: {sc['problems']}. A parser that "
                  f'drops items understates a regression.')
            return 1
    d = classify(base, cur, baseline_files=base_files)
    d['self_check'] = {'baseline': self_check(base), 'current': self_check(cur)}
    pathlib.Path(a.out).write_text(json.dumps(d, indent=1, sort_keys=True))
    print(f"baseline {base['totals']}  {base['verdict']}")
    print(f"current  {cur['totals']}  {cur['verdict']}")
    print(f"delta    {d['delta_totals']}")
    print(f"classes  {d['counts_by_classification']}")
    for k, v in sorted(d['counts_by_kind'].items()):
        print(f"  {k:22s} {v}")
    if d['newly_introduced']:
        print(f"\nNEWLY INTRODUCED ({len(d['newly_introduced'])}):")
        for r in d['newly_introduced']:
            print(f"  [{r['kind']}] {r['module']}::{r['ident'][:90]}"
                  f"{'  (new module)' if r.get('new_module') else ''}")
    else:
        print('\nNEWLY INTRODUCED: none')
    print(f"written: {a.out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
