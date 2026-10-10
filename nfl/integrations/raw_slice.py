#!/usr/bin/env python3.12
"""Refresh a slate's raw roster slice from the newest full roster capture, keeping every earlier slice.

    python3.12 nfl/integrations/raw_slice.py --raw-dir nfl/dfs/salaries/raw/classic_early_2026W5

WHY (gap INT-G1). The scheduled capture commits a REDUCED weekly-roster blob without `status` or names, so the
research universe reads a hand-made slice of the full file in the slate's raw directory. That slice went stale: on
2026-10-10 it still listed Kaytron Allen on WAS after WAS waived him (W03) and MIA signed him, and it lacked two
players newly active on slate clubs. This tool closes the gap without touching the capture code: it takes the
newest full roster file the capture left on disk (`nfl_vintage/raw/weekly_rosters.<sha16>.csv`, matched to a
manifest PASS row by its sha), keeps the rows of the slate's clubs, and writes
`NFLVERSE_ROSTER_WEEKLY_2026.<full-sha16>.slate16.csv.gz`.

The previous slice is MOVED to `<raw-dir>/superseded/`, never deleted, because the research universe requires
exactly one slice in the directory. Every refresh appends to PROVENANCE.json. A refresh to identical bytes is a
no-op (RAW_SLICE_UNCHANGED).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

STEM = 'NFLVERSE_ROSTER_WEEKLY_2026'
FULL_DIR = _REPO / 'nfl_vintage' / 'raw'
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'


def newest_full_roster(manifest=MANIFEST, full_dir=FULL_DIR):
    """(capture_id, sha256, path) of the newest PASS weekly_rosters row whose full file is on disk, or None."""
    best = None
    for ln in open(manifest):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('source') != 'weekly_rosters' or r.get('state') != 'PASS':
            continue
        sha = (r.get('value') or {}).get('sha256') or ''
        p = pathlib.Path(full_dir) / f'weekly_rosters.{sha[:16]}.csv'
        if sha and p.exists() and (best is None or str(r['capture_id']) > best[0]):
            best = (str(r['capture_id']), sha, p)
    return best


def slate_clubs(raw_dir):
    """Clubs of the slice currently in the directory (the slate does not change between refreshes)."""
    cur = sorted(pathlib.Path(raw_dir).glob(f'{STEM}.*.csv.gz'))
    if len(cur) != 1:
        return None, cur
    rows = csv.DictReader(io.StringIO(gzip.decompress(cur[0].read_bytes()).decode()))
    return sorted({r['team'] for r in rows}), cur


def refresh(raw_dir, *, manifest=MANIFEST, full_dir=FULL_DIR, now=None) -> Outcome:
    raw_dir = pathlib.Path(raw_dir).resolve()
    clubs, cur = slate_clubs(raw_dir)
    if clubs is None:
        return Outcome.fail('RAW_SLICE_NOT_EXACTLY_ONE', f'{len(cur)} roster slices in {raw_dir}; expected one')
    src = newest_full_roster(manifest, full_dir)
    if src is None:
        return Outcome.blocked('RAW_SLICE_NO_FULL_ROSTER_ON_DISK',
                               'no PASS weekly_rosters capture has its full file in nfl_vintage/raw; run capture_vintage',
                               cause=Cause.EMPTY_INPUT)
    cid, sha, path = src
    name = f'{STEM}.{sha[:16]}.slate16.csv.gz'
    if cur[0].name == name:
        return Outcome.ok('RAW_SLICE_UNCHANGED', value=str(cur[0]), detail=f'{name} is already the slice')
    text = path.read_text()
    if hashlib.sha256(text.encode()).hexdigest() != sha:
        return Outcome.fail('RAW_SLICE_FULL_FILE_SHA_MISMATCH', f'{path.name} does not hash to its manifest row')
    rd = csv.DictReader(io.StringIO(text))
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=rd.fieldnames, lineterminator='\n')
    w.writeheader()
    kept = 0
    for r in rd:
        if r['team'] in clubs:
            w.writerow(r)
            kept += 1
    if not kept:
        return Outcome.blocked('RAW_SLICE_EMPTY', f'no rows for {clubs}', cause=Cause.DATA)
    (raw_dir / name).write_bytes(gzip.compress(out.getvalue().encode(), mtime=0))
    sup = raw_dir / 'superseded'
    sup.mkdir(exist_ok=True)
    cur[0].rename(sup / cur[0].name)
    pv = raw_dir / 'PROVENANCE.json'
    d = json.loads(pv.read_text()) if pv.exists() else {'files': []}
    d.setdefault('slice_refreshes', []).append({
        'refreshed_at_utc': now or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'kind': STEM, 'file': str((raw_dir / name).relative_to(_REPO)) if raw_dir.resolve().is_relative_to(_REPO)
        else str(raw_dir / name), 'full_file_sha256': sha, 'source_capture_id': cid, 'rows_kept': kept,
        'filter': f'team in the {len(clubs)} slate clubs', 'superseded': f'superseded/{cur[0].name}',
        'tool': 'nfl/integrations/raw_slice.py'})
    pv.write_text(json.dumps(d, indent=1) + '\n')
    return Outcome.ok('RAW_SLICE_REFRESHED', value=str(raw_dir / name),
                      detail=f'{cur[0].name} -> {name} ({kept} rows, capture {cid})')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--raw-dir', required=True)
    a = ap.parse_args(argv)
    o = refresh(a.raw_dir)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
