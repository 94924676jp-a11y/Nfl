#!/usr/bin/env python3.12
"""Tonight's showdown, one command per football state: slate state -> projection -> worlds -> portfolio.

    python3.12 nfl/tools/showdown_tonight.py EXPORT --tag ATL_NO_2026W4 --scenario BASE \
        --designations nfl/dfs/salaries/showdown_atl_no/DESIGNATIONS_ATL_NO_2026W4.json \
        [--out NAME ...] [--official-inactives JSON] [--n-sims 2000]

A SCENARIO IS A FOOTBALL STATE, NOTHING ELSE. `--out NAME` marks a player OUT on top of the team's own
designations (an IF-INACTIVE precompute); `--official-inactives` applies a captured list. Each scenario
writes its own directory, so precomputed states never overwrite one another, and when the inactives
arrive the only change is the football state: the same code reruns on it.

IF-LIMITED is NOT a scenario here: there is no measured snap- or route-reduction for a limited player,
and inventing one would be a silent constant. A limited player is either active (full role) or out.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def run(export, tag, scenario, designations=None, outs=(), official_inactives=None, n_sims=2000):
    from nfl.tools import showdown_slate_state as SSS, showdown_slate_run as SR, showdown_portfolio as SPF
    P = SR.paths(tag)
    P['dir'].mkdir(parents=True, exist_ok=True)
    desig = dict(designations or {})
    for n in outs:
        desig[n] = 'OUT'
    SSS.OUT = P['state']
    st = SSS.build(export, designations=desig, official_inactives=official_inactives)
    print('state', st.state.value, st.code, st.detail, flush=True)
    if st.state.value != 'PASS':
        return st
    dr = SR.run(tag, n_sims=n_sims)
    print('draws', dr.state.value, dr.code, dr.detail, flush=True)
    if dr.state.value != 'PASS':
        return dr
    sd = P['dir'] / scenario
    sd.mkdir(exist_ok=True)
    for k in ('state', 'proj', 'draws', 'worlds'):
        shutil.copy2(P[k], sd / P[k].name)
    state = json.loads(P['state'].read_text())
    from nfl.tools import availability as AV
    absent = sorted(v['name'] for v in state['players'].values()
                    if v['current_availability']['status'] in AV.ABSENT_STATUSES)
    (sd / 'SCENARIO.json').write_text(json.dumps({
        'scenario': scenario, 'export': str(export), 'designations': desig,
        'forced_out': list(outs), 'official_inactives': official_inactives,
        'absent_in_state': absent, 'n_sims': n_sims}, indent=1))
    pf = SPF.run(export, sd / P['draws'].name, sd, f'SHOWDOWN_{tag.split("_2026")[0]}', inactives=absent,
                 proj_path=sd / P['proj'].name, state_path=sd / P['state'].name)
    print('portfolio', pf.state.value, pf.code, pf.detail, flush=True)
    role_diagnostic(P['dir'] / f'SHOWDOWN_{tag.split("_2026")[0]}_ROLE_REVIEW.csv', sd / P['proj'].name,
                    sd / f'SHOWDOWN_{tag.split("_2026")[0]}_ROLE_DIAGNOSTIC.csv')
    return pf


def role_diagnostic(review_csv, proj_path, out_csv):
    """Sunday's lesson as a DIAGNOSTIC only: depth pieces whose measured usage exceeds what we project.

    Week 4 confirmed WR3+/TE2+/RB2 under-allocation (nfl/dfs/salaries/postgame/WEEK4_POSTGAME_REPORT.md
    section 2). Nothing here changes a projection; it lists, per player, measured per-game targets and
    carries (weeks 1-3) beside ours, and flags a depth piece where measured exceeds projected.
    """
    import csv
    if not pathlib.Path(review_csv).exists():
        return
    proj = json.loads(pathlib.Path(proj_path).read_text())
    by_g = {r.get('gsis_id'): r for r in proj['rows'].values() if r.get('gsis_id')}
    out = []
    for r in csv.DictReader(open(review_csv)):
        g = int(r['games'] or 0) or 1
        pr = by_g.get(r['gsis_id']) or {}
        mt, mc = int(r['targets']) / g, int(r['carries']) / g
        pt, pc = pr.get('targets'), pr.get('carries')
        rk = int(r['depth_rank']) if str(r['depth_rank']).isdigit() else None
        depth_piece = (rk is not None and ((r['position'] == 'WR' and rk >= 3) or (r['position'] == 'TE' and rk >= 2)
                                           or (r['position'] == 'RB' and rk >= 2)))
        flag = depth_piece and ((isinstance(pt, (int, float)) and mt > pt) or (isinstance(pc, (int, float)) and mc > pc))
        out.append([r['club'], r['player'], r['position'], r['depth_pos'], r['depth_rank'], r['roster_status'],
                    r['injury_report_status'], round(mt, 2), '' if pt is None else round(pt, 2), round(mc, 2),
                    '' if pc is None else round(pc, 2), r['off_snap_pct_by_week'], r['rz_targets'], r['rz_carries'],
                    'IN_PROJECTION' if pr else 'NOT_IN_DK_PROJECTION', 'MEASURED_ABOVE_PROJECTED' if flag else ''])
    with open(out_csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['club', 'player', 'pos', 'depth_pos', 'depth_rank', 'roster_status', 'injury_status',
                    'measured_tgt_pg', 'proj_tgt', 'measured_car_pg', 'proj_car', 'snaps_by_week', 'rz_tgt_wk1_3',
                    'rz_car_wk1_3', 'projection', 'diagnostic_flag'])
        w.writerows(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--scenario', required=True)
    ap.add_argument('--designations')
    ap.add_argument('--out', action='append', default=[])
    ap.add_argument('--official-inactives')
    ap.add_argument('--n-sims', type=int, default=2000)
    a = ap.parse_args()
    d = json.loads(pathlib.Path(a.designations).read_text()) if a.designations else None
    oi = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    o = run(a.export, a.tag, a.scenario, d, a.out, oi, a.n_sims)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
