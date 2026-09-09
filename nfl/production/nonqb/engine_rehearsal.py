"""K: prove the whole non-QB engine executes once the real source exists.

TEST-ONLY. The appearance input is a marked fixture, so `assert_publishable`
refuses the run and no artifact is written. This is an ENGINEERING proof that
the wiring works end to end -- it is not a forecast and cannot become one.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome             # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402
from nfl.production.nonqb import accounting as ACC                 # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402


def run(season=2026, week=1, teams=('NE', 'SEA'), n_per_team=6, m=100,
        seed=20260908):
    rng = np.random.default_rng([seed, 1])
    players, pos, shares = [], [], []
    for t in teams:
        for i in range(n_per_team):
            p = 'WR' if i < 3 else ('TE' if i < 4 else 'RB')
            pid = f'{t}_{p}_{i}'
            players.append({'gsis_id': pid, 'team': t, 'position': p})
            pos.append(p)
            shares.append(float(np.clip(rng.beta(2, 6), 0.01, 0.9)))
    fixture = {'_test_only': True, 'practice_progression': {},
               'teammate_availability': {},
               'p_appear': {q['gsis_id']: 0.9 for q in players}}
    out = {'TEST_ONLY': True, 'season': season, 'week': week,
           'fixture_provenance': 'synthetic appearance fixture, generated in '
                                 'nfl/production/nonqb/engine_rehearsal.py; '
                                 'no real 2026 appearance data was used',
           'publication': 'IMPOSSIBLE -- assert_publishable refuses any run '
                          'carrying TEST_ONLY data',
           'g0a_effect': 'NONE -- a TEST_ONLY run cannot satisfy G0A',
           'layers': {}, 'accounting': {}}

    tv = TV.forecast(season, week, list(teams), m=m, seed=seed)
    out['layers']['team_environment'] = f'{tv.state.value}[{tv.code}]'
    ap = LY.appearance(season, week, players, fixture=fixture, m=m, seed=seed)
    out['layers']['appearance'] = f'{ap.state.value}[{ap.code}]'
    pa = LY.participation(ap, dict(zip([q['gsis_id'] for q in players],
                                       shares)), m=m)
    out['layers']['participation'] = f'{pa.state.value}[{pa.code}]'

    # groups: one allocation group per team, players contiguous
    ids = [q['gsis_id'] for q in players]
    starts, counts = [], []
    i = 0
    for t in teams:
        n = sum(1 for q in players if q['team'] == t)
        starts.append(i); counts.append(n); i += n
    par = _params('targets')
    tc = LY.targets_carries(pa, 'targets', shares, pos, (starts, counts), ids,
                            par, m=m, seed=seed)
    out['layers']['targets_carries'] = f'{tc.state.value}[{tc.code}]'
    if tc.state.name != 'PASS':
        out['accounting']['fatal'] = tc.detail[:200]
        return out

    S, other = tc.value['share'], tc.value['other']
    tgt_vol = np.stack([tv.value[('team_targets', t)] for t in teams])
    team_tgt = np.repeat(tgt_vol, counts, axis=0)
    T = S * team_tgt
    cv = LY.receiving_conversion(tc, T, {'catch_rate': 0.62,
                                         'yards_per_reception': 11.0}, m=m,
                                 seed=seed)
    out['layers']['receiving_conversion'] = f'{cv.state.value}[{cv.code}]'
    td = LY.td_layer(cv, cv.value['receptions'],
                     {'td_per_opportunity': 0.05}, m=m, seed=seed)
    out['layers']['td_layer'] = f'{td.state.value}[{td.code}]'

    R = cv.value['receptions']
    # ACCOUNTING IS A MODULE, NOT A PRINTOUT. These identities are checked in
    # every cell by nonqb.accounting and FAIL rather than being reported as a
    # deviation the reader is expected to notice.
    A_draws = np.stack([np.asarray(pa.value[pid], np.float32).reshape(-1)
                        for pid in ids])
    chain = ACC.reconcile_chain(tv, ap, pa, tc, cv, td)
    out['chain_executed'] = f'{chain.state.value}[{chain.code}]'
    rec = ACC.reconcile_nonqb(
        S, other, tgt_vol, T, (A_draws > 0).astype(np.float32),
        starts, counts, receptions=R, receiving_td=td.value['td'],
        receiving_yards=cv.value['receiving_yards'])
    out['accounting'] = {'state': f'{rec.state.value}[{rec.code}]',
                         **{k: v for k, v in rec.evidence.items()
                            if k != 'value'}}
    out['accounting_detail'] = rec.detail[:300]
    g = LY.assert_publishable(ap, pa, tc, cv, td)
    out['publication_gate'] = f'{g.state.value}[{g.code}]'
    out['all_layers_executed'] = all(
        v.startswith('PASS') for v in out['layers'].values())
    return out


def _params(cls):
    """Frozen P4C parameters, read from the research output."""
    import numpy as _np
    r = json.load(open(os.path.join(_ROOT, 'nfl', 'research', 'p4c',
                                    'p4c_results.json')))[cls]
    ev = max(int(k) for k in r)
    p = r[str(ev)]['params']
    sd = float(_np.mean(list(p['sigma_lr'].values())))
    rng = _np.random.default_rng(20260908)
    return {'add_pool': {k: rng.normal(0, sd * 0.05, 400).astype(_np.float32)
                         for k in ('WR', 'TE', 'RB')},
            'mass_pool': _np.full(200, p['mass_mean'], _np.float32),
            'mass_mean': p['mass_mean'],
            '_source': f'p4c_results.json {cls} {ev}',
            '_note': 'add_pool and mass_pool are reconstructed from the '
                     'frozen summary statistics for this TEST_ONLY rehearsal; '
                     'the real run refits them from the panel'}


if __name__ == '__main__':
    print(json.dumps(run(), indent=1, default=str))
