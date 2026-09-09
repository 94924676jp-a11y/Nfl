"""J1 downstream: what restoring team-level dependence does to the SIMULATOR.

Runs the full football engine twice on identical seeds -- once with D1's
independent per-metric draws and once with A3's joint residuals -- and compares
the joint object, not just the marginals.

The owner's instruction is the design brief: unchanged marginals do not imply
unchanged player distributions, because everything downstream composes
non-linearly.
"""
from __future__ import annotations

import collections, json, os, sys, time
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                # noqa: E402
from nfl.capture import coverage as C                              # noqa: E402
from nfl.production import team_volume_v1 as TV                    # noqa: E402
from nfl.production.nonqb import football_engine as FE             # noqa: E402
from nfl.production.nonqb import qb_allocation as QA               # noqa: E402
from nfl.production.rehearsal import run_slate as RS               # noqa: E402
from nfl.production.nonqb import engine_rehearsal as ER            # noqa: E402

SEASON, WEEK, M, SEED = 2026, 1, 400, 20260908


def _corr(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.std() < 1e-12 or b.std() < 1e-12:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


def run(joint, max_games=None):
    """One full slate, TEST_ONLY appearance stand-in, draws retained."""
    TV.cache_clear()
    TV.JOINT_RESIDUALS_DEFAULT = bool(joint)
    plan = C.load_week_plan(SEASON, WEEK)
    assert plan.state is State.PASS
    ko = {c.game_id: c.kickoff_utc for c in plan.value}
    games = sorted(ko)[:max_games] if max_games else sorted(ko)
    _, rr = RS.roster(SEASON, WEEK)
    by_team = collections.defaultdict(list)
    for r in rr:
        if r['gsis_id'] and r['position'] in FE.RECEIVING_POS:
            by_team[r['team']].append({'gsis_id': r['gsis_id'],
                                       'position': r['position'],
                                       'team': r['team']})
    everyone = [q for t in sorted(by_team) for q in by_team[t]]
    qbp = [{'gsis_id': r['gsis_id'], 'position': r['position'],
            'team': r['team']} for r in rr
           if r['gsis_id'] and r['position'] == 'QB']
    fits = FE.slate_fits(SEASON, WEEK, everyone)
    assert fits.state is State.PASS, fits.detail
    qo = FE.qb_slate(SEASON, WEEK, qbp, m=M, seed=SEED)
    qb = qo.value if qo.state is State.PASS else None
    if qb is not None:
        qa = QA.allocate(SEASON, WEEK, sorted({q['team'] for q in qbp}), qbp,
                         m=M, seed=SEED)
        if qa.state is State.PASS:
            qb['allocation'] = qa.value
    out = []
    for gid in games:
        players = [q for t in gid.split('_')[2:4] for q in by_team.get(t, [])]
        inj = ER.stub_injuries(SEASON, WEEK, players)
        k = ko[gid]
        g, payload = FE.run_game(
            SEASON, WEEK, gid, players, fits.value, m=M, seed=SEED,
            injuries_rows=inj, test_only=True,
            kickoff_utc=(k.isoformat().replace('+00:00', 'Z')
                         if hasattr(k, 'isoformat') else k),
            run_id='J1_DOWNSTREAM', qb=qb)
        if payload:
            out.append((gid, g, payload))
    TV.JOINT_RESIDUALS_DEFAULT = False
    return out


# ------------------------------------------------------------- diagnostics
def diagnose(runs):
    """Every quantity the owner named, computed per game and pooled."""
    d = collections.defaultdict(list)
    for gid, g, p in runs:
        ix = p['index']
        T, Cc = p['draws']['targets'], p['draws']['carries']
        RY, RC = p['draws']['receiving_yards'], p['draws']['receptions']
        RTD, RUTD = p['draws']['receiving_td'], p['draws']['rush_td']
        teams = ix['teams']
        tv = p['team_draws']
        qb = p.get('qb')

        # ---- team-level, per team
        for t in teams:
            d['team_corr_carries_dropbacks'].append(
                _corr(tv[t]['team_carries'], tv[t]['team_dropbacks_part']))
            d['team_corr_carries_targets'].append(
                _corr(tv[t]['team_carries'], tv[t]['team_targets']))
        # ---- opposing-team, within the game
        if len(teams) == 2:
            a, b = teams
            d['opp_corr_carries_carries'].append(
                _corr(tv[a]['team_carries'], tv[b]['team_carries']))
            d['opp_corr_snaps_snaps'].append(
                _corr(tv[a]['team_off_snaps'], tv[b]['team_off_snaps']))

        # ---- competing receivers on the SAME team (top two by mean targets)
        for t in teams:
            idx = [i for i, tt in enumerate(ix['recv_team']) if tt == t]
            if len(idx) >= 2:
                order = sorted(idx, key=lambda i: -T[i].mean())[:2]
                d['recv_corr_competing_targets'].append(
                    _corr(T[order[0]], T[order[1]]))
                d['recv_corr_competing_yards'].append(
                    _corr(RY[order[0]], RY[order[1]]))
        # ---- RB rushing vs receiving, same player
        for j, pid in enumerate(ix['rb_ids']):
            i = ix['recv_ids'].index(pid) if pid in ix['recv_ids'] else None
            if i is not None:
                d['rb_corr_carries_targets'].append(_corr(Cc[j], T[i]))
        # ---- QB vs his own receivers
        if qb is not None:
            for t in teams:
                qi = [i for i, tt in enumerate(qb['team']) if tt == t]
                ri = [i for i, tt in enumerate(ix['recv_team']) if tt == t]
                if not qi or not ri:
                    continue
                py = np.stack([qb['draws']['pyds'][i] for i in qi]).sum(0)
                ptd = np.stack([qb['draws']['ptd'][i] for i in qi]).sum(0)
                team_ry = np.stack([RY[i] for i in ri]).sum(0)
                team_rtd = np.stack([RTD[i] for i in ri]).sum(0)
                d['qb_corr_passyds_teamrecvyds'].append(_corr(py, team_ry))
                d['qb_corr_passtd_teamrecvtd'].append(_corr(ptd, team_rtd))
                top = max(ri, key=lambda i: T[i].mean())
                d['qb_corr_passyds_topreceiver'].append(_corr(py, RY[top]))
        # ---- marginals and tails, pooled over players
        for i in range(T.shape[0]):
            d['_mean_targets'].append(float(T[i].mean()))
            d['_mean_recv_yards'].append(float(RY[i].mean()))
            d['_p90_recv_yards'].append(float(np.quantile(RY[i], 0.90)))
            d['_p99_recv_yards'].append(float(np.quantile(RY[i], 0.99)))
            d['_sd_recv_yards'].append(float(RY[i].std()))
        for j in range(Cc.shape[0]):
            d['_mean_carries'].append(float(Cc[j].mean()))
            d['_p90_carries'].append(float(np.quantile(Cc[j], 0.90)))
        d['_mean_recv_td'].append(float(RTD.mean()))
        d['_mean_rush_td'].append(float(RUTD.mean()))
        # team totals per draw: the joint object a game-level market would see
        for t in teams:
            ri = [i for i, tt in enumerate(ix['recv_team']) if tt == t]
            if ri:
                tot = np.stack([RY[i] for i in ri]).sum(0)
                d['_team_recvyds_mean'].append(float(tot.mean()))
                d['_team_recvyds_sd'].append(float(tot.std()))
                d['_team_recvyds_p90'].append(float(np.quantile(tot, 0.90)))
        # accounting
        rec_acc, rush_acc = p['accounting']
        d['_acc_recv_pass'].append(float(rec_acc.state is State.PASS))
        d['_acc_rush_pass'].append(float(rush_acc.state is State.PASS))
        d['_acc_cells'].append(float(rec_acc.evidence.get('n_cells_checked', 0)))
        d['_neg_yard_cells'].append(
            float(rec_acc.evidence.get('n_negative_yard_cells', 0)))
        qv = g['accounting'].get('qb_team_volume', '')
        d['_qb_volume_pass'].append(float(qv.startswith('PASS')))
    return d


HIST = {'team_corr_carries_dropbacks': -0.393,
        'team_corr_carries_targets': -0.388,
        'opp_corr_carries_carries': -0.535,
        'opp_corr_snaps_snaps': -0.464}

CORRS = ('team_corr_carries_dropbacks', 'team_corr_carries_targets',
         'opp_corr_carries_carries', 'opp_corr_snaps_snaps',
         'recv_corr_competing_targets', 'recv_corr_competing_yards',
         'rb_corr_carries_targets', 'qb_corr_passyds_teamrecvyds',
         'qb_corr_passtd_teamrecvtd', 'qb_corr_passyds_topreceiver')


def main(max_games=None):
    t0 = time.time()
    res = {}
    for joint in (False, True):
        runs = run(joint, max_games=max_games)
        res[joint] = diagnose(runs)
        print(f'  {"A3 joint" if joint else "A0 independent"}: '
              f'{len(runs)} games, {time.time()-t0:.0f}s', flush=True)
    OUT = {'artifact': 'J1_DOWNSTREAM',
           'label': 'EXPLORATORY. TEST_ONLY appearance stand-in. Not '
                    'promoted, not prospective evidence.',
           'season': SEASON, 'week': WEEK, 'draws': M, 'seed': SEED,
           'historical_reference': HIST, 'dependence': {}, 'marginals': {},
           'accounting': {}}
    for k in CORRS:
        a = np.array([x for x in res[False][k] if np.isfinite(x)])
        b = np.array([x for x in res[True][k] if np.isfinite(x)])
        if not len(a) and not len(b):
            continue
        OUT['dependence'][k] = {
            'n': int(min(len(a), len(b))),
            'independent': float(a.mean()) if len(a) else None,
            'joint_A3': float(b.mean()) if len(b) else None,
            'change': (float(b.mean() - a.mean())
                       if len(a) and len(b) else None),
            'historical': HIST.get(k)}
    for k in [x for x in res[False] if x.startswith('_') and
              not x.startswith('_acc') and not x.startswith('_qb_v')
              and not x.startswith('_neg')]:
        a = np.array(res[False][k], float)
        b = np.array(res[True][k], float)
        OUT['marginals'][k.lstrip('_')] = {
            'independent': float(np.nanmean(a)),
            'joint_A3': float(np.nanmean(b)),
            'relative_change': float((np.nanmean(b) - np.nanmean(a))
                                     / max(abs(np.nanmean(a)), 1e-9))}
    for k in ('_acc_recv_pass', '_acc_rush_pass', '_qb_volume_pass',
              '_acc_cells', '_neg_yard_cells'):
        OUT['accounting'][k.lstrip('_')] = {
            'independent': float(np.mean(res[False][k])),
            'joint_A3': float(np.mean(res[True][k]))}
    OUT['runtime_s'] = round(time.time() - t0, 1)
    json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'j1_downstream.json'), 'w'), indent=1)
    print('\nDEPENDENCE (mean correlation across the slate)')
    print(f'{"quantity":34s}{"indep":>9s}{"A3":>9s}{"change":>9s}{"hist":>9s}')
    for k, v in OUT['dependence'].items():
        h = f"{v['historical']:+.3f}" if v['historical'] is not None else '   --'
        print(f'{k:34s}{v["independent"]:>+9.4f}{v["joint_A3"]:>+9.4f}'
              f'{v["change"]:>+9.4f}{h:>9s}')
    print('\nMARGINALS (pooled over players/games)')
    print(f'{"quantity":34s}{"indep":>11s}{"A3":>11s}{"rel":>9s}')
    for k, v in OUT['marginals'].items():
        print(f'{k:34s}{v["independent"]:>11.4f}{v["joint_A3"]:>11.4f}'
              f'{v["relative_change"]:>+9.4f}')
    print('\nACCOUNTING')
    for k, v in OUT['accounting'].items():
        print(f'  {k:24s} indep {v["independent"]:>10.4f}   A3 {v["joint_A3"]:>10.4f}')
    return 0


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', type=int, default=None)
    a = ap.parse_args()
    sys.exit(main(a.games))
