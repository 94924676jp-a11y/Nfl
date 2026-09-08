"""TD2 section 8: does any conversion candidate survive composition?

The candidate replaces the CONVERSION component only. V, S and Z machinery are
frozen. Substitution is draw-preserving and mean-shifting.

A candidate that improves conversion in isolation and worsens composed TD
forecasts is COMPOSITION_FAILED regardless of primitive performance.
"""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'td1'))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
import td2_lib as T                                            # noqa: E402
import run_td2 as R2                                           # noqa: E402
import run_td1 as TD1                                          # noqa: E402
import rc1_lib as L                                            # noqa: E402


def main():
    OUT = {'prereg_sha256': R2.PREREG,
           'protocol': 'V, S and Z frozen; conversion candidate substituted '
                       'draw-preservingly by scaling k_rz and k_nrz',
           'kinds': {}}
    for kind, arm in (('rec', 'L4'), ('rush', 'L4')):
        label, opp, td = T.ESTIMANDS[kind][0]
        # TD2 frame carries the candidate; TD1 frame carries the simulator
        t2 = {}
        rs2 = T.load(kind, opp, td)
        fitted = {}
        for ev in T.EVAL:
            fitted[ev] = R2.fit(rs2, ev)
        for r in rs2:
            if r['season'] in fitted:
                t2[(r['season'], r['week'], r['team'], r['gsis_id'])] = \
                    R2.predict(arm, r, fitted[r['season']])
        base_l0 = {}
        for r in rs2:
            if r['season'] in fitted:
                base_l0[(r['season'], r['week'], r['team'], r['gsis_id'])] = \
                    R2.predict('B_pos', r, fitted[r['season']])

        rs_all = TD1.attach(TD1.load(kind))
        res = {'control': collections.defaultdict(list),
               arm: collections.defaultdict(list),
               'B_pos': collections.defaultdict(list)}
        Y, G = [], []
        for ev in L.EVAL:
            rs = [r for r in rs_all if L.eligible(r, ev)]
            y = np.array([r['TD'] for r in rs], float)
            Y.append(y); G += [r['game_id'] for r in rs]
            D0 = TD1.simulate(rs, ev, rs_all)
            res['control']['crps'].append(L.crps_matrix(D0, y))
            res['control']['p1'].append((D0 >= 0.5).mean(1))
            for nm, tbl in ((arm, t2), ('B_pos', base_l0)):
                cand = lambda r, _t=tbl: _t.get(
                    (r['season'], r['week'], r['team'], r['gsis_id']))
                D = TD1.simulate(rs, ev, rs_all, k_candidate=cand)
                res[nm]['crps'].append(L.crps_matrix(D, y))
                res[nm]['p1'].append((D >= 0.5).mean(1))
            OUT['kinds'].setdefault(kind, {}).setdefault('by_season', {})[ev] = {
                'n': len(rs),
                'control_crps': float(res['control']['crps'][-1].mean()),
                f'{arm}_crps': float(res[arm]['crps'][-1].mean()),
                'B_pos_crps': float(res['B_pos']['crps'][-1].mean())}
        Y = np.concatenate(Y)
        d = OUT['kinds'][kind]
        for nm in ('control', arm, 'B_pos'):
            c = np.concatenate(res[nm]['crps'])
            p1 = np.concatenate(res[nm]['p1'])
            d[nm] = {'crps': float(c.mean()),
                     'brier_TD_ge_1': float(((p1 - (Y >= 1)) ** 2).mean()),
                     'bias': float(p1.mean() - (Y >= 1).mean())}
        base = d['control']['crps']
        for nm in (arm, 'B_pos'):
            d[nm]['crps_rel_pct_vs_control'] = 100 * (base - d[nm]['crps']) / base
            d[nm]['improves'] = d[nm]['crps'] < base
        # game-clustered bootstrap on the CRPS difference
        by = collections.defaultdict(list)
        for i, g in enumerate(G): by[g].append(i)
        keys = list(by); idxs = [np.array(by[k]) for k in keys]
        rng = np.random.default_rng(T.SEED)
        cc = np.concatenate(res['control']['crps'])
        ca = np.concatenate(res[arm]['crps'])
        boot = []
        for _ in range(400):
            pick = rng.integers(0, len(keys), len(keys))
            sel = np.concatenate([idxs[j] for j in pick])
            boot.append(float(cc[sel].mean() - ca[sel].mean()))
        d['crps_diff_ci'] = {'point': float(cc.mean() - ca.mean()),
                             'lo': float(np.quantile(boot, 0.025)),
                             'hi': float(np.quantile(boot, 0.975))}
        print(f'\n== {kind} composition ==')
        print(f"   control        CRPS {d['control']['crps']:.6f}  "
              f"Brier {d['control']['brier_TD_ge_1']:.6f}")
        for nm in ('B_pos', arm):
            print(f"   {nm:<14} CRPS {d[nm]['crps']:.6f}  "
                  f"Brier {d[nm]['brier_TD_ge_1']:.6f}  "
                  f"{d[nm]['crps_rel_pct_vs_control']:+.4f}%  "
                  f"{'improves' if d[nm]['improves'] else 'WORSE'}")
        print(f"   CRPS diff (control - {arm}) {d['crps_diff_ci']['point']:+.6f}  "
              f"95% CI [{d['crps_diff_ci']['lo']:+.6f}, {d['crps_diff_ci']['hi']:+.6f}]")
        for ev, v in d['by_season'].items():
            print(f"     {ev}: control {v['control_crps']:.6f}  "
                  f"{arm} {v[f'{arm}_crps']:.6f}")
    json.dump(OUT, open(f'{HERE}/td2_composition.json', 'w'), indent=1, default=str)
    print('\nwrote td2_composition.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
