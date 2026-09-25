#!/usr/bin/env python3.12
"""How many distinct row counts does each captured source ever produce?

    python3.12 nfl/tools/source_rowcount_census.py [--json]

THE QUESTION NOBODY HAD ASKED

Truncation is usually hunted by looking for a suspicious number -- 25 per club,
100 per page, a round 1000. That only finds the cap you already suspect. This
asks a question with no number in it: does this feed's row count VARY the way a
live feed's must?

Run on 2026-09-25 it found `espn_injuries_json` taking exactly two values in 648
captures -- 35 until 2026-09-15T17:05Z and 800 after 19:36Z, every one recorded
PASS, from payloads that were always ~8.8 MB and always varying. 800 is 25x32,
the known per-club cap. 35 was a parser extracting almost nothing from a whole
document for 436 consecutive captures, and nobody had characterised it.

TWO SIGNATURES

  DEGENERATE   very few distinct counts relative to the number of captures. A
               feed that answers the same way every day is not answering.
  STEP         the set of counts before a date and after it do not overlap. A
               schema or parser change that held on both sides, which is what
               makes it invisible: every individual capture looks self-consistent.

A static file legitimately produces one count forever, so a hit is a question,
not a defect. The tool prints what it measured and leaves the reading to a human.

LIMITS
  This is a source-text (or record-level) heuristic, not a behavioural
  measurement. Every row it emits is a question for a human, the counts are a
  floor rather than a survey, and it does not know what is deliberate.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'nfl/vintage_manifest.jsonl'

#: Below this many distinct counts, for a source captured at least
#: MIN_CAPTURES times, the feed is not varying like a live one.
DEGENERATE_MAX_DISTINCT = 3
MIN_CAPTURES = 20


def load(path=MANIFEST) -> dict:
    """source -> [(capture_id, n_data_rows)], in capture order."""
    out = collections.defaultdict(list)
    for line in Path(path).open():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        v = r.get('value')
        if not isinstance(v, dict):
            continue
        n = v.get('n_data_rows')
        if isinstance(n, int) and not isinstance(n, bool):
            out[r.get('source', '?')].append((r.get('capture_id', ''), n))
    return {k: sorted(v) for k, v in out.items()}


#: A step needs this many captures on each side, and each side must itself be
#: near-constant. Without the second condition the detector fires on every
#: cumulative file: a monotonically growing count makes the very first split
#: disjoint, so `depth_charts` reported a "step" at its second capture. A
#: growing file is expected; two flat plateaus at different heights are not.
MIN_SIDE = 10


def step_change(pairs) -> dict | None:
    """A split into two near-constant plateaus at different heights."""
    counts = [n for _, n in pairs]
    best = None
    for i in range(MIN_SIDE, len(pairs) - MIN_SIDE + 1):
        before, after = set(counts[:i]), set(counts[i:])
        if not before.isdisjoint(after):
            continue
        if len(before) > DEGENERATE_MAX_DISTINCT:
            continue
        if len(after) > DEGENERATE_MAX_DISTINCT:
            continue
        cand = {'at_capture': pairs[i][0],
                'last_before': pairs[i - 1][0],
                'n_before': i, 'n_after': len(pairs) - i,
                'before': sorted(before), 'after': sorted(after)}
        if best is None or min(cand['n_before'], cand['n_after']) > min(
                best['n_before'], best['n_after']):
            best = cand
    return best


def census(path=MANIFEST) -> dict:
    out = {}
    for src, pairs in sorted(load(path).items()):
        counts = [n for _, n in pairs]
        c = collections.Counter(counts)
        rec = {
            'n_captures': len(pairs),
            'n_distinct': len(c),
            'most_common': c.most_common(5),
            'window': [pairs[0][0], pairs[-1][0]] if pairs else [],
            'flags': [],
        }
        if len(pairs) >= MIN_CAPTURES and len(c) <= DEGENERATE_MAX_DISTINCT:
            rec['flags'].append('DEGENERATE')
        st = step_change(pairs)
        if st and len(pairs) >= MIN_CAPTURES:
            rec['flags'].append('STEP')
            rec['step'] = st
        out[src] = rec
    return out


def main() -> int:
    c = census()
    if '--json' in sys.argv:
        print(json.dumps(c, indent=1, sort_keys=True))
        return 0
    print(f'SOURCE ROW-COUNT CENSUS  {MANIFEST.name}\n')
    print(f'{"source":<26}{"captures":>9}{"distinct":>9}  flags')
    for src, r in sorted(c.items(), key=lambda kv: -kv[1]['n_captures']):
        print(f'{src:<26}{r["n_captures"]:>9}{r["n_distinct"]:>9}  '
              f'{",".join(r["flags"])}')
    for src, r in sorted(c.items()):
        if not r['flags']:
            continue
        print(f'\n== {src}  {",".join(r["flags"])} ==')
        print(f'  counts: {r["most_common"]}')
        print(f'  window: {r["window"][0]} -> {r["window"][1]}')
        if 'step' in r:
            s = r['step']
            print(f'  step at {s["at_capture"]} (last before '
                  f'{s["last_before"]})')
            print(f'    before {s["before"]}\n    after  {s["after"]}')
    print('\nA static file legitimately produces one count forever, so a flag '
          'is a question, not a defect.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
