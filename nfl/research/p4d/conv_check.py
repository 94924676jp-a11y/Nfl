"""P4D step 0: is the incumbent Stage-A logistic regression CONVERGED?

Before adding a single feature or a single calibrator, check the thing itself.
stage_a.fit_logistic is plain gradient descent, fixed step 0.5, 300 iterations.
An under-fitted logistic regression is calibrated in the large almost
immediately (the intercept converges first) while its RANKING is still
compressed -- which is exactly the symptom P4C reported.
"""
import os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
for p in (os.path.abspath(os.path.join(HERE, '..', 'p1')),
          os.path.abspath(os.path.join(HERE, '..', 'p2')),
          os.path.abspath(os.path.join(HERE, '..', 'p3')),
          os.path.abspath(os.path.join(HERE, '..', 'p4c')),
          P4B, '/home/user/nfl'):
    sys.path.insert(0, p)
import stage_a as A
import p3_features as F

rows = pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))
POSALL = ('WR', 'TE', 'RB', 'QB')
cand = [r for r in rows if r['position'] in POSALL and (r.get('f_n_prior') or 0) >= 1]
for r in cand:
    r['y_app'] = 1 if r['appeared'] else 0
ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
ev = 2024
tr = [r for r in cand if r['season'] < ev]
X = np.array([F.featurise_p3(r, True, ALL) for r in tr], float)
y = np.array([r['y_app'] for r in tr], float)
print(f'training rows {len(y)}, features {X.shape[1]}, base rate {y.mean():.4f}')

mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
mu[0] = 0.0; sd[0] = 1.0
Xs = (X - mu) / sd
l2 = 1.0


def obj(w):
    z = np.clip(Xs @ w, -30, 30)
    p = 1 / (1 + np.exp(-z))
    ll = -(y * np.log(np.maximum(p, 1e-12))
           + (1 - y) * np.log(np.maximum(1 - p, 1e-12))).mean()
    return ll + 0.5 * l2 * (w[1:] ** 2).sum() / len(y)


def grad(w):
    p = 1 / (1 + np.exp(-np.clip(Xs @ w, -30, 30)))
    g = Xs.T @ (p - y) / len(y) + l2 * w / len(y)
    g[0] -= l2 * w[0] / len(y)
    return g


def gd(iters, lr=0.5):
    w = np.zeros(Xs.shape[1])
    for _ in range(iters):
        w -= lr * grad(w)
    return w


def newton(iters=50, tol=1e-12):
    w = np.zeros(Xs.shape[1])
    R = l2 * np.eye(Xs.shape[1]) / len(y)
    R[0, 0] = 0.0
    for i in range(iters):
        z = np.clip(Xs @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        W = p * (1 - p)
        H = (Xs * W[:, None]).T @ Xs / len(y) + R
        g = grad(w)
        try:
            step = np.linalg.solve(H + 1e-10 * np.eye(len(w)), g)
        except np.linalg.LinAlgError:
            break
        w_new = w - step
        if np.abs(w_new - w).max() < tol:
            w = w_new
            break
        w = w_new
    return w, i + 1


w300 = gd(300)
wstar, nit = newton()
print(f'\nincumbent  (GD, 300 iters, lr=0.5): objective {obj(w300):.6f}  '
      f'||grad||inf {np.abs(grad(w300)).max():.6e}  ||w|| {np.linalg.norm(w300):.4f}')
print(f'converged  (Newton, {nit} iters)   : objective {obj(wstar):.6f}  '
      f'||grad||inf {np.abs(grad(wstar)).max():.6e}  ||w|| {np.linalg.norm(wstar):.4f}')
print(f'\nobjective gap {obj(w300)-obj(wstar):+.6f} nats/row  '
      f'({100*(obj(w300)-obj(wstar))/obj(wstar):+.2f}% of the converged loss)')
print(f'coefficient norm ratio incumbent/converged: '
      f'{np.linalg.norm(w300)/np.linalg.norm(wstar):.4f}')
for k in (300, 1000, 3000, 10000, 30000):
    w = gd(k)
    print(f'   GD {k:6d} iters: obj {obj(w):.6f}  ||grad||inf '
          f'{np.abs(grad(w)).max():.3e}  ||w||/||w*|| '
          f'{np.linalg.norm(w)/np.linalg.norm(wstar):.4f}')

# what does this do to the predictions?
te = [r for r in cand if r['season'] == ev]
Xt = np.array([F.featurise_p3(r, True, ALL) for r in te], float)
yt = np.array([r['y_app'] for r in te], float)
Xts = (Xt - mu) / sd
for lbl, w in (('incumbent', w300), ('converged', wstar)):
    p = 1 / (1 + np.exp(-np.clip(Xts @ w, -30, 30)))
    o = np.argsort(p)
    auc = ((np.searchsorted(np.sort(p[yt == 0]), p[yt == 1], 'right')).sum()
           / ((yt == 1).sum() * (yt == 0).sum()))
    print(f'{lbl:10s} 2024: mean p {p.mean():.4f} (obs {yt.mean():.4f}) '
          f'sd {p.std():.4f} Brier {((p-yt)**2).mean():.5f} '
          f'logloss {-(yt*np.log(np.maximum(p,1e-12))+(1-yt)*np.log(np.maximum(1-p,1e-12))).mean():.5f} '
          f'AUC {auc:.4f} p01 {np.percentile(p,1):.4f} p99 {np.percentile(p,99):.4f}')
