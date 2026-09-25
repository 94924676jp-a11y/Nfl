#!/usr/bin/env python3.12
"""Cross-layer completeness audit: find the joins nobody makes.

    python3.12 nfl/tools/cross_layer_audit.py [<draw_manifest.json>]

WHY THIS EXISTS

On 2026-09-24 a DFS portfolio was selected from a universe built off the
`dk_scoring` layer alone. Both kickers were modelled, in their own `kicking`
layer, with the lowest zero-probability of any players on the slate. Nothing
failed. No test broke. The portfolio was simply built out of 27 of 29 available
players and reported as complete.

Every module involved was correct in isolation. The defect lived in the SPACE
BETWEEN two stages, which is where no unit test looks. This tool audits that
space, and is written so the kicker defect is one output row among many rather
than a special case somebody had to remember.

THE RELATIONS IT CHECKS

ORPHANED_OUTPUT     a declared family is produced and no non-test consumer
                    outside the producing module ever reads it.
UNIVERSE_MISMATCH   a player carries football in one layer and vanishes from
                    another that downstream treats as the roster.
PARTIAL_JOIN        a consumer reads some of the player-bearing scoring layers
                    and not the rest.
FIXTURE_PINNED      a module presenting as production resolves inputs from a
                    hard-coded single-game fixture directory, so it cannot run
                    for another game whatever its imports suggest.

WHAT IT DOES NOT DO

It does not judge severity and does not know what is deliberate. A row here is
a question that must be answered in writing, not a bug.

LIMITS
  This is a source-text (or record-level) heuristic, not a behavioural
  measurement. Every row it emits is a question for a human, the counts are a
  floor rather than a survey, and it does not know what is deliberate.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / 'nfl'
REGISTRY = REPO / 'nfl/production/contracts/registry.py'

#: Layers whose rows are players and whose values are DK-relevant. Any of them
#: missing from a DFS universe silently shrinks the searchable contest.
DK_BEARING = ('dk_scoring', 'kicking')

_FIXTURE = re.compile(r"['\"][^'\"]*(?:20\d\d[_-]?W\d+|"
                      r"[A-Z]{2,3}_[A-Z]{2,3}_20\d\d|20\d\d_\d\d_[A-Z]{2,3})"
                      r"[^'\"]*['\"]")

PRODUCTION_TREES = ('nfl/production', 'nfl/dfs', 'nfl/product', 'nfl/truth',
                    'nfl/postgame', 'nfl/market', 'nfl/prospective')


def declared_families() -> dict:
    """layer -> set(metrics), exactly as the contract registry declares."""
    out = {}
    for node in ast.walk(ast.parse(REGISTRY.read_text())):
        if not isinstance(node, ast.Call):
            continue
        kw = {k.arg: k.value for k in node.keywords}
        if 'name' not in kw or 'row_axis' not in kw:
            continue
        try:
            name = ast.literal_eval(kw['name'])
            metrics = ast.literal_eval(kw['metrics']) if 'metrics' in kw else ()
        except (ValueError, TypeError):
            continue
        if isinstance(name, str):
            out[name] = set(metrics)
    return out


def _py_files():
    for p in sorted(PKG.rglob('*.py')):
        if '__pycache__' not in p.parts:
            yield p


def consumers(token: str) -> dict:
    """Files mentioning `token`, split test / producer / real consumer."""
    hits = {'tests': [], 'producer': [], 'consumers': []}
    for p in _py_files():
        try:
            s = p.read_text()
        except OSError:
            continue
        if token not in s:
            continue
        rel = str(p.relative_to(REPO))
        if '/tests/' in rel or rel.split('/')[-1].startswith('test_'):
            hits['tests'].append(rel)
        elif 'contracts/registry' in rel or 'run_forecast' in rel:
            hits['producer'].append(rel)
        else:
            hits['consumers'].append(rel)
    return hits


def untested_refusal_codes() -> tuple:
    """(untested, total) refusal codes declared outside research and tests.

    A code is counted as tested when its literal appears ANYWHERE in the test
    corpus, which is generous: the real coverage is lower than this reports.
    The ratchet uses it because a generous measure that cannot drift upward is
    worth more than a precise one nobody maintains.
    """
    pat = re.compile(
        r"(?:Outcome\.(?:fail|blocked|refus\w*)|raise \w*Error)"
        r"\(\s*'([A-Z][A-Z0-9_]{5,})'")
    tests = '\n'.join(
        p.read_text() for p in sorted((PKG / 'tests').glob('*.py')))
    codes = set()
    for p in _py_files():
        rel = str(p.relative_to(REPO))
        if '/tests/' in rel or '/research/' in rel:
            continue
        codes |= set(pat.findall(p.read_text()))
    return sorted(c for c in codes if c not in tests), len(codes)


def relation_counts() -> dict:
    """kind -> count, for the ratchet. Recomputed, never read from a file."""
    fam = declared_families()
    counts = {'ORPHANED_OUTPUT': 0, 'PARTIAL_JOIN': 0, 'FIXTURE_PINNED': 0}
    census = {}
    for layer in sorted(fam):
        a, b = consumers(f"'{layer}'"), consumers(f'{layer}__')
        real = sorted(set(a['consumers']) | set(b['consumers']))
        census[layer] = set(real)
        if not real or all(c.startswith('nfl/research/') for c in real):
            counts['ORPHANED_OUTPUT'] += 1
    per = {l: census[l] for l in DK_BEARING if l in census}
    if len(per) > 1:
        for f in set().union(*per.values()):
            miss = [l for l, cs in per.items() if f not in cs]
            if miss and len(miss) < len(per):
                counts['PARTIAL_JOIN'] += 1
    for p in _py_files():
        rel = str(p.relative_to(REPO))
        if not any(rel.startswith(t) for t in PRODUCTION_TREES):
            continue
        src = p.read_text()
        for cand in _FIXTURE.finditer(src):
            lit = cand.group(0)
            if ' ' in lit or len(lit) > 120:
                continue
            counts['FIXTURE_PINNED'] += 1
            break
    return counts


def main() -> int:
    fam = declared_families()
    findings, census = [], {}

    for layer in sorted(fam):
        a, b = consumers(f"'{layer}'"), consumers(f'{layer}__')
        real = sorted(set(a['consumers']) | set(b['consumers']))
        tests = sorted(set(a['tests']) | set(b['tests']))
        census[layer] = {'consumers': real, 'tests': tests}
        if not real:
            findings.append(('ORPHANED_OUTPUT', layer,
                             'declared and produced; no non-test consumer'))
        elif all(c.startswith('nfl/research/') for c in real):
            findings.append(('ORPHANED_OUTPUT', layer,
                             'research-only consumers: ' + ', '.join(real[:4])))

    per_layer = {l: set(census[l]['consumers']) for l in DK_BEARING
                 if l in census}
    if len(per_layer) > 1:
        for f in sorted(set().union(*per_layer.values())):
            miss = [l for l, cs in per_layer.items() if f not in cs]
            if miss and len(miss) < len(per_layer):
                have = [l for l in per_layer if f in per_layer[l]]
                findings.append(('PARTIAL_JOIN', f,
                                 'reads ' + ','.join(have)
                                 + ' but never ' + ','.join(miss)))

    mpath = (Path(sys.argv[1]) if len(sys.argv) > 1 else
             REPO / 'nfl/research/unsealed/2026_03_ATL_GB/2fc4e9599f0889f1'
                    '/player_draws_manifest.json')
    if mpath.exists():
        layers = json.loads(mpath.read_text())['layers']
        gs = {l: set(d.get('row_ids') or [])
              for l, d in layers.items() if d.get('row_axis') == 'gsis_id'}
        dkrows = gs.get('dk_scoring', set())
        for l, ids in sorted(gs.items()):
            if l == 'dk_scoring':
                continue
            lost = ids - dkrows
            if lost:
                findings.append(
                    ('UNIVERSE_MISMATCH', f'{l} -> dk_scoring',
                     f'{len(lost)} of {len(ids)} row(s) carry football in {l} '
                     f'with no dk_scoring row: ' + ','.join(sorted(lost)[:4])))
    else:
        findings.append(('NOT_CHECKED', 'UNIVERSE_MISMATCH', f'no {mpath}'))

    for p in _py_files():
        rel = str(p.relative_to(REPO))
        if not any(rel.startswith(t) for t in PRODUCTION_TREES):
            continue
        try:
            s = p.read_text()
        except OSError:
            continue
        m = None
        for cand in _FIXTURE.finditer(s):
            lit = cand.group(0)
            if ' ' in lit or len(lit) > 120:
                continue          # prose in a docstring, not an input path
            m = cand
            break
        if m:
            findings.append(('FIXTURE_PINNED',
                             f'{rel}:{s[:m.start()].count(chr(10)) + 1}',
                             f'input literal {m.group(0)}'))

    print('CROSS-LAYER COMPLETENESS AUDIT')
    print(f'registry declares {len(fam)} families\n')
    print('CONSUMPTION CENSUS')
    for l in sorted(census):
        c, t = census[l]['consumers'], census[l]['tests']
        print(f'  {l:<20} {len(c):>2} consumer(s), {len(t):>2} test(s)'
              + ('' if c else '   <-- NOBODY'))
    print()
    by = {}
    for kind, subj, why in findings:
        by.setdefault(kind, []).append((subj, why))
    order = sorted(by, key=lambda k: (k == 'FIXTURE_PINNED', k))
    for kind in order:
        rows = by[kind]
        print(f'== {kind} ({len(rows)}) ==')
        cap = 12 if kind == 'FIXTURE_PINNED' else len(rows)
        for subj, why in rows[:cap]:
            print(f'  {subj}\n      {why}')
        if len(rows) > cap:
            print(f'  ... and {len(rows) - cap} more')
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
