"""P ladder: ridge under the 48-column ceiling, plus the one pre-declared
monotonic family (isotonic recalibration of the control)."""
import collections, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p_lib as L                                              # noqa: E402

LAMBDAS = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
MAX_COLS = 48
BASE = ['p_ewma1', 'p_ewma2', 'p_ewma3', 'p_ewma5', 'p_ewma8', 'p_expanding',
        'p_last']
BLOCKS = {
    'A': ['p_var', 'p_trend', 'p_step', 'p_snap_prior', 'p_snap_expanding',
          'p_n', 'p_prev_season'],
    'B': ['p_app_prior', 'p_missed_run', 'p_n_games', 'p_stability', 'pa'],
    'C': ['p_mate_P_sum', 'p_mate_P_max', 'p_team_conc', 'p_vacated',
          'p_mate_step'],
    'D': ['p_team_dropbacks', 'p_team_n', 'p_team_stability'],
    'E': ['is_TE', 'is_RB', 'TExbase', 'RBxbase'],
}
NEEDS_FLAG = {'p_var', 'p_trend', 'p_step', 'p_prev_season', 'p_stability',
              'pa', 'p_snap_prior'}
GROUP_FLAG = {'C': 'p_mate_P_sum', 'D': 'p_team_dropbacks'}


def value(r, f, pa):
    if f == 'pa':
        return pa.get(id(r))
    if f == 'is_TE':
        return 1.0 if r['position'] == 'TE' else 0.0
    if f == 'is_RB':
        return 1.0 if r['position'] == 'RB' else 0.0
    if f == 'TExbase':
        return (r.get('p_ewma2') or 0.0) if r['position'] == 'TE' else 0.0
    if f == 'RBxbase':
        return (r.get('p_ewma2') or 0.0) if r['position'] == 'RB' else 0.0
    return r.get(f)


def design(rs, blocks, pa):
    feats = list(BASE)
    for b in blocks:
        feats += BLOCKS[b]
    flags = [f for f in feats if f in NEEDS_FLAG]
    gflags = [b for b in blocks if b in GROUP_FLAG]
    ncol = len(feats) + len(flags) + len(gflags)
    if ncol > MAX_COLS:
        raise ValueError(f'COMPLEXITY_CEILING: {ncol} exceeds {MAX_COLS}')
    X = np.zeros((len(rs), ncol), np.float64)
    for i, r in enumerate(rs):
        j = 0
        for f in feats:
            v = value(r, f, pa)
            X[i, j] = 0.0 if v is None else float(v)
            j += 1
        for f in flags:
            X[i, j] = 1.0 if value(r, f, pa) is None else 0.0
            j += 1
        for b in gflags:
            X[i, j] = 1.0 if value(r, GROUP_FLAG[b], pa) is None else 0.0
            j += 1
    return X, feats, ncol


def _fit(X, y, lam):
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Z = (X - mu) / sd
    n, p = Z.shape
    A = Z.T @ Z + lam * n / max(p, 1) * np.eye(p)
    return {'mu': mu, 'sd': sd, 'b': np.linalg.solve(A, Z.T @ (y - y.mean())),
            'y0': float(y.mean())}


def _pred(f, X):
    return f['y0'] + ((X - f['mu']) / f['sd']) @ f['b']


def fit_rung(sub, ev, blocks, pa):
    tr = [r for r in sub if r['season'] < ev and L.eligible(r)]
    X, feats, ncol = design(tr, blocks, pa)
    y = np.array([r[L.TARGET] for r in tr], np.float64)
    ts = sorted({r['season'] for r in tr})
    inner = ts[-1]
    ia = [i for i, r in enumerate(tr) if r['season'] < inner]
    ib = [i for i, r in enumerate(tr) if r['season'] == inner]
    if len(ia) >= 500 and len(ib) >= 500:
        best, lam = None, LAMBDAS[0]
        for lm in LAMBDAS:
            f = _fit(X[ia], y[ia], lm)
            e = float(np.mean((y[ib] - _pred(f, X[ib])) ** 2))
            if best is None or e < best:
                best, lam = e, lm
        note = f'inner season {inner}, n_fit {len(ia)}, n_val {len(ib)}'
    else:
        lam, note = 1.0, 'inner validation not identified; lam=1.0'
    return _fit(X, y, lam), {'lam': lam, 'inner': note, 'n_train': len(tr),
                             'n_columns': ncol, 'features': feats}


def predict_rung(fit, rs, blocks, pa):
    X, _f, _n = design(rs, blocks, pa)
    return np.clip(_pred(fit, X), 0.0, 1.0)


# ---- the ONE pre-declared monotonic family -------------------------------
def fit_isotonic(sub, ev, control):
    """Isotonic regression of realised P on the control forecast, prior seasons
    only. Pre-declared in the pre-registration and justified there by Stage 2's
    measured SD ratio of 0.85-0.90."""
    tr = [(control(r), r[L.TARGET]) for r in sub
          if r['season'] < ev and L.eligible(r) and control(r) is not None]
    if len(tr) < 500:
        return None
    tr.sort()
    x = np.array([a for a, _ in tr]); y = np.array([b for _, b in tr])
    # pool-adjacent-violators
    lvl = y.astype(float).copy()
    w = np.ones(len(y))
    i = 0
    while i < len(lvl) - 1:
        if lvl[i] <= lvl[i + 1]:
            i += 1
            continue
        nw = w[i] + w[i + 1]
        nv = (w[i] * lvl[i] + w[i + 1] * lvl[i + 1]) / nw
        lvl[i] = nv; w[i] = nw
        lvl = np.delete(lvl, i + 1); w = np.delete(w, i + 1)
        x = np.delete(x, i + 1)
        if i > 0:
            i -= 1
    return {'x': x, 'y': lvl}


def apply_isotonic(iso, v):
    if iso is None or v is None:
        return v
    return float(np.clip(np.interp(v, iso['x'], iso['y']), 0.0, 1.0))
