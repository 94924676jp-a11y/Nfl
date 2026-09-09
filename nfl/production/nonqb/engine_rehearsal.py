"""K + H: the whole non-QB engine on the REAL slate, with only the feed stubbed.

WHAT IS REAL HERE AND WHAT IS NOT

Real: the 2026 week-1 slate and its captured schedule, the captured roster, the
frozen team-volume fit, the frozen P3 appearance mechanism, the accepted
ewma_hl2 participation prior, the accepted P4C system-C parameters fitted on
seasons before 2026, the RC1 conversion baseline with its own shrinkage and
per-catch yardage pools, and the TD2 pooled positional control.

NOT real, and the ONLY thing that is not: the 2026 injuries rows. The feed is
published but covers 2 of 32 teams, so a TEST-ONLY stand-in is supplied in its
place -- and it enters through exactly the same argument the captured feed
would, so this run is evidence about the code the real run will execute.

CONSEQUENCE, AND IT IS THE POINT: `assert_publishable` refuses this run, no
artifact is written, and it cannot satisfy G0A or become prospective evidence.
The stand-in is marked at its origin and the mark propagates.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
for _q in (_ROOT, os.path.join(_ROOT, 'nfl', 'research', 'p4c')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.capture import coverage as C                             # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402
from nfl.production.nonqb import accounting as ACC                # noqa: E402
from nfl.production.nonqb import frozen_priors as FP              # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import p4c_params as P4                 # noqa: E402
from nfl.production.nonqb import participation_prior as PP        # noqa: E402
from nfl.production.rehearsal import run_slate as RS              # noqa: E402

POS = ('WR', 'TE', 'RB')
CLS = 'targets'


def stub_injuries(season, week, players):
    """The TEST-ONLY stand-in for the unpublished feed.

    Every player is entered as a full practice participant with no game-status
    designation. That is deliberately the LEAST informative legitimate row
    shape: it exercises the mechanism without inventing an injury story, and
    it is marked TEST_ONLY at source.
    """
    return [{'season': str(season), 'week': str(week), 'team': q['team'],
             'gsis_id': q['gsis_id'], 'report_status': '',
             'practice_status': 'Full Participation in Practice'}
            for q in players]


def run(season=2026, week=1, m=200, seed=20260908, max_games=None):
    t0 = time.time()
    out = {'artifact': 'NFL_V1_R3_ENGINE_REHEARSAL', 'TEST_ONLY': True,
           'season': season, 'week': week, 'n_draws': m,
           'stubbed_input': f'injuries_{season} ONLY',
           'everything_else': 'real captured inputs and frozen fits',
           'fixture_provenance': 'nfl/production/nonqb/engine_rehearsal.py '
                                 'stub_injuries(): every rostered player '
                                 'entered as a full practice participant with '
                                 'no game-status designation. No real 2026 '
                                 'injury information was used or invented.',
           'publication': 'IMPOSSIBLE -- assert_publishable refuses any run '
                          'carrying TEST_ONLY data',
           'g0a_effect': 'NONE -- a TEST_ONLY run cannot satisfy G0A',
           'games': [], 'layers': {}, 'accounting': {}}

    plan = C.load_week_plan(season, week)
    if plan.state is not State.PASS:
        out['fatal'] = f'{plan.code}: {plan.detail}'
        return out
    games = sorted({c.game_id for c in plan.value})
    if max_games:
        games = games[:max_games]
    _, rrows = RS.roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        if r['gsis_id'] and r['position'] in POS:
            by_team[r['team']].append(
                {'gsis_id': r['gsis_id'], 'position': r['position'],
                 'team': r['team'], 'player_name': r.get('player_name')})
    everyone = [q for t in sorted(by_team) for q in by_team[t]]
    out['n_players_on_slate'] = len(everyone)

    # ---- slate-level frozen fits, computed once -------------------------
    fits = {}
    for name, o in (('p4c_params', P4.params(CLS, season)),
                    ('class_point_forecast',
                     P4.class_point_forecast(CLS, season, week, everyone)),
                    ('participation_prior',
                     PP.share_prior(season, week, everyone)),
                    ('receiving_priors', FP.receiving_priors(season)),
                    ('td_priors', FP.td_priors(season, 'rec'))):
        out['layers'][name] = f'{o.state.value}[{o.code}]'
        if o.state is not State.PASS:
            out['fatal'] = f'{name}: {o.code}: {o.detail[:200]}'
            return out
        fits[name] = o
    out['fit_evidence'] = {
        k: {kk: vv for kk, vv in fits[k].evidence.items() if kk != 'value'}
        for k in fits}

    par = fits['p4c_params'].value
    Cpt = fits['class_point_forecast'].value
    share_prior = fits['participation_prior'].value
    recv = fits['receiving_priors'].value
    tdp = dict(fits['td_priors'].value)
    tdp['pos_catch_rate'] = recv['pos_catch_rate']
    ordinal = season * 100 + week

    states = collections.Counter()
    acc_rows = []
    for gid in games:
        away, home = gid.split('_')[2:4]
        players = [q for t in (away, home) for q in by_team.get(t, [])]
        ids = [q['gsis_id'] for q in players]
        pos = [q['position'] for q in players]
        starts, counts, i = [], [], 0
        for t in (away, home):
            n = len(by_team.get(t, []))
            starts.append(i); counts.append(n); i += n
        g = {'game_id': gid, 'n_players': len(players), 'layers': {}}

        tv = TV.forecast(season, week, [away, home], m=m, seed=seed)
        g['layers']['team_environment'] = f'{tv.state.value}[{tv.code}]'
        ap = LY.appearance(season, week, players, m=m, seed=seed,
                           fixture={'_test_only': True,
                                    'practice_progression': {},
                                    'teammate_availability': {},
                                    'injuries_rows': stub_injuries(
                                        season, week, players)})
        g['layers']['appearance'] = f'{ap.state.value}[{ap.code}]'
        pa = LY.participation(ap, share_prior, m=m)
        g['layers']['participation'] = f'{pa.state.value}[{pa.code}]'
        Cv = [Cpt.get(pid, 0.0) for pid in ids]
        tc = LY.targets_carries(pa, CLS, Cv, pos, (starts, counts), ids, par,
                                m=m, seed=seed)
        g['layers']['targets_carries'] = f'{tc.state.value}[{tc.code}]'
        for k, v in g['layers'].items():
            states[(k, v)] += 1
        if tv.state is not State.PASS or tc.state is not State.PASS:
            g['halted'] = tc.detail[:200] if tc.state is not State.PASS \
                else tv.detail[:200]
            out['games'].append(g)
            continue

        S, other = tc.value['share'], tc.value['other']
        vol = np.stack([tv.value[('team_targets', t)] for t in (away, home)])
        T = S * np.repeat(vol, counts, axis=0)
        cv = LY.receiving_conversion(tc, T, recv, ids, pos, ordinal, m=m,
                                     seed=seed)
        g['layers']['receiving_conversion'] = f'{cv.state.value}[{cv.code}]'
        td = LY.td_layer(cv, T, tdp, ids, pos, ordinal, m=m, seed=seed)
        g['layers']['td_layer'] = f'{td.state.value}[{td.code}]'
        for k in ('receiving_conversion', 'td_layer'):
            states[(k, g['layers'][k])] += 1
        if cv.state is not State.PASS or td.state is not State.PASS:
            g['halted'] = (cv.detail or td.detail)[:200]
            out['games'].append(g)
            continue

        A = np.stack([np.asarray(pa.value[pid], np.float32).reshape(-1)
                      for pid in ids])
        rec = ACC.reconcile_nonqb(
            S, other, vol, T, (A > 0).astype(np.float32), starts, counts,
            receptions=cv.value['receptions'],
            receiving_td=td.value['td'],
            receiving_yards=cv.value['receiving_yards'])
        g['accounting'] = f'{rec.state.value}[{rec.code}]'
        g['accounting_detail'] = rec.detail[:200]
        chain = ACC.reconcile_chain(tv, ap, pa, tc, cv, td)
        g['chain'] = f'{chain.state.value}[{chain.code}]'
        acc_rows.append(rec)
        g['summary'] = {
            'mean_targets': float(T.mean()),
            'mean_receptions': float(cv.value['receptions'].mean()),
            'mean_receiving_yards': float(cv.value['receiving_yards'].mean()),
            'sd_receiving_yards_within_player': float(
                cv.value['receiving_yards'].std(axis=1).mean()),
            'mean_td': float(td.value['td'].mean()),
            'other_mass_mean': float(other.mean()),
            'appearance_mean': float(A.mean())}
        g['publication_gate'] = '{}[{}]'.format(
            *(lambda o: (o.state.value, o.code))(
                LY.assert_publishable(ap, pa, tc, cv, td)))
        out['games'].append(g)

    out['layer_state_distribution'] = {f'{k}: {v}': n
                                       for (k, v), n in sorted(states.items())}
    ok = [r for r in acc_rows if r.state is State.PASS]
    out['accounting'] = {
        'n_games_reconciled': len(ok),
        'n_games_failing': len(acc_rows) - len(ok),
        'worst': {k: max((float(r.evidence.get(k, 0.0)) for r in acc_rows),
                         default=None)
                  for k in ('share_simplex_closure_maxdev',
                            'player_opportunity_within_team_maxreldev')},
        'violations': {k: sum(int(r.evidence.get(k, 0)) for r in acc_rows)
                       for k in ('share_non_negative_violations',
                                 'receptions_within_targets_violations',
                                 'receiving_td_within_receptions_violations',
                                 'zero_receptions_implies_zero_yards_'
                                 'violations',
                                 'allocation_only_when_available_violations')},
        'total_cells_checked': sum(int(r.evidence.get('n_cells_checked', 0))
                                   for r in acc_rows),
        'n_negative_yard_cells': sum(
            int(r.evidence.get('n_negative_yard_cells', 0))
            for r in acc_rows),
        'negative_yards_note': 'reported, never refused: RC1 resamples real '
                               'per-catch gains and a reception for a loss is '
                               'ordinary football',
        'identities': list(ACC.IDENTITY_NAMES)}
    out['all_games_complete'] = (len(ok) == len(games))
    out['n_games'] = len(games)
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=200)
    a = ap.parse_args()
    r = run(m=a.draws, max_games=a.games)
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'engine_rehearsal.json'), 'w'), indent=1,
              default=str)
    print(json.dumps({k: v for k, v in r.items() if k != 'games'}, indent=1,
                     default=str))
    if r.get('games'):
        print('\nfirst game:', json.dumps(r['games'][0], indent=1,
                                          default=str))
    print('\nwrote engine_rehearsal.json')
