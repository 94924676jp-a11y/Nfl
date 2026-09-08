"""Mechanism check for the voided probe. p_fit._fit penalises with
lam*n/p, so the per-column penalty falls as columns are added: p=2 gives
0.500*n, p=7 gives 0.143*n. Adding ANY five columns therefore relaxes the
penalty on p_ewma1/p_ewma2 by 3.5x. Pad the control with five pure-noise
columns and the gap should close."""
import collections, json, os, sys
import numpy as np
S = os.path.dirname(os.path.abspath(__file__))
R = '/home/user/nfl/nfl/research'
for p in (f'{R}/p1s', f'{R}/s2', f'{R}/p4c', f'{R}/p4e', f'{R}/s4'):
    sys.path.insert(0, p)
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import p_lib as L, p_fit as PF, p4c_build as CB
rows, sub = L.load(); pa = CB.appearance(rows); L.attach(sub, pa)
CTRL = ['p_ewma1', 'p_ewma2']
rng = np.random.default_rng(20260908)


def ok(r, ev):
    return L.eligible(r, ev) and all(r.get(f) is not None for f in CTRL)


def X(rs, npad):
    A = np.array([[float(r[f]) for f in CTRL] for r in rs], np.float64)
    return A if not npad else np.hstack([A, rng.standard_normal((len(rs), npad))])


out = {}
for npad in (0, 5):
    pr, yy = [], []
    for ev in L.EVAL:
        tr = [r for r in sub if r['season'] < ev and ok(r, None)]
        te = [r for r in sub if ok(r, ev) and r['season'] == ev]
        y = np.array([r[L.TARGET] for r in tr])
        f = PF._fit(X(tr, npad), y, 1.0)
        pr.append(np.clip(PF._pred(f, X(te, npad)), 0, 1))
        yy.append(np.array([r[L.TARGET] for r in te]))
    pr = np.concatenate(pr); yy = np.concatenate(yy)
    m = float(np.mean(np.abs(pr - yy)))
    out[f'ctrl_plus_{npad}_noise_cols'] = {'n': int(len(yy)), 'mae': m,
                                           'effective_penalty': f'1.0*n/{2+npad}'}
    print(f'  control + {npad} pure-noise columns: MAE {m:.6f}  '
          f'(penalty 1.0*n/{2+npad})')
a = out['ctrl_plus_0_noise_cols']['mae']; b = out['ctrl_plus_5_noise_cols']['mae']
out['rel_pct_from_noise_alone'] = 100.0 * (a - b) / a
print(f'\n  MAE improvement from FIVE PURE-NOISE COLUMNS ALONE: '
      f'{100*(a-b)/a:+.4f}%')
json.dump(out, open(f'{S}/probe_mechanism.json', 'w'), indent=1)
