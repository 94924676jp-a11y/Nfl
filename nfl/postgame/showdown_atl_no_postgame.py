#!/usr/bin/env python3.12
"""ATL@NO DraftKings Showdown (2026-10-05) -- immutable POSTGAME_ACTUAL truth package.

    python3.12 nfl/postgame/showdown_atl_no_postgame.py PBP_GZ ENTRY_HISTORY_CSV

Layers kept apart (owner directive 2026-10-06): PRELOCK_FORECAST and PRELOCK_PORTFOLIO are the sealed artifacts in
nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX (and the prop seal); this module writes only POSTGAME_ACTUAL
under nfl/postgame/showdown_atl_no_2026W4/. It reads prelock artifacts, never writes them, and nothing here is an
input to any forecast.

ACTUALS come from nflverse play-by-play for game 2026_04_ATL_NO and are scored with the SAME DK scorer the projection
used (nfl.product.dk_scoring), so a forecast error is football, not two formulas disagreeing. The reconciliation is the
test: every owner entry's lineup (from the sealed upload, joined by Entry ID) is rescored from these actuals and must
equal the DK-reported points for that Entry ID. It also settles the missed-field-goal rule empirically.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.product import dk_scoring as DKS  # noqa: E402

GAME = '2026_04_ATL_NO'
SD = _REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX'
UPLOAD = SD / 'SHOWDOWN_ATL_NO_DK_UPLOAD.csv'
UPLOAD_SHA = '8f4d9a77f37957ab44b116ebc35a950a601fb2a2d39f1d8823f7fd847c6931d5'
OUT = _REPO / 'nfl/postgame/showdown_atl_no_2026W4'
RAW = _REPO / 'nfl/postgame/raw/showdown_atl_no_2026W4'
CONTESTS = ('196285137', '196285160', '196285161')


class PostgameError(RuntimeError):
    pass


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def preserve(pbp_gz, history_csv):
    RAW.mkdir(parents=True, exist_ok=True)
    rec = []
    for src, kind in ((pbp_gz, 'NFLVERSE_PBP_2026'), (history_csv, 'DK_CONTEST_ENTRY_HISTORY_OWNER')):
        h = _sha(src)
        dst = RAW / f'{kind}.{h[:16]}{"".join(pathlib.Path(src).suffixes)}'
        if not dst.exists():
            shutil.copy2(src, dst)
            dst.chmod(0o444)
        rec.append({'kind': kind, 'file': str(dst.relative_to(_REPO)), 'sha256': h})
    if _sha(UPLOAD) != UPLOAD_SHA:
        raise PostgameError('FINAL_UPLOAD_HASH_CHANGED')
    rec.append({'kind': 'FINAL_UPLOAD_PRELOCK_PORTFOLIO', 'file': str(UPLOAD.relative_to(_REPO)), 'sha256': UPLOAD_SHA})
    (RAW / 'PROVENANCE.json').write_text(json.dumps({'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                                                     'files': rec, 'IMMUTABLE': True}, indent=1))
    return rec


def actuals(pbp_gz, state):
    """Delegates to the slate-generic scorer (nfl.postgame.showdown_postgame.actuals), which is this module's former
    body parametrised by game. Byte parity on this game is a test (test_showdown_postgame)."""
    from nfl.postgame import showdown_postgame as SP
    try:
        return SP.actuals(pbp_gz, state, GAME)
    except SP.PostgameError as e:
        raise PostgameError(str(e)) from e


def reconcile(act, state, history_csv):
    by_id = {}
    for v in state['players'].values():
        key = f"{v['name']}|{v['team']}"
        by_id[str(v['cpt_dk_id'])] = (key, 1.5)
        by_id[str(v['flex_dk_id'])] = (key, 1.0)
    hist = {r['Entry_Key']: r for r in csv.DictReader(open(history_csv, encoding='utf-8-sig')) if r['Contest_Key'] in CONTESTS}
    up = list(csv.reader(open(UPLOAD)))
    rows, mism = [], collections.Counter()
    for r in up[1:]:
        eid, cid = r[0], r[2]
        slots = [by_id[x] for x in r[4:10]]
        h = hist.get(eid)
        if h is None:
            raise PostgameError(f'ENTRY_NOT_IN_HISTORY {eid}')
        for rule in ('A', 'B'):
            pts = round(sum(m * act['players'][k][f'dk_{rule}'] for k, m in slots), 2)
            ok = abs(pts - float(h['Points'])) < 0.011
            mism[(rule, ok)] += 1
        ptsA = round(sum(m * act['players'][k]['dk_A'] for k, m in slots), 2)
        ptsB = round(sum(m * act['players'][k]['dk_B'] for k, m in slots), 2)
        win = float(h['Winnings_Non_Ticket'].replace('$', '').replace(',', '') or 0)
        rows.append({'entry_id': eid, 'contest_id': cid, 'captain': slots[0][0], 'flex': [k for k, _ in slots[1:]],
                     'dk_points': float(h['Points']), 'recomputed_rule_A': ptsA, 'recomputed_rule_B': ptsB,
                     'place': int(h['Place']), 'field': int(h['Contest_Entries']),
                     'fee': float(h['Entry_Fee'].replace('$', '')), 'winnings': win,
                     'winnings_ticket': h['Winnings_Ticket'], 'places_paid': int(h['Places_Paid'])})
    return rows, {f'rule_{a}_{"match" if b else "mismatch"}': n for (a, b), n in mism.items()}


def run(pbp_gz, history_csv):
    OUT.mkdir(parents=True, exist_ok=True)
    prov = preserve(pbp_gz, history_csv)
    state = json.loads(next(SD.glob('SHOWDOWN_*_STATE.json')).read_text())
    act = actuals(pbp_gz, state)
    rows, rec = reconcile(act, state, history_csv)
    doc = {'ARTIFACT': 'ATL_NO_POSTGAME_ACTUAL', 'LAYER': 'POSTGAME_ACTUAL', 'game': GAME, 'provenance': prov,
           'final_score': act['final'], 'n_plays': act['n_plays'], 'dst_components': act['dst'],
           'player_actuals': act['players'], 'reconciliation': rec, 'n_entries': len(rows),
           'NOT_A_FORECAST_INPUT': True, 'written_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    (OUT / 'ATL_NO_POSTGAME_ACTUAL.json').write_text(json.dumps(doc, indent=1, default=float))
    with (OUT / 'ATL_NO_OWNER_ENTRIES_GRADED.csv').open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return doc, rows


if __name__ == '__main__':
    doc, rows = run(sys.argv[1], sys.argv[2])
    print(doc['final_score'], doc['reconciliation'])
    top = sorted(((k, v['dk_A'], v['dk_B']) for k, v in doc['player_actuals'].items()), key=lambda x: -x[1])[:16]
    for t in top:
        print(t)
    print('DST', json.dumps(doc['dst_components']))
