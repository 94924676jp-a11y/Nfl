"""R1 diagnostics: did V2 repair the defect, or did it just shrink every zero?

A repair that removes week-1 zero mass by removing zero mass everywhere is not
a repair, it is a second defect pointing the other way. D5 measured the SAME
cell mis-specified in OPPOSITE directions either side of the season boundary:
in weeks 2-18 a rank-1 quarterback who was not the previous primary took zero
dropbacks 71.74% of the time against a V1 model mean of 0.3808 -- V1
UNDER-assigns there. So this script scores V2 on both populations, and the
in-season one is the one that can fail.

Also measured here: the two engine-level symptoms the brief named -- top-passer
share, and the fraction of team-games projecting two quarterbacks at five or
more dropbacks -- against their realised values on the same frame.

    python3.12 nfl/research/v2/r1/r1_diagnostics.py
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb3')):
    if q not in sys.path:
        sys.path.insert(0, q)

from nfl.production.nonqb import qb_room_v2 as V2   # noqa: E402

SEASONS = (2021, 2022, 2023, 2024, 2025)
SCORE_SEASONS = (2022, 2023, 2024)          # forward-chained: 2021 has no prior
M = 500
SEED = 20260914
B = 2000


def clustered_ci(diff, clusters, b=B, seed=SEED):
    d = np.asarray(diff, float)
    cl = np.asarray(clusters)
    uc = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in uc}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(b):
        pick = rng.choice(uc, size=len(uc), replace=True)
        s = np.concatenate([idx[c] for c in pick])
        out.append(d[s].mean())
    return round(float(np.quantile(out, 0.025)), 4), \
        round(float(np.quantile(out, 0.975)), 4)


def main():
    tg = V2.load_pbp(SEASONS)
    pp = V2.previous_primary_from_panel()
    dw = V2.load_depth_weekly([2021, 2022, 2023, 2024])
    depth = {}
    for k, g in tg.items():
        r = dw.get((g['season'], g['week'], g['team']))
        if r:
            depth[k] = r
    dates = {k: g['date'] for k, g in tg.items() if g['season'] == 2025}
    for k, v in V2.load_depth_daily_asof(dates).items():
        depth.setdefault(k, v)
    frame = V2.build_frame(tg, depth, pp)

    rooms = collections.defaultdict(list)
    for r in frame:
        rooms[(r['game_id'], r['team'])].append(r)

    import qb3_lib as Q
    qframe = Q.build_frame(Q.load_qb_panel(), Q.load_depth())

    pars_v2, pars_v1, pools = {}, {}, {}
    for y in SCORE_SEASONS:
        cut = y * 100 + 1
        pars_v2[y] = V2.fit(frame, tg, cut, use_opener=True, prior='jeffreys')
        pars_v1[y] = Q.fit(qframe, y)
        pools[y] = np.asarray([len(g['db']) for g in tg.values()
                               if g['season'] * 100 + g['week'] < cut], float)

    rec = []
    tg_rec = []
    for key, rs in sorted(rooms.items()):
        y = rs[0]['season']
        if y not in SCORE_SEASONS:
            continue
        room_sorted = sorted(rs, key=lambda x: x['rank'])
        room = [{'pid': x['pid'], 'rank': x['rank'],
                 'was_prev_primary': x['was_prev_primary']}
                for x in room_sorted]
        o = room_sorted[0]['ord']
        rng = np.random.default_rng([SEED, o, 11])
        V = pools[y][rng.integers(0, len(pools[y]), M)]
        al = V2.allocate_dropbacks(pars_v2[y], room, V, seed=SEED, ordinal=o,
                                   team=room_sorted[0]['team'],
                                   is_opener=bool(room_sorted[0]['is_opener']))
        trip = [(x['pid'], x['rank'], x['was_prev_primary'])
                for x in room_sorted]
        S1 = Q.allocate(pars_v1[y], trip, m=M, seed=SEED, ordinal=o,
                        team=room_sorted[0]['team'])
        DB = al['db']
        tot = DB.sum(0)
        with np.errstate(invalid='ignore', divide='ignore'):
            top_v2 = np.where(tot > 0, DB.max(0) / np.maximum(tot, 1), np.nan)
        tg_rec.append({
            'key': key, 'season': y, 'week': room_sorted[0]['week'],
            'is_opener': room_sorted[0]['is_opener'],
            'top_share_v2': float(np.nanmean(top_v2)),
            'top_share_v1': float(np.nanmean(S1.max(0))),
            'two_qb_ge5_v2': float(((DB >= 5).sum(0) >= 2).mean()),
            'two_qb_ge5_v1': float((
                (np.rint(S1 * V[None, :]) >= 5).sum(0) >= 2).mean()),
        })
        for i, x in enumerate(room_sorted):
            rec.append({
                'key': key, 'season': y, 'week': x['week'],
                'team': x['team'], 'rank': x['rank'],
                'was_prev_primary': x['was_prev_primary'],
                'is_opener': x['is_opener'],
                'zero_v2': float((DB[i] == 0).mean()),
                'zero_v1': float((S1[i] <= 0).mean()),
                'realised_zero': int(x['db'] == 0),
            })

    def block(rows, label):
        if not rows:
            return None
        zv2 = np.array([r['zero_v2'] for r in rows])
        zv1 = np.array([r['zero_v1'] for r in rows])
        ry = np.array([r['realised_zero'] for r in rows], float)
        cl = np.array([str(r['key'][0]) for r in rows])
        return {'label': label, 'n': len(rows),
                'n_games': int(len({r['key'][0] for r in rows})),
                'realised_zero': round(float(ry.mean()), 4),
                'V1_mean': round(float(zv1.mean()), 4),
                'V2_mean': round(float(zv2.mean()), 4),
                'V1_gap': round(float((zv1 - ry).mean()), 4),
                'V1_gap_ci': clustered_ci(zv1 - ry, cl),
                'V2_gap': round(float((zv2 - ry).mean()), 4),
                'V2_gap_ci': clustered_ci(zv2 - ry, cl),
                'V1_brier': round(float(((zv1 - ry) ** 2).mean()), 4),
                'V2_brier': round(float(((zv2 - ry) ** 2).mean()), 4)}

    r1 = [r for r in rec if r['rank'] == 1]
    out = {'spec_version': V2.SPEC_VERSION,
           'forward_chained_seasons': list(SCORE_SEASONS),
           'm_draws': M, 'n_rows_scored': len(rec),
           'n_team_games_scored': len(tg_rec),
           'zero_mass_reliability': [
               block(r1, 'rank-1 QB, ALL weeks'),
               block([r for r in r1 if r['is_opener']],
                     'rank-1 QB, SEASON OPENER'),
               block([r for r in r1 if not r['is_opener']],
                     'rank-1 QB, IN-SEASON'),
               block([r for r in r1 if not r['is_opener']
                      and not r['was_prev_primary']],
                     'rank-1 QB, IN-SEASON, not the previous primary '
                     '(D5 says V1 UNDER-assigns here)'),
               block([r for r in r1 if r['is_opener']
                      and not r['was_prev_primary']],
                     'rank-1 QB, OPENER, not the previous primary '
                     '(the cell that produced 0.412)'),
               block([r for r in rec if r['rank'] == 2], 'rank-2 QB, all'),
               block([r for r in rec if r['rank'] == 3], 'rank-3 QB, all'),
               block(rec, 'every charted QB'),
           ]}

    ts_v2 = np.array([r['top_share_v2'] for r in tg_rec])
    ts_v1 = np.array([r['top_share_v1'] for r in tg_rec])
    realised_top, realised_two = [], []
    for r in tg_rec:
        seq = tg[r['key']]['db']
        c = collections.Counter(x[0] for x in seq)
        realised_top.append(max(c.values()) / len(seq))
        realised_two.append(int(sum(1 for v in c.values() if v >= 5) >= 2))
    realised_top = np.asarray(realised_top, float)
    realised_two = np.asarray(realised_two, float)
    two1 = np.array([r['two_qb_ge5_v1'] for r in tg_rec])
    two2 = np.array([r['two_qb_ge5_v2'] for r in tg_rec])
    op = np.array([bool(r['is_opener']) for r in tg_rec])

    def sym(sel, label):
        return {'stratum': label, 'n_team_games': int(sel.sum()),
                'top_passer_share': {
                    'realised': round(float(realised_top[sel].mean()), 4),
                    'V1': round(float(ts_v1[sel].mean()), 4),
                    'V2': round(float(ts_v2[sel].mean()), 4)},
                'frac_two_qb_at_5plus_dropbacks': {
                    'realised': round(float(realised_two[sel].mean()), 4),
                    'V1': round(float(two1[sel].mean()), 4),
                    'V2': round(float(two2[sel].mean()), 4)}}

    out['engine_symptoms'] = [sym(np.ones(len(tg_rec), bool), 'all weeks'),
                              sym(op, 'SEASON OPENER'),
                              sym(~op, 'IN-SEASON')]

    # the previous-primary feature: panel (attempts) vs pbp (true dropbacks)
    agree = dis = 0
    for key, g in tg.items():
        c = collections.Counter()
        for pid, kind, comp, yds in g['db']:
            c[pid] += 1
        if not c:
            continue
        pbp_primary = max(c.items(), key=lambda x: x[1])[0]
        o = g['season'] * 100 + g['week']
        panel = pp['primary'].get((g['team'], o))
        if panel is None:
            continue
        agree += int(panel == pbp_primary)
        dis += int(panel != pbp_primary)
    out['prev_primary_feature_definition_check'] = {
        'what': ('panel_p3.dropbacks_as_passer is an ATTEMPT count, not a '
                 'dropback count. This measures how often the primary it '
                 'names differs from the true-dropback primary.'),
        'n_team_games': agree + dis, 'agree': agree, 'disagree': dis,
        'disagree_rate': round(dis / max(agree + dis, 1), 5)}

    p = _REPO / 'nfl' / 'research' / 'v2' / 'r1' / 'R1_DIAGNOSTICS.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    print('WROTE', p)


if __name__ == '__main__':
    main()
