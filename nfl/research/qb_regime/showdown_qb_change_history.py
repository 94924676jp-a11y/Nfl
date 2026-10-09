#!/usr/bin/env python3.12
"""Were our Showdown forecast errors larger for clubs whose starting QB had changed? Descriptive, every graded slate.

    python3.12 nfl/research/qb_regime/showdown_qb_change_history.py --out OUT.json

Owner directive 2026-10-09. A club-game is QB_CHANGE when its starter (most dropbacks) is not the most frequent
starter of that club's previous 8 regular-season games (2025-2026 nflverse play-by-play); otherwise STABLE.

Per club-game, from the FROZEN pregame forecast and its graded actuals:
  player DK error (MAE, mean signed error) over players either projected >= 3 or scoring >= 3,
  the starter's pass attempts error, and team points error where the frozen worlds carry club points.
Graded slates: DET@BUF 2026W2 (research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME), ATL@NO 2026W4 and TB@DAL 2026W5
(nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl + frozen worlds). IND@KC, NYG@LAR, PIT@CLE, PHI@CHI have no graded
frozen projection in the repository and are listed with their QB status only.

WHAT THIS CAN SAY: six graded club-games across three games. It can show whether a pattern is visible; it cannot
establish one. Engine versions differ between slates (W2 predates V1 role state), which is a confound named here.
"""
from __future__ import annotations

import argparse
import glob
import json
import pathlib
import sys

import numpy as np
import pandas as pd

_REPO = pathlib.Path(__file__).resolve().parents[3]


def starters():
    cols = ['game_id', 'season', 'week', 'season_type', 'posteam', 'passer_player_name', 'qb_dropback']
    p = pd.concat([pd.read_csv(glob.glob(str(_REPO / 'nfl/research/postgame/pbp_2025.*.csv.gz'))[0], low_memory=False, usecols=cols),
                   pd.read_csv(glob.glob(str(_REPO / 'nfl/dfs/salaries/raw/classic_early_2026W5/NFLVERSE_PBP_2026.*.csv.gz'))[0],
                               low_memory=False, usecols=cols)])
    p = p[(p.season_type == 'REG') & (p.qb_dropback == 1) & p.passer_player_name.notna()]
    p['gidx'] = p.season * 100 + p.week
    db = p.groupby(['game_id', 'gidx', 'posteam']).passer_player_name.agg(lambda s: s.value_counts().idxmax()).reset_index()
    att = p.groupby(['game_id', 'posteam']).size()
    return db, att


def classify(db, team, game_id):
    rows = db[db.posteam == team].sort_values('gidx')
    x = rows[rows.game_id == game_id]
    if x.empty:
        return None
    prior = rows[rows.gidx < x.gidx.iloc[0]].tail(8)
    dom = prior.passer_player_name.value_counts()
    st = x.passer_player_name.iloc[0]
    return {'starter': st, 'prior8': {k: int(v) for k, v in dom.items()},
            'status': 'QB_CHANGE' if dom.empty or dom.idxmax() != st else 'STABLE'}


def ledger_rows(tag):
    L = [json.loads(x) for x in (_REPO / 'nfl/postgame/SHOWDOWN_PLAYER_GRADING_LEDGER.jsonl').read_text().splitlines() if x.strip()]
    return [r for r in L if r['tag'] == tag]


def club_errors(rows):
    out = {}
    for t in sorted({r['player'].rsplit('|', 1)[1] for r in rows}):
        R = [r for r in rows if r['player'].endswith('|' + t) and r['pos'] not in ('DST', 'K')
             and max(r['ours_mean'], r['actual']) >= 3]
        e = np.array([r['our_error'] for r in R])
        out[t] = {'n_players': len(R), 'player_dk_mae': round(float(np.abs(e).mean()), 2), 'player_dk_bias': round(float(e.mean()), 2)}
    return out


def team_points(draws_path, final):
    d = json.loads(pathlib.Path(draws_path).read_text())
    wp = d['world_points']
    P = np.asarray(wp['points'], float)
    m = {wp['home']: float(P[:, 0].mean()), wp['away']: float(P[:, 1].mean())}
    return {t: {'ours_mean': round(m[t], 2), 'actual': final[t], 'error': round(final[t] - m[t], 2)} for t in m}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    db, att = starters()
    slates = {
        'DET_BUF_2026W2': {'game_id': '2026_02_DET_BUF', 'teams': ('DET', 'BUF')},
        'IND_KC_2026W2': {'game_id': '2026_02_IND_KC', 'teams': ('IND', 'KC')},
        'NYG_LAR_2026W2': {'game_id': '2026_02_NYG_LA', 'teams': ('NYG', 'LA')},
        'PHI_CHI_2026W3': {'game_id': '2026_03_PHI_CHI', 'teams': ('PHI', 'CHI')},
        'PIT_CLE_2026W4': {'game_id': '2026_04_PIT_CLE', 'teams': ('PIT', 'CLE')},
        'ATL_NO_2026W4': {'game_id': '2026_04_ATL_NO', 'teams': ('ATL', 'NO')},
        'TB_DAL_2026W5': {'game_id': '2026_05_TB_DAL', 'teams': ('TB', 'DAL')},
    }
    gids = set(db.game_id)
    for s, v in slates.items():
        if v['game_id'] not in gids:
            alt = [g for g in gids if g.startswith(v['game_id'][:8]) and all(t in g for t in v['teams'])]
            if alt:
                v['game_id'] = alt[0]
        v['qb'] = {t: classify(db, t, v['game_id']) for t in v['teams']}
    # graded
    det = json.loads((_REPO / 'nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME/GRADE_PROJECTIONS.json').read_text())['rows']
    rows = [{'player': f"{r['player']}|{r['team']}", 'pos': r['position'], 'ours_mean': r['stats']['dk_points']['mean'],
             'actual': r['stats']['dk_points']['actual'], 'our_error': r['stats']['dk_points']['actual'] - r['stats']['dk_points']['mean']}
            for r in det if r['stats'].get('dk_points', {}).get('state') == 'GRADED']
    slates['DET_BUF_2026W2']['graded'] = {'engine': 'W2 research engine (pre-V1 role state)', 'clubs': club_errors(rows)}
    slates['ATL_NO_2026W4']['graded'] = {'engine': 'production v2 (RW_INACTIVES_CHARTFIX)', 'clubs': club_errors(ledger_rows('ATL_NO_2026W4')),
                                         'team_points': team_points(_REPO / 'nfl/dfs/salaries/showdown_atl_no/RW_INACTIVES_CHARTFIX/SHOWDOWN_ATL_NO_2026W4_DRAWS.json',
                                                                    {'ATL': 45, 'NO': 24})}
    slates['TB_DAL_2026W5']['graded'] = {'engine': 'OFFICIAL 2026-10-08', 'clubs': club_errors(ledger_rows('TB_DAL_2026W5')),
                                         'team_points': team_points(_REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL/SHOWDOWN_TB_DAL_2026W5_DRAWS.json',
                                                                    {'TB': 24, 'DAL': 16})}
    # summary by status
    by = {'QB_CHANGE': [], 'STABLE': []}
    for s, v in slates.items():
        g = v.get('graded')
        if not g:
            continue
        for t in v['teams']:
            q = v['qb'][t]
            c = g['clubs'].get(t)
            if q and c:
                tp = (g.get('team_points') or {}).get(t)
                by[q['status']].append({'slate': s, 'club': t, 'starter': q['starter'], **c,
                                        'team_points_error': tp['error'] if tp else None})
    summ = {k: {'club_games': len(v), 'mean_player_dk_mae': round(float(np.mean([x['player_dk_mae'] for x in v])), 2) if v else None,
                'mean_abs_team_points_error': round(float(np.mean([abs(x['team_points_error']) for x in v if x['team_points_error'] is not None])), 2)
                if any(x['team_points_error'] is not None for x in v) else None, 'rows': v} for k, v in by.items()}
    doc = {'ARTIFACT': 'SHOWDOWN_QB_CHANGE_HISTORY', 'slates': slates, 'by_status': summ,
           'READING': ('Descriptive only. Six graded club-games over three games, two engine generations. '
                       'No causal or even associational claim is supported at this size.')}
    pathlib.Path(a.out).write_text(json.dumps(doc, indent=1, default=str) + '\n')
    for k, v in summ.items():
        print(k, v['club_games'], 'mean player MAE', v['mean_player_dk_mae'], 'mean |team pts err|', v['mean_abs_team_points_error'])
        for x in v['rows']:
            print('   ', x)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
