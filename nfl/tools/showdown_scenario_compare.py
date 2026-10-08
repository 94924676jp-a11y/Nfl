#!/usr/bin/env python3.12
"""Side-by-side comparison of two Showdown scenarios of one slate, stage by stage. Read-only.

    python3.12 nfl/tools/showdown_scenario_compare.py SCENARIO_A SCENARIO_B --club TB --out CMP.json

Built for the TB@DAL QB scenarios (2026-10-08) after two precomputes run concurrently produced one upload.
It answers two questions separately:

  CHAIN      did each scenario consume ITS OWN upstream artifacts? The draws record the sha256 of the state
             and projection they were built from; those must equal the scenario's own copies, and the
             state must carry the scenario's own designations and starters (SCENARIO.json).
  RESPONSE   where the scenario inputs differ, which stages moved and which did not:
             designations -> slate state -> starter identification -> QB opportunity -> team passing volume
             -> receiver targets -> joint simulation -> player projections -> portfolio.

A stage that does not move is reported as UNCHANGED with the reason the model gives, never hidden: the
reader decides whether "unchanged" is appropriate. Nothing here builds, edits or selects anything.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _load(sd):
    sd = pathlib.Path(sd)
    g = lambda pat: next(sd.glob(pat))  # noqa: E731
    out = {'dir': sd, 'scenario': json.loads((sd / 'SCENARIO.json').read_text()),
           'state_path': g('SHOWDOWN_*_STATE.json'), 'proj_path': g('SHOWDOWN_*_PROJ.json'), 'draws_path': g('SHOWDOWN_*_DRAWS.json')}
    out['state'] = json.loads(out['state_path'].read_text())
    out['proj'] = json.loads(out['proj_path'].read_text())
    out['draws'] = json.loads(out['draws_path'].read_text())
    out['csv'] = {r['player']: r for r in csv.DictReader(open(g('*_PROJECTIONS.csv')))}
    out['exp'] = list(csv.DictReader(open(g('*_EXPOSURES.csv')))) if list(sd.glob('*_EXPOSURES.csv')) else []
    out['cpt'] = list(csv.DictReader(open(g('*_CPT_EXPOSURES.csv')))) if list(sd.glob('*_CPT_EXPOSURES.csv')) else []
    out['lineups'] = list(csv.DictReader(open(g('*_FINAL_LINEUPS.csv'))))
    out['upload_sha256'] = _sha(g('*_DK_UPLOAD.csv'))
    return out


def chain(s):
    d = s['draws']
    starters = s['scenario'].get('confirmed_starters') or {}
    desig = s['scenario'].get('designations') or {}
    by = {p['name']: p for p in s['state']['players'].values()}
    bad_desig = [n for n, v in desig.items() if n in by and
                 (by[n]['current_availability'].get('designation') or '').upper() != v.upper()]
    named = sorted({(p.get('predicted_lineup_context') or {}).get('relayed_name') for p in by.values()} - {None})
    res = {'draws.state_sha256 == own STATE': d.get('state_sha256') == _sha(s['state_path']),
           'draws.projection_sha256 == own PROJ': d.get('projection_sha256') == _sha(s['proj_path']),
           'state designations == SCENARIO designations': not bad_desig,
           'state starters == SCENARIO starters': named == sorted(starters)}
    return {'PASS': all(res.values()), 'checks': res, 'designation_mismatches': bad_desig,
            'state_named_starters': named, 'scenario_starters': sorted(starters)}


def _rows_by_name(proj):
    return {r['name']: r for r in proj['rows'].values()}


def _mean(xs):
    return round(statistics.fmean(xs), 3) if xs else None


def compare(a_dir, b_dir, club):
    A, B = _load(a_dir), _load(b_dir)
    out = {'ARTIFACT': 'SHOWDOWN_SCENARIO_COMPARISON', 'A': A['scenario']['scenario'], 'B': B['scenario']['scenario'],
           'club_focus': club, 'CHAIN': {'A': chain(A), 'B': chain(B)}, 'STAGES': {}}
    S = out['STAGES']
    da, db = A['scenario']['designations'], B['scenario']['designations']
    S['1_designations'] = {n: [da.get(n), db.get(n)] for n in sorted(set(da) | set(db)) if da.get(n) != db.get(n)}
    pa = {p['name']: p for p in A['state']['players'].values()}
    pb = {p['name']: p for p in B['state']['players'].values()}
    S['2_slate_state'] = {n: {'A': [pa[n]['current_availability']['status'], pa[n]['current_availability'].get('designation'), pa[n].get('depth_rank')],
                              'B': [pb[n]['current_availability']['status'], pb[n]['current_availability'].get('designation'), pb[n].get('depth_rank')]}
                          for n in sorted(set(pa) & set(pb))
                          if (pa[n]['current_availability']['status'], pa[n]['current_availability'].get('designation'), pa[n].get('depth_rank'))
                          != (pb[n]['current_availability']['status'], pb[n]['current_availability'].get('designation'), pb[n].get('depth_rank'))}
    ra, rb = _rows_by_name(A['proj']), _rows_by_name(B['proj'])
    S['3_starter_identification'] = {n: [ra[n].get('is_predicted_starter'), rb[n].get('is_predicted_starter')]
                                     for n in sorted(set(ra) & set(rb))
                                     if ra[n].get('is_predicted_starter') != rb[n].get('is_predicted_starter')}
    qbs = sorted(n for n in set(ra) | set(rb) if (ra.get(n) or rb.get(n))['position'] == 'QB'
                 and (ra.get(n) or rb.get(n))['team'] == club)
    f = lambda r, k: (round(r[k], 2) if isinstance((r or {}).get(k), (int, float)) else (r or {}).get(k))  # noqa: E731
    S['4_qb_opportunity'] = {n: {k: [f(ra.get(n), k), f(rb.get(n), k)] for k in
                                 ('projection_state', 'p_plays', 'pass_attempts', 'pass_yards', 'carries', 'dk_points')}
                             for n in qbs}
    tva, tvb = A['proj']['team_volume'].get(club, {}), B['proj']['team_volume'].get(club, {})
    cwa, cwb = A['draws']['club_worlds'][club], B['draws']['club_worlds'][club]
    S['5_team_passing'] = {'proj_pass_attempts': [tva.get('proj_pass_attempts'), tvb.get('proj_pass_attempts')],
                           'proj_targets': [tva.get('proj_targets'), tvb.get('proj_targets')],
                           'sim_mean_pass_attempts': [_mean([w[0] for w in cwa]), _mean([w[0] for w in cwb])],
                           'sim_mean_rush_attempts': [_mean([w[1] for w in cwa]), _mean([w[1] for w in cwb])],
                           'football_centre': [A['proj'].get('football_centre'), B['proj'].get('football_centre')],
                           'WHY_IF_EQUAL': ('club volume and the scoring centre are club-level blends of the club\'s own '
                                            'history (proj_v1.team_volume, nfl/sim/football_points.py); no term in '
                                            'either depends on which quarterback starts')}
    rec = sorted(n for n in set(ra) & set(rb) if ra[n]['team'] == club and ra[n]['position'] in ('WR', 'TE', 'RB'))
    S['6_receiver_targets'] = {n: {'targets': [f(ra[n], 'targets'), f(rb[n], 'targets')],
                                   'rec_yards': [f(ra[n], 'rec_yards'), f(rb[n], 'rec_yards')],
                                   'dk_points': [f(ra[n], 'dk_points'), f(rb[n], 'dk_points')]} for n in rec
                               if (ra[n].get('targets') or 0) > 0.5 or (rb[n].get('targets') or 0) > 0.5}
    wa, wb = A['draws']['world_points']['points'], B['draws']['world_points']['points']
    S['7_joint_simulation'] = {'mean_world_points_home_away': [[_mean([w[0] for w in wa]), _mean([w[1] for w in wa])],
                                                              [_mean([w[0] for w in wb]), _mean([w[1] for w in wb])]],
                               'draws_identical': A['draws']['draws'] == B['draws']['draws']}
    ca, cb = A['csv'], B['csv']
    moved = {}
    for n in sorted(set(ca) | set(cb)):
        x, y = ca.get(n, {}), cb.get(n, {})
        if (x.get('sim_mean'), x.get('availability')) != (y.get('sim_mean'), y.get('availability')):
            moved[n] = {'team': x.get('team') or y.get('team'),
                        'sim_mean': [x.get('sim_mean'), y.get('sim_mean')],
                        'availability': [x.get('availability'), y.get('availability')]}
    S['8_player_projections'] = {'n_moved': len(moved), 'n_players': len(set(ca) | set(cb)), 'moved': moved}

    def expo(rows, key):
        t = {}
        for r in rows:
            t[r[key]] = t.get(r[key], 0) + int(r['n'])
        return t
    ea, eb = expo(A['exp'], 'player'), expo(B['exp'], 'player')
    xa, xb = expo(A['cpt'], 'captain'), expo(B['cpt'], 'captain')
    la = {tuple([r['CPT']] + sorted(r[f'FLEX{i}'] for i in range(1, 6))) for r in A['lineups']}
    lb = {tuple([r['CPT']] + sorted(r[f'FLEX{i}'] for i in range(1, 6))) for r in B['lineups']}
    S['9_portfolio'] = {'upload_sha256': [A['upload_sha256'], B['upload_sha256']],
                        'distinct_lineups': [len(la), len(lb)], 'shared_lineups': len(la & lb),
                        'exposure_changes_total_slots': {n: [ea.get(n, 0), eb.get(n, 0)] for n in sorted(set(ea) | set(eb))
                                                         if ea.get(n, 0) != eb.get(n, 0)},
                        'captain_changes': {n: [xa.get(n, 0), xb.get(n, 0)] for n in sorted(set(xa) | set(xb))
                                            if xa.get(n, 0) != xb.get(n, 0)}}
    # RESPONSE VERDICT: the scenario inputs differ in who starts at QB, so the QB stage MUST move; a portfolio
    # identical to the other scenario's is a failure whatever the reason.
    resp = {'qb_opportunity_moved': any(v['pass_attempts'][0] != v['pass_attempts'][1] for v in S['4_qb_opportunity'].values()),
            'portfolio_differs': A['upload_sha256'] != B['upload_sha256'],
            'team_volume_moved': S['5_team_passing']['proj_pass_attempts'][0] != S['5_team_passing']['proj_pass_attempts'][1],
            'receivers_moved': any(v['targets'][0] != v['targets'][1] or v['dk_points'][0] != v['dk_points'][1]
                                   for v in S['6_receiver_targets'].values())}
    out['RESPONSE'] = resp
    out['VERDICT'] = ('ISOLATION_PASS' if out['CHAIN']['A']['PASS'] and out['CHAIN']['B']['PASS']
                      and resp['qb_opportunity_moved'] and resp['portfolio_differs'] else 'ISOLATION_FAIL')
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--club', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    res = compare(a.a, a.b, a.club)
    txt = json.dumps(res, indent=1, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(txt + '\n')
    print(txt[:6000])
    sys.exit(0 if res['VERDICT'] == 'ISOLATION_PASS' else 2)
