"""R1: tonight's DEN@KC quarterback rooms under qb_room_v2, against V1.

TEAM VOLUME IS HELD FIXED AT V1's OWN DRAWS. The team-dropback vectors are read
straight out of the sealed board's `player_draws.npz`
(`team_volume/team_dropbacks_part`, row axis DEN, KC), so the only thing that
differs between the two columns of every table below is the allocator. A
rebuilt volume model would have changed two things at once.

    python3.12 nfl/research/v2/r1/r1_tonight.py
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb import qb_room_v2 as V2          # noqa: E402
from nfl.production.nonqb import qb_allocation as QA       # noqa: E402

SEALED = (_REPO / 'nfl' / 'research' / 'live' / '2026_01_DEN_KC'
          / 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8' / 'f91342d6787a66a1')
SEED = 20260908
ORDINAL = 202601
SEASON, WEEK = 2026, 1
V1_QB_ROWS = ['00-0035264', '00-0036879', '00-0039732',
              '00-0033873', '00-0036945', '00-0040906']
NAMES = {'00-0033873': 'Patrick Mahomes', '00-0036945': 'Justin Fields',
         '00-0040906': 'KC QB3', '00-0039732': 'Bo Nix',
         '00-0035264': 'Jarrett Stidham', '00-0036879': 'Sam Ehlinger'}


def sealed():
    z = np.load(SEALED / 'player_draws.npz', allow_pickle=True)
    tv = z['team_volume__team_dropbacks_part']
    idx = {p: i for i, p in enumerate(V1_QB_ROWS)}
    v1 = {}
    for p, i in idx.items():
        db = z['qb__db'][i].astype(float)
        v1[p] = {
            'p_zero_dropbacks': float((db == 0).mean()),
            'dropbacks': float(db.mean()),
            'attempts': float(z['qb__att'][i].mean()),
            'completions': float(z['qb__cmp'][i].mean()),
            'pass_yards': float(z['qb__pyds'][i].mean()),
            'sacks': float(z['qb__sacks'][i].mean()),
            'scrambles': float(z['qb__scr'][i].mean()),
            'q_db': [int(np.quantile(db, q)) for q in (0.1, 0.5, 0.9)],
            'q_att': [int(np.quantile(z['qb__att'][i], q))
                      for q in (0.1, 0.5, 0.9)],
            'q_cmp': [int(np.quantile(z['qb__cmp'][i], q))
                      for q in (0.1, 0.5, 0.9)],
            'q_pyds': [float(np.quantile(z['qb__pyds'][i], q))
                       for q in (0.1, 0.5, 0.9)],
            'conditional_pass_yards': (float(z['qb__pyds'][i][db > 0].mean())
                                       if (db > 0).any() else None),
        }
    return {'DEN': tv[0].astype(float), 'KC': tv[1].astype(float)}, v1


def main():
    tdb, v1 = sealed()
    m = len(tdb['KC'])

    tg = V2.load_pbp((2021, 2022, 2023, 2024, 2025))
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
    par = V2.fit(frame, tg, ORDINAL, use_opener=True, prior='jeffreys')

    dc = QA.captured_depth_chart()
    if dc.state.value != 'PASS':
        raise SystemExit(f'DEPTH_CHART_REFUSED: {dc.code} {dc.detail}')
    prev = QA.previous_primary_detail(SEASON, WEEK)

    inact_path = (_REPO / 'nfl' / 'research' / 'live' / '2026_01_DEN_KC'
                  / 'INACTIVES_INGESTION.json')
    inactives_state = ('NO_INACTIVES_INGESTION -- the official list is not '
                       'published at the time this ran, so every rostered '
                       'quarterback is treated as eligible and no emergency '
                       'third-QB designation is available to consume.')
    if inact_path.exists():
        inactives_state = 'INACTIVES_INGESTION present -- see the artifact.'

    out = {'spec_version': V2.SPEC_VERSION, 'game_id': '2026_01_DEN_KC',
           'n_draws': m, 'seed': SEED, 'ordinal': ORDINAL,
           'team_volume_source': ('sealed V1 draws, '
                                  'team_volume/team_dropbacks_part -- held '
                                  'fixed so the allocator is the only '
                                  'treatment'),
           'inactives': inactives_state,
           'prior': par['prior'],
           'trained_on_ordinals_before': par['trained_on_ordinals_before'],
           'p_exit': round(par['p_exit'], 4),
           'teams': {}}

    for team in ('KC', 'DEN'):
        room_ranks = dc.value[team]
        d = prev.get(team) or {}
        room = [{'pid': p, 'rank': V2.rank_bucket(r),
                 'was_prev_primary': int(d.get('pid') == p)}
                for p, r in sorted(room_ranks.items(), key=lambda x: x[1])]
        o = V2.room_forecast(par, room, tdb[team], seed=SEED, ordinal=ORDINAL,
                             team=team, is_opener=bool(d.get('is_season_opener')))
        if o.state.value != 'PASS':
            raise SystemExit(f'{team}: {o.code} {o.detail}')
        rows = []
        for r in o.value['rows']:
            p = r['pid']
            n_donor = len(par['donors'].get(p) or [])
            rows.append({
                'pid': p, 'name': NAMES.get(p, p), 'rank': r['rank'],
                'was_prev_primary': r['was_prev_primary'],
                'n_prior_games_with_a_dropback': n_donor,
                'league_donor_fallback': n_donor == 0,
                'V2': {k: (round(v, 4) if isinstance(v, float) else v)
                       for k, v in r.items()
                       if k not in ('pid', 'rank', 'was_prev_primary',
                                    'emergency')},
                'V1_sealed': {k: (round(v, 4) if isinstance(v, float) else v)
                              for k, v in v1[p].items()},
            })
        out['teams'][team] = {
            'configuration': QA.qb3_configuration(
                [(x['pid'], x['rank'], x['was_prev_primary']) for x in room],
                d),
            'is_season_opener': bool(d.get('is_season_opener')),
            'prev_primary_pid': d.get('pid'),
            'prev_primary_ordinal': d.get('ordinal'),
            'team_dropbacks_mean': round(float(tdb[team].mean()), 4),
            'team_dropbacks_int_mean': round(
                float(np.rint(tdb[team]).mean()), 4),
            'p_any_exit': round(float(o.value['allocation']['exited'].mean()),
                                4),
            'rows': rows,
        }
        # closure, restated on the artifact
        DB = o.value['allocation']['db']
        out['teams'][team]['closure_max_integer_deviation'] = int(
            np.abs(DB.sum(0) - o.value['allocation']['team_dropbacks_int']
                   ).max())
        out['teams'][team]['qb_sum_dropbacks_mean'] = round(
            float(DB.sum(0).mean()), 4)
        out['teams'][team]['_v2_db'] = DB

    # THE ROOM-LEVEL SYMPTOMS, on tonight's two rooms, V1 sealed against V2.
    z = np.load(SEALED / 'player_draws.npz', allow_pickle=True)
    v1db = z['qb__db'].astype(float)
    idx = {p_: i for i, p_ in enumerate(V1_QB_ROWS)}
    for team in ('KC', 'DEN'):
        rows = out['teams'][team]['rows']
        pids = [r['pid'] for r in rows]
        A = np.stack([v1db[idx[p_]] for p_ in pids])
        tot = A.sum(0)
        with np.errstate(invalid='ignore', divide='ignore'):
            t1 = np.where(tot > 0, A.max(0) / np.maximum(tot, 1), np.nan)
        qb1 = pids[0]
        s1 = np.where(tot > 0, A[0] / np.maximum(tot, 1), np.nan)
        B = out['teams'][team].pop('_v2_db')
        totb = B.sum(0)
        with np.errstate(invalid='ignore', divide='ignore'):
            t2 = np.where(totb > 0, B.max(0) / np.maximum(totb, 1), np.nan)
            s2 = np.where(totb > 0, B[0] / np.maximum(totb, 1), np.nan)
        out['teams'][team]['room_symptoms'] = {
            'chart_qb1': qb1,
            'top_passer_share': {'V1': round(float(np.nanmean(t1)), 4),
                                 'V2': round(float(np.nanmean(t2)), 4)},
            'chart_qb1_share': {'V1': round(float(np.nanmean(s1)), 4),
                                'V2': round(float(np.nanmean(s2)), 4)},
            'frac_draws_two_qb_at_5plus_dropbacks': {
                'V1': round(float(((A >= 5).sum(0) >= 2).mean()), 4),
                'V2': round(float(((B >= 5).sum(0) >= 2).mean()), 4)},
        }

    p = _REPO / 'nfl' / 'research' / 'v2' / 'r1' / 'R1_TONIGHT_DEN_KC.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    print('WROTE', p)


if __name__ == '__main__':
    main()
