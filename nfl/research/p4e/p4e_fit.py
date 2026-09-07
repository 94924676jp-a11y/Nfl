"""P4E candidate: a LEARNED centre for the additive share weight.

Everything downstream of the weight is P4C's, untouched. The only change is
what `W`'s centre is: P4C uses `ewma(prior appeared shares)` with a flat
position-prior fallback; a candidate uses a ridge fit on strictly-prior
information.

Two disciplines that are easy to get wrong and are not optional here:

  * the additive residual pool must be OUT OF FOLD. P4C's pool is honest by
    accident -- an EWMA is not fitted, so its training residuals are its
    out-of-sample residuals. A fitted centre's in-sample residuals are
    optimistically small, and resampling them would hand the candidate a
    narrower predictive distribution that it has not earned. So residuals are
    collected by expanding-window replay INSIDE the training block.

  * the ridge penalty is chosen on an inner validation season inside the
    training block, never on the evaluation season.
"""
import collections
import numpy as np

import p4c_build as CB
import p4c_lib as CL
import p4e_build as PB

LAMBDAS = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)


def _fit(X, y, lam):
    mu = X.mean(0)
    sd = X.std(0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Z = (X - mu) / sd
    n, p = Z.shape
    A = Z.T @ Z + lam * n / max(p, 1) * np.eye(p)
    b = np.linalg.solve(A, Z.T @ (y - y.mean()))
    return {'mu': mu, 'sd': sd, 'b': b, 'y0': float(y.mean())}


def _pred(f, X):
    return f['y0'] + ((X - f['mu']) / f['sd']) @ f['b']


def _train_rows(sub, upto):
    """Appeared rows with a share, in seasons < upto. The fit target is the
    CONDITIONAL share given appearance, matching P4C's residual pool."""
    return [r for r in sub if r['season'] < upto and r['appeared']
            and r.get('s_carries') is not None]


def fit_centre(sub, ev, blocks, seasons):
    """Return (fit, lam, oof_resid_by_position, diagnostics)."""
    tr_seasons = sorted(s for s in seasons if s < ev)
    tr = _train_rows(sub, ev)
    X, feats = PB.design(tr, blocks)
    y = np.array([r['s_carries'] for r in tr], np.float64)

    # ---- inner validation: last training season, fitted on the ones before --
    inner = tr_seasons[-1]
    ia = [i for i, r in enumerate(tr) if r['season'] < inner]
    ib = [i for i, r in enumerate(tr) if r['season'] == inner]
    if len(ia) >= 200 and len(ib) >= 200:
        best, lam = None, LAMBDAS[0]
        for L_ in LAMBDAS:
            f = _fit(X[ia], y[ia], L_)
            e = float(np.mean((y[ib] - _pred(f, X[ib])) ** 2))
            if best is None or e < best:
                best, lam = e, L_
        inner_note = f'inner season {inner}, n_fit {len(ia)}, n_val {len(ib)}'
    else:
        lam, inner_note = 1.0, ('inner validation not identified '
                                f'(n_fit {len(ia)}, n_val {len(ib)}); lam=1.0')

    fit = _fit(X, y, lam)

    # ---- out-of-fold residual pool, expanding window inside training --------
    pool = collections.defaultdict(list)
    for t in tr_seasons[1:]:
        ja = [i for i, r in enumerate(tr) if r['season'] < t]
        jb = [i for i, r in enumerate(tr) if r['season'] == t]
        if len(ja) < 200 or not jb:
            continue
        f = _fit(X[ja], y[ja], lam)
        p = np.clip(_pred(f, X[jb]), 0.0, 1.0)
        for k, i in enumerate(jb):
            pool[tr[i]['position']].append(float(y[i] - p[k]))
    diag = {'lam': lam, 'inner': inner_note, 'n_train': len(tr),
            'n_features': X.shape[1], 'features': feats,
            'oof_pool_n': {k: len(v) for k, v in pool.items()},
            'oof_pool_seasons': tr_seasons[1:]}
    return fit, {k: np.array(v, np.float32) for k, v in pool.items()}, diag


def weights(cellv, fit, pool, blocks, seed_rng):
    """P4C's additive weight with a learned centre. Same rng seed as the
    control, so the two are compared on the same draw sequence."""
    te = cellv['te']
    X, _ = PB.design(te, blocks)
    mu = np.clip(_pred(fit, X), 0.0, 1.0).astype(np.float32)
    positions = [r['position'] for r in te]
    fallback = (np.concatenate([v for v in pool.values()]) if pool
                else np.zeros(1, np.float32))
    W = mu[:, None] + CB._resample(pool, positions, cellv['n'], CL.M_DRAWS,
                                   seed_rng, fallback)
    np.clip(W, 0.0, 1.0, out=W)
    return W, mu
