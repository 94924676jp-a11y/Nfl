#!/usr/bin/env python3.12
"""PM-1 acquisition: nflverse pbp_participation and injuries, 2016-2025, stored as downloaded, with provenance.

    python3.12 nfl/research/participation_pm1/acquire.py [--seasons 2016-2025]

Owner authorization 2026-10-11 (decision E1). Snap counts are NOT fetched: they come from Pro Football Reference, whose
terms are PROHIBITED_BY_TERMS (nfl/research/integrations/PLATFORM_TERMS_AND_APIS.md).

Each file is written to nfl/vintage/ as gzip of the ORIGINAL bytes, named hist_participation_<season>.<sha16>.csv.gz
and hist_injuries_<season>.<sha16>.csv.gz. The names were chosen so that no existing glob in the repository
(injuries.*.csv.gz, pbp_*.csv.gz) can pick them up and change a live path. sha16 is the first 16 hex characters of the
original file's SHA-256. ACQUISITION.json records URL, retrieval time, HTTP status, byte count and full SHA-256 of
every file, and every refusal. An empty or non-200 response is a named refusal, never a stored file.

Licence: participation is FTN data distributed by nflverse under CC-BY-SA 4.0 (attribution: FTN Data via nflverse).
Injuries are distributed by nflverse; the upstream source's terms apply (recorded UNKNOWN in the terms audit).
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[3]
VINTAGE = _REPO / 'nfl/vintage'
RECORD = pathlib.Path(__file__).with_name('ACQUISITION.json')
URLS = {
    'participation': 'https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_{s}.csv',
    'injuries': 'https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{s}.csv',
}
#: a real season file is far larger than this; anything smaller is an error page or an empty release, not data
MIN_BYTES = {'participation': 1_000_000, 'injuries': 50_000}


def fetch(kind: str, season: int) -> dict:
    url = URLS[kind].format(s=season)
    rec = {'kind': kind, 'season': season, 'url': url,
           'retrieved_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            status, body = r.status, r.read()
    except Exception as e:  # noqa: BLE001
        rec.update(state='REFUSED', code='FETCH_FAILED', detail=f'{type(e).__name__}: {e}')
        return rec
    rec.update(http_status=status, bytes=len(body))
    if status != 200 or len(body) < MIN_BYTES[kind] or not body[:200].decode('utf-8', 'replace').count(','):
        rec.update(state='REFUSED', code='NOT_A_DATA_FILE',
                   detail=f'status {status}, {len(body)} bytes, head {body[:80]!r}')
        return rec
    sha = hashlib.sha256(body).hexdigest()
    fam = 'hist_participation' if kind == 'participation' else 'hist_injuries'
    out = VINTAGE / f'{fam}_{season}.{sha[:16]}.csv.gz'
    if not out.exists():
        out.write_bytes(gzip.compress(body, compresslevel=9, mtime=0))
    header = body.split(b'\n', 1)[0].decode('utf-8', 'replace').strip().split(',')
    rec.update(state='STORED', sha256=sha, path=str(out.relative_to(_REPO)), stored_bytes=out.stat().st_size,
               n_lines=body.count(b'\n'), header=header)
    return rec


def restore() -> int:
    """Re-fetch every RECORDED file missing from disk and keep it only if its SHA-256 equals the recorded one.

    The injuries files are not redistributed by this repository (NOTICE.md, owner decision 2026-10-12), so a fresh
    checkout reproduces PM-1 with this. An upstream file that has changed since 2026-10-11 is REFUSED, never
    substituted: PM-1's tables were computed on the recorded bytes."""
    rec = json.loads(RECORD.read_text())
    bad = 0
    for r in rec['files']:
        if r.get('state') != 'STORED':
            continue
        out = _REPO / r['path']
        if out.exists():
            continue
        try:
            with urllib.request.urlopen(r['url'], timeout=120) as h:
                body = h.read()
        except Exception as e:  # noqa: BLE001
            print(f"REFUSED FETCH_FAILED {r['path']}: {type(e).__name__}: {e}")
            bad += 1
            continue
        sha = hashlib.sha256(body).hexdigest()
        if sha != r['sha256']:
            print(f"REFUSED UPSTREAM_CHANGED {r['path']}: got {sha[:16]}, recorded {r['sha256'][:16]}")
            bad += 1
            continue
        out.write_bytes(gzip.compress(body, compresslevel=9, mtime=0))
        print(f"RESTORED {r['path']}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--seasons', default='2016-2025')
    ap.add_argument('--restore', action='store_true',
                    help='re-fetch recorded files missing from disk, refusing any whose bytes differ from the record')
    a = ap.parse_args()
    if a.restore:
        return restore()
    lo, hi = (int(x) for x in a.seasons.split('-'))
    prev = json.loads(RECORD.read_text()) if RECORD.exists() else {'ARTIFACT': 'PM1_ACQUISITION', 'files': []}
    for s in range(lo, hi + 1):
        for kind in ('participation', 'injuries'):
            r = fetch(kind, s)
            prev['files'].append(r)
            print(f"{kind:13s} {s} {r['state']:8s} {r.get('bytes', '-'):>10} {r.get('sha256', r.get('detail', ''))[:40]}",
                  flush=True)
            RECORD.write_text(json.dumps(prev, indent=1) + '\n')
    bad = [r for r in prev['files'] if r['state'] != 'STORED']
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
