#!/usr/bin/env python3.12
"""Independent check of an upload-format lineup file against DraftKings' own pool and the owner's entries.

    python3.12 nfl/tools/classic_upload_verify.py 2026W4

WHY IT IS SEPARATE FROM THE OPTIMISER. classic_portfolio verifies each lineup against the metadata
it built itself, so a defect in that metadata would pass its own check. This reads only the upload
CSV, the DK pool and entries from the hash-verified owner export, and the slate state's reported-OUT
list, and re-derives every rule from those. It shares no code with the optimiser's verifier.

CHECKS
  header       exactly Entry ID, Contest Name, Contest ID, Entry Fee, QB, RB, RB, WR, WR, WR, TE, FLEX, DST
  entry map    the file's Entry IDs are the owner's Entry IDs, each exactly once, each under its own
               contest id, contest name and fee as the owner's export records them
  slots        every id is in the DK pool; QB/RB/WR/TE/DST slots hold that DK position; FLEX holds a
               player DK marks FLEX-eligible
  lineup       9 distinct players, DK salary <= 50000, players from at least 2 games, nobody reported OUT
  portfolio    distinct lineups per contest, and how many lineups of each smaller contest also appear
               in a larger one (the 20-max set must not be the 150-max set's top 20)

It modifies nothing and submits nothing.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import early_only as EO  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
HEADER = ['Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee',
          'QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST']
SLOT_POS = {'QB': {'QB'}, 'RB': {'RB'}, 'WR': {'WR'}, 'TE': {'TE'}, 'DST': {'DST'}}
CAP = 50000
OUT_STATES = AV.ABSENT_STATUSES   # every absence, including relayed and unverified ones
#: slates finalized before the roster-eligibility gate existed (2026-10-08); reported NOT_CHECKED, never PASS
LEGACY_PRE_ROSTER_GATE = frozenset({'2026W2', '2026W3', '2026W4'})


def _plain(f):
    """The owner's entries export decompressed to a sibling temp file the eligibility gate can read as CSV."""
    import gzip
    import tempfile
    raw = gzip.decompress(pathlib.Path(f['entries_blob']).read_bytes())
    tmp = pathlib.Path(tempfile.mkdtemp()) / 'entries.csv'
    tmp.write_bytes(raw)
    return tmp


def verify(rows, pool, entries, out_ids) -> Outcome:
    """rows: the upload CSV as lists of strings, header first. Returns a measured result or a FAIL."""
    if not rows:
        return Outcome.blocked('UPLOAD_VERIFY_EMPTY_INPUT', 'the upload file has no rows',
                               cause=Cause.EMPTY_INPUT)
    v = []
    if rows[0] != HEADER:
        v.append(f'header {rows[0]!r} is not the DK upload header')
    body = rows[1:]
    if not body:
        return Outcome.blocked('UPLOAD_VERIFY_EMPTY_INPUT', 'the upload file has a header and no lineups',
                               cause=Cause.EMPTY_INPUT)
    by_id = {p['dk_id']: p for p in pool}
    own = {e['entry_id']: e for e in entries}
    seen = collections.Counter(r[0] for r in body)
    for eid, k in seen.items():
        if k > 1:
            v.append(f'entry {eid} appears {k} times')
        if eid not in own:
            v.append(f'entry {eid} is not one of the owner\'s entries')
    for eid in own:
        if eid not in seen:
            v.append(f'owner entry {eid} has no lineup')
    lineups = collections.defaultdict(list)
    for r in body:
        if len(r) != len(HEADER):
            v.append(f'row for {r[:1]} has {len(r)} columns')
            continue
        eid, cname, cid, fee, ids = r[0], r[1], r[2], r[3], r[4:]
        e = own.get(eid)
        if e and (cname, cid, fee) != (e['contest_name'], e['contest_id'], e['entry_fee']):
            v.append(f'entry {eid} filed under {cid}/{cname}/{fee}, the owner export says '
                     f'{e["contest_id"]}/{e["contest_name"]}/{e["entry_fee"]}')
        ps = []
        for slot, d in zip(HEADER[4:], ids):
            p = by_id.get(d)
            if p is None:
                v.append(f'entry {eid}: id {d} in slot {slot} is not in the DK pool')
                continue
            ok = p['flex_eligible'] and p['dk_pos'] in ('RB', 'WR', 'TE') if slot == 'FLEX' \
                else p['dk_pos'] in SLOT_POS[slot]
            if not ok:
                v.append(f'entry {eid}: {p["dk_name"]} ({p["dk_pos"]}) cannot fill {slot}')
            ps.append(p)
        if len(set(ids)) != 9:
            v.append(f'entry {eid}: a player appears twice')
        if len(ps) == 9:
            sal = sum(p['salary'] for p in ps)
            if sal > CAP:
                v.append(f'entry {eid}: DK salary {sal} over {CAP}')
            if len({p['game_info'].split(' ')[0] for p in ps}) < 2:
                v.append(f'entry {eid}: players from fewer than 2 games')
        for d in ids:
            if d in out_ids:
                v.append(f'entry {eid}: {by_id.get(d, {}).get("dk_name", d)} is reported OUT')
        lineups[cid].append(frozenset(ids))
    per = {cid: {'n': len(l), 'n_distinct': len(set(l))} for cid, l in lineups.items()}
    for cid, l in lineups.items():
        if len(set(l)) != len(l):
            v.append(f'contest {cid}: {len(l) - len(set(l))} duplicate lineup(s)')
    order = sorted(lineups, key=lambda c: -len(lineups[c]))
    overlap = {}
    for i, small in enumerate(order):
        for big in order[:i]:
            shared = len(set(lineups[small]) & set(lineups[big]))
            overlap[f'{small}_in_{big}'] = {'shared_lineups': shared, 'of': len(set(lineups[small]))}
    ev = {'per_contest': per, 'cross_contest_identical_lineups': overlap, 'violations': v}
    if v:
        return Outcome.fail('UPLOAD_VERIFY_VIOLATIONS', f'{len(v)} violation(s); first: {v[0]}', **ev)
    return Outcome.measured('UPLOAD_VERIFIED', {'n_lineups': len(body)}, n_measured=len(body),
                            what='upload rows verified against the DK pool and the owner entries',
                            detail=f'{len(body)} rows, {len(own)} owner entries, 0 violations', **ev)


def run(slate_id: str) -> Outcome:
    f = EO.slate_files(slate_id)
    po, eo = EO.pool(f['entries_blob'], f['entries_sha']), EO.entries(f['entries_blob'], f['entries_sha'])
    for o in (po, eo):
        if o.state.value != 'PASS':
            return o
    up = OUT_DIR / f'DK_{slate_id}_EARLY_UPLOAD.csv'
    if not up.exists():
        return Outcome.blocked('UPLOAD_VERIFY_NO_FILE', f'{up.name} does not exist (no full legal portfolio was built)',
                               cause=Cause.NOT_EXECUTED)
    state = json.loads((OUT_DIR / f'DK_{slate_id}_EARLY_STATE.json').read_text())
    out_ids = {v.get('dk_id') or k for k, v in state['players'].items()
               if v['current_availability']['status'] in OUT_STATES}
    rows = list(csv.reader(up.read_text().splitlines()))
    o = verify(rows, po.value, eo.value, out_ids)
    # ROSTER ELIGIBILITY (TB@DAL 2026-10-08, found absent from the Classic path 2026-10-09): every uploaded player needs
    # positive roster evidence (ACT, or DEV with an elevation record). A slate from 2026W5 on must declare its roster
    # capture or the verify fails closed; 2026W2-W4 predate the gate and are recorded as unchecked, never as PASS.
    from nfl.tools import showdown_run_guards as G
    if f.get('roster_capture'):
        _ld = lambda k, d: json.loads((_REPO / f[k]).read_text()) if f.get(k) else d  # noqa: E731
        rb, rrep = G.upload_roster_eligibility(up, f['entries_blob_plain'] if f.get('entries_blob_plain') else _plain(f),
                                               _REPO / f['roster_capture'], int(slate_id[:4]), int(slate_id.split('W')[1]),
                                               _ld('official_inactives', []), _ld('transactions', {}), _ld('elevations', []))
    elif slate_id in LEGACY_PRE_ROSTER_GATE:
        rb, rrep = [], {'status': 'NOT_CHECKED_LEGACY_SLATE', 'reason': 'slate predates the roster-eligibility gate'}
    else:
        rb, rrep = ['ROSTER_ELIGIBILITY_UNVERIFIED (slate declares no roster_capture)'], {'status': 'UNVERIFIED'}
    if rb and o.state.value == 'PASS':
        o = Outcome.fail('UPLOAD_VERIFY_ROSTER_ELIGIBILITY', '; '.join(rb), cause=Cause.DATA, **(o.evidence or {}))
    doc = {'ARTIFACT': 'CLASSIC_UPLOAD_VERIFY', 'slate_id': slate_id,
           'upload_sha256': hashlib.sha256(up.read_bytes()).hexdigest(),
           'entries_sha256': f['entries_sha'], 'state': o.state.value, 'code': o.code, 'detail': o.detail,
           **{k: (o.evidence or {}).get(k) for k in ('per_contest', 'cross_contest_identical_lineups',
                                                      'violations')}, 'roster_eligibility': rrep}
    (OUT_DIR / f'DK_{slate_id}_EARLY_UPLOAD_VERIFY.json').write_text(json.dumps(doc, indent=1))
    return o


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = run(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    print(json.dumps({k: (o.evidence or {}).get(k) for k in ('per_contest', 'cross_contest_identical_lineups')},
                     indent=1))
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
