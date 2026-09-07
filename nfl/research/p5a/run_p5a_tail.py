"""P5A items 22, 27: subgroup metrics and TAIL calibration.

Rushing yards are driven by rare large gains, so a good mean MAE is not
allowed to stand in for a good tail. This computes, per system, the model's
implied probability that a player-game contains at least one 20+ yard rush,
against the observed rate, and asks whether player identity or team context
contributes anything to that probability.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
sys.path.insert(0, HERE); sys.path.insert(0, P4C)
import p5a_lib as L                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
from run_p4c import groups_of                                  # noqa: E402
from run_p5a import BLOCKS, features, fit_eb_k, ridge, pred_ridge, eb  # noqa

CLS = 'carries'
BIG = 20.0


def main():
    t0 = time.time()
    D = pickle.load(open(f'{HERE}/pg.pkl', 'rb'))
    carries, pg = D['carries'], D['pg']
    pgi = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in pg}
    rows = CB.load_panel(); vol = CB.load_volume(); pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, CLS); c = CL.CLASSES[CLS]
    OUT = {}
    for ev in L.EVAL:
        store = vol.get((c['den'], ev))
        par = CB.fit_params(sub, CLS, ev, rows)
        te = [r for r in sub if r['season'] == ev and r.get('s_carries') is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        n = len(te)
        starts, cg, gk = groups_of(te)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
        mass = CB.mass_draws('C', par, len(starts), CL.M_DRAWS,
                             np.random.default_rng(CL.SEED + 5002))
        W = CB.gen_weights('C', np.array([r['_C'] for r in te], np.float32),
                           [r['position'] for r in te], par, CLS, n, CL.M_DRAWS,
                           np.random.default_rng(CL.SEED + 3034))
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        Ad = (np.random.default_rng(CL.SEED + 1009)
              .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
        S, _o, _b = CL.allocate(W, Ad, starts, cg, 'occupancy', 1.0 - mass)
        cnt = np.clip(np.rint((store['B'][ti] * S)).astype(np.int32), 0, None)
        keep = [pgi.get((r['season'], r['week'], r['team'], r['gsis_id']))
                for r in te]
        y = np.array([q['rush_yards'] if q else 0.0 for q in keep], float)
        big_obs = np.array([1.0 if (q and q['max_run'] >= BIG) else 0.0
                            for q in keep])
        tr = [r for r in pg if r['season'] < ev]
        trc = [x for x in carries if x['season'] < ev]
        pool = L.Pool([x['yards'] for x in trc])
        pool.body_or_stuff = pool.y[pool.y < L.EXPLOSIVE]
        pools = {'ypc': pool.mean, 'exp': pool.p_exp, 'stuff': pool.p_stuff}
        acts = {'ypc': lambda r: r['rush_yards'] / r['carries'],
                'exp': lambda r: r['n_explosive'] / r['carries'],
                'stuff': lambda r: r['n_stuff'] / r['carries']}
        ks = {}
        for b, src in (('player', 'p'), ('team', 't'), ('opp', 'd')):
            for m in ('ypc', 'exp', 'stuff'):
                ks[(b, m)] = fit_eb_k(
                    tr, lambda r, s=src, mm=m: (None if r[s] is None or r[s]['n'] < 1
                                                else (r[s]['n'], r[s][mm])),
                    acts[m], pools[m])
        res = {}
        for sysname in ('A', 'B', 'E'):
            blocks = BLOCKS[sysname]
            if not blocks:
                mu = np.full(n, pool.mean)
            else:
                Xtr = np.array([features(r, blocks, ks, pools) for r in tr])
                Xte = np.array([features(q, blocks, ks, pools) if q else
                                np.array(features({'p': None, 't': None, 'd': None},
                                                  blocks, ks, pools))
                                for q in keep])
                wtr = np.array([r['carries'] for r in tr], float)
                mu = pred_ridge(ridge(Xtr, [acts['ypc'](r) for r in tr], wtr), Xte)
            mu = np.clip(mu, 1.0, 8.0)
            # model-implied per-carry P(>= BIG) under the chosen emp_shift family
            q_big = np.array([float((pool.y + (m - pool.mean) >= BIG).mean())
                              for m in mu])
            # P(at least one big run) marginalised over the CARRY DRAWS
            p_big = np.array([float(np.mean(1.0 - (1.0 - q_big[i]) ** cnt[i]))
                              for i in range(n)])
            res[sysname] = {
                'p_big_mean': float(p_big.mean()),
                'observed_big_rate': float(big_obs.mean()),
                'calibration_in_the_large': float(p_big.mean() - big_obs.mean()),
                'brier': float(((p_big - big_obs) ** 2).mean()),
                'auc_big': None,
                'per_carry_q_big_mean': float(q_big.mean()),
                'per_carry_q_big_sd': float(q_big.std()),
                'observed_per_carry_big': None,   # filled in below
            }
            # does the model's p_big DISCRIMINATE big-run games?
            o = np.argsort(p_big)
            n1 = int(big_obs.sum()); n0 = len(big_obs) - n1
            if n1 and n0:
                r_ = np.empty(len(p_big))
                r_[o] = np.arange(1, len(p_big) + 1)
                res[sysname]['auc_big'] = float(
                    (r_[big_obs == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
            res[sysname]['_p_big'] = p_big
        # observed per-carry P(>=BIG) in the evaluation season
        obs_pc = float(np.mean([1.0 if x['yards'] >= BIG else 0.0
                                for x in carries if x['season'] == ev]))
        for k in res:
            res[k]['observed_per_carry_big'] = obs_pc

        # ---- does player identity add to TAIL probability? ----------------
        prior_exp = np.array([(q['p']['exp'] if (q and q['p'] and q['p']['n'] >= 25)
                               else np.nan) for q in keep])
        m = ~np.isnan(prior_exp)
        tail_player = None
        if m.sum() > 200:
            o = np.argsort(prior_exp[m])
            b = big_obs[m]
            n1 = int(b.sum()); n0 = len(b) - n1
            r_ = np.empty(int(m.sum())); r_[o] = np.arange(1, int(m.sum()) + 1)
            tail_player = {
                'n': int(m.sum()),
                'auc_prior_explosive_rate_vs_big_run': float(
                    (r_[b == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
                if n1 and n0 else None,
                'corr_prior_exp_vs_big': float(np.corrcoef(prior_exp[m], b)[0, 1]),
            }
        # ---- subgroups ----------------------------------------------------
        def tier(k):
            return ('0' if k == 0 else '1-4' if k <= 4 else '5-9' if k <= 9
                    else '10-14' if k <= 14 else '15+')
        realc = np.array([q['carries'] if q else 0 for q in keep])
        splits = {
            'carry_volume_tier': [tier(k) for k in realc],
            'role_stability': ['role_change' if r.get('role_change') == 1
                               else 'stable' for r in te],
            'information_quality': [r.get('info_quality') or 'UNKNOWN' for r in te],
            'prior_history_depth': ['<25 carries' if not (q and q['p'] and q['p']['n'] >= 25)
                                    else ('25-199' if q['p']['n'] < 200 else '200+')
                                    for q in keep],
            'efficiency_history': ['low' if (q and q['p'] and q['p']['n'] >= 25
                                             and q['p']['ypc'] < pool.mean)
                                   else ('high' if (q and q['p'] and q['p']['n'] >= 25)
                                         else 'none') for q in keep],
        }
        # CRPS per subgroup needs the draws; recompute A and E compactly
        crps = {}
        for sysname in ('A', 'E'):
            blocks = BLOCKS[sysname]
            if not blocks:
                mu = np.full(n, pool.mean)
            else:
                Xtr = np.array([features(r, blocks, ks, pools) for r in tr])
                Xte = np.array([features(q, blocks, ks, pools) if q else
                                np.array(features({'p': None, 't': None, 'd': None},
                                                  blocks, ks, pools))
                                for q in keep])
                wtr = np.array([r['carries'] for r in tr], float)
                mu = pred_ridge(ridge(Xtr, [acts['ypc'](r) for r in tr], wtr), Xte)
            mu = np.clip(mu, 1.0, 8.0)
            pars = [{'shift': mu[i] - pool.mean} for i in range(n)]
            Y = L.compound(cnt, 'emp_shift', pool, pars, L.SEED + 77)
            crps[sysname] = L.crps_samples(Y, y)
            del Y
        sg = {}
        for sname, lab in splits.items():
            lab = np.array(lab); dd = {}
            for u in sorted(set(lab.tolist())):
                mm = lab == u
                if mm.sum() < 60:
                    continue
                dd[u] = {'n': int(mm.sum()),
                         'crps_A': float(crps['A'][mm].mean()),
                         'crps_E': float(crps['E'][mm].mean()),
                         'mean_yards': float(y[mm].mean()),
                         'big_run_rate': float(big_obs[mm].mean())}
            sg[sname] = dd
        for k in res:
            res[k].pop('_p_big', None)
        OUT[ev] = {'n': n, 'tail': res, 'tail_player_identity': tail_player,
                   'subgroups': sg}
        print(f'{ev}: P(20+ run in game) forecast/observed  ' + '  '.join(
            f'{k}={res[k]["p_big_mean"]:.4f}/{res[k]["observed_big_rate"]:.4f} '
            f'(AUC {res[k]["auc_big"]:.3f})' for k in ('A', 'B', 'E')))
        if tail_player:
            print(f'      prior explosive rate vs a 20+ run: '
                  f'AUC {tail_player["auc_prior_explosive_rate_vs_big_run"]:.4f} '
                  f'r {tail_player["corr_prior_exp_vs_big"]:+.4f} '
                  f'(n={tail_player["n"]})')
        json.dump(OUT, open(f'{HERE}/p5a_tail.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p5a_tail.json')


if __name__ == '__main__':
    main()
