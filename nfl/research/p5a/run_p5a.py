"""P5A main: the A -> B -> C -> D -> E ladder over the ACCEPTED carry allocation.

The carry distribution is P4C's, imported and not rebuilt: same appearance
model, same joint allocation (system C, reserved stochastic mass), same
team-volume draws, same shared-draw structure. Only the CONVERSION layer
changes between systems, so a difference is attributable to the conversion
information and to nothing else.
"""
import collections, json, math, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
P4D = os.path.abspath(os.path.join(HERE, '..', 'p4d'))
sys.path.insert(0, HERE)
sys.path.insert(0, P4C)
import p5a_lib as L                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
from run_p4c import groups_of                                  # noqa: E402

CLS = 'carries'
EB_GRID = [0, 5, 10, 20, 40, 80, 160, 320, 640, 1280, 2560]


def eb(n, x, k, pool):
    return (n * x + k * pool) / (n + k) if (n + k) > 0 else pool


def fit_eb_k(rows, get, act, pool):
    """Shrinkage constant chosen on PRIOR-SEASON rows by carry-weighted MSE."""
    best, bv = 0, None
    for k in EB_GRID:
        e = w = 0.0
        for r in rows:
            g = get(r)
            if g is None:
                p = pool
            else:
                p = eb(g[0], g[1], k, pool)
            e += r['carries'] * (act(r) - p) ** 2
            w += r['carries']
        v = e / max(w, 1)
        if bv is None or v < bv:
            best, bv = k, v
    return best


def ridge(X, y, w, l2=1.0):
    X = np.asarray(X, float); y = np.asarray(y, float); w = np.asarray(w, float)
    mu = np.average(X, axis=0, weights=w)
    sd = np.sqrt(np.average((X - mu) ** 2, axis=0, weights=w)); sd[sd == 0] = 1
    Xs = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    W = np.diag(w) if False else w
    A = (Xs * W[:, None]).T @ Xs + l2 * np.eye(Xs.shape[1])
    A[0, 0] -= l2
    b = (Xs * W[:, None]).T @ y
    return {'w': np.linalg.solve(A, b), 'mu': mu, 'sd': sd}


def pred_ridge(m, X):
    X = np.asarray(X, float)
    Xs = np.hstack([np.ones((len(X), 1)), (X - m['mu']) / m['sd']])
    return Xs @ m['w']


# feature blocks per rung, cumulative
BLOCKS = {'A': (), 'B': ('player',), 'C': ('player', 'team'),
          'D': ('player', 'opp'), 'E': ('player', 'team', 'opp')}


def features(r, blocks, ks, pools):
    f = []
    for b in blocks:
        src = {'player': 'p', 'team': 't', 'opp': 'd'}[b]
        s = r[src]
        for m, pk in (('ypc', 'ypc'), ('exp', 'exp'), ('stuff', 'stuff')):
            if s is None or s['n'] < 1:
                f.append(pools[pk])
            else:
                f.append(eb(s['n'], s[m], ks[(b, m)], pools[pk]))
    return f


def main():
    t0 = time.time()
    D = pickle.load(open(f'{HERE}/pg.pkl', 'rb'))
    carries, pg = D['carries'], D['pg']
    pgi = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in pg}
    rows = CB.load_panel()
    vol = CB.load_volume()
    pa = CB.appearance(rows)
    sub = CB.prepare_class(rows, CLS)
    c = CL.CLASSES[CLS]
    OUT = {}
    for ev in L.EVAL:
        store = vol.get((c['den'], ev))
        if store is None:
            continue
        par = CB.fit_params(sub, CLS, ev, rows)
        te = [r for r in sub if r['season'] == ev and r.get('s_carries') is not None
              and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
              and r['_C'] is not None and (r['team'], r['ord']) in store['index']]
        te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
        n = len(te)
        starts, counts_g, gkeys = groups_of(te)
        G = len(starts)
        ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
        mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                             np.random.default_rng(CL.SEED + 5002))
        avail = 1.0 - mass
        W = CB.gen_weights('C', np.array([r['_C'] for r in te], np.float32),
                           [r['position'] for r in te], par, CLS, n, CL.M_DRAWS,
                           np.random.default_rng(CL.SEED + 3034))
        p_app = np.array([pa[id(r)] for r in te], np.float32)
        Ad = (np.random.default_rng(CL.SEED + 1009)
              .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
        S, _o, _b = CL.allocate(W, Ad, starts, counts_g, 'occupancy', avail)
        Ycar = (store['B'][ti] * S).astype(np.float32)
        cnt = np.rint(Ycar).astype(np.int32)
        np.clip(cnt, 0, None, out=cnt)

        # ---- attach the carry-level history rows -------------------------
        keep, y = [], []
        for i, r in enumerate(te):
            k = (r['season'], r['week'], r['team'], r['gsis_id'])
            q = pgi.get(k)
            keep.append(q)
            y.append(q['rush_yards'] if q else 0.0)
        y = np.array(y, float)
        cluster = [f"{r['team']}_{r['ord']}" for r in te]

        # ---- prior-season pools and shrinkage constants -------------------
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

        scores, thr, crps_row, fam_pick = {}, {}, {}, {}
        SYS = ['A', 'B', 'C', 'D', 'E']
        for sysname in SYS:
            blocks = BLOCKS[sysname]
            if not blocks:
                mu = np.full(n, pool.mean); pe = np.full(n, pool.p_exp)
                ps = np.full(n, pool.p_stuff)
            else:
                Xtr = np.array([features(r, blocks, ks, pools) for r in tr])
                Xte = np.array([features(q, blocks, ks, pools) if q else
                                np.array(features(
                                    {'p': None, 't': None, 'd': None},
                                    blocks, ks, pools))
                                for q in keep])
                wtr = np.array([r['carries'] for r in tr], float)
                mu = pred_ridge(ridge(Xtr, [acts['ypc'](r) for r in tr], wtr), Xte)
                pe = pred_ridge(ridge(Xtr, [acts['exp'](r) for r in tr], wtr), Xte)
                ps = pred_ridge(ridge(Xtr, [acts['stuff'](r) for r in tr], wtr), Xte)
            mu = np.clip(mu, 1.0, 8.0)
            pe = np.clip(pe, 0.01, 0.35)
            ps = np.clip(ps, 0.05, 0.45)
            best_fam, best_c = None, None
            per_fam = {}
            for fam in L.FAMILIES:
                pars = []
                for i in range(n):
                    if fam == 'emp_shift':
                        pars.append({'shift': mu[i] - pool.mean})
                    elif fam == 'emp_tilt':
                        pars.append({'cdf': np.cumsum(L.tilt_pmf(pool, mu[i]))})
                    elif fam == 'mix2':
                        pars.append({'p_exp': pe[i]})
                    else:
                        pars.append({'p_stuff': ps[i], 'p_exp': pe[i]})
                Y = L.compound(cnt, fam, pool, pars, L.SEED + 77)
                sc = L.score(Y, y, np.random.default_rng(L.SEED + 31))
                per_fam[fam] = sc['crps']
                if best_c is None or sc['crps'] < best_c:
                    best_fam, best_c, bestY, bestsc = fam, sc['crps'], Y, sc
                del Y
            scores[sysname] = bestsc
            scores[sysname]['family'] = best_fam
            scores[sysname]['per_family_crps'] = per_fam
            thr[sysname] = L.thresholds(bestY, y)
            crps_row[sysname] = L.crps_samples(bestY, y)
            fam_pick[sysname] = best_fam
            del bestY
        chosen = L.select_system(scores)

        # ---- ORACLES, after selection, never eligible ---------------------
        realc = np.array([q['carries'] if q else 0 for q in keep], np.int32)
        cnt_or = np.repeat(realc[:, None], CL.M_DRAWS, axis=1)
        pars = [{'shift': 0.0} for _ in range(n)]
        oc = L.compound(cnt_or, 'emp_shift', pool, pars, L.SEED + 77)
        scores['O_carries'] = L.score(oc, y, np.random.default_rng(L.SEED + 31))
        crps_row['O_carries'] = L.crps_samples(oc, y)
        del oc
        realypc = np.array([(q['rush_yards'] / q['carries']) if (q and q['carries'])
                            else pool.mean for q in keep])
        pars = [{'shift': realypc[i] - pool.mean} for i in range(n)]
        oe = L.compound(cnt, 'emp_shift', pool, pars, L.SEED + 77)
        scores['O_eff'] = L.score(oe, y, np.random.default_rng(L.SEED + 31))
        crps_row['O_eff'] = L.crps_samples(oe, y)
        del oe
        realexp = np.array([(q['n_explosive'] / q['carries']) if (q and q['carries'])
                            else pool.p_exp for q in keep])
        pars = [{'p_exp': float(np.clip(realexp[i], 0, 1))} for i in range(n)]
        ox = L.compound(cnt, 'mix2', pool, pars, L.SEED + 77)
        scores['O_explosive'] = L.score(ox, y, np.random.default_rng(L.SEED + 31))
        crps_row['O_explosive'] = L.crps_samples(ox, y)
        del ox
        pars = [{'shift': realypc[i] - pool.mean} for i in range(n)]
        oa = L.compound(cnt_or, 'emp_shift', pool, pars, L.SEED + 77)
        scores['O_all'] = L.score(oa, y, np.random.default_rng(L.SEED + 31))
        crps_row['O_all'] = L.crps_samples(oa, y)
        del oa

        boots = {k: L.block_boot(crps_row[k], crps_row['A'], cluster)
                 for k in crps_row if k != 'A'}
        OUT[ev] = {
            'n': n, 'n_team_games': G,
            'carry_count_mean_sim': float(cnt.mean()),
            'carry_count_mean_real': float(realc.mean()),
            'pool': {'mean': pool.mean, 'p_exp': pool.p_exp,
                     'p_stuff': pool.p_stuff, 'n_train_carries': int(len(pool.y))},
            'eb_k': {f'{a}_{b}': v for (a, b), v in ks.items()},
            'scores': scores, 'thresholds': thr, 'bootstrap_vs_A': boots,
            'chosen_eligible_system': chosen, 'family_by_system': fam_pick,
            'systems_offered': list(L.ELIGIBLE_SYSTEMS),
        }
        print(f'\n{ev} n={n} G={G} pooled ypc={pool.mean:.4f} '
              f'k(player)={ks[("player","ypc")]}/{ks[("player","exp")]}/'
              f'{ks[("player","stuff")]}')
        for k in SYS + ['O_carries', 'O_eff', 'O_explosive', 'O_all']:
            s = scores[k]
            print(f'  {k:12s} CRPS {s["crps"]:8.4f} MAE {s["mae"]:7.3f} '
                  f'r {(s["r"] or 0):+.3f} rPIT {s["randomised_pit"]["chi2"]:7.1f} '
                  f'cov90 {s["coverage"]["90"]["coverage"]:.3f} '
                  f'fam {s.get("family","-")}')
        print(f'  chosen={chosen}')
        json.dump(OUT, open(f'{HERE}/p5a_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p5a_results.json')


if __name__ == '__main__':
    main()
