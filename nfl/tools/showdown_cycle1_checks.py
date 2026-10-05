#!/usr/bin/env python3.12
"""Cycle 1 ledger checks that can run from the repository tonight. Diagnostics only; nothing feeds back.

    python3.12 nfl/tools/showdown_cycle1_checks.py SCENARIO_DIR

COR-01 / COR-02  CORRELATION RECOVERY. Pearson correlations of per-world DK points between role pairs, read off the
                 scenario's sealed joint-simulation draws, beside the published single-game values (Spikeweek
                 2018-23; FantasyLabs). A VALIDATION TARGET ONLY: the ledger is explicit that these are never an
                 imposed copula, and nothing here changes the simulator. Roles are assigned by simulated mean within
                 team and position (QB = the scenario's confirmed starter).
DATA-04          CROSS-SLATE OWNERSHIP POINT. A prior ATL Showdown (238K lineups, stat-api sample table) showed Bijan
                 25.4% CPT / 50.5% FLEX, London 13.3 / 36.3, Penix 2.8 / 34.0. Printed beside tonight's SHADOW
                 CPT/FLEX ownership (FC_ONLY and BLEND). Different slate, different opponent: a sanity point, never a fit.
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]

PUBLISHED = {   # pair: (Spikeweek COR-01, FantasyLabs COR-02); None = not published by that source
    'QB-WR1': (0.542, 0.54), 'QB-WR2': (0.514, 0.48), 'QB-TE1': (0.366, 0.49), 'QB-RB1': (0.09, 0.38),
    'WR1-WR2_same_team': (0.345, None), 'WR1-opposing_WR1': (0.56, None),
    'QB-own_DST': (None, 0.07), 'QB-opposing_DST': (None, -0.16),
}
DATA04 = {'Bijan Robinson': (25.4, 50.5), 'Drake London': (13.3, 36.3), 'Michael Penix Jr.': (2.8, 34.0)}


def roles(sd):
    proj = list(csv.DictReader(open(next(sd.glob('SHOWDOWN_*_PROJECTIONS.csv')))))
    scen = json.loads((sd / 'SCENARIO.json').read_text())
    starters = scen.get('confirmed_starters') or {}
    out = {}
    for team in sorted({r['team'] for r in proj}):
        rows = [r for r in proj if r['team'] == team and r['sim_mean'] and r['state'] != 'INACTIVE']
        by = lambda pos: sorted((r for r in rows if r['pos'] == pos), key=lambda r: -float(r['sim_mean']))
        qb = next((r['player'] for r in by('QB') if starters.get(r['player']) == team), None) or (by('QB')[0]['player'] if by('QB') else None)
        wr, te, rb, dst = by('WR'), by('TE'), by('RB'), by('DST')
        out[team] = {'QB': qb, 'WR1': wr[0]['player'] if wr else None, 'WR2': wr[1]['player'] if len(wr) > 1 else None,
                     'TE1': te[0]['player'] if te else None, 'RB1': rb[0]['player'] if rb else None,
                     'DST': dst[0]['player'] if dst else None}
    return out


def run(sd):
    sd = pathlib.Path(sd)
    d = json.loads(next(sd.glob('SHOWDOWN_*_DRAWS.json')).read_text())
    draws = {k.split('|')[0]: np.asarray(v, dtype=float) for k, v in d['draws'].items()}
    R = roles(sd)
    teams = list(R)
    corr = lambda a, b: (round(float(np.corrcoef(draws[a], draws[b])[0, 1]), 3)
                         if a in draws and b in draws and draws[a].std() > 0 and draws[b].std() > 0 else None)
    rows = []
    for t in teams:
        o = [x for x in teams if x != t][0]
        r, ro = R[t], R[o]
        pairs = {'QB-WR1': (r['QB'], r['WR1']), 'QB-WR2': (r['QB'], r['WR2']), 'QB-TE1': (r['QB'], r['TE1']),
                 'QB-RB1': (r['QB'], r['RB1']), 'WR1-WR2_same_team': (r['WR1'], r['WR2']),
                 'WR1-opposing_WR1': (r['WR1'], ro['WR1']), 'QB-own_DST': (r['QB'], r['DST']),
                 'QB-opposing_DST': (r['QB'], ro['DST'])}
        for name, (a, b) in pairs.items():
            sw, fl = PUBLISHED[name]
            ours = corr(a, b) if a and b else None
            rows.append({'team': t, 'pair': name, 'players': [a, b], 'ours': ours, 'spikeweek_COR01': sw, 'fantasylabs_COR02': fl,
                         'ours_minus_spikeweek': None if ours is None or sw is None else round(ours - sw, 3),
                         'ours_minus_fantasylabs': None if ours is None or fl is None else round(ours - fl, 3)})
    # SAME-WORLD COHERENCE vs history (nfl/research/coherence/TEAM_COHERENCE_2021_2025.json)
    hist = json.loads((_REPO / 'nfl/research/coherence/TEAM_COHERENCE_2021_2025.json').read_text())
    proj = {r['player']: r for r in csv.DictReader(open(next(sd.glob('SHOWDOWN_*_PROJECTIONS.csv'))))}
    wp = np.asarray(d['world_points']['points'], dtype=float)
    cols = {d['world_points']['home']: 0, d['world_points']['away']: 1}
    cs = d.get('club_scoring_worlds') or {}
    off = {}
    coh = {}
    for t, c in cols.items():
        keys = [k for k in d['draws'] if k.endswith('|' + t) and proj.get(k.split('|')[0], {}).get('pos') in ('QB', 'RB', 'WR', 'TE')]
        off[t] = sum(np.asarray(d['draws'][k], dtype=float) for k in keys)
        td = np.asarray(cs[t], dtype=float)[:, 1] if t in cs else None
        coh[t] = {'corr_team_td_vs_team_off_dk': None if td is None else round(float(np.corrcoef(td, off[t])[0, 1]), 3),
                  'corr_team_points_vs_team_off_dk': round(float(np.corrcoef(wp[:, c], off[t])[0, 1]), 3)}
    h, a = list(cols)
    coherence = {'ours_by_team': coh,
                 'ours_corr_home_points_vs_away_points': round(float(np.corrcoef(wp[:, 0], wp[:, 1])[0, 1]), 3),
                 'ours_corr_home_off_dk_vs_away_off_dk': round(float(np.corrcoef(off[h], off[a])[0, 1]), 3),
                 'history_2021_2025': {k: hist[k] for k in hist if k.startswith('corr_')} | {'team_games': hist['team_games']},
                 'FINDING': ('DEFECT-COHERENCE (measured 2026-10-05): within a simulated world, a team\'s offensive DK points '
                             'track its touchdowns and points far more loosely than in 2021-25 games (see the numbers). The '
                             'TD identity holds, so this is not broken accounting: yardage/receptions are drawn too '
                             'independently of scoring. Effect: same-team boom-together is understated, so stacks are '
                             'undervalued in the top tail. NOT fixed tonight (no validated fix before lock; the sealed football '
                             'model is preserved); registered as the first post-lock football item.')}
    own = {}
    for src, dname in (('FC_ONLY', 'SHADOW_' + sd.name), ('BLEND', 'SHADOW_' + sd.name + '_BLEND')):
        p = sd.parent / dname / 'SHOWDOWN_ATL_NO_SHADOW_OWNERSHIP.csv'
        if p.exists():
            own[src] = {r['player']: (float(r['shadow_cpt_own_pct']), float(r['shadow_flex_own_pct'])) for r in csv.DictReader(open(p))}
    data04 = [{'player': n, 'prior_ATL_slate_cpt_flex': v,
               **{f'tonight_shadow_{s}_cpt_flex': own[s].get(n) for s in own},
               'prior_cpt_to_flex_ratio': round(v[0] / v[1], 2),
               **{f'tonight_{s}_ratio': (round(own[s][n][0] / own[s][n][1], 2) if own[s].get(n) and own[s][n][1] else None)
                  for s in own}} for n, v in DATA04.items()]
    doc = {'ARTIFACT': 'SHOWDOWN_CYCLE1_CHECKS', 'scenario': sd.name,
           'as_of_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'draws_sha256': d.get('projection_sha256'), 'n_worlds': len(next(iter(draws.values()))),
           'roles': R, 'correlation_recovery': rows,
           'CORRELATION_STATUS': ('VALIDATION TARGET ONLY (COR-01/COR-02). Published values have no intervals and differ '
                                  'between sources (QB-RB1 0.09 vs 0.38); a gap is a question for the post-lock football '
                                  'program, never a reason to impose a copula or edit tonight\'s simulator.'),
           'same_world_coherence': coherence,
           'data04_cross_slate_ownership': data04,
           'DATA04_STATUS': 'different slate (prior ATL Showdown, 238K lineups); a sanity point, not a fit, not a target'}
    p = sd / 'SHOWDOWN_ATL_NO_CYCLE1_CHECKS.json'
    p.write_text(json.dumps(doc, indent=1, default=str))
    return p, doc


if __name__ == '__main__':
    p, doc = run(sys.argv[1])
    print(p)
    for r in doc['correlation_recovery']:
        print(f"{r['team']:4} {r['pair']:20} ours {r['ours']}  spikeweek {r['spikeweek_COR01']}  fantasylabs {r['fantasylabs_COR02']}  {r['players']}")
    for r in doc['data04_cross_slate_ownership']:
        print(r)
    print(json.dumps(doc['same_world_coherence'], indent=1))
