#!/usr/bin/env python3.12
"""The lock-critical classic-slate run, in order, one process per stage, with a ledger.

    python3.12 nfl/tools/classic_slate_pipeline.py 2026W4 --as-of 2026-10-04T15:40:00Z \
        [--official-inactives nfl/dfs/salaries/raw/INACTIVES_2026W4.json] --page <scratch>/page.html

Owner priority 17 (2026-10-03). Each stage is the production tool itself, run as a separate process
so a firewall that refuses on imported modules (FantasyCruncher, Hard Rock) sees a clean process.
The run STOPS at the first stage that refuses, except the two downstream comparisons (FC, Hard Rock),
whose refusal is recorded and does not touch a lineup.

  0 snapshot       copy the current artifacts to runs/<slate>/<utc>/ for the change log
  1 state          DK universe, freshness gate, identity, availability, inactives, depth
  2 run            role state -> football-only projection -> sanity gate -> 2,000 joint worlds
  3 book           research book, team accounting gate, forecast seal
  4 portfolios     150-max, 20-max, 3-entry (refused without a current book with accounting PASS)
  5 verify         independent upload verifier
  6 book           rebuilt with exposures (the seal time stands if the worlds are unchanged)
  7 board          owner board and exposure reasoning
  8 fc             FantasyCruncher comparison, clean process, EXTERNAL_COMPARISON_ONLY
  9 props          Hard Rock comparison against the seal (BLOCKED until a post-seal board exists)
 10 audit          independent production audit
 11 changes        change log against the snapshot
 12 page           owner page
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import shutil
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = _REPO / 'nfl/dfs/salaries'
PY = 'python3.12'
SNAP = ('STATE.json', 'PROJ.json', 'DRAWS.json', 'RESEARCH_BOOK.json', 'PORTFOLIOS.json', 'UPLOAD.csv',
        'PROP_DIAGNOSTIC.json', 'OWNER_BOARD.json', 'SEAL.json')
DOWNSTREAM_ONLY = {'fc', 'props'}


def stages(slate, as_of, inactives, page):
    st = [PY, 'nfl/tools/classic_slate_state.py', slate, '--as-of', as_of]
    if inactives:
        st += ['--official-inactives', inactives]
    return [('state', st),
            ('run', [PY, 'nfl/tools/classic_slate_run.py', slate]),
            ('book', [PY, 'nfl/tools/classic_research_book.py', slate]),
            ('portfolios', [PY, 'nfl/opt/classic_portfolio.py', slate]),
            ('verify', [PY, 'nfl/tools/classic_upload_verify.py', slate]),
            ('book_with_exposures', [PY, 'nfl/tools/classic_research_book.py', slate]),
            ('board', [PY, 'nfl/tools/classic_owner_board.py', slate]),
            ('fc', [PY, 'nfl/tools/classic_fc_compare.py', slate]),
            ('props', [PY, 'nfl/tools/classic_prop_compare.py', slate]),
            ('audit', [PY, 'nfl/tools/classic_production_audit.py', slate]),
            ('changes', [PY, 'nfl/tools/classic_change_log.py', slate]),
            ('page', [PY, 'nfl/tools/classic_owner_page.py', slate, '--out', page])]


def snapshot(slate):
    ts = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    d = OUT_DIR / 'runs' / slate / ts
    d.mkdir(parents=True, exist_ok=True)
    kept = []
    for n in SNAP:
        p = OUT_DIR / f'DK_{slate}_EARLY_{n}'
        if p.exists():
            shutil.copy2(p, d / p.name)
            kept.append(n)
    (OUT_DIR / 'runs' / slate / 'LATEST_SNAPSHOT').write_text(ts)
    return d, kept


def run(slate, as_of, inactives, page, dry=False):
    snap, kept = (OUT_DIR / "runs" / slate / "DRY_RUN_NO_SNAPSHOT", []) if dry else snapshot(slate)
    ledger = {'ARTIFACT': 'CLASSIC_PIPELINE_RUN', 'slate_id': slate, 'as_of': as_of, 'inactives_file': inactives,
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'snapshot': {'dir': str(snap.relative_to(_REPO)), 'files': kept}, 'stages': [], 'STATE': 'RUNNING'}
    for name, cmd in stages(slate, as_of, inactives, page):
        if dry:
            ledger['stages'].append({'stage': name, 'cmd': cmd, 'rc': None, 'result': 'DRY_RUN'})
            continue
        t0 = dt.datetime.now(dt.timezone.utc)
        p = subprocess.run(cmd, cwd=_REPO, capture_output=True, text=True)
        lines = [ln for ln in (p.stdout or '').splitlines() if ln.strip()]
        verdicts = [ln for ln in lines if re.match(r'^(PASS|FAIL|BLOCKED)\[', ln)]
        last = verdicts[-1:] or lines[-1:] or ['']   # the tool's verdict line, not trailing JSON
        rec = {'stage': name, 'cmd': cmd, 'rc': p.returncode, 'result': last[0][:400],
               'seconds': round((dt.datetime.now(dt.timezone.utc) - t0).total_seconds(), 1),
               'stderr_tail': (p.stderr or '')[-600:] if p.returncode else ''}
        ledger['stages'].append(rec)
        if p.returncode != 0 and name not in DOWNSTREAM_ONLY:
            ledger['STATE'] = f'STOPPED_AT_{name.upper()}'
            break
    else:
        ledger['STATE'] = 'DRY_RUN' if dry else 'COMPLETE'
    ledger['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    (OUT_DIR / f'DK_{slate}_EARLY_RUN_LEDGER.json').write_text(json.dumps(ledger, indent=1))
    return ledger


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--official-inactives', default=None)
    ap.add_argument('--page', required=True)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    led = run(a.slate_id, a.as_of, a.official_inactives, a.page, dry=a.dry_run)
    for s in led['stages']:
        print(f"{s['stage']:20} rc={s['rc']} {s['result']}")
    print(led['STATE'])
    return 0 if led['STATE'] in ('COMPLETE', 'DRY_RUN') else 1


if __name__ == '__main__':
    sys.exit(main())
