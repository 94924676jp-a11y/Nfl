"""P4B second pass: randomised PIT, exceedance calibration, subgroup oracle.

WHY A SECOND PIT. The predictive distribution here is MIXED, not continuous:
it carries an atom at zero of mass 1 - P(appear), roughly 0.28. The ordinary
PIT of a mixed distribution is not uniform even when the forecast is perfect,
so the chi-squared values in the first pass (thousands on 9 df) measure the
atom, not miscalibration. The randomised PIT
    u = F(y-) + V (F(y) - F(y-)),  V ~ U(0,1)
is uniform under a correct forecast for any distribution, and it is the number
that can be read as a calibration diagnostic.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, '..', 'p1'), os.path.join(HERE, '..', 'p2'),
          os.path.join(HERE, '..', 'p3'), HERE, '/home/user/nfl'):
    sys.path.insert(0, os.path.abspath(p))
import p4b_lib as L                                            # noqa: E402
from run_p4b import appearance, share_history, load_volume     # noqa: E402


def rpit(draws, y, rng):
    y = np.asarray(y, float).reshape(-1, 1)
    lo = (draws < y).mean(axis=1)
    hi = (draws <= y).mean(axis=1)
    return lo + rng.random(len(lo)) * (hi - lo)


def pit_stats(u):
    h, _ = np.histogram(u, bins=10, range=(0, 1))
    exp = len(u) / 10.0
    return {'hist': h.tolist(), 'expected_per_bin': exp,
            'chi2': float((((h - exp) ** 2) / exp).sum()), 'df': 9,
            'chi2_crit_p001': 27.877, 'mean': float(u.mean()),
            'ks': float(np.abs(np.sort(u) - (np.arange(len(u)) + .5) / len(u)).max())}


def main():
    t0 = time.time()
    rows = pickle.load(open(f'{HERE}/panel_enriched.pkl', 'rb'))
    vol = load_volume()
    pa = appearance(rows)
    out = {}
    for target, (den_key, positions) in L.TARGETS.items():
        sub = share_history(rows, target, positions)
        skey, ykey = f's_{target}', f'y_{target}'
        res_t = {}
        for ev in L.EVAL:
            store = vol.get((den_key, ev))
            if store is None:
                continue
            tr = [r for r in sub if r['season'] < ev and r.get(skey) is not None]
            te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
                  and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
                  and (r['team'], r['ord']) in store['index']]
            if len(te) < 200 or len(tr) < 500:
                continue
            pri = {}
            for p_ in positions:
                v = [r[skey] for r in tr if r['position'] == p_ and r['appeared']]
                if v:
                    pri[p_] = float(np.mean(v))
            for r in tr + te:
                h = r['_app_hist']
                r['_C'] = L.ewma(h) if h else pri.get(r['position'])
            pool = collections.defaultdict(list)
            for r in tr:
                if r['appeared'] and r['_C'] is not None and r.get(skey) is not None:
                    pool[r['position']].append(r[skey] - r['_C'])
            pool = {k: np.array(v, np.float32) for k, v in pool.items()}
            te = [r for r in te if r['_C'] is not None and r['position'] in pool]
            n = len(te)
            y = np.array([r[ykey] for r in te], float)
            p_app = np.array([pa[id(r)] for r in te], np.float32)
            C = np.array([r['_C'] for r in te], np.float32)
            ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])

            rng = np.random.default_rng(L.SEED + 1009)
            Ad = (rng.random((n, L.M_DRAWS), np.float32) < p_app[:, None])
            g = np.random.default_rng(L.SEED + 2003)
            Sd = np.empty((n, L.M_DRAWS), np.float32)
            for i, r in enumerate(te):
                pl = pool[r['position']]
                Sd[i] = pl[g.integers(0, len(pl), L.M_DRAWS)]
            Sd += C[:, None]
            np.clip(Sd, 0.0, 1.0, out=Sd)

            vols = {'A': np.repeat(store['point'][ti][:, None], L.M_DRAWS, 1),
                    'B': store['B'][ti],
                    'D': np.repeat(store['realized'][ti][:, None], L.M_DRAWS, 1)}
            crps_row, pitr, thr = {}, {}, {}
            for k, T in vols.items():
                Y = Ad * T * Sd
                crps_row[k] = L.crps_samples(Y, y)
                pitr[k] = pit_stats(rpit(Y, y, np.random.default_rng(L.SEED + 31)))
                thr[k] = L.thresholds(Y, y, L.THRESHOLDS[target])
                del Y

            # ---- subgroups. Every split is a PREGAME quantity ---------------
            S_real = np.array([r[skey] for r in te], float)
            A_real = np.array([1.0 if r['appeared'] else 0.0 for r in te])
            T_pt = store['point'][ti].astype(float)
            T_re = store['realized'][ti].astype(float)
            arms = {'PP': p_app * T_pt * C, 'RP': p_app * T_re * C,
                    'PR': p_app * T_pt * S_real, 'RR': p_app * T_re * S_real,
                    'RRR': A_real * T_re * S_real}
            def pbucket(p):
                return ('p<0.50' if p < .5 else 'p 0.50-0.80' if p < .8
                        else 'p 0.80-0.95' if p < .95 else 'p>=0.95')
            splits = {
                'position': [r['position'] for r in te],
                'role_stability': ['role_change' if r.get('role_change') == 1
                                   else 'stable' for r in te],
                'appearance_uncertainty': [pbucket(p) for p in p_app],
                'information_quality': [r.get('info_quality') or 'UNKNOWN'
                                        for r in te],
            }
            subg = {}
            for sname, lab in splits.items():
                lab = np.array(lab)
                d = {}
                for u in sorted(set(lab.tolist())):
                    m = lab == u
                    if m.sum() < 60:
                        continue
                    d[u] = {
                        'n': int(m.sum()),
                        'crps': {k: float(crps_row[k][m].mean()) for k in vols},
                        'oracle_mae': {k: float(np.abs(y[m] - v[m]).mean())
                                       for k, v in arms.items()},
                        'appearance_rate': float(A_real[m].mean()),
                    }
                subg[sname] = d

            res_t[ev] = {'n': n, 'randomised_pit': pitr, 'thresholds': thr,
                         'subgroups': subg}
            print(f'  {target:12s} {ev} n={n:5d} rPIT chi2 '
                  f'A={pitr["A"]["chi2"]:8.1f} B={pitr["B"]["chi2"]:8.1f} '
                  f'D*={pitr["D"]["chi2"]:8.1f} (crit 27.9)')
            out[target] = res_t
            json.dump(out, open(f'{HERE}/p4b_results2.json', 'w'), indent=1)
        out[target] = res_t
        json.dump(out, open(f'{HERE}/p4b_results2.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4b_results2.json')


if __name__ == '__main__':
    main()
