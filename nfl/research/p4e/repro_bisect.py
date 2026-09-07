"""Isolate the ~1e-5 baseline-reproduction discrepancy.

Replicates run_p4c.py's carries/system-C code path LITERALLY, in the same
process as p4e_build's cell(), and compares every intermediate array.
Only scratchpad module paths are used.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as PB                                          # noqa: E402
import p4c_lib as L                                             # noqa: E402
import p4c_build as CB                                          # noqa: E402
from run_p4c import groups_of                                   # noqa: E402

EV = 2024
CLS = 'carries'


def p4c_path(rows, vol, pa, sub, ev):
    """Verbatim from run_p4c.main(), reduced to system C."""
    c = L.CLASSES[CLS]
    mode = c['mode']; skey, ykey = c['share'], c['y']
    store = vol[(c['den'], ev)]
    par = CB.fit_params(sub, CLS, ev, rows)
    te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
          and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
          and r['_C'] is not None
          and (r['team'], r['ord']) in store['index']]
    te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    n = len(te)
    starts, counts, gkeys = groups_of(te)
    G = len(starts)
    y = np.array([r[ykey] for r in te], float)
    C = np.array([r['_C'] for r in te], np.float32)
    positions = [r['position'] for r in te]
    p_app = np.array([pa[id(r)] for r in te], np.float32)
    ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
    T = store['B'][ti]
    rngA = np.random.default_rng(L.SEED + 1009)
    Ad = (rngA.random((n, L.M_DRAWS), np.float32) < p_app[:, None])
    si = ['A', 'B', 'C', 'C2', 'D_dir', 'D_sln', 'D_emp', 'E'].index('C')
    rng = np.random.default_rng(L.SEED + 3000 + 17 * si)
    W = CB.gen_weights('C', C, positions, par, CLS, n, L.M_DRAWS, rng)
    mass = CB.mass_draws('C', par, G, L.M_DRAWS,
                         np.random.default_rng(L.SEED + 5000 + si))
    avail = (1.0 - mass) if mode == 'simplex' else mass
    S, other, nbind = L.allocate(W, Ad, starts, counts, 'occupancy', avail)
    Y = (T * S).astype(np.float32)
    crps = float(L.crps_samples(Y, y).mean())
    return dict(n=n, y=y, C=C, p_app=p_app, Ad=Ad, T=T, W=W, mass=mass,
                avail=avail, S=S, Y=Y, crps=crps, te=te, starts=starts,
                counts=counts, par=par)


def cmp(name, a, b):
    a = np.asarray(a); b = np.asarray(b)
    if a.shape != b.shape:
        print(f'  {name:10s} SHAPE {a.shape} vs {b.shape}')
        return
    same = np.array_equal(a, b)
    d = float(np.abs(a.astype(np.float64) - b.astype(np.float64)).max())
    print(f'  {name:10s} dtype {str(a.dtype):8s}/{str(b.dtype):8s} '
          f'bit-identical={same}  maxabs={d:.3e}')


def main():
    rows, vol, pa, sub, D = PB.load_all()
    print('--- WITHOUT attach_features ---')
    a = p4c_path(rows, vol, pa, sub, EV)
    b = PB.cell(rows, vol, pa, sub, EV)
    cnt, S2 = PB.counts_from_weights(b, b['W_ctrl'])
    crps2 = float(L.crps_samples(cnt, b['y']).mean())
    print(f'  p4c crps  {a["crps"]:.12f}')
    print(f'  p4e crps  {crps2:.12f}')
    print(f'  published {PB.PUBLISHED[EV]:.12f}')
    for k, v in (('y', b['y']), ('C', b['C_pre']), ('p_app', b['p_app']),
                 ('Ad', b['Ad']), ('T', b['T']), ('W', b['W_ctrl'])):
        cmp(k, a[k], v)
    cmp('avail', a['avail'], b['avail'])
    cmp('S', a['S'], S2)
    cmp('Y', a['Y'], cnt)

    print('\n--- WITH attach_features (as run_p4e_diag does) ---')
    PB.attach_features(sub)
    a2 = p4c_path(rows, vol, pa, sub, EV)
    b2 = PB.cell(rows, vol, pa, sub, EV)
    cnt2, _ = PB.counts_from_weights(b2, b2['W_ctrl'])
    print(f'  p4c crps  {a2["crps"]:.12f}')
    print(f'  p4e crps  {float(L.crps_samples(cnt2, b2["y"]).mean()):.12f}')
    print(f'  n before {a["n"]}  n after {a2["n"]}')
    cmp('C(pre/post attach)', a['C'], a2['C'])


main()
