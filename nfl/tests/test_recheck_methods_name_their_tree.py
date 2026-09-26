#!/usr/bin/env python3.12
"""A recheck that does not say which tree it read is not a recheck.

MEASURED 2026-09-26, and I made the error before I found it. Every
manifest-based `recheck_method` in nfl/INFORMATION_GAP_REGISTRY.json named a
path -- `nfl/vintage_manifest.jsonl` -- and no tree. So a recheck reads whatever
checkout the reader happens to be standing on, and the checkouts do not agree:

    nfl/vintage_manifest.jsonl      rows   newest depth_charts capture
      origin/capture-prod           9561   2026-09-26T19:35:22Z   <- authoritative
      engineering branch            6757   2026-09-24T06:07:41Z   2 days behind
      origin/main                   4311   2026-09-15T19:05:04Z   11 days behind

    nfl/availability_manifest.jsonl rows
      origin/main                     70   <- authoritative
      engineering branch              25
      origin/capture-prod             24

The two manifests have DIFFERENT authoritative trees, because
`nfl-capture.yml` checks out and commits to capture-prod while
`nfl-availability.yml` checks out main and pushes to main. So there is not even
a single blanket rule a careless reader could fall back on.

I read depth_charts off the engineering branch first and was about to record
that the capture series had gone quiet two days ago. It had not: capture-prod
held a capture from nineteen minutes earlier. That is the exact sentence
`nfl/production/capture_cadence.py` exists to refuse -- "this file's age is the
age of this checkout and not of the system" -- and DEF-075 records that the
module is absent from both trees that run the capture pipeline.

This test makes the registry state the tree, so the next reader cannot make that
mistake from the method field alone.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
REG = _REPO / 'nfl' / 'INFORMATION_GAP_REGISTRY.json'

passed = failed = 0

#: manifest filename -> the tree that holds the authoritative copy, and why.
AUTHORITATIVE = {
    'vintage_manifest.jsonl': (
        'origin/capture-prod',
        'nfl-capture.yml and nfl-t90.yml check out env.CAPTURE_BRANCH '
        '(capture-prod) and commit captures there'),
    'availability_manifest.jsonl': (
        'origin/main',
        'nfl-availability.yml takes a bare checkout (the default branch) and '
        'ends with `git push origin HEAD:main`'),
}


def check(label, cond, detail=''):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f'  FAIL {label}  {detail}')


def gaps():
    return json.loads(REG.read_text())['gaps']


def test_every_manifest_recheck_method_names_its_tree():
    offenders = []
    checked = 0
    for g in gaps():
        m = str(g.get('recheck_method') or '')
        for fname, (tree, _why) in AUTHORITATIVE.items():
            if fname not in m:
                continue
            checked += 1
            if tree not in m:
                offenders.append({'gap': g['id'], 'manifest': fname,
                                  'expected_tree': tree, 'method': m[:70]})
    check('at least one manifest-based recheck exists to check', checked > 0,
          checked)
    check(f'every one of the {checked} manifest-based recheck methods names '
          f'its authoritative tree', not offenders, offenders)


def test_the_trees_really_do_disagree_so_this_is_not_pedantry():
    """If the three copies agreed, naming the tree would be decoration."""
    def rows(ref):
        out = subprocess.run(
            ['git', 'show', f'{ref}:nfl/vintage_manifest.jsonl'],
            cwd=_REPO, capture_output=True, text=True)
        return out.stdout.count('\n') if out.returncode == 0 else None
    cap = rows('origin/capture-prod')
    main = rows('origin/main')
    if cap is None or main is None:
        check('both trees readable', False, f'capture-prod={cap} main={main}')
        return
    check('capture-prod holds strictly more manifest rows than main, so the '
          'tree a recheck reads changes its answer', cap > main,
          f'capture-prod={cap} main={main}')


def test_a_recheck_that_was_performed_records_which_tree_it_read():
    """`recheck_evidence` is where the measurement lives. It must be traceable
    to a tree, or it is a number with no provenance -- which is the thing this
    whole register exists to refuse."""
    done = [g for g in gaps() if g.get('recheck_evidence')]
    check('some recheck evidence exists', bool(done), len(done))
    for g in done:
        ev = str(g['recheck_evidence'])
        check(f"{g['id']} recheck evidence names the tree it read",
              any(t in ev for t in ('origin/', 'capture-prod')), ev[:90])


def test_the_horizon_is_measured_against_evidence_not_against_the_reading():
    """The registry's own rule, asserted rather than trusted.

    `recheck_horizon_days` runs on `evidence_as_of_utc`, never on
    `last_rechecked_utc`, because re-reading an unchanged file is not a recheck.
    nfl/tools/discovery.py:220 honours this. I got it wrong by hand first, which
    is why it is pinned here.
    """
    d = json.loads(REG.read_text())
    rule = str(d.get('recheck_rule') or '')
    check('the rule is still stated in the artifact',
          'evidence_as_of_utc' in rule and 'NEVER' in rule, rule[:80])
    src = (_REPO / 'nfl/tools/discovery.py').read_text()
    m = re.search(r"declared = g\.get\('(\w+)'\)", src)
    check('the detector reads the declared evidence instant, not the reading',
          m is not None and m.group(1) == 'evidence_as_of_utc',
          m.group(1) if m else 'pattern not found')


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_recheck_methods_name_their_tree: {passed} ok, {failed} failed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
