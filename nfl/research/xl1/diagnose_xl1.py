"""XL1 diagnosis: the four cross-layer links, measured, with a level check.

The engine generates the shared passing event TWICE. This script measures the
disagreement on all four links and -- the part that had never been done -- asks
WHICH SIDE IS WRONG by comparing each side's level against history.

    python3.12 nfl/research/xl1/diagnose_xl1.py [--games N] [--draws M]

Diagnosis only. No candidate is fitted and no candidate is scored here; that
waits on a committed pre-registration.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.capture import coverage as C                              # noqa: E402
from nfl.production.nonqb import engine_rehearsal as ER            # noqa: E402
from nfl.production.nonqb import football_engine as FE             # noqa: E402
from nfl.production import team_volume_v1 as TV                    # noqa: E402
from nfl.production.rehearsal import run_slate as RS               # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# Historical team-game levels, REG 2020-2025, n = 3,230 team-games. Measured by
# nfl/research/xl1/history_levels.json, which this file refuses to run without.
HIST = os.path.join(HERE, 'history_levels.json')

# The four links. (label, receiving-side key, QB-side key)
LINKS = (('completions', 'receptions', 'cmp'),
         ('passing_yards', 'receiving_yards', 'pyds'),
         ('passing_td', 'receiving_td', 'ptd'))


def _summ(x):
    x = np.asarray(x, float).ravel()
    if not x.size:
        return None
    return {'mean': round(float(x.mean()), 4),
            'sd': round(float(x.std()), 4),
            'p05': round(float(np.percentile(x, 5)), 4),
            'p50': round(float(np.percentile(x, 50)), 4),
            'p95': round(float(np.percentile(x, 95)), 4)}


def collect(season, week, m, seed, max_games, joint_residuals):
    # A3 is selected by the module default, the same switch J1's downstream
    # study used. It is restored in a finally block so an exception here cannot
    # leave the production default flipped.
    prior = TV.JOINT_RESIDUALS_DEFAULT
    TV.JOINT_RESIDUALS_DEFAULT = bool(joint_residuals)
    try:
        return _collect(season, week, m, seed, max_games)
    finally:
        TV.JOINT_RESIDUALS_DEFAULT = prior


def _collect(season, week, m, seed, max_games):
    plan = C.load_week_plan(season, week)
    if plan.state is not State.PASS:
        raise SystemExit(f'week plan {plan.code}: {plan.detail}')
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    games = sorted(ko)[:max_games] if max_games else sorted(ko)

    _, rrows = RS.roster(season, week)
    by_team = collections.defaultdict(list)
    for r in rrows:
        if r['gsis_id'] and r['position'] in ER.POS:
            by_team[r['team']].append({'gsis_id': r['gsis_id'],
                                       'position': r['position'],
                                       'team': r['team'],
                                       'player_name': r.get('player_name')})
    everyone = [q for t in sorted(by_team) for q in by_team[t]]
    fits = FE.slate_fits(season, week, everyone)
    if fits.state is not State.PASS:
        raise SystemExit(f'slate fits {fits.code}: {fits.detail[:200]}')

    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rrows
           if r['gsis_id'] and r['position'] == 'QB']
    qo = FE.qb_slate(season, week, qbp, m=m, seed=seed)
    if qo.state is not State.PASS:
        raise SystemExit(f'qb slate {qo.code}: {qo.detail[:200]}')
    qb = qo.value
    qa = FE.QA.allocate(season, week, sorted({q['team'] for q in qbp}), qbp,
                        m=m, seed=seed)
    if qa.state is not State.PASS:
        raise SystemExit(f'qb allocation {qa.code}: {qa.detail[:200]}')
    qb['allocation'] = qa.value

    rows = []
    for gid in games:
        players = [q for t in gid.split('_')[2:4] for q in by_team.get(t, [])]
        g, payload = FE.run_game(
            season, week, gid, players, fits.value, m=m, seed=seed,
            injuries_rows=ER.stub_injuries(season, week, players),
            test_only=True, kickoff_utc=ko[gid], qb=qb)
        if payload is None:
            rows.append({'game_id': gid, 'halted_at': g.get('halted_at'),
                         'reason': (g.get('halt_reason') or '')[:160]})
            continue
        ix, dr = payload['index'], payload['draws']
        rteam = np.asarray(ix['recv_team'])
        qbi = payload['qb']
        if qbi is None:
            rows.append({'game_id': gid, 'halted_at': 'qb_absent'})
            continue
        qteam = np.asarray(qbi['team'])
        for t in ix['teams']:
            rm, qm = (rteam == t), (qteam == t)
            if not rm.any() or not qm.any():
                continue
            rec = {'game_id': gid, 'team': t}
            for label, rkey, qkey in LINKS:
                lhs = np.asarray(dr[rkey], float)[rm].sum(0)
                rhs = np.asarray(qbi['draws'][qkey], float)[qm].sum(0)
                rec[label] = {'receiving_side': _summ(lhs),
                              'qb_side': _summ(rhs),
                              'mean_abs_diff': round(
                                  float(np.abs(lhs - rhs).mean()), 4),
                              'exact_draws': int((np.abs(lhs - rhs)
                                                  < 1e-9).sum()),
                              'n_draws': int(lhs.size),
                              'corr': (round(float(np.corrcoef(lhs, rhs)[0, 1]), 6)
                                       if lhs.std() > 0 and rhs.std() > 0
                                       else None)}
            # The upstream link nobody has measured: the team target budget D1
            # draws against the pass attempts the QB layer draws.
            tt = np.asarray(payload['team_draws'][t]['team_targets'], float)
            att = np.asarray(qbi['draws']['att'], float)[qm].sum(0)
            rec['targets_vs_attempts'] = {
                'team_targets_D1': _summ(tt), 'qb_attempts': _summ(att),
                'mean_attempts_minus_targets': round(
                    float((att - tt).mean()), 4)}
            rows.append(rec)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None)
    ap.add_argument('--draws', type=int, default=200)
    ap.add_argument('--seed', type=int, default=20260908)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--joint-residuals', action='store_true', default=True)
    a = ap.parse_args()
    if not os.path.exists(HIST):
        raise SystemExit(f'{HIST} missing. Build it first; this script will '
                         f'not report a simulator level with nothing to '
                         f'compare it against.')
    with open(HIST) as fh:
        hist = json.load(fh)
    rows = collect(a.season, a.week, a.draws, a.seed, a.games,
                   a.joint_residuals)
    ok = [r for r in rows if 'passing_yards' in r]
    if not ok:
        raise SystemExit(f'no team produced both sides; {len(rows)} row(s) '
                         f'halted: {rows[:2]}')
    summary = {'artifact': 'XL1_DIAGNOSIS', 'TEST_ONLY': True,
               'engine_version': FE.ENGINE_VERSION,
               'season': a.season, 'week': a.week, 'n_draws': a.draws,
               'joint_residuals': a.joint_residuals,
               'n_team_games': len(ok), 'history': hist['team_game_means'],
               'history_n_team_games': hist['n_team_games'], 'links': {}}
    for label, _, _ in LINKS:
        rs = [r[label] for r in ok]
        summary['links'][label] = {
            'mean_receiving_side': round(statistics.mean(
                x['receiving_side']['mean'] for x in rs), 4),
            'mean_qb_side': round(statistics.mean(
                x['qb_side']['mean'] for x in rs), 4),
            'historical_mean': hist['team_game_means'][label],
            'mean_abs_diff': round(statistics.mean(
                x['mean_abs_diff'] for x in rs), 4),
            'team_games_with_any_exact_draw': sum(
                1 for x in rs if x['exact_draws']),
            'draws_exact': sum(x['exact_draws'] for x in rs),
            'draws_total': sum(x['n_draws'] for x in rs),
            'mean_corr': round(statistics.mean(
                x['corr'] for x in rs if x['corr'] is not None), 6),
        }
    tv = [r['targets_vs_attempts'] for r in ok]
    summary['links']['targets_vs_attempts'] = {
        'mean_team_targets_D1': round(statistics.mean(
            x['team_targets_D1']['mean'] for x in tv), 4),
        'mean_qb_attempts': round(statistics.mean(
            x['qb_attempts']['mean'] for x in tv), 4),
        'historical_mean_targets': hist['team_game_means']['targets'],
        'historical_mean_throws': hist['team_game_means']['throws'],
        'mean_attempts_minus_targets': round(statistics.mean(
            x['mean_attempts_minus_targets'] for x in tv), 4),
        'historical_attempts_minus_targets':
            hist['team_game_means']['throws_minus_targets'],
    }
    summary['per_team_game'] = ok
    dest = os.path.join(HERE, 'xl1_diagnosis.json')
    with open(dest, 'w') as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    show = {k: v for k, v in summary.items() if k != 'per_team_game'}
    print(json.dumps(show, indent=2, sort_keys=True))
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
