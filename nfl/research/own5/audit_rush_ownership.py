"""OWN-5 Part B: who owns a team's carries, and where the rushing gate fails.

    INTEL1_PBP_GLOB='.../pbp20*.csv.gz' \
        python3.12 nfl/research/own5/audit_rush_ownership.py

Ownership and accounting first. No rushing model is searched and the historical
0.157/0.1568 is DIAGNOSTIC EVIDENCE, never a fitting target.
"""
from __future__ import annotations

import collections
import csv
import glob
import gzip
import json
import os
import statistics
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

csv.field_size_limit(10 ** 7)
HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(_ROOT, 'nfl', 'research', 'inputs')


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def historical_from_pbp(files):
    """Team carries decomposed by who took them. Closure must be exact."""
    passers = collections.defaultdict(set)
    rows = []
    for path in files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG' or _i(r.get('two_point_attempt')):
                    continue
                po = r.get('posteam') or ''
                if not po:
                    continue
                k = (_i(r.get('season')), _i(r.get('week')), po)
                if _i(r.get('qb_dropback')) and (r.get('passer_player_id') or ''):
                    passers[k].add(r['passer_player_id'])
                rows.append((k, r))
    tg = collections.defaultdict(collections.Counter)
    for k, r in rows:
        if not _i(r.get('rush_attempt')):
            continue
        c = tg[k]
        c['team_rush_attempts'] += 1
        rid = r.get('rusher_player_id') or ''
        sc, kn = _i(r.get('qb_scramble')), _i(r.get('qb_kneel'))
        is_qb = sc or kn or (rid and rid in passers[k])
        c['kneels'] += bool(kn)
        c['scrambles'] += bool(sc)
        if is_qb:
            c['qb_rushes'] += 1
            if not sc and not kn:
                c['qb_designed'] += 1
        else:
            c['nonqb_rushes'] += 1
    ks = list(tg)
    M = lambda key: round(statistics.mean(tg[x][key] for x in ks), 4)
    res = [tg[x]['team_rush_attempts'] - tg[x]['qb_rushes']
           - tg[x]['nonqb_rushes'] for x in ks]
    tc = M('team_rush_attempts')
    return {'n_team_games': len(ks),
            'means': {k: M(k) for k in
                      ('team_rush_attempts', 'qb_rushes', 'scrambles',
                       'kneels', 'qb_designed', 'nonqb_rushes')},
            'closure_team_eq_qb_plus_nonqb': {
                'exact': sum(1 for v in res if v == 0), 'n': len(ks),
                'max_abs': max(abs(v) for v in res)},
            'qb_share_of_team_carries': round(M('qb_rushes') / tc, 4),
            'qb_share_excluding_kneels': round(
                (M('qb_rushes') - M('kneels')) / tc, 4)}


def historical_from_panel():
    """The same decomposition through the panel the model actually fits on."""
    tg = collections.defaultdict(collections.Counter)
    with gzip.open(os.path.join(INPUTS, 'panel_p3.csv.gz'), 'rt') as fh:
        for r in csv.DictReader(fh):
            k = (r['season'], r['week'], r['team'])
            try:
                car = float(r.get('carries') or 0)
            except ValueError:
                car = 0.0
            c = tg[k]
            c['panel_carries'] += car
            c['pos_' + (r.get('position') or '?')] += car
            try:
                c['team_carries'] = max(c['team_carries'],
                                        float(r.get('team_rush_att') or 0))
            except ValueError:
                pass
    ks = [k for k in tg if tg[k]['team_carries'] > 0]
    M = lambda key: statistics.mean(tg[x][key] for x in ks)
    tc = M('team_carries')
    out = {'n_team_games': len(ks), 'team_carries': round(tc, 4),
           'shares': {}, 'unattributed_share':
               round((tc - M('panel_carries')) / tc, 6)}
    for p in ('RB', 'QB', 'WR', 'TE'):
        out['shares'][p] = round(M('pos_' + p) / tc, 4)
    out['shares']['non_RB_mass'] = round(1.0 - out['shares']['RB'], 4)
    return out


def fitted_mass():
    """What the P4C `other` mass is fitted as, and on what scale."""
    from sportsplatform.governance.outcome import State
    from nfl.production.nonqb import football_engine as FE
    from nfl.production.rehearsal import run_slate as RS
    _, rrows = RS.roster(2026, 1)
    ev = [{'gsis_id': r['gsis_id'], 'position': r['position'],
           'team': r['team'], 'player_name': r.get('player_name')}
          for r in rrows if r['gsis_id'] and r['position'] in FE.RECEIVING_POS]
    f = FE.slate_fits(2026, 1, ev)
    if f.state is not State.PASS:
        return {'status': f'{f.state.value}[{f.code}]'}
    out = {}
    for name in ('carries', 'targets'):
        par = f.value[f'p4c_params_{name}'].value
        pool = np.asarray(par['mass_pool'], float)
        out[name] = {'mass_mean': round(float(par['mass_mean']), 6),
                     'pool_n': int(pool.size),
                     'pool_p50': round(float(np.percentile(pool, 50)), 6)}
    out['construction'] = (
        "p4c_build: pool = mall[k] - ms[k], where mall is the sum of ALL "
        "players' realised shares for that team-game and ms the modelled "
        "subset. mall is 1.0 because the panel closes exactly, so the pool is "
        "a SHARE on [0,1] -- not a weight.")
    out['consumption'] = (
        "p4c_lib.allocate(simplex): other = w_other / (sum(W*A) + w_other). "
        "sum(W*A) is on the relative-weight scale and is NOT normalised to 1, "
        "so a fitted share is diluted by whatever sum(W*A) happens to be.")
    return out


def main():
    files = sorted(glob.glob(os.environ.get('INTEL1_PBP_GLOB', '')))
    if not files:
        raise SystemExit('PBP_NOT_LOCATED: set INTEL1_PBP_GLOB. The historical '
                         'decomposition is refused rather than assumed.')
    out = {'artifact': 'OWN5_RUSH_OWNERSHIP_AUDIT',
           'no_model_searched': True,
           'historical_target_is_evidence_not_a_fitting_target': True,
           'historical_pbp': historical_from_pbp(files),
           'historical_panel': historical_from_panel(),
           'fitted_other_mass': fitted_mass()}
    dest = os.path.join(HERE, 'own5_rush_ownership.json')
    with open(dest, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True, default=float)
    print(json.dumps(out, indent=2, sort_keys=True, default=float))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
