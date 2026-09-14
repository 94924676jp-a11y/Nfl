"""R1 acceptance test: the week-1 depth-chart QB1 cohort, before and after.

The cohort is every depth-chart rank-1 quarterback in week 1 of 2021-2024,
n = 128 team-games, the same population `nfl/research/v2/d5/D5_ZERO_MASS_AUDIT.md`
measured. Realised zero-dropback games in that cohort: 0 of 128.

BEFORE is `qb3_lib.allocate` -- V1, unmodified, imported read-only. AFTER is
`qb_room_v2`. Nothing in either allocator is edited by this script.

Team dropback volume is drawn from the EMPIRICAL pool of team dropbacks in
seasons strictly earlier than the season being scored, so no realised outcome
of the game being scored enters the replay.

    python3.12 nfl/research/v2/r1/r1_cohort.py
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
COHORT_SEASONS = (2021, 2022, 2023, 2024)
M = 2000
SEED = 20260914


def load_everything():
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
    return tg, frame, depth


def team_db_pool(tg, cut):
    v = [len(g['db']) for g in tg.values()
         if g['season'] * 100 + g['week'] < cut]
    if not v:
        raise SystemExit('TEAM_DB_POOL_EMPTY')
    return np.asarray(v, float)


def v1_zero_mass(frame, cohort_rows, cut_by_season):
    """V1, forward-chained exactly as D5 ran it: qb3_lib's own frame and fit."""
    import qb3_lib as Q
    qframe = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    out = {}
    pars = {y: Q.fit(qframe, y) for y in COHORT_SEASONS}
    rooms = collections.defaultdict(list)
    for r in frame:
        rooms[(r['game_id'], r['team'])].append(r)
    vals = []
    for r in cohort_rows:
        key = (r['game_id'], r['team'])
        room = sorted(rooms[key], key=lambda x: x['rank'])
        trip = [(x['pid'], x['rank'], x['was_prev_primary']) for x in room]
        par = pars[r['season']]
        S = Q.allocate(par, trip, m=M, seed=SEED,
                       ordinal=r['ord'], team=r['team'])
        i = [x[0] for x in trip].index(r['pid'])
        vals.append(float((S[i] <= 0).mean()))
    return np.asarray(vals)


def v2_zero_mass(tg, frame, cohort_rows, use_opener, prior, forward_chained):
    rooms = collections.defaultdict(list)
    for r in frame:
        rooms[(r['game_id'], r['team'])].append(r)
    cuts = {}
    vals, pstart, prepl = [], [], []
    for r in cohort_rows:
        cut = (r['season'] * 100 + 1) if forward_chained else 202601
        key = (cut, use_opener, prior)
        if key not in cuts:
            cuts[key] = (V2.fit(frame, tg, cut, use_opener=use_opener,
                                prior=prior), team_db_pool(tg, cut))
        par, pool = cuts[key]
        rng = np.random.default_rng([SEED, r['ord'], 7])
        V = pool[rng.integers(0, len(pool), M)]
        room = [{'pid': x['pid'], 'rank': x['rank'],
                 'was_prev_primary': x['was_prev_primary']}
                for x in sorted(rooms[(r['game_id'], r['team'])],
                                key=lambda x: x['rank'])]
        al = V2.allocate_dropbacks(par, room, V, seed=SEED, ordinal=r['ord'],
                                   team=r['team'],
                                   is_opener=bool(r['is_opener']))
        i = [x['pid'] for x in room].index(r['pid'])
        db = al['db'][i]
        vals.append(float((db == 0).mean()))
        pstart.append(float((al['starter_index'] == i).mean()))
        prepl.append(float(((al['starter_index'] != i) & (db > 0)).mean()))
    return np.asarray(vals), np.asarray(pstart), np.asarray(prepl)


def describe(v):
    return {'n': int(len(v)), 'mean': round(float(v.mean()), 4),
            'p50': round(float(np.quantile(v, 0.50)), 4),
            'p90': round(float(np.quantile(v, 0.90)), 4),
            'max': round(float(v.max()), 4),
            'frac_ge_0.25': round(float((v >= 0.25).mean()), 4),
            'frac_ge_0.41': round(float((v >= 0.41).mean()), 4)}


def main():
    tg, frame, depth = load_everything()
    cohort = [r for r in frame
              if r['rank'] == 1 and r['week'] == 1
              and r['season'] in COHORT_SEASONS]
    cohort.sort(key=lambda r: (r['season'], r['team']))
    realised_zero = sum(1 for r in cohort if r['db'] == 0)
    res = {'spec_version': V2.SPEC_VERSION,
           'cohort': 'week-1 depth-chart QB1, 2021-2024',
           'n_cohort': len(cohort),
           'realised_zero_dropback_games': realised_zero,
           'n_frame_rows': len(frame),
           'n_charted_team_games': len(depth),
           'pbp_seasons': list(SEASONS), 'm_draws': M}

    v1 = v1_zero_mass(frame, cohort, None)
    res['V1_qb3_forward_chained'] = describe(v1)

    for tag, use_opener, fc in (
            ('V2_structure_only_pooled_cells_forward_chained', False, True),
            ('V2_full_forward_chained', True, True),
            ('V2_full_fit_through_2025', True, False),
            ('V2_structure_only_fit_through_2025', False, False)):
        sub = [r for r in cohort if r['season'] != 2021] if fc else cohort
        z, ps, pr = v2_zero_mass(tg, frame, sub, use_opener, 'jeffreys', fc)
        res[tag] = describe(z)
        res[tag]['mean_p_start'] = round(float(ps.mean()), 4)
        res[tag]['mean_p_replacement_state'] = round(float(pr.mean()), 4)
        res[tag]['forward_chained'] = fc
        res[tag]['seasons'] = sorted({r['season'] for r in sub})
    # no-prior sensitivity
    z, ps, pr = v2_zero_mass(tg, frame, cohort, True, 'none', False)
    res['V2_full_fit_through_2025_no_prior'] = describe(z)
    res['V2_full_fit_through_2025_no_prior']['mean_p_start'] = \
        round(float(ps.mean()), 4)

    # V1 on the same 96 forward-chained rows, for a like-for-like pair
    sub = [r for r in cohort if r['season'] != 2021]
    res['V1_qb3_forward_chained_2022_2024'] = describe(
        v1_zero_mass(frame, sub, None))

    par = V2.fit(frame, tg, 202601, use_opener=True, prior='jeffreys')
    res['fit_202601'] = {
        'p_exit': round(par['p_exit'], 4),
        'n_team_games': par['n_team_games'], 'n_exit': par['n_exit'],
        'post_pool_mean': round(float(par['post_pool'].mean()), 4),
        'post_pool_median': round(float(np.median(par['post_pool'])), 4),
        'cameo_frac_nonzero': round(float((par['cameo_pool'] > 0).mean()), 4),
        'n_relievers': dict(collections.Counter(
            par['n_relievers_pool'].tolist())),
        'p_reliever_by_rank': {str(k): round(v, 4)
                               for k, v in par['p_reliever_by_rank'].items()},
        'n_reliever_by_rank': {str(k): v
                               for k, v in par['n_reliever_by_rank'].items()},
        'cells': {str(k): {'n': par['n_start'][k], 'k': par['k_start'][k],
                           'p_raw': round(par['p_start_raw'][k], 4),
                           'p_jeffreys': round(par['p_start'][k], 4)}
                  for k in sorted(par['p_start'], key=str)},
    }
    print(json.dumps(res, indent=1))
    out = _REPO / 'nfl' / 'research' / 'v2' / 'r1' / 'R1_COHORT_ACCEPTANCE.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1) + '\n')
    print('WROTE', out)


if __name__ == '__main__':
    main()
