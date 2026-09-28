#!/usr/bin/env python3.12
"""Least squares with cluster-robust standard errors, on the standard library.

WHY CLUSTERED ERRORS ARE THE DEFAULT HERE AND NOT AN OPTION. Football observations arrive in
groups: two clubs share a game, a club's weeks share a coach, players in a week share weather and
game scripts. A naive standard error treats those as independent and understates uncertainty -- this
project has already measured that error at roughly threefold on prop grading (pooled naive 0.587pp
against 1.359pp clustered by player-game). Any `ols()` here that is given a cluster key reports the
cluster-robust error, and a caller who omits the key gets a result that says NAIVE_SE_ONLY so it
cannot be quoted as though it were robust.

No numpy: Gaussian elimination with partial pivoting on the normal equations. For the handful of
regressors these models use that is exact enough, and it keeps the warehouse dependency-free.
"""
from __future__ import annotations

import math


def _solve(A, b):
    """Gaussian elimination with partial pivoting. Returns None when singular."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        if abs(M[piv][c]) < 1e-12:
            return None
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / pv
            if f:
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def _inv(A):
    n = len(A)
    out = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        col = _solve(A, e)
        if col is None:
            return None
        out.append(col)
    # out is the transpose of the inverse's columns
    return [[out[j][i] for j in range(n)] for i in range(n)]


def ols(rows, y_name, x_names, cluster=None, intercept=True):
    """Fit y on x_names. rows: list of dicts. Returns coefficients, SEs and diagnostics.

    Rows with a missing or non-numeric value on any used field are DROPPED and counted, never
    imputed. The count is reported so a silent sample collapse is visible.
    """
    used, dropped = [], 0
    for r in rows:
        # NUMERIC IS REQUIRED OF THE RESPONSE AND THE REGRESSORS ONLY. The cluster key is a LABEL
        # -- a game_id is a string by nature -- and the first version required it to be numeric,
        # which silently dropped every row and reported NOT_IDENTIFIED on twelve quantities that
        # were fully populated.
        vals = [r.get(y_name)] + [r.get(x) for x in x_names]
        if any(v is None or isinstance(v, (str, bool))
               or (isinstance(v, float) and v != v) for v in vals):
            dropped += 1
            continue
        if cluster is not None and r.get(cluster) in (None, ''):
            dropped += 1
            continue
        used.append(r)
    n = len(used)
    k = len(x_names) + (1 if intercept else 0)
    if n <= k + 2:
        return {'state': 'NOT_IDENTIFIED', 'n': n, 'n_dropped': dropped,
                'reason': f'{n} usable rows for {k} parameters'}
    X = [([1.0] if intercept else []) + [float(r[x]) for x in x_names] for r in used]
    Y = [float(r[y_name]) for r in used]
    XtX = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[i][a] * Y[i] for i in range(n)) for a in range(k)]
    beta = _solve([row[:] for row in XtX], Xty[:])
    if beta is None:
        return {'state': 'NOT_IDENTIFIED', 'n': n, 'reason': 'singular normal equations'}
    resid = [Y[i] - sum(beta[a] * X[i][a] for a in range(k)) for i in range(n)]
    ybar = sum(Y) / n
    sst = sum((v - ybar) ** 2 for v in Y)
    sse = sum(e * e for e in resid)
    inv = _inv([row[:] for row in XtX])
    if inv is None:
        return {'state': 'NOT_IDENTIFIED', 'n': n, 'reason': 'singular XtX'}
    names = (['intercept'] if intercept else []) + list(x_names)
    if cluster is None:
        s2 = sse / (n - k)
        se = [math.sqrt(max(0.0, s2 * inv[a][a])) for a in range(k)]
        se_kind = 'NAIVE_SE_ONLY'
        n_clusters = None
    else:
        groups = {}
        for i, r in enumerate(used):
            groups.setdefault(r[cluster], []).append(i)
        meat = [[0.0] * k for _ in range(k)]
        for idx in groups.values():
            u = [sum(X[i][a] * resid[i] for i in idx) for a in range(k)]
            for a in range(k):
                for b in range(k):
                    meat[a][b] += u[a] * u[b]
        g = len(groups)
        scale = (g / max(1, g - 1)) * ((n - 1) / max(1, n - k))
        V = [[scale * sum(inv[a][c] * meat[c][d] * inv[d][b]
                          for c in range(k) for d in range(k)) for b in range(k)]
             for a in range(k)]
        se = [math.sqrt(max(0.0, V[a][a])) for a in range(k)]
        se_kind = f'CLUSTER_ROBUST_BY_{cluster}'
        n_clusters = g
    return {
        'state': 'FITTED', 'n': n, 'n_dropped': dropped,
        'coef': {names[a]: round(beta[a], 6) for a in range(k)},
        'se': {names[a]: round(se[a], 6) for a in range(k)},
        't': {names[a]: (round(beta[a] / se[a], 3) if se[a] > 0 else None) for a in range(k)},
        'r2': round(1.0 - sse / sst, 5) if sst > 0 else None,
        'rmse': round(math.sqrt(sse / n), 5),
        'se_kind': se_kind, 'n_clusters': n_clusters,
        'SE_SEMANTICS': ('a naive standard error treats club-games in the same game as independent '
                         'and understates uncertainty; measured at roughly threefold elsewhere in '
                         'this project. Quote the cluster-robust figure.'),
    }


def predict(fit, x):
    if fit.get('state') != 'FITTED':
        return None
    c = fit['coef']
    v = c.get('intercept', 0.0)
    for name, val in x.items():
        if name in c:
            if val is None:
                return None
            v += c[name] * float(val)
    return v


def quantiles(vals, qs=(0.05, 0.25, 0.5, 0.75, 0.95)):
    v = sorted(x for x in vals if x is not None and not isinstance(x, str))
    if not v:
        return {}
    out = {}
    for q in qs:
        i = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
        out[f'p{int(q * 100)}'] = v[i]
    return out
