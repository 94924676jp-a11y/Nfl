#!/usr/bin/env python3.12
"""Full-field DK Showdown evidence archive: ingest, reconcile, and grade the sealed duplication shadow. SHADOW_ONLY.

    python3.12 nfl/field/showdown_field_archive.py ingest STANDINGS.zip --contest-id CID --slate TB_DAL \
        --contest-name "..." --source "DK contest standings export, owner download"
    python3.12 nfl/field/showdown_field_archive.py reconcile --contest-id CID --slate TB_DAL [--export DKEntries.csv]
    python3.12 nfl/field/showdown_field_archive.py grade --contest-id CID --slate TB_DAL --shadow DUPE_SHADOW_B4_X.json

Owner directive 2026-10-07: keep B4 / B3S running prelock as sealed shadow reports only, with the corrected
copy-count semantics, and keep accumulating complete-field evidence. This is the accumulation step; nothing here is
read by selection.

INGEST is immutable and content-addressed: the CSV is stored gzipped (mtime 0) as DK_STANDINGS.<sha16>.csv.gz under
nfl/postgame/raw/showdown_history/<cid>_<SLATE>/ with one PROVENANCE.jsonl record (sha256 of the uncompressed CSV).
An existing archive for the contest is never overwritten (ARCHIVE_EXISTS). A zip is read in memory; only .csv
members are considered and exactly one is required.

RECONCILE checks what the external audit (2026-10-07) asked for, and refuses by name rather than repairing:
  entries parse (CPT identity + an unordered set of five FLEX identities, six distinct players); CPT ownership sums to
  100% and FLEX to 500% when recomputed from the lineups; no per-slot share exceeds 100%; the recomputed shares agree
  with DK's own %Drafted block within the repository's 0.5 pp recount flag; with a DKEntries export, every lineup is
  under the $50,000 cap and uses both clubs. Counts: entries, empty entries, distinct lineups, the copy-count
  distribution (ALL copies per canonical lineup), and score ties among DISTINCT lineups (a tie is not a duplicate).

GRADE scores a sealed prelock shadow (nfl/field/showdown_dupe_shadow.py output) against the archive. Semantics, as
recorded in nfl/postgame/dupe_research/DUPE_COPY_COUNT_SEMANTICS.json: the shadow predicts N x q = expected ALL
copies of a lineup; for one of our entered lineups the expected OTHER copies are (N-1) x q. The grade reports, per
model, in unique-lineup units over our lineups: actual all copies, actual other copies (all copies minus our own
entries holding that lineup), predicted, and actual/predicted. It refuses a shadow that is not a PRELOCK record
(MODE != PRELOCK), whose seal does not verify, or that was written at or after kickoff.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys
import zipfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_history_calibration as HC  # noqa: E402

RAW = _REPO / 'nfl/postgame/raw/showdown_history'
CAP = 50000
RECOUNT_FLAG_PP = 0.5      # the repository's existing recount flag for %Drafted vs recomputed (CHEAP_OWNERSHIP_LOSO)


class ArchiveError(RuntimeError):
    pass


def need(ok, code, detail=''):
    if not ok:
        raise ArchiveError(f'{code} {detail}'.strip())


def _dir(cid, slate, root=RAW):
    return pathlib.Path(root) / f'{cid}_{slate}'


# ------------------------------------------------------------------------------------------------- ingest
def _csv_bytes(path):
    p = pathlib.Path(path)
    need(p.is_file() and p.stat().st_size > 0, 'INPUT_MISSING_OR_EMPTY', str(p))
    if p.suffix.lower() == '.zip':
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.lower().endswith('.csv') and not n.endswith('/')]
            need(len(names) == 1, 'ZIP_NEEDS_EXACTLY_ONE_CSV', str(names))
            return z.read(names[0]), {'zip_name': p.name, 'zip_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                                      'member': names[0]}
    return p.read_bytes(), {}


def ingest(path, cid, slate, contest_name, source, root=RAW, now=None):
    raw, zmeta = _csv_bytes(path)
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
    need(rows and rows[0] == HC.EXPECTED_HEADER, 'SCHEMA', str(rows[0] if rows else None))
    need(len(rows) > 1, 'STANDINGS_EMPTY')
    d = _dir(cid, slate, root)
    need(not (d / 'PROVENANCE.jsonl').exists(), 'ARCHIVE_EXISTS', str(d))
    d.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(raw).hexdigest()
    out = d / f'DK_STANDINGS.{h[:16]}.csv.gz'
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode='wb', mtime=0) as g:
        g.write(raw)
    out.write_bytes(buf.getvalue())
    rel = str(out.relative_to(_REPO)) if out.is_relative_to(_REPO) else str(out)
    rec = {'kind': 'DK_SHOWDOWN_STANDINGS', 'contest_id': str(cid), 'contest': contest_name, 'slate': slate,
           'file': rel, 'sha256': h, 'storage': 'gzip (mtime 0); sha256 is of the uncompressed CSV',
           'sha256_gz': hashlib.sha256(out.read_bytes()).hexdigest(), **zmeta, 'source': source,
           'captured_at': (now or dt.datetime.now(dt.timezone.utc)).isoformat(), 'IMMUTABLE': True,
           'NOT_A_FOOTBALL_INPUT': True}
    (d / 'PROVENANCE.jsonl').write_text(json.dumps(rec) + '\n')
    return d, rec


# ---------------------------------------------------------------------------------------------- load / parse
def load(cid, slate, root=RAW):
    d = _dir(cid, slate, root)
    recs = [json.loads(x) for x in (d / 'PROVENANCE.jsonl').read_text().splitlines() if x.strip()]
    need(len(recs) == 1 and recs[0]['contest_id'] == str(cid), 'PROVENANCE', str(d))
    rec = recs[0]
    f = pathlib.Path(rec['file'])
    f = f if f.is_absolute() else _REPO / f
    b = gzip.decompress(f.read_bytes())
    need(hashlib.sha256(b).hexdigest() == rec['sha256'], 'SHA256_MISMATCH', str(f))
    rows = list(csv.reader(io.StringIO(b.decode('utf-8-sig'))))
    need(rows and rows[0] == HC.EXPECTED_HEADER, 'SCHEMA', str(rows[0] if rows else None))
    entries, empty, slot = [], 0, {}
    for i, r in enumerate(rows[1:], start=2):
        need(len(r) in (9, 11), 'ROW_WIDTH', f'{cid} line {i}')
        if r[1].strip():
            if not r[5].strip():
                empty += 1
            else:
                c, fl = HC.parse_lineup(r[5].strip(), i)
                entries.append({'rank': int(r[0]), 'entry_id': r[1].strip(), 'user': r[2].rsplit(' (', 1)[0].strip(),
                                'points': float(r[4]), 'cpt': c, 'flex': fl})
        if len(r) == 11 and r[7].strip():
            slot[(r[7].strip(), r[8].strip())] = float(r[9].rstrip('%'))
    need(entries, 'NO_FILLED_ENTRIES', str(cid))
    need(slot, 'NO_DRAFTED_BLOCK', str(cid))
    return {'rec': rec, 'entries': entries, 'n_empty': empty, 'dk_pct': slot}


def _pool(export):
    from nfl.field import showdown_dupe_research as DR
    return DR._pool_meta(pathlib.Path(export))


# ------------------------------------------------------------------------------------------------ reconcile
def reconcile(cid, slate, export=None, root=RAW):
    S = load(cid, slate, root)
    E = S['entries']
    n = len(E)
    cpt = collections.Counter(e['cpt'] for e in E)
    flx = collections.Counter(x for e in E for x in e['flex'])
    cpt_pct = {p: 100.0 * v / n for p, v in cpt.items()}
    flx_pct = {p: 100.0 * v / n for p, v in flx.items()}
    problems = []
    if abs(sum(cpt_pct.values()) - 100.0) > 1e-6:
        problems.append(f'CPT_TOTAL {sum(cpt_pct.values()):.4f}')
    if abs(sum(flx_pct.values()) - 500.0) > 1e-6:
        problems.append(f'FLEX_TOTAL {sum(flx_pct.values()):.4f}')
    over = [p for p, v in list(cpt_pct.items()) + list(flx_pct.items()) if v > 100.0 + 1e-9]
    if over:
        problems.append(f'SLOT_SHARE_OVER_100 {over[:5]}')
    gaps = []
    for (name, pos), dk in S['dk_pct'].items():
        ours = cpt_pct.get(name, 0.0) if pos == 'CPT' else flx_pct.get(name, 0.0)
        if abs(ours - dk) > RECOUNT_FLAG_PP:
            gaps.append({'player': name, 'slot': pos, 'dk': dk, 'recomputed': round(ours, 3)})
    if gaps:
        problems.append(f'DRAFTED_RECOUNT_GAP {len(gaps)} > {RECOUNT_FLAG_PP} pp')
    legality = 'NOT_CHECKED_NO_EXPORT'
    if export:
        meta = _pool(export)
        bad = []
        for e in E:
            ps = [e['cpt'], *e['flex']]
            if any(p not in meta for p in ps):
                bad.append((e['entry_id'], 'PLAYER_NOT_IN_POOL'))
                continue
            sal = meta[e['cpt']]['cpt_salary'] + sum(meta[x]['flex_salary'] for x in e['flex'])
            teams = {meta[p]['team'] for p in ps}
            if sal > CAP:
                bad.append((e['entry_id'], f'OVER_CAP {sal}'))
            if len(teams) < 2:
                bad.append((e['entry_id'], 'ONE_CLUB'))
        legality = 'ALL_LEGAL' if not bad else f'{len(bad)} ILLEGAL'
        if bad:
            problems.append(f'ILLEGAL_LINEUPS {bad[:5]}')
    lines = collections.Counter((e['cpt'], e['flex']) for e in E)
    copies = collections.Counter(lines.values())
    pts = collections.defaultdict(set)
    for e in E:
        pts[round(e['points'], 2)].add((e['cpt'], e['flex']))
    ties = sum(1 for s in pts.values() if len(s) > 1)
    return {'ARTIFACT': 'SHOWDOWN_FIELD_RECONCILIATION', 'contest_id': str(cid), 'slate': slate,
            'standings_sha256': S['rec']['sha256'], 'VERDICT': 'RECONCILED' if not problems else 'NOT_RECONCILED',
            'problems': problems, 'drafted_gaps': gaps[:40],
            'counts': {'entries_filled': n, 'entries_empty': S['n_empty'], 'distinct_lineups': len(lines),
                       'copy_count_distribution_ALL_copies': {str(k): v for k, v in sorted(copies.items())},
                       'entries_in_duplicated_lineups': sum(v for v in lines.values() if v > 1),
                       'score_ties_among_distinct_lineups': ties},
            'legality': legality,
            'SEMANTICS': 'a lineup = CPT identity + unordered set of five FLEX identities; copies are ALL entries holding '
                         'it; a score tie between distinct lineups is not a duplicate'}


# ---------------------------------------------------------------------------------------------------- grade
def _verify_seal(doc):
    body = {k: v for k, v in doc.items() if k != 'seal_sha256'}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest() == doc.get('seal_sha256')


def grade(cid, slate, shadow_path, root=RAW, allow_dry_run=False):
    doc = json.loads(pathlib.Path(shadow_path).read_text())
    need(doc.get('ARTIFACT') == 'SHOWDOWN_DUPE_SHADOW_COMPARISON', 'NOT_A_DUPE_SHADOW', str(shadow_path))
    need(_verify_seal(doc), 'SEAL_DOES_NOT_VERIFY', str(shadow_path))
    if doc.get('MODE') != 'PRELOCK':
        need(allow_dry_run, 'NOT_A_PRELOCK_RECORD', f"MODE {doc.get('MODE')} (a dry run is never graded as evidence)")
    else:
        need(dt.datetime.fromisoformat(doc['written_at']) < dt.datetime.fromisoformat(doc['kickoff']),
             'SEAL_WRITTEN_AT_OR_AFTER_KICKOFF', f"{doc['written_at']} vs {doc['kickoff']}")
    S = load(cid, slate, root)
    lines = collections.Counter((e['cpt'], e['flex']) for e in S['entries'])
    ours = [r for r in doc['lineups'] if r['contest_id'] == str(cid)]
    need(ours, 'NO_SHADOW_LINEUPS_FOR_CONTEST', str(cid))
    own_ids = {r.get('entry_id') for r in ours if r.get('entry_id')}
    own_count = collections.Counter((e['cpt'], e['flex']) for e in S['entries'] if e['entry_id'] in own_ids)
    seen, rows = set(), []
    for r in ours:
        key = (r['captain'], tuple(sorted(r['flex'])))
        if key in seen:
            continue                                   # unique-lineup units
        seen.add(key)
        allc = lines.get(key, 0)
        mine = own_count.get(key, 0)
        if own_ids and mine == 0:
            raise ArchiveError(f'OWN_ENTRY_NOT_IN_STANDINGS {r.get("entry_id")} {key}')
        pred = {m: (v.get('copies') if isinstance(v, dict) else None) for m, v in r['models'].items()}
        rows.append({'lineup': key, 'actual_all_copies': allc, 'own_entries': mine,
                     'actual_other_copies': allc - mine, 'pred_all_copies': pred,
                     'E1_all_copies': r['legacy'].get('E1_independent_copies')})
    models = sorted({m for x in rows for m, v in x['pred_all_copies'].items() if v is not None})
    summ = {}
    for m in models + ['E1']:
        if m == 'E1':
            p = [x['E1_all_copies'] for x in rows]
        else:
            p = [x['pred_all_copies'].get(m) for x in rows]
        ok = [i for i, v in enumerate(p) if v is not None]
        P = sum(p[i] for i in ok)
        A_all = sum(rows[i]['actual_all_copies'] for i in ok)
        A_oth = sum(rows[i]['actual_other_copies'] for i in ok)
        n_own = sum(rows[i]['own_entries'] for i in ok)
        summ[m] = {'n_lineups': len(ok), 'pred_all_copies': round(P, 2), 'actual_all_copies': A_all,
                   'actual_other_copies': A_oth, 'all_over_pred': round(A_all / P, 4) if P > 0 else None,
                   'own_entries': n_own, 'other_over_pred': round(A_oth / P, 4) if P > 0 else None}
    return {'ARTIFACT': 'SHOWDOWN_DUPE_SHADOW_GRADE', 'STATUS': 'SHADOW_ONLY -- EVIDENCE ACCUMULATION, NOT A PROMOTION',
            'contest_id': str(cid), 'slate': slate, 'shadow': str(shadow_path), 'shadow_seal': doc['seal_sha256'],
            'shadow_mode': doc.get('MODE'), 'standings_sha256': S['rec']['sha256'],
            'UNITS': 'unique-lineup units over our lineups', 'summary': summ, 'lineups': rows,
            'SEMANTICS': 'pred = N x q = expected ALL copies; other copies = all copies minus our own entries holding the '
                         'lineup; for one entered lineup the expected other copies are (N-1) x q (difference q, negligible)'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('ingest', 'reconcile', 'grade'))
    ap.add_argument('path', nargs='?')
    ap.add_argument('--contest-id', required=True)
    ap.add_argument('--slate', required=True)
    ap.add_argument('--contest-name')
    ap.add_argument('--source')
    ap.add_argument('--export')
    ap.add_argument('--shadow')
    a = ap.parse_args()
    try:
        if a.cmd == 'ingest':
            need(a.path and a.contest_name and a.source, 'INGEST_NEEDS', 'path, --contest-name, --source')
            d, rec = ingest(a.path, a.contest_id, a.slate, a.contest_name, a.source)
            print(d, rec['sha256'])
        elif a.cmd == 'reconcile':
            r = reconcile(a.contest_id, a.slate, a.export)
            out = _dir(a.contest_id, a.slate) / 'RECONCILIATION.json'
            out.write_text(json.dumps(r, indent=1))
            print(out, r['VERDICT'], r['problems'])
        else:
            need(a.shadow, 'GRADE_NEEDS_SHADOW')
            g = grade(a.contest_id, a.slate, a.shadow)
            out = _dir(a.contest_id, a.slate) / f'DUPE_SHADOW_GRADE.{g["shadow_seal"][:12]}.json'
            need(not out.exists(), 'GRADE_EXISTS', str(out))
            out.write_text(json.dumps(g, indent=1, default=str))
            print(out, json.dumps(g['summary']))
    except ArchiveError as e:
        print(f'REFUSED[{str(e).split()[0]}] {e}')
        sys.exit(3)
