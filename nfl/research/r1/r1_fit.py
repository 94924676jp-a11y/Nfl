"""R1 ladder: ridge on prior-only features, under the pre-declared ceiling.

Complexity ceiling from predeclaration_r1.md section 7: linear/ridge only, at
most 48 design columns including missingness flags, ridge penalty from a fixed
grid selected on an inner validation season inside the training block.

Missingness flags are emitted ONLY for features that can actually be None, and
the team-context and teammate-context groups share one flag each because they go
missing together (a team's first game of the panel). That keeps the design at 34
columns rather than 54, under the ceiling rather than through it.
"""
import collections, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r1_lib as L                                             # noqa: E402

LAMBDAS = (0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
MAX_COLS = 48

BASE = ['h_ewma3_w', 'h_ewma8_w', 'h_expanding_w', 'h_pos_mean', 'h_eff_n',
        'h_sd']
BLOCKS = {
    'A': ['h_targets_career', 'h_targets_last8', 'h_games', 'h_recency',
          'h_prev_season_w'],
    'B': ['h_P_ewma2', 'h_P_step', 'h_P_sd', 'p_app', 'role_up', 'role_down'],
    'C': ['h_team_top_share', 'h_team_hhi', 'h_team_dropbacks'],
    'D': ['h_mate_P', 'h_mate_S', 'h_vacated_P'],
    'E': ['is_TE', 'is_RB', 'TExbase', 'RBxbase'],
}
NEEDS_FLAG = {'h_sd', 'h_prev_season_w', 'h_P_step', 'h_P_sd', 'p_app'}
GROUP_FLAG = {'C': ['h_team_top_share', 'h_team_hhi', 'h_team_dropbacks'],
              'D': ['h_mate_P', 'h_mate_S', 'h_vacated_P']}


def value(r, f, pa):
    if f == 'p_app':
        return pa.get(id(r))
    if f == 'role_up':
        return 1.0 if r.get('h_role') == 'up' else 0.0
    if f == 'role_down':
        return 1.0 if r.get('h_role') == 'down' else 0.0
    if f == 'is_TE':
        return 1.0 if r['position'] == 'TE' else 0.0
    if f == 'is_RB':
        return 1.0 if r['position'] == 'RB' else 0.0
    if f == 'TExbase':
        b = r.get('h_ewma3_w')
        return (b or 0.0) if r['position'] == 'TE' else 0.0
    if f == 'RBxbase':
        b = r.get('h_ewma3_w')
        return (b or 0.0) if r['position'] == 'RB' else 0.0
    return r.get(f)


def design(rs, blocks, pa):
    feats = list(BASE)
    for b in blocks:
        feats += BLOCKS[b]
    flags = [f for f in feats if f in NEEDS_FLAG]
    gflags = [b for b in blocks if b in GROUP_FLAG]
    ncol = len(feats) + len(flags) + len(gflags)
    if ncol > MAX_COLS:
        raise ValueError(f'COMPLEXITY_CEILING: {ncol} columns exceeds {MAX_COLS}')
    X = np.zeros((len(rs), ncol), np.float64)
    for i, r in enumerate(rs):
        j = 0
        for f in feats:
            v = value(r, f, pa)
            X[i, j] = 0.0 if v is None else float(v)
            j += 1
        for f in flags:
            v = value(r, f, pa)
            X[i, j] = 1.0 if v is None else 0.0
            j += 1
        for b in gflags:
            v = value(r, GROUP_FLAG[b][0], pa)
            X[i, j] = 1.0 if v is None else 0.0
            j += 1
    return X, feats, ncol


def _fit(X, y, lam):
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd < 1e-12, 1.0, sd)
    Z = (X - mu) / sd
    n, p = Z.shape
    A = Z.T @ Z + lam * n / max(p, 1) * np.eye(p)
    b = np.linalg.solve(A, Z.T @ (y - y.mean()))
    return {'mu': mu, 'sd': sd, 'b': b, 'y0': float(y.mean())}


def _pred(f, X):
    return f['y0'] + ((X - f['mu']) / f['sd']) @ f['b']


def fit_rung(sub, ev, blocks, pa, seasons):
    tr = [r for r in sub if r['season'] < ev and L.eligible(r)]
    X, feats, ncol = design(tr, blocks, pa)
    y = np.array([r['R_star'] for r in tr], np.float64)
    tr_seasons = sorted({r['season'] for r in tr})
    inner = tr_seasons[-1]
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
        lam, note = 1.0, f'inner validation not identified; lam=1.0'
    fit = _fit(X, y, lam)
    return fit, {'lam': lam, 'inner': note, 'n_train': len(tr),
                 'n_columns': ncol, 'features': feats}


def predict_rung(fit, rs, blocks, pa):
    X, _f, _n = design(rs, blocks, pa)
    return np.clip(_pred(fit, X), 0.0, 2.0)
