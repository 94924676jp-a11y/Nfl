#!/usr/bin/env python3.12
"""Who reads `vintage_manifest.jsonl`, and which of them assume it is one file.

    python3.12 nfl/tools/manifest_consumer_census.py [--json]

WHY THIS RUNS BEFORE ANY SHARDING

The manifest is 53.55 MB over 6,757 records and grows ~0.81 MB/day; the hard
push rejection lands near 2026-11-21. Sharding it is an owner decision and is
NOT taken here. What is taken here is the thing that decision needs: a list of
every consumer and which ones would break.

The distinction that matters is not "reads the manifest" but **how**:

  PARAMETERISED     takes a manifest path as an argument. A shard-aware loader
                    can be passed in and the module never notices.
  HARDCODED         builds `_REPO / 'nfl' / 'vintage_manifest.jsonl'` itself.
                    Sharding requires editing this module.
  WHOLE_FILE_SCAN   iterates every record to find what it wants. Sharding
                    changes its cost and, if it stops at the first match,
                    possibly its answer.
  INDEX_ASSUMED     relies on ordering or on "the last matching record wins".
                    These are the dangerous ones: split the file and the
                    winner can change without any error.

A module can be several of these. The census does not decide anything; it makes
the blast radius countable before somebody estimates it from memory.

HEURISTIC, AND SAID SO
This reads source text, not behaviour. A row here is a question for a human,
and the counts are a floor rather than a survey.

LIMITS
  This is a source-text (or record-level) heuristic, not a behavioural
  measurement. Every row it emits is a question for a human, the counts are a
  floor rather than a survey, and it does not know what is deliberate.
"""
from __future__ import annotations

import json
import re
import sys
import pathlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / 'nfl'
NEEDLE = 'vintage_manifest'

_PARAM = re.compile(r'def \w+\([^)]*manifest(?:_path)?\s*[=,)]', re.S)
_HARD = re.compile(r"['\"]vintage_manifest\.jsonl['\"]")
_SCAN = re.compile(r'\.read_text\(\)\.splitlines\(\)|for .* in open\(|'
                   r'\.readlines\(\)|splitlines\(\)')
_ORDER = re.compile(r'\[-1\]|reversed\(|sorted\(|max\(|last\b|newest')


def classify(src: str) -> list:
    tags = []
    if _PARAM.search(src):
        tags.append('PARAMETERISED')
    if _HARD.search(src):
        tags.append('HARDCODED')
    if _SCAN.search(src):
        tags.append('WHOLE_FILE_SCAN')
    if _ORDER.search(src):
        tags.append('INDEX_ASSUMED')
    return tags or ['MENTIONS_ONLY']


def census() -> dict:
    out = {}
    for p in sorted(PKG.rglob('*.py')):
        if '__pycache__' in p.parts:
            continue
        try:
            src = p.read_text()
        except OSError:
            continue
        if NEEDLE not in src:
            continue
        rel = str(p.relative_to(REPO))
        # EXCLUDE SELF. An auditor that counts its own mentions inflates the
        # number it exists to report. This is the third tool in this repo to
        # need the line: discovery_audit counted six of its own references,
        # cross_layer_audit needed the same exclusion, and this one listed
        # itself as a manifest consumer that would need editing to shard.
        if rel == str(pathlib.Path(__file__).resolve().relative_to(REPO)):
            continue
        out[rel] = {
            'tags': classify(src),
            'tree': ('tests' if '/tests/' in rel
                     else 'research' if '/research/' in rel else 'production'),
            'n_mentions': src.count(NEEDLE),
        }
    return out


def main() -> int:
    c = census()
    if '--json' in sys.argv:
        print(json.dumps(c, indent=1, sort_keys=True))
        return 0
    trees = {}
    tagc = {}
    for rel, d in c.items():
        trees.setdefault(d['tree'], []).append(rel)
        for t in d['tags']:
            tagc[t] = tagc.get(t, 0) + 1
    print(f'MANIFEST CONSUMER CENSUS  {len(c)} file(s) mention {NEEDLE}\n')
    for t in sorted(trees):
        print(f'  {t:<12} {len(trees[t])}')
    print('\nby tag (a file may carry several):')
    for t, n in sorted(tagc.items(), key=lambda kv: -kv[1]):
        print(f'  {t:<18} {n}')
    blast = sorted(rel for rel, d in c.items()
                   if d['tree'] != 'tests'
                   and 'PARAMETERISED' not in d['tags']
                   and 'MENTIONS_ONLY' not in d['tags'])
    print(f'\nWOULD REQUIRE AN EDIT TO SHARD ({len(blast)}), '
          f'non-test, not parameterised:')
    for rel in blast:
        print(f'  {",".join(c[rel]["tags"]):<45} {rel}')
    risky = sorted(rel for rel, d in c.items()
                   if d['tree'] != 'tests' and 'INDEX_ASSUMED' in d['tags']
                   and 'WHOLE_FILE_SCAN' in d['tags'])
    print(f'\nANSWER COULD CHANGE SILENTLY ({len(risky)}) -- scans the whole '
          f'file AND depends on order:')
    for rel in risky:
        print(f'  {rel}')
    print('\nThis is a source-text heuristic. Every row is a question for a '
          'human, and the counts are a floor.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
