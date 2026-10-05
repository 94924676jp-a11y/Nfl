#!/usr/bin/env python3.12
"""Our Showdown projection beside FantasyCruncher's, AFTER ours exists. FC is never a model input.

    python3.12 nfl/tools/showdown_fc_compare.py SCENARIO_DIR FC_CSV

Joins on (name, team) for FLEX rows only. For each player: our draw mean / median / P90, our opportunity
(attempts, carries, targets, TD expectation) and role, against FC's FLEX projection, ceiling and pDepth.
A disagreement is decomposed into the layer that would have to differ (ROLE / VOLUME / EFFICIENCY / TD /
INJURY / DEPTH / DATA / MODEL) by rules stated in `reason()`; it is a triage label, not a verdict.
FC zero projections are NOT read as inactive.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
MATERIAL = 3.0          # reporting rule: |ours - FC| in DK points before a row is triaged


def reason(o, fc, row):
    if o is None:
        return 'DATA'
    if fc['fc'] == 0 and o > 1:
        return 'DEPTH_OR_DATA (FC zero is not an inactive signal)'
    if (fc.get('pdepth') or '').endswith(('1',)) and (row.get('depth_rank') not in (None, 1)):
        return 'DEPTH'
    if row.get('designation'):
        return 'INJURY'
    if row['pos'] in ('K',):
        return 'MODEL (same-world kicker vs FC point estimate)'
    if row['pos'] == 'DST':
        return 'MODEL (DST tail UNVALIDATED)'
    return 'ROLE_OR_VOLUME' if abs(o - fc['fc']) > 0.25 * max(fc['fc'], 1) else 'EFFICIENCY_OR_TD'


def run(sd, fc_csv):
    sd = pathlib.Path(sd)
    proj = json.loads(next(sd.glob('SHOWDOWN_*_PROJ.json')).read_text())
    draws = json.loads(next(sd.glob('SHOWDOWN_*_DRAWS.json')).read_text())['draws']
    rows = list(csv.reader(open(fc_csv, newline='', encoding='utf-8-sig')))
    hdr = next(i for i, r in enumerate(rows) if 'Player' in r and 'FC' in r)
    H = {h: j for j, h in enumerate(rows[hdr])}
    fc = {}
    for r in rows[hdr + 1:]:
        if len(r) < len(H) or r[H['Pos']] == 'CPTN':
            continue
        fc[(r[H['Player']], r[H['Team']])] = {'fc': float(r[H['FC']] or 0), 'ceiling': float(r[H['Ceiling']] or 0),
                                              'pdepth': r[H['pDepth']], 'salary': int(r[H['Salary']] or 0)}
    out = []
    for p in proj['rows'].values():
        key = f"{p['name']}|{p['team']}"
        d = draws.get(key)
        f = fc.get((p['name'], p['team']))
        m = None if d is None else float(np.mean(d))
        row = {'player': p['name'], 'team': p['team'], 'pos': p['position'],
               'our_mean': None if m is None else round(m, 2),
               'our_median': None if d is None else round(float(np.median(d)), 2),
               'our_p90': None if d is None else round(float(np.percentile(d, 90)), 2),
               'our_pass_att': round(p.get('pass_attempts') or 0, 1), 'our_carries': round(p.get('carries') or 0, 1),
               'our_targets': round(p.get('targets') or 0, 1),
               'our_td': round(sum(((p.get('td') or {}).get(k) or 0) for k in ('rec_td', 'rush_td', 'pass_td')), 2),
               'our_role': p.get('role_band'), 'depth_rank': p.get('depth_rank'),
               'designation': (p.get('availability') if 'INACTIVE' in str(p.get('availability')) else ''),
               'fc_flex': None if f is None else f['fc'], 'fc_ceiling': None if f is None else f['ceiling'],
               'fc_pdepth': None if f is None else f['pdepth']}
        row['diff_ours_minus_fc'] = None if (m is None or f is None) else round(m - f['fc'], 2)
        row['triage'] = ('' if row['diff_ours_minus_fc'] is None or abs(row['diff_ours_minus_fc']) < MATERIAL
                         else reason(m, f, row))
        row['NOT_IN_FC_FILE'] = f is None
        out.append(row)
    out.sort(key=lambda r: -abs(r['diff_ours_minus_fc'] or 0))
    pre = next(sd.glob('SHOWDOWN_*_PROJ.json')).name.split('_2026')[0]
    dst = sd / f'{pre}_FC_COMPARISON.csv'
    with dst.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    return dst, out


if __name__ == '__main__':
    p, out = run(sys.argv[1], sys.argv[2])
    print(p)
    for r in out[:25]:
        print(r)
