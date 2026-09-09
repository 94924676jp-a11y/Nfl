"""K/L: the complete football engine, run two ways.

    --mode test_only   the whole slate with a marked injury stand-in
    --mode real        the whole slate on nothing but captured inputs

The two share one engine (`football_engine.py`). A rehearsal that reimplemented
the chain would be testing itself.

TEST-ONLY runs are structurally unpublishable: the stand-in is marked at source,
the mark propagates through every layer, `assert_publishable` refuses, no
artifact is written, and the run cannot satisfy G0A or become prospective
evidence.
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
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.capture import coverage as C                              # noqa: E402
from nfl.production import authorization as AUTH                   # noqa: E402
from nfl.production.nonqb import football_engine as FE             # noqa: E402
from nfl.production.nonqb import readiness as RD                   # noqa: E402
from nfl.production.rehearsal import run_slate as RS               # noqa: E402

POS = FE.RECEIVING_POS


def stub_injuries(season, week, players):
    """The TEST-ONLY stand-in for the unfiled reports.

    Every player is a full practice participant with no game-status
    designation: the least informative legitimate row shape. It exercises the
    mechanism without inventing an injury story, and it is marked at source.
    """
    return [{'season': str(season), 'week': str(week), 'team': q['team'],
             'gsis_id': q['gsis_id'], 'report_status': '',
             'practice_status': 'Full Participation in Practice'}
            for q in players]


def run(season=2026, week=1, m=200, seed=20260908, mode='test_only',
        max_games=None):
    t0 = time.time()
    test_only = (mode == 'test_only')
    out = {'artifact': ('NFL_V1_R4_ENGINE_REHEARSAL' if test_only
                        else 'NFL_V1_R4_REAL_SLATE'),
           'mode': mode, 'TEST_ONLY': test_only,
           'engine_version': FE.ENGINE_VERSION,
           'season': season, 'week': week, 'n_draws': m,
           'games': [], 'layers': {}}
    if test_only:
        out.update(
            stubbed_input='injuries_%d ONLY' % season,
            everything_else='real captured inputs and frozen fits',
            fixture_provenance='engine_rehearsal.stub_injuries(): every '
                               'rostered player entered as a full practice '
                               'participant with no game-status designation. '
                               'No real 2026 injury information was used or '
                               'invented.',
            publication='IMPOSSIBLE -- assert_publishable refuses any run '
                        'carrying TEST_ONLY data',
            g0a_effect='NONE -- a TEST_ONLY run cannot satisfy G0A',
            prospective_validation='NONE -- this is not prospective evidence')
    else:
        out.update(stubbed_input='NONE',
                   fixtures_used='NONE -- every layer called with fixture=None')

    plan = C.load_week_plan(season, week)
    if plan.state is not State.PASS:
        out['fatal'] = f'{plan.code}: {plan.detail}'
        return out
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    games = sorted(ko)[:max_games] if max_games else sorted(ko)

    _, rrows = RS.roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        if r['gsis_id'] and r['position'] in POS:
            by_team[r['team']].append(
                {'gsis_id': r['gsis_id'], 'position': r['position'],
                 'team': r['team'], 'player_name': r.get('player_name')})
    everyone = [q for t in sorted(by_team) for q in by_team[t]]
    out['n_players_on_slate'] = len(everyone)
    out['position_counts'] = dict(collections.Counter(
        q['position'] for q in everyone))

    fits = FE.slate_fits(season, week, everyone)
    out['layers']['slate_fits'] = f'{fits.state.value}[{fits.code}]'
    if fits.state is not State.PASS:
        out['fatal'] = fits.detail[:300]
        out['fit_states'] = fits.evidence.get('states')
        return out
    out['fit_states'] = fits.evidence['states']
    out['fit_evidence'] = fits.evidence['evidence_by_fit']

    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    out['n_qb_on_slate'] = len(qbp)
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    out['layers']['qb_layer'] = f'{qo.state.value}[{qo.code}]'
    qb = qo.value if qo.state is State.PASS else None
    if qb is None:
        out['qb_layer_detail'] = qo.detail[:250]

    gr = RD.game_readiness(season, week)
    out['game_readiness'] = {g['game_id']: g['state'] for g in gr['games']}
    out['n_games_ready'] = gr['n_executable']

    states, accs, recs = collections.Counter(), [], []
    for gid in games:
        players = [q for t in gid.split('_')[2:4] for q in by_team.get(t, [])]
        inj = stub_injuries(season, week, players) if test_only else None
        k = ko[gid]
        g, payload = FE.run_game(
            season, week, gid, players, fits.value, m=m, seed=seed,
            injuries_rows=inj, test_only=test_only,
            kickoff_utc=(k.isoformat().replace('+00:00', 'Z')
                         if hasattr(k, 'isoformat') else k),
            run_id=out['artifact'], qb=qb)
        for kk, v in g['layers'].items():
            states[(kk, v)] += 1
        if payload:
            accs.append(payload['accounting'])
            recs.extend(payload['records'])
            g['summary'] = _summary(payload['draws'])
        out['games'].append(g)

    out['layer_state_distribution'] = {f'{k}: {v}': n
                                       for (k, v), n in sorted(states.items())}
    out['n_games'] = len(games)
    out['n_player_records'] = len(recs)
    out['coverage'] = _coverage(recs)
    out['accounting'] = _accounting(accs)
    pub = AUTH.may_publish()
    out['publication'] = f'{pub.state.value}[{pub.code}]'
    out['gates'] = json.loads(
        (RD.EL.STATE).read_text())['gates']
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def _summary(d):
    return {k: {'mean': float(np.asarray(v).mean()),
                'sd_within_player': float(np.asarray(v).std(axis=1).mean())}
            for k, v in d.items()}


def _coverage(records):
    by_pos = collections.Counter(r['position'] for r in records)
    present = collections.defaultdict(collections.Counter)
    absent = collections.defaultdict(collections.Counter)
    for r in records:
        for k, v in r['metrics'].items():
            (present if v['status'] == 'PRESENT' else absent)[
                r['position']][k] += 1
    return {'n_records': len(records), 'by_position': dict(by_pos),
            'metrics_present': {p: dict(c) for p, c in present.items()},
            'metrics_absent': {p: dict(c) for p, c in absent.items()}}


def _accounting(accs):
    if not accs:
        return {'n_games': 0,
                'note': 'no game produced draws, so nothing was reconciled. '
                        'This is NOT a passing accounting result.'}
    rec = [a for a, _ in accs]
    rush = [b for _, b in accs]
    def agg(rows, keys):
        return {k: sum(int(r.evidence.get(k, 0) or 0) for r in rows)
                for k in keys}
    return {
        'n_games': len(accs),
        'receiving_ok': sum(1 for r in rec if r.state is State.PASS),
        'rushing_ok': sum(1 for r in rush if r.state is State.PASS),
        'total_cells_checked': sum(int(r.evidence.get('n_cells_checked', 0))
                                   for r in rec + rush),
        'violations': {
            **agg(rec, ('share_non_negative_violations',
                        'receptions_within_targets_violations',
                        'receiving_td_within_receptions_violations',
                        'zero_receptions_implies_zero_yards_violations',
                        'allocation_only_when_available_violations')),
            **agg(rush, ('rushing_td_within_carries_violations',
                         'n_td_without_a_carry'))},
        'worst': {
            'share_simplex_closure_maxdev': max(
                float(r.evidence.get('share_simplex_closure_maxdev', 0))
                for r in rec),
            'player_opportunity_within_team_maxreldev': max(
                float(r.evidence.get(
                    'player_opportunity_within_team_maxreldev', 0))
                for r in rec),
            'team_carry_closure_maxdev': max(
                float(r.evidence.get('team_carry_closure_maxdev', 0))
                for r in rush)},
        'n_negative_receiving_yard_cells': sum(
            int(r.evidence.get('n_negative_yard_cells', 0)) for r in rec),
        'rushing_yards_status': 'NOT_APPLICABLE -- no governed control',
    }


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='test_only',
                    choices=('test_only', 'real'))
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=200)
    a = ap.parse_args()
    r = run(mode=a.mode, m=a.draws, max_games=a.games)
    name = ('engine_rehearsal.json' if a.mode == 'test_only'
            else 'slate_rehearsal.json')
    json.dump(r, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   name), 'w'), indent=1, default=str)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ('games', 'fit_evidence')},
                     indent=1, default=str))
    if r.get('games'):
        print('\nfirst game:', json.dumps(r['games'][0], indent=1,
                                          default=str)[:2500])
    print(f'\nwrote {name}')
