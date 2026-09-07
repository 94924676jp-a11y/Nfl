"""P4D downstream: each appearance system through the FROZEN P4C machinery.

The P4C modules are imported, not copied and not edited. Share point models,
share residual pools, reconciliation, stochastic residual mass and team-volume
draws come from p4c_build/p4c_lib exactly as P4C ran them. The allocation
system is P4C's C -- reserved stochastic mass -- for all five classes.

THE APPEARANCE PROBABILITY IS THE ONLY THING THAT CHANGES. The appearance draw
matrix is generated from the same seed stream for every system, so two systems
with identical probabilities would produce byte-identical draws; an adversarial
probe asserts exactly that.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
sys.path.insert(0, HERE)
sys.path.insert(0, P4C)
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402
from run_p4c import groups_of                                  # noqa: E402
import p4d_lib as L                                            # noqa: E402

SYSTEMS = ['A', 'A+S', 'A1', 'A1+cal', 'R', 'R+cal', 'O']


def main():
    t0 = time.time()
    rows = CB.load_panel()
    vol = CB.load_volume()
    probs = pickle.load(open(f'{HERE}/p4d_probs.pkl', 'rb'))
    P = {}
    for (name, ev), d in probs.items():
        P.setdefault(name, {}).update(
            {k: float(p) for k, p in zip(d['keys'], d['p'])})
    OUT = {}
    for cls, c in CL.CLASSES.items():
        mode = c['mode']
        skey, ykey = c['share'], c['y']
        sub = CB.prepare_class(rows, cls)
        res = {}
        for ev in CL.EVAL:
            store = vol.get((c['den'], ev))
            if store is None:
                continue
            par = CB.fit_params(sub, cls, ev, rows)
            te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
                  and (r.get('f_n_prior') or 0) >= 1 and r['_C'] is not None
                  and (r['team'], r['ord']) in store['index']
                  and (r['gsis_id'], r['ord'], r['team']) in P['A']]
            te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
            if len(te) < 200:
                continue
            n = len(te)
            starts, counts, gkeys = groups_of(te)
            G = len(starts)
            y = np.array([r[ykey] for r in te], float)
            C = np.array([r['_C'] for r in te], np.float32)
            positions = [r['position'] for r in te]
            ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
            T = store['B'][ti]
            row_cluster = [f"{r['team']}_{r['ord']}" for r in te]
            kk = [(r['gsis_id'], r['ord'], r['team']) for r in te]
            mass = CB.mass_draws('C', par, G, CL.M_DRAWS,
                                 np.random.default_rng(CL.SEED + 5002))
            avail = (1.0 - mass) if mode == 'simplex' else mass
            W = CB.gen_weights('C', C, positions, par, cls, n, CL.M_DRAWS,
                               np.random.default_rng(CL.SEED + 3034))
            per, crps_row = {}, {}
            for sysname in SYSTEMS:
                if sysname not in P:
                    continue
                p_app = np.array([P[sysname][k] for k in kk], np.float32)
                # identical seed stream for every system
                Ad = (np.random.default_rng(CL.SEED + 1009)
                      .random((n, CL.M_DRAWS), np.float32) < p_app[:, None])
                S, _o, _b = CL.allocate(W, Ad, starts, counts, 'occupancy', avail)
                Y = (T * S).astype(np.float32)
                sc = CL.score(Y, y, np.random.default_rng(CL.SEED + 31))
                sc['thresholds'] = CL.thresholds(Y, y, CL.THRESHOLDS[cls])
                per[sysname] = sc
                crps_row[sysname] = CL.crps_samples(Y, y)
                del Y, S
            boots = {k: CL.block_boot(crps_row[k], crps_row['A'], row_cluster)
                     for k in per if k != 'A'}
            res[ev] = {'n': n, 'scores': per, 'bootstrap_vs_A': boots}
            print(f'  {cls:11s} {ev} n={n:5d} ' + ' '.join(
                f'{k}: CRPS={per[k]["crps"]:.4f} '
                f'rPIT={per[k]["randomised_pit"]["chi2"]:.1f}'
                for k in SYSTEMS if k in per))
            OUT[cls] = res
            json.dump(OUT, open(f'{HERE}/p4d_downstream.json', 'w'), indent=1)
        OUT[cls] = res
        json.dump(OUT, open(f'{HERE}/p4d_downstream.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4d_downstream.json')


if __name__ == '__main__':
    main()
