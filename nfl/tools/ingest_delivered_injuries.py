#!/usr/bin/env python3.12
r"""Ingest a delivered authoritative injury/game-status evidence package.

    python3.12 nfl/tools/ingest_delivered_injuries.py \
        --package /path/to/sunday --season 2026 --week 1 \
        --delivered-by 'networked agent' \
        --out nfl/research/live/DELIVERED_INJURY_INGEST.json

    --dry-run     do every check and write nothing

WHY A SCRIPT AND NOT A SEQUENCE OF COMMANDS AT THE KEYBOARD

The same reason `ingest_inactives.py` is one: the window is short and the step
most likely to be skipped under time pressure is a refusal. Every guard runs
here, in order, and any one of them stops the run before a projection moves.

  1  package verified against BOTH its manifest and its checksums
  2  raw bytes preserved and content-addressed BEFORE anything is parsed
  3  identity resolved through the governed roster crosswalk, or refused
  4  statuses checked against the governed vocabulary, never corrected
  5  explicit no-designation statements recorded as their own kind
  6  quarantined evidence recorded with its reason, never adjudicated
  7  one blob, one manifest row, every clock distinct, none restamped
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.capture import delivered_injuries as DI               # noqa: E402


def _jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='delivered injury ingestion')
    ap.add_argument('--package', required=True)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--delivered-by', required=True)
    ap.add_argument('--roster-csv', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--vintage-root', default=None)
    ap.add_argument('--manifest', default=None)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(argv)

    rec = {'artifact': 'DELIVERED_INJURY_INGEST',
           'spec_version': DI.SPEC_VERSION, 'package': a.package,
           'season': a.season, 'week': a.week, 'delivered_by': a.delivered_by,
           'dry_run': bool(a.dry_run), 'ingested_at': DI._now_iso(),
           'steps': []}

    def step(name, ok, **ev):
        rec['steps'].append({'step': name, 'ok': bool(ok), **ev})
        print(('  ok   ' if ok else '  STOP ') + name +
              (f'  {ev.get("detail")}' if ev.get('detail') else ''))
        return ok

    def finish(code):
        rec['exit_code'] = code
        rec['terminal_state'] = ('DELIVERED_INJURY_INGEST_READY' if code == 0
                                 else 'DELIVERED_INJURY_INGEST_BLOCKED')
        if a.out:
            p = pathlib.Path(a.out)
            if not p.is_absolute():
                p = _REPO / a.out
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
            print(f'  ->   {p}')
        print(rec['terminal_state'])
        return code

    root = pathlib.Path(a.package)
    print(f'package {root}  season {a.season} week {a.week}')

    v = DI.verify_package(root)
    if not step('1. package verified against manifest and checksums',
                v.state is State.PASS, code=v.code,
                n_raw_verified=v.evidence.get('n_raw_verified'),
                n_checksums_verified=v.evidence.get('n_checksums_verified'),
                n_fetch_errors=v.evidence.get('n_fetch_errors'),
                detail=(f'{v.evidence.get("n_raw_verified")} raw + '
                        f'{v.evidence.get("n_checksums_verified")} checksums'
                        if v.state is State.PASS else v.detail[:160])):
        return finish(2)
    manifest = v.value['manifest']
    by_id = {e['source_id']: e for e in manifest}

    cand = _jl(root / 'status_candidates.jsonl')
    obs = _jl(root / 'status_observations.jsonl')
    stmts = _jl(root / 'team_status_statements.jsonl')
    recon = json.loads((root / 'reconciliation.json').read_text())
    rec['package_counts'] = {'candidates': len(cand), 'observations': len(obs),
                             'team_statements': len(stmts),
                             'manifest_entries': len(manifest)}
    if not step('1b. evidence sets present', bool(cand),
                detail=f'{len(cand)} candidates, {len(obs)} observations, '
                       f'{len(stmts)} team statements'):
        return finish(2)

    cited = sorted({c['source_id'] for c in cand})
    bad = []
    for s in cited:
        want = next((c['content_sha256'] for c in cand
                     if c['source_id'] == s), None)
        if by_id.get(s, {}).get('sha256') != want:
            bad.append(s)
    if not step('1c. every cited source hash matches the package manifest',
                not bad, cited=cited, mismatched=bad,
                detail=f'{len(cited)} cited source(s)'):
        return finish(2)

    raw_blobs, raw_ev = [], []
    for s in cited:
        e = by_id[s]
        raw = (root / e['raw_path']).read_bytes()
        if a.dry_run:
            raw_ev.append({'source_id': s, 'sha256': e['sha256'],
                           'n_bytes': len(raw), 'stored': False,
                           'dry_run': True})
            continue
        st = DI.store_raw(raw, source_id=s, vintage_root=a.vintage_root)
        if st.state is not State.PASS:
            step('2. raw bytes preserved before parse', False, code=st.code,
                 detail=st.detail[:160])
            return finish(2)
        bp = pathlib.Path(st.value)
        rel = (str(bp.relative_to(_REPO))
               if str(bp).startswith(str(_REPO)) else str(bp))
        raw_blobs.append(rel)
        raw_ev.append({'source_id': s, 'sha256': st.evidence['sha256'],
                       'n_bytes': st.evidence['n_bytes'], 'blob': rel,
                       'deduplicated': st.evidence['blob_already_present']})
    step('2. raw bytes preserved before parse', True, blobs=raw_ev,
         detail=f'{len(raw_ev)} document(s)')

    rcsv = a.roster_csv
    if rcsv is None:
        c2 = sorted((_REPO / 'nfl_vintage' / 'raw').glob('weekly_rosters.*.csv'))
        rcsv = str(c2[-1]) if c2 else None
    ri = DI.roster_index(rcsv, a.season, a.week) if rcsv else None
    if ri is None or ri.state is not State.PASS:
        step('3. roster identity vintage resolves', False, roster_csv=rcsv,
             detail=(ri.detail[:160] if ri else
                     'no raw weekly_rosters vintage on disk'))
        return finish(2)
    step('3. roster identity vintage resolves', True, roster_csv=str(rcsv),
         n_players=ri.evidence['n_players'], n_teams=ri.evidence['n_teams'],
         columns_read=ri.evidence['columns_read'],
         columns_refused=ri.evidence['columns_refused'],
         detail=f'{ri.evidence["n_players"]} players, '
                f'{ri.evidence["n_teams"]} clubs')
    roster = ri.value
    roster_teams = {x['team'] for x in roster.values()}

    rb = DI.rows_from_candidates(cand, roster, a.season, a.week)
    rec['row_build'] = {'code': rb.code, 'state': rb.state.value,
                        'detail': rb.detail[:400],
                        'evidence': {k: x for k, x in rb.evidence.items()}}
    if not step('4. delivered rows built', rb.state is State.PASS,
                code=rb.code, n_rows=rb.evidence.get('n_rows'),
                n_refused=rb.evidence.get('n_refused'),
                unmapped=rb.evidence.get('unmapped'),
                detail=(f'{rb.evidence.get("n_rows")} rows across '
                        f'{rb.evidence.get("n_teams")} clubs, '
                        f'{rb.evidence.get("n_refused")} refused'
                        if rb.state is State.PASS else rb.detail[:200])):
        return finish(2)
    rows = rb.value

    nd = DI.no_designation_records(stmts, roster_teams)
    step('5. explicit no-designation statements recorded', True,
         n_statements=nd.evidence['n_statements'], teams=nd.evidence['teams'],
         n_refused=nd.evidence['n_refused'],
         detail=f'{nd.evidence["n_statements"]} club(s): '
                f'{",".join(nd.evidence["teams"])} -- recorded as evidence, '
                f'NOT converted to rows and NOT clearing any gate')

    q = DI.quarantine_records(obs, cand, recon)
    step('6. quarantined evidence recorded, not adjudicated', True,
         n_quarantined=q.evidence['n_quarantined'], teams=q.evidence['teams'],
         detail=f'{q.evidence["n_quarantined"]} observation(s) held back')
    rec['quarantined'] = q.value

    csv_bytes = DI.to_csv_bytes(rows)
    sha = DI._sha256_bytes(csv_bytes)
    vroot = pathlib.Path(a.vintage_root) if a.vintage_root else DI.VINTAGE
    blob = vroot / f'injuries.{sha[:16]}.csv.gz'
    prim_id = sorted({c['source_id'] for c in cand})[0]
    prim_rows = [c for c in cand if c['source_id'] == prim_id]
    primary = {
        'source_id': prim_id,
        'source_url': prim_rows[0]['source_url'],
        'content_sha256': prim_rows[0]['content_sha256'],
        'retrieval_start': min(c['retrieval_start'] for c in prim_rows),
        'retrieved_at': max(c['retrieved_at'] for c in prim_rows),
        'publication_time': prim_rows[0]['publication_time'],
        'source_modified_time': prim_rows[0]['source_modified_time'],
        'effective_time': prim_rows[0]['effective_time'],
        'game_date': prim_rows[0]['game_date'],
        'http_status': by_id[prim_id].get('http_status'),
    }
    pkg_sha = DI._sha256_bytes(
        json.dumps(v.value['checksums'], sort_keys=True).encode())
    brel = (str(blob.relative_to(_REPO))
            if str(blob).startswith(str(_REPO)) else str(blob))
    row = DI.manifest_row(csv_bytes=csv_bytes, blob_rel=brel, rows=rows,
                          primary=primary, season=a.season,
                          delivered_by=a.delivered_by, package_sha256=pkg_sha,
                          raw_blobs=raw_blobs, no_designations=nd.value,
                          quarantined=q.value,
                          generated_at=rec['ingested_at'])
    rec['manifest_row'] = row
    pv = row['value']['provenance']
    rec['clocks'] = {k: pv.get(k) for k in
                     ('requested_at', 'retrieved_at', 'publication_time',
                      'source_timestamp', 'effective_time',
                      'effective_for_date', 'generated_at',
                      'cache_timestamp')}
    distinct = len({x for x in (pv['retrieved_at'], pv['publication_time'],
                                pv['source_timestamp'], pv['generated_at'])
                    if x})
    if not step('7a. the four populated clocks are distinct', distinct == 4,
                clocks=rec['clocks'], detail=f'{distinct} distinct'):
        return finish(2)

    if a.dry_run:
        step('7b. dry run: nothing written', True, would_write_blob=str(blob),
             would_append=str(a.manifest or DI.MANIFEST))
        rec['csv_sha256'] = sha
        return finish(0)

    vroot.mkdir(parents=True, exist_ok=True)
    existed = blob.exists()
    if not existed:
        tmp = blob.with_suffix(blob.suffix + '.tmp')
        with gzip.GzipFile(tmp, 'wb', mtime=0) as f:
            f.write(csv_bytes)
        tmp.replace(blob)
    back = gzip.open(blob, 'rt').read().encode()
    if not step('7b. injuries blob written and reads back identical',
                DI._sha256_bytes(back) == sha, blob=str(blob), sha256=sha,
                deduplicated=existed,
                detail=f'{len(csv_bytes)} bytes, sha {sha[:16]}'
                       + (' (already present, not rewritten)'
                          if existed else '')):
        return finish(2)

    apx = DI.append_manifest(row, manifest=a.manifest)
    step('7c. manifest row appended', apx.state is State.PASS,
         capture_id=row['capture_id'],
         detail=f'capture {row["capture_id"]} -> {apx.value}')
    rec['csv_sha256'] = sha
    rec['blob'] = str(blob)
    return finish(0)


if __name__ == '__main__':
    raise SystemExit(main())
