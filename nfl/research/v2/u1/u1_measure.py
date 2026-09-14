"""Measure the rush-accounting identity on a sealed board, independently of
the product gate.

    python3.12 nfl/research/v2/u1/u1_measure.py <run_dir> [<run_dir> ...]

Row identity comes from `player_draws_manifest.json` `layers[<layer>]['row_ids']`
in every case; nothing is positional. `team_volume` and `rush_category` are on
`row_axis: 'team'`, `qb`/`rushing` on `row_axis: 'gsis_id'`, and the gsis -> team
map is read from the board's own player rows.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

TOL = 0.5                      # RUSH_OVERALLOCATION_TOLERANCE, quality_gates


def load(run_dir):
    d = pathlib.Path(run_dir)
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    z = np.load(d / 'player_draws.npz')
    board = json.loads((d / 'board.json').read_text())
    return man, z, board


def rows(man, layer):
    return {g: i for i, g in enumerate(man['layers'][layer]['row_ids'])}


def report(run_dir):
    man, z, board = load(run_dir)
    team_of = {p['gsis_id']: p['team'] for p in board['players']}
    qr, tr = rows(man, 'qb'), rows(man, 'team_volume')
    rr = rows(man, 'rushing') if 'rushing' in man['layers'] else {}
    cr = rows(man, 'rush_category') if 'rush_category' in man['layers'] else {}
    pr = (rows(man, 'rush_player_pool')
          if 'rush_player_pool' in man['layers'] else {})
    cat = {k: z['rush_category__' + k].astype(float)
           for k in man['layers']['rush_category']['metrics']} if cr else {}
    tc = z['team_volume__team_carries'].astype(float)
    ro = z['qb__rush_opp'].astype(float)
    scr = z['qb__scr'].astype(float)
    car = z['rushing__carries'].astype(float) if rr else None
    rtd = z['rushing__rushing_td'].astype(float) if rr else None
    pool = (z['rush_player_pool__unmodelled_back_pool'].astype(float)
            if pr else None)
    print(f'\n=== {run_dir}')
    print(f'    run_id {man["run_id"]}  draws {man["n_draws"]}')
    if rr and car is not None:
        print(f'    rushing/carries dtype {z["rushing__carries"].dtype}  '
              f'non-integer cells '
              f'{int((np.abs(car - np.rint(car)) > 0).sum())}')
        print(f'    rushing_td <= carries in every cell: '
              f'{bool(np.all(rtd <= car))}')
    for team in sorted(board['teams']):
        lev = tc[tr[team]]
        qi = sorted(i for g, i in qr.items() if team_of.get(g) == team)
        ri = sorted(i for g, i in rr.items() if team_of.get(g) == team)
        RO = ro[qi].sum(0) if qi else np.zeros_like(lev)
        SC = scr[qi].sum(0) if qi else np.zeros_like(lev)
        RB = car[ri].sum(0) if ri else np.zeros_like(lev)
        owners = RB + RO                    # == RB + SC + (RO - SC)
        over = owners - lev
        n_over = int((over > TOL).sum())
        print(f'  -- {team}: qb rows {len(qi)}, named backs {len(ri)}')
        print(f'     team_carries mean {lev.mean():9.4f}   '
              f'integer? {bool(np.all(lev == np.rint(lev)))}')
        print(f'     named backs  mean {RB.mean():9.4f}   '
              f'qb rush_opp mean {RO.mean():7.4f}  (scr {SC.mean():.4f})')
        print(f'     owners       mean {owners.mean():9.4f}')
        print(f'     OVER-ALLOCATED DRAWS (> {TOL}): {n_over:4d} / '
              f'{lev.size}   max excess {over.max():+8.4f}   '
              f'mean excess {over.mean():+8.4f}')
        print(f'     negative designed rush draws: '
              f'{int(((RO - SC) < -1e-9).sum())}')
        if cr and team in cr:
            t = cr[team]
            catsum = sum(cat[k][t] for k in cat)
            a1q = SC + cat['designed_qb'][t]
            dis = int((np.abs(RO - a1q) > 1e-9).sum())
            print('     categories ' + '  '.join(
                f'{k}={cat[k][t].mean():.4f}' for k in sorted(cat)))
            print(f'     unowned_after = tc - scr - sum(cat): mean '
                  f'{(lev - SC - catsum).mean():+.6f}  '
                  f'max |.| {np.abs(lev - SC - catsum).max():.6f}')
            print(f'     A1 answer for qb rush opp mean {a1q.mean():.4f} vs '
                  f'QB layer {RO.mean():.4f} -- disagreeing cells {dis}')
            if ri and pool is not None and team in pr:
                resid = cat['rb'][t] - (RB + pool[pr[team]])
                print(f'     rb category == named backs + unmodelled pool: '
                      f'{bool(np.all(np.abs(resid) < 1e-9))}')


if __name__ == '__main__':
    for a in sys.argv[1:]:
        report(a)
