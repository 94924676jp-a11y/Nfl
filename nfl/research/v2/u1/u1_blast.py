"""Blast radius: every rush quantity a board publishes, two runs side by side.

    python3.12 nfl/research/v2/u1/u1_blast.py <before_run_dir> <after_run_dir>

Row identity is by `row_ids` from the manifest in both runs; a player present
in one and not the other is NAMED rather than dropped from the comparison.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np


def load(d):
    d = pathlib.Path(d)
    man = json.loads((d / 'player_draws_manifest.json').read_text())
    z = np.load(d / 'player_draws.npz')
    b = json.loads((d / 'board.json').read_text())
    return man, z, b


def grab(d):
    man, z, b = load(d)
    team_of = {p['gsis_id']: p['team'] for p in b['players']}
    pos_of = {p['gsis_id']: p.get('position') for p in b['players']}
    R = lambda l: {g: i for i, g in enumerate(man['layers'][l]['row_ids'])}
    qr, tr, cr, rr = R('qb'), R('team_volume'), R('rush_category'), R('rushing')
    out = {'run_id': man['run_id'], 'team_of': team_of, 'pos_of': pos_of,
           'teams': sorted(b['teams']), 'player_carries': {}, 'team': {},
           'qb_rush': {}, 'cat': {}}
    car = z['rushing__carries'].astype(float)
    rtd = z['rushing__rushing_td'].astype(float)
    out['td_within_carries'] = bool(np.all(rtd <= car))
    out['carries_non_integer'] = int((np.abs(car - np.rint(car)) > 0).sum())
    for g, i in rr.items():
        out['player_carries'][g] = (float(car[i].mean()), float(car[i].std()),
                                    float(rtd[i].mean()))
    tc = z['team_volume__team_carries'].astype(float)
    ro = z['qb__rush_opp'].astype(float)
    scr = z['qb__scr'].astype(float)
    cat = {k: z['rush_category__' + k].astype(float)
           for k in man['layers']['rush_category']['metrics']}
    for t in out['teams']:
        qi = sorted(i for g, i in qr.items() if team_of.get(g) == t)
        ri = sorted(i for g, i in rr.items() if team_of.get(g) == t)
        lev = tc[tr[t]]
        RB = car[ri].sum(0) if ri else np.zeros_like(lev)
        RO = ro[qi].sum(0)
        over = RB + RO - lev
        out['team'][t] = {
            'team_carries_mean': float(lev.mean()),
            'named_backs_mean': float(RB.mean()),
            'n_named_backs': len(ri),
            'qb_rush_opp_mean': float(RO.mean()),
            'scr_mean': float(scr[qi].sum(0).mean()),
            'owners_mean': float((RB + RO).mean()),
            'draws_over': int((over > 0.5).sum()),
            'max_excess': float(over.max()),
            'draws_over_zero_tol': int((over > 0).sum())}
        out['cat'][t] = {k: float(cat[k][cr[t]].mean()) for k in sorted(cat)}
    return out


def main(a, b):
    A, B = grab(a), grab(b)
    print(f'BEFORE {A["run_id"]}   AFTER {B["run_id"]}')
    print(f'rushing_td <= carries in every cell: before {A["td_within_carries"]}'
          f'  after {B["td_within_carries"]}')
    print(f'non-integer carry cells: before {A["carries_non_integer"]}  '
          f'after {B["carries_non_integer"]}')
    for t in sorted(set(A['teams']) | set(B['teams'])):
        ta, tb = A['team'].get(t, {}), B['team'].get(t, {})
        print(f'\n-- {t}')
        for k in ('team_carries_mean', 'n_named_backs', 'named_backs_mean',
                  'scr_mean', 'qb_rush_opp_mean', 'owners_mean',
                  'draws_over', 'max_excess', 'draws_over_zero_tol'):
            va, vb = ta.get(k), tb.get(k)
            d = (f'{vb - va:+.4f}' if isinstance(va, (int, float))
                 and isinstance(vb, (int, float)) else '')
            print(f'   {k:22s} {va!s:>12} -> {vb!s:>12}   {d}')
        print('   categories:')
        for c in sorted(set(A['cat'].get(t, {})) | set(B['cat'].get(t, {}))):
            va = A['cat'].get(t, {}).get(c)
            vb = B['cat'].get(t, {}).get(c)
            print(f'     {c:12s} {va!s:>9} -> {vb!s:>9}   '
                  f'{(vb - va):+.4f}' if va is not None and vb is not None
                  else f'     {c:12s} {va} -> {vb}')
    print('\n-- per named back (mean carries, sd, mean rushing_td)')
    for g in sorted(set(A['player_carries']) | set(B['player_carries'])):
        va = A['player_carries'].get(g)
        vb = B['player_carries'].get(g)
        tm = A['team_of'].get(g) or B['team_of'].get(g)
        ps = A['pos_of'].get(g) or B['pos_of'].get(g)
        f = lambda v: ('ABSENT' if v is None
                       else f'{v[0]:7.4f} sd {v[1]:6.4f} td {v[2]:6.4f}')
        print(f'   {tm} {ps} {g}: {f(va)}  ->  {f(vb)}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
