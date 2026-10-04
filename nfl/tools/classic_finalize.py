#!/usr/bin/env python3.12
"""Promote a post-news run to the FINAL_*_POST_INACTIVES files, or refuse and say why.

    python3.12 nfl/tools/classic_finalize.py 2026W4

Owner directive 2026-10-04 (pre-lock staging): the destinations

    DK_<slate>_EARLY_FINAL_150_MAX_POST_INACTIVES.csv
    DK_<slate>_EARLY_FINAL_20_MAX_POST_INACTIVES.csv
    DK_<slate>_EARLY_FINAL_3_ENTRY_POST_INACTIVES.csv
    DK_<slate>_EARLY_FINAL_DK_UPLOAD_POST_INACTIVES.csv

are populated ONLY when every gate below reads PASS against the artifacts on disk -- this tool trusts
no ledger, it re-reads each artifact and its hashes:

  EVIDENCE        state.official_inactives.STATE is APPLIED (official capture) or APPLIED_OWNER_RELAYED.
                  REHEARSAL_NOT_EVIDENCE, AWAITING_*, and a bare name list never finalize.
  CHAIN           the portfolio was built from the current state/projection/draws (hashes), the seal
                  covers the current projection and worlds, the verifier passed on the current upload.
  AUDIT           accounting PASS and reproducibility PASS on the current inputs, written after the portfolio.
  PRELOCK         NO_RERUN_REQUIRED, checked after the state was built.
  FILLED          each contest holds exactly its entry count.

Otherwise DK_<slate>_EARLY_FINAL_MANIFEST.json says NOT_POPULATED with every failed gate, and any FINAL
file from an earlier run is moved out of the way (into runs/<slate>/superseded_<utc>/) so a stale FINAL
can never sit next to a newer, unfinalized portfolio. The FINAL files are never DraftKings-submitted by
this repository; uploading is the owner's act.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

OUT_DIR = _REPO / 'nfl/dfs/salaries'
FINAL_EVIDENCE_STATES = {'APPLIED': 'FINAL_POST_INACTIVES_OFFICIAL_CAPTURED',
                         'APPLIED_OWNER_RELAYED': 'FINAL_POST_INACTIVES_OWNER_RELAYED_NOT_OFFICIAL'}
PROFILE_FILE = {'MAX150': 'FINAL_150_MAX_POST_INACTIVES.csv', 'MAX20': 'FINAL_20_MAX_POST_INACTIVES.csv',
                'MAX3': 'FINAL_3_ENTRY_POST_INACTIVES.csv'}
UPLOAD_FILE = 'FINAL_DK_UPLOAD_POST_INACTIVES.csv'
#: OWNER SCOPE (2026-10-04): the 8 Early Only 1:00 PM ET games, (away, home). Nothing else may appear in
#: the pool, a lineup, an exposure/stack/game table, the upload, or the Hard Rock board.
EARLY_ONLY_GAMES = {'2026W4': frozenset({('ARI', 'NYG'), ('NE', 'BUF'), ('NYJ', 'CHI'), ('DAL', 'HOU'),
                                         ('LA', 'PHI'), ('GB', 'TB'), ('TEN', 'BAL'), ('JAX', 'CIN')})}
EARLY_ONLY_KICKOFF = '01:00PM ET'
UPLOAD_SLOTS = ('QB', 'RB', 'WR', 'TE', 'FLEX', 'DST')


def scope_gate(slate, st, port, out_dir):
    """Every player and every table inside the owner's 8 Early Only games, or a named refusal."""
    want = EARLY_ONLY_GAMES.get(slate)
    if want is None:
        return {'ok': False, 'why': f'no declared Early Only scope for {slate}'}
    games = {gid: (g['away'], g['home']) for gid, g in (st.get('games') or {}).items()}
    bad = []
    if set(games.values()) != set(want):
        bad.append(f'state games {sorted(games.values())} != the 8 Early Only games')
    if EARLY_ONLY_KICKOFF not in str(st.get('kickoff', '')):
        bad.append(f"kickoff {st.get('kickoff')!r} is not the 1:00 PM ET window")
    clubs = {c for pr in want for c in pr}
    ids = set(games)
    off_pool = [p['name'] for p in st['players'].values() if p.get('game_id') not in ids or p['team'] not in clubs]
    if off_pool:
        bad.append(f'{len(off_pool)} pool players outside the 8 games: {off_pool[:5]}')
    for c in port.get('contests', []):
        for lu in c['lineups']:
            for sl in lu['slots']:
                p = st['players'].get(sl['dk_id'])
                if p is None or p.get('game_id') not in ids:
                    bad.append(f"{c['profile']} entry {lu.get('entry_id')}: {sl.get('name')} ({sl['dk_id']}) is not in an Early Only game")
        r = c.get('report') or {}
        extra = sorted(set(r.get('game_exposure') or {}) - ids)
        if extra:
            bad.append(f"{c['profile']} game exposure lists {extra}")
        stray = [e.get('dk_id') for e in (r.get('player_exposure') or {}).values() if e.get('dk_id') not in st['players']]
        if stray:
            bad.append(f"{c['profile']} exposure table holds {len(stray)} players outside the pool")
    up = out_dir / f'DK_{slate}_EARLY_UPLOAD.csv'
    if up.exists():
        rows = list(csv.reader(up.open()))
        hdr = rows[0]
        cols = [i for i, h in enumerate(hdr) if h in UPLOAD_SLOTS]
        for r in rows[1:]:
            for i in cols:
                p = st['players'].get(r[i])
                if p is None or p.get('game_id') not in ids:
                    bad.append(f'upload entry {r[0]}: player id {r[i]} is not in an Early Only game')
    for name in ('HARD_ROCK_SLOTS.json', 'PROP_DIAGNOSTIC.json'):
        d = _j(out_dir / f'DK_{slate}_EARLY_{name}') or {}
        t = sorted({x.get('team') for x in d.get('rows', []) if x.get('team') and x.get('team') not in clubs})
        if t:
            bad.append(f'{name} has rows for clubs outside the 8 games: {t}')
    return {'ok': not bad, 'games': sorted(games), 'violations': bad[:20], 'n_violations': len(bad)}


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _j(p):
    return json.loads(p.read_text()) if p.exists() else None


def gates(slate, out_dir=OUT_DIR):
    f = lambda n: out_dir / f'DK_{slate}_EARLY_{n}'  # noqa: E731
    st, port, seal = _j(f('STATE.json')), _j(f('PORTFOLIOS.json')), _j(f('SEAL.json'))
    ver, aud, pre = _j(f('UPLOAD_VERIFY.json')), _j(f('AUDIT.json')), _j(f('PRELOCK.json'))
    g = {}
    missing = [n for n, v in (('STATE', st), ('PORTFOLIOS', port), ('SEAL', seal), ('UPLOAD_VERIFY', ver),
                              ('AUDIT', aud), ('PRELOCK', pre)) if v is None] + \
              [n for n in ('UPLOAD.csv', 'PROJ.json', 'WORLDS.npz') if not f(n).exists()]
    if missing:
        return {'ARTIFACTS_PRESENT': {'ok': False, 'why': f'missing {missing}'}}, st, port
    oi = (st.get('official_inactives') or {}).get('STATE')
    g['EVIDENCE'] = {'ok': oi in FINAL_EVIDENCE_STATES, 'state': oi,
                     'packet_id': (st.get('official_inactives') or {}).get('packet_id')}
    g['SCOPE_EARLY_ONLY_1PM'] = scope_gate(slate, st, port, out_dir)
    clubs = sorted({c for g in (st.get('games') or {}).values() for c in (g['away'], g['home'])})
    have = set((st.get('official_inactives') or {}).get('clubs_with_full_list') or ())
    g['EVERY_CLUB_HAS_ITS_INACTIVE_LIST'] = {'ok': bool(clubs) and set(clubs) <= have,
                                             'missing': sorted(set(clubs) - have)}
    stale = [k for k, p in (port.get('inputs') or {}).items()
             if not (_REPO / p).exists() or _sha(_REPO / p) != (port.get('inputs_sha256') or {}).get(k)]
    g['PORTFOLIO_ON_CURRENT_INPUTS'] = {'ok': not stale and bool(port.get('inputs')), 'stale': stale}
    g['SEAL_COVERS_CURRENT_FORECAST'] = {'ok': seal.get('projection_sha256') == _sha(f('PROJ.json'))
                                         and seal.get('worlds_sha256') == _sha(f('WORLDS.npz'))}
    g['UPLOAD_VERIFIED'] = {'ok': ver.get('state') == 'PASS' and ver.get('upload_sha256') == _sha(f('UPLOAD.csv')),
                            'verdict': f"{ver.get('state')}[{ver.get('code')}]"}
    g['AUDIT'] = {'ok': (aud.get('accounting') or {}).get('state') == 'PASS'
                  and (aud.get('reproducibility') or {}).get('state') == 'PASS'
                  and str(aud.get('built_at_utc', '')) >= str(port.get('built_at_utc', '~')),
                  'accounting': (aud.get('accounting') or {}).get('state'),
                  'reproducibility': (aud.get('reproducibility') or {}).get('state')}
    g['PRELOCK'] = {'ok': pre.get('state') == 'PASS' and pre.get('code') == 'NO_RERUN_REQUIRED'
                    and str(pre.get('checked_at_utc', '')) >= str(st.get('built_at_utc', '~')),
                    'verdict': f"{pre.get('state')}[{pre.get('code')}]"}
    g['FILLED'] = {'ok': all(c['FILLED'] and len(c['lineups']) == c['n_entries'] for c in port['contests'])
                   and {c['profile'] for c in port['contests']} == set(PROFILE_FILE),
                   'per_contest': {c['profile']: f"{len(c['lineups'])}/{c['n_entries']}" for c in port['contests']}}
    return g, st, port


def _supersede(slate, out_dir):
    old = [p for p in [out_dir / f'DK_{slate}_EARLY_{n}' for n in (*PROFILE_FILE.values(), UPLOAD_FILE)] if p.exists()]
    if not old:
        return []
    d = out_dir / 'runs' / slate / ('superseded_' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    d.mkdir(parents=True, exist_ok=True)
    for p in old:
        shutil.move(str(p), d / p.name)
    return [str(d / p.name) for p in old]


def finalize(slate, out_dir=OUT_DIR) -> Outcome:
    g, st, port = gates(slate, out_dir)
    failed = sorted(k for k, v in g.items() if not v['ok'])
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    man = {'ARTIFACT': 'CLASSIC_FINAL_MANIFEST', 'slate_id': slate, 'checked_at_utc': now, 'gates': g,
           'NOT_SUBMITTED': 'this repository never uploads to DraftKings; the owner does'}
    if failed:
        man.update({'STATE': 'NOT_POPULATED', 'failed_gates': failed, 'moved_aside': _supersede(slate, out_dir)})
        (out_dir / f'DK_{slate}_EARLY_FINAL_MANIFEST.json').write_text(json.dumps(man, indent=1, default=str))
        return Outcome.blocked('FINAL_NOT_POPULATED', f'{len(failed)} gate(s) not passed: {", ".join(failed)}',
                               cause=Cause.DATA, failed=failed)
    raw = (out_dir / f'DK_{slate}_EARLY_UPLOAD.csv').read_bytes()   # the VERIFIED bytes, never re-encoded
    eol = '\r\n' if b'\r\n' in raw else '\n'
    up = raw.decode('utf-8')
    rows = list(csv.reader(io.StringIO(up, newline='')))
    head, body = rows[0], rows[1:]
    cid = head.index('Contest ID')
    files = {}
    for c in port['contests']:
        keep = [r for r in body if r[cid] == str(c['contest_id'])]
        if len(keep) != c['n_entries']:
            return Outcome.fail('FINAL_UPLOAD_CONTEST_COUNT', f"{c['profile']}: {len(keep)} upload rows for {c['n_entries']} entries")
        buf = io.StringIO()
        csv.writer(buf, lineterminator=eol).writerows([head, *keep])
        files[PROFILE_FILE[c['profile']]] = buf.getvalue()
    files[UPLOAD_FILE] = up
    for n, txt in files.items():
        (out_dir / f'DK_{slate}_EARLY_{n}').write_bytes(raw if n == UPLOAD_FILE else txt.encode('utf-8'))
    man.update({'STATE': FINAL_EVIDENCE_STATES[g['EVIDENCE']['state']],
                'evidence': {k: (st.get('official_inactives') or {}).get(k)
                             for k in ('STATE', 'packet_id', 'packet_sha256', 'source', 'received_at', 'starters')},
                'files': {n: _sha(out_dir / f'DK_{slate}_EARLY_{n}') for n in files},
                'upload_sha256': _sha(out_dir / f'DK_{slate}_EARLY_UPLOAD.csv')})
    (out_dir / f'DK_{slate}_EARLY_FINAL_MANIFEST.json').write_text(json.dumps(man, indent=1, default=str))
    return Outcome.ok('FINAL_POPULATED', man['files'], f"{man['STATE']}: {len(files)} files")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    o = finalize(ap.parse_args().slate_id)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
