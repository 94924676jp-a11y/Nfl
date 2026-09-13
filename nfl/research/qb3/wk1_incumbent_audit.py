"""QB3 week-1 incumbent audit. DIAGNOSIS ONLY -- nothing here changes a forecast.

THE OBSERVATION THAT STARTED IT. On the 2026-09-13 4:25 slate the top
quarterback took only 52-58% of his club's modelled dropbacks on seven of eight
clubs, against 90.4% for Arizona. Closure was exact and team dropbacks were
plausible, so the shortfall is in the ALLOCATION, not the accounting.

THE MECHANISM, read out of the frozen contract and the code that implements it.
`qb3_lib.allocate` draws the primary's identity with
`rng.choice(n, p=pp/pp.sum())` where `pp` is each quarterback's cell
`p_primary`. Those cell values, fitted on 2020-2024:

    (1, yes) 0.9046     (1, no)  0.4922
    (2, no)  0.0686     (2+, yes) 0.6167

When the depth chart's QB1 IS last game's primary the room normalises to
0.930/0.070 and the starter dominates. When they DISAGREE -- QB1 is new, and
last game's primary is still charted behind him -- the room normalises to
0.444/0.556 and the INCUMBENT is favoured over the charted starter. That is the
~50/50, and it is arithmetic, not noise.

THE QUESTION THIS FILE ANSWERS, AND IT IS THE ONLY ONE THAT SEPARATES THE THREE
CLASSIFICATIONS. `p_primary` is a MARGINAL rate: P(is primary | my own cell),
pooled over every team-game. Normalising two marginals across a room is not
P(I am the primary | this room). Whether that composition recovers the true
conditional is an empirical question, so we ask it of the data:

    in team-games whose room is in the DISAGREE configuration, how often does
    the depth chart's QB1 actually take the primary role?

If the answer is near 0.44 the layer is right and the 4:25 board is honest
uncertainty. If it is far above, the composition is losing information the
inputs contain, and the defect is in the specification rather than the code.

MID-GAME REPLACEMENT IS KEPT SEPARATE THROUGHOUT. A starter who is knocked out
in the second quarter produces a partial share that no pregame forecaster could
have known. Scoring that as a model error manufactures a defect; hiding it
manufactures adequacy. It is carried as its own stratum and reported.

Walk-forward everywhere: for evaluation season Y every rate comes from seasons
< Y, exactly as the pre-registration fixes in s.7.
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import qb3_lib as Q                                                  # noqa: E402

AGREE = 'AGREE'
DISAGREE = 'DISAGREE'
NO_PREV = 'NO_PREV_PRIMARY_IN_ROOM'


def rooms(frame):
    """(season, week, team) -> the charted quarterback rows, one room."""
    by = collections.defaultdict(list)
    for r in frame:
        by[(r['season'], r['week'], r['team'])].append(r)
    return by


def configuration(room):
    """How the two pregame signals stand relative to each other.

    AGREE    the chart's QB1 is also last game's primary
    DISAGREE the chart's QB1 is not, and last game's primary is charted behind him
    NO_PREV  nobody in the room was last game's primary (no incumbent to disagree with)
    """
    top = [r for r in room if r['rank'] == 1]
    if not top:
        return None
    if any(r['was_prev_primary'] for r in top):
        return AGREE
    if any(r['was_prev_primary'] for r in room if r['rank'] != 1):
        return DISAGREE
    return NO_PREV


def replacement_game(room):
    """Did more than one charted quarterback actually take a dropback?

    This is the identifiable footprint of an in-game change. It is NOT a claim
    that an injury occurred -- benchings and blowout relief look the same from
    a box score -- so it is named for what it measures.
    """
    return sum(1 for r in room if r['db'] >= 1) > 1


def predicted_top_share(par, room, m=400, seed=Q.SEED):
    """What the production allocation gives the chart's QB1, mean over draws."""
    trip = [(r['pid'], r['rank'], r['was_prev_primary']) for r in room]
    S = Q.allocate(par, trip, m=m, seed=seed,
                   ordinal=room[0]['ord'], team=room[0]['team'])
    idx = [i for i, r in enumerate(room) if r['rank'] == 1]
    return float(np.mean(S[idx[0]])) if idx else float('nan')


def run(eval_seasons=(2021, 2022, 2023, 2024), week1_only=None):
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    by = rooms(frame)
    fits, out = {}, []
    for (season, week, team), room in sorted(by.items()):
        if season not in eval_seasons:
            continue
        if week1_only is True and week != 1:
            continue
        if week1_only is False and week == 1:
            continue
        cfg = configuration(room)
        if cfg is None:
            continue
        if season not in fits:
            fits[season] = Q.fit(frame, season)
        par = fits[season]
        top = [r for r in room if r['rank'] == 1][0]
        out.append({
            'season': season, 'week': week, 'team': team,
            'configuration': cfg,
            'n_qb_in_room': len(room),
            'replacement_game': replacement_game(room),
            'top_pid': top['pid'],
            'top_is_primary': int(top['is_primary']),
            'top_actual_share': float(top['share']),
            'top_predicted_share': predicted_top_share(par, room),
            'fit_n': {str(k): v for k, v in par['n'].items()},
        })
    return out


def summarise(recs, label):
    """Per-configuration calibration of the chart QB1's share. No adequacy words."""
    o = {'label': label, 'n_team_games': len(recs), 'strata': {}}
    for cfg in (AGREE, DISAGREE, NO_PREV):
        s = [r for r in recs if r['configuration'] == cfg]
        if not s:
            continue
        row = {}
        for name, sub in (('all', s),
                          ('clean', [r for r in s if not r['replacement_game']]),
                          ('replacement', [r for r in s if r['replacement_game']])):
            if not sub:
                continue
            a = np.array([r['top_actual_share'] for r in sub])
            p = np.array([r['top_predicted_share'] for r in sub])
            ip = np.array([r['top_is_primary'] for r in sub], float)
            row[name] = {
                'n': len(sub),
                'actual_P_top_is_primary': round(float(ip.mean()), 4),
                'predicted_mean_share': round(float(p.mean()), 4),
                'actual_mean_share': round(float(a.mean()), 4),
                'bias_pred_minus_actual': round(float((p - a).mean()), 4),
                'mean_abs_error': round(float(np.abs(p - a).mean()), 4),
            }
        # clustered by team, because one club's seasons are not independent
        clean = [r for r in s if not r['replacement_game']]
        if len(clean) >= 2:
            d = np.array([r['top_predicted_share'] - r['top_actual_share']
                          for r in clean])
            cl = np.array([r['team'] for r in clean])
            lo, hi = Q.clustered_ci(d, cl, B=2000)
            row['clean_bias_team_clustered_95'] = [round(lo, 4), round(hi, 4)]
            row['n_clusters'] = int(len(set(cl)))
        o['strata'][cfg] = row
    return o


def main():
    result = {'artifact': 'QB3_WEEK1_INCUMBENT_AUDIT',
              'governance': 'DIAGNOSIS ONLY -- no production value is changed',
              'contract_sha256':
                  'be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e',
              'contract_path': 'nfl/research/qb3/predeclaration_qb3.md'}
    allw = run()
    w1 = run(week1_only=True)
    wk = run(week1_only=False)
    result['cells'] = {}
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    par = Q.fit(frame, 2026)
    for c in sorted(par['n'], key=str):
        pool = par['share_pool'][c]
        result['cells'][str(c)] = {
            'n': par['n'][c], 'p_primary': round(par['p_primary'][c], 4),
            'pool_mean': round(float(pool.mean()), 4),
            'P_share_eq_1': round(float((pool == 1.0).mean()), 4),
            'P_share_eq_0': round(float((pool == 0.0).mean()), 4)}
    a, b = par['p_primary'][(1, 0)], par['p_primary'][('2+', 1)]
    c, d = par['p_primary'][(1, 1)], par['p_primary'][(2, 0)]
    result['room_normalisation'] = {
        'DISAGREE_top_vs_incumbent': [round(a / (a + b), 4), round(b / (a + b), 4)],
        'AGREE_top_vs_backup': [round(c / (c + d), 4), round(d / (c + d), 4)]}
    result['summaries'] = [summarise(allw, 'all weeks'),
                           summarise(w1, 'week 1 only'),
                           summarise(wk, 'weeks 2+')]
    result['configuration_counts'] = {
        lab: dict(collections.Counter(r['configuration'] for r in recs))
        for lab, recs in (('all weeks', allw), ('week 1 only', w1),
                          ('weeks 2+', wk))}
    print(json.dumps(result, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
