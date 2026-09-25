#!/usr/bin/env python3.12
"""Read the live or last suite run out of the append-only progress file.

    python3.12 nfl/tools/suite_progress.py           # the most recent run
    python3.12 nfl/tools/suite_progress.py --all     # every run in the file
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PATH = os.environ.get('NFL_SUITE_PROGRESS',
                      str(REPO / 'nfl/tests/_suite_progress.jsonl'))


def runs(path=PATH) -> dict:
    out = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        out.setdefault(r.get('run_id', '?'), []).append(r)
    return out


def summarise(rows: list) -> str:
    start = next((r for r in rows if r.get('phase') == 'suite_start'), None)
    done = [r for r in rows if r.get('phase') == 'module_done']
    n = start.get('n_modules') if start else '?'
    bad = [r for r in done if r.get('result') in ('FAIL', 'IMPORT_ERROR')]
    notally = [r for r in done if r.get('result') == 'NO_TALLY']
    fin = any(r.get('phase') == 'suite_scan_done' for r in rows)
    lines = [f'  modules done {len(done)} of {n}   elapsed {rows[-1]["t"]}s'
             f'   {"COMPLETE" if fin else "IN FLIGHT / STOPPED EARLY"}',
             f'  failing or import-error: {len(bad)}   NO_TALLY: '
             f'{len(notally)}']
    for r in bad[:20]:
        lines.append(f'    {r["result"]:<13} {r["module"]} '
                     f'failing={r.get("checks_failing")}')
    if not fin and done:
        lines.append(f'  last module entered: {rows[-1].get("module")}')
    return '\n'.join(lines)


def main() -> int:
    rs = runs()
    if not rs:
        print(f'no progress recorded at {PATH}')
        return 0
    keys = sorted(rs) if '--all' in sys.argv else [sorted(rs)[-1]]
    for k in keys:
        print(f'run {k}')
        print(summarise(rs[k]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
