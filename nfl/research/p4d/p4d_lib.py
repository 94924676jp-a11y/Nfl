"""P4D: appearance ranking, recalibration, and the metrics that judge them.

Nothing here touches the P4C opportunity machinery. The appearance probability
is the only component P4D changes, and the downstream runner imports P4C
unmodified so that stays true by construction rather than by intention.
"""
import bisect, collections, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.abspath(os.path.join(HERE, '..', 'p1')),
          os.path.abspath(os.path.join(HERE, '..', 'p2')),
          os.path.abspath(os.path.join(HERE, '..', 'p3')),
          os.path.abspath(os.path.join(HERE, '..', 'p4b')),
          os.path.abspath(os.path.join(HERE, '..', 'p4c')),
          HERE, '/home/user/nfl'):
    sys.path.insert(0, p)
import stage_a as A                                            # noqa: E402
import p3_features as F                                        # noqa: E402

EVAL = [2022, 2023, 2024, 2025]
POSALL = ('WR', 'TE', 'RB', 'QB')
EPS = 1e-12
# Pre-declared in predeclaration_p4d.md section 8, before any result.
BANDS = [(0.00, 0.25), (0.25, 0.50), (0.50, 0.80), (0.80, 0.95), (0.95, 1.01)]
BANDS_P4C = [(0.00, 0.50), (0.50, 0.80), (0.80, 0.95), (0.95, 1.01)]
MIDLO, MIDHI = 0.25, 0.80
FEATURE_BLOCKS = ('streak', 'long_window', 'trajectory', 'depth_of_history',
                  'prior_injury_history', 'teammate_context')


# ---------------------------------------------------------------------------
def fit_logistic_converged(X, y, l2=1.0, iters=60, tol=1e-11):
    """Same model, same penalty, actually solved. Newton with the identical
    standardisation and the identical unpenalised intercept as
    stage_a.fit_logistic, so A1 differs from A in the OPTIMISER and in nothing
    else."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    mu = X.mean(0); sd = X.std(0); sd[sd == 0] = 1.0
    mu[0] = 0.0; sd[0] = 1.0
    Xs = (X - mu) / sd
    n, d = Xs.shape
    w = np.zeros(d)
    R = l2 * np.eye(d) / n
    R[0, 0] = 0.0
    for _ in range(iters):
        z = np.clip(Xs @ w, -30, 30)
        p = 1 / (1 + np.exp(-z))
        g = Xs.T @ (p - y) / n + R @ w
        W = np.maximum(p * (1 - p), 1e-10)
        H = (Xs * W[:, None]).T @ Xs / n + R + 1e-10 * np.eye(d)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
        w_new = w - step
        if np.abs(w_new - w).max() < tol:
            w = w_new
            break
        w = w_new
    return {'w': w, 'mu': mu, 'sd': sd}


def predict(model, X):
    return A.predict(model, X)


# ---------------------------------------------------------------------------
# NEW FEATURE BLOCKS. Every value is computed from STRICTLY EARLIER games of
# the same player, or from the team's PREVIOUS game. Nothing reads the row's
# own outcome and nothing reads a later `ord`.
# ---------------------------------------------------------------------------
def attach_p4d_features(rows):
    hist = collections.defaultdict(list)
    prev_game_appeared = collections.defaultdict(dict)   # (team,pos) -> ord -> n
    for r in sorted(rows, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        past = hist[pid]
        ap = [x['appeared'] for x in past]
        ss = [x.get('snap_share') for x in past if x.get('snap_share') is not None]

        # -- streak -------------------------------------------------------
        st = 0
        for v in reversed(ap):
            if v:
                st += 1
            else:
                break
        best = cur = 0
        for v in ap:
            cur = cur + 1 if v else 0
            best = max(best, cur)
        r['g_streak'] = st
        r['g_longest_streak'] = best

        # -- long_window --------------------------------------------------
        r['g_rate8'] = float(np.mean(ap[-8:])) if ap else None
        r['g_rate10'] = float(np.mean(ap[-10:])) if ap else None
        r['g_rate_career'] = float(np.mean(ap)) if ap else None
        sea = [x['appeared'] for x in past if x['season'] == r['season']]
        r['g_rate_season'] = float(np.mean(sea)) if sea else None
        r['g_n_season'] = len(sea)

        # -- trajectory ---------------------------------------------------
        def ew(v, hl):
            if not v:
                return None
            lam = 0.5 ** (1 / hl); n = d = 0.0; w = 1.0
            for x in reversed(v):
                n += w * x; d += w; w *= lam
            return n / d
        e3, e8 = ew(ss, 3.0), ew(ss, 8.0)
        r['g_snap_traj'] = (e3 - e8) if (e3 is not None and e8 is not None) else None
        r['g_snap_step'] = (float(np.mean(ss[-3:])) - float(np.mean(ss[-6:-3]))
                            if len(ss) >= 6 else None)
        a3, a8 = ew([float(v) for v in ap], 3.0), ew([float(v) for v in ap], 8.0)
        r['g_app_traj'] = (a3 - a8) if (a3 is not None and a8 is not None) else None

        # -- depth_of_history ---------------------------------------------
        r['g_week'] = r['week']

        # -- prior_injury_history -----------------------------------------
        inj = [1.0 if x.get('f_inj_available') else 0.0 for x in past]
        r['g_inj_count'] = float(np.sum(inj)) if inj else 0.0
        r['g_inj_rate'] = float(np.mean(inj)) if inj else None
        # -- teammate_context ----------------------------------------------
        hist[pid].append(r)
    # position-group competition depth, from the team's PREVIOUS game only
    by_team = collections.defaultdict(list)
    for r in rows:
        by_team[r['team']].append(r)
    for tm, rs in by_team.items():
        ords = sorted({x['ord'] for x in rs})
        prev_of = {o: (ords[i - 1] if i else None) for i, o in enumerate(ords)}
        cnt = collections.Counter()
        for x in rs:
            if x['appeared']:
                cnt[(x['ord'], x['position'])] += 1
        for x in rs:
            p_ = prev_of[x['ord']]
            x['g_pos_depth_prev'] = (float(cnt[(p_, x['position'])])
                                     if p_ is not None else None)
    return rows


REPORT_LEVELS = ['Out', 'Doubtful', 'Questionable']


def featurise_p4d(r, use_injury, groups, blocks):
    """P3 design row plus the P4D blocks. A block is added or removed whole."""
    f = list(F.featurise_p3(r, use_injury, groups))

    def num(v, d=0.0):
        f.append(d if v is None else float(v))
        f.append(1.0 if v is None else 0.0)

    if 'streak' in blocks:
        f.append(min(r.get('g_streak') or 0, 12) / 12.0)
        f.append(min(r.get('g_longest_streak') or 0, 20) / 20.0)
    if 'long_window' in blocks:
        num(r.get('g_rate8')); num(r.get('g_rate10'))
        num(r.get('g_rate_career')); num(r.get('g_rate_season'))
        f.append(min(r.get('g_n_season') or 0, 17) / 17.0)
    if 'trajectory' in blocks:
        num(r.get('g_snap_traj')); num(r.get('g_snap_step'))
        num(r.get('g_app_traj'))
    if 'depth_of_history' in blocks:
        n = min(r.get('f_n_prior') or 0, 20) / 20.0
        re_ = r.get('f_rate_ewma'); se = r.get('f_snap_ewma')
        f.append(n * (0.0 if re_ is None else float(re_)))
        f.append(n * (0.0 if se is None else float(se)))
        f.append((1.0 - n) * (0.0 if re_ is None else float(re_)))
        f.append(1.0 / (1.0 + (r.get('f_n_prior') or 0)))
        f.append(min(r.get('g_week') or 0, 18) / 18.0)
    if 'prior_injury_history' in blocks:
        f.append(min(r.get('g_inj_count') or 0, 15) / 15.0)
        num(r.get('g_inj_rate'))
        if use_injury:
            pr = r.get('f_prev_report')
            for L in REPORT_LEVELS:
                f.append(1.0 if pr == L else 0.0)
            f.append(1.0 if pr is None else 0.0)
    if 'teammate_context' in blocks:
        num(r.get('g_pos_depth_prev'))
    if 'DEPTH_CHART_DIAGNOSTIC' in blocks:
        d = r.get('f_depth')
        f.append(0.0 if d is None else min(float(d), 5.0) / 5.0)
        f.append(1.0 if d is None else 0.0)
        for k in (1, 2, 3):
            f.append(1.0 if d == k else 0.0)
    return f


# ---------------------------------------------------------------------------
# CALIBRATORS. Every one is MONOTONE, so none of them can change any ranking.
# ---------------------------------------------------------------------------
def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_platt(p, y):
    """Logistic recalibration on the logit. Two parameters, Newton."""
    z = _logit(p)
    X = np.column_stack([np.ones(len(z)), z])
    w = np.zeros(2)
    for _ in range(100):
        q = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (q - y) / len(y)
        W = np.maximum(q * (1 - q), 1e-10)
        H = (X * W[:, None]).T @ X / len(y) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        w = w - step
        if np.abs(step).max() < 1e-12:
            break
    return {'kind': 'platt', 'w': w}


def fit_isotonic(p, y, min_bin=1):
    """Pool-adjacent-violators. Exact, monotone, non-parametric."""
    o = np.argsort(p, kind='mergesort')
    ps, ys = np.asarray(p, float)[o], np.asarray(y, float)[o]
    val = list(ys); wt = [1.0] * len(ys)
    i = 0
    while i < len(val) - 1:
        if val[i] <= val[i + 1] + 1e-15:
            i += 1
            continue
        nw = wt[i] + wt[i + 1]
        nv = (val[i] * wt[i] + val[i + 1] * wt[i + 1]) / nw
        val[i:i + 2] = [nv]; wt[i:i + 2] = [nw]
        i = max(i - 1, 0)
    xs, vs, k = [], [], 0
    for v, w in zip(val, wt):
        k += int(round(w))
        xs.append(ps[min(k, len(ps)) - 1]); vs.append(v)
    return {'kind': 'isotonic', 'x': np.array(xs), 'v': np.array(vs)}


def fit_spline(p, y, k=12):
    """Monotone spline: isotonic on k quantile knots, then linear interpolation
    between knot means. Smoother than raw PAVA, still monotone by
    construction."""
    z = _logit(p)
    qs = np.quantile(z, np.linspace(0, 1, k + 1))
    qs = np.unique(qs)
    idx = np.clip(np.searchsorted(qs, z, 'right') - 1, 0, len(qs) - 2)
    mz, my, ws = [], [], []
    for b in range(len(qs) - 1):
        m = idx == b
        if m.sum() >= 20:
            mz.append(float(z[m].mean())); my.append(float(y[m].mean()))
            ws.append(float(m.sum()))
    if len(mz) < 3:
        return fit_platt(p, y)
    iso = fit_isotonic(np.array(mz), np.array(my))
    yy = np.interp(np.array(mz), iso['x'], iso['v'])
    # enforce monotonicity after interpolation
    for i in range(1, len(yy)):
        yy[i] = max(yy[i], yy[i - 1])
    return {'kind': 'spline', 'z': np.array(mz), 'y': yy}


def apply_cal(cal, p):
    if cal is None:
        return np.asarray(p, float)
    if cal['kind'] == 'platt':
        z = _logit(p)
        return 1 / (1 + np.exp(-np.clip(cal['w'][0] + cal['w'][1] * z, -30, 30)))
    if cal['kind'] == 'isotonic':
        return np.clip(np.interp(np.asarray(p, float), cal['x'], cal['v']),
                       1e-6, 1 - 1e-6)
    if cal['kind'] == 'spline':
        return np.clip(np.interp(_logit(p), cal['z'], cal['y']),
                       1e-6, 1 - 1e-6)
    raise ValueError(cal['kind'])


CAL_FAMILIES = {'platt': fit_platt, 'isotonic': fit_isotonic, 'spline': fit_spline}


# ---------------------------------------------------------------------------
def auc(y, p):
    y = np.asarray(y); p = np.asarray(p, float)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return None
    r = np.empty(len(p))
    o = np.argsort(p, kind='mergesort')
    ps = p[o]
    i = 0
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[i]:
            j += 1
        r[o[i:j + 1]] = (i + j) / 2.0 + 1
        i = j + 1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def pr_auc(y, p):
    y = np.asarray(y); p = np.asarray(p, float)
    o = np.argsort(-p, kind='mergesort')
    ys = y[o]
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
    prec = tp / np.maximum(tp + fp, 1)
    rec = tp / max(ys.sum(), 1)
    return float(np.sum(np.diff(np.concatenate([[0.0], rec])) * prec))


def cal_slope_intercept(y, p):
    """Logistic regression of the outcome on the logit of the forecast.
    slope 1 / intercept 0 is perfect; slope < 1 means over-dispersed
    probabilities, slope > 1 means UNDER-dispersed (compressed)."""
    z = _logit(p)
    X = np.column_stack([np.ones(len(z)), z])
    w = np.zeros(2)
    for _ in range(100):
        q = 1 / (1 + np.exp(-np.clip(X @ w, -30, 30)))
        g = X.T @ (q - y) / len(y)
        W = np.maximum(q * (1 - q), 1e-10)
        H = (X * W[:, None]).T @ X / len(y) + 1e-9 * np.eye(2)
        step = np.linalg.solve(H, g)
        w = w - step
        if np.abs(step).max() < 1e-12:
            break
    return {'intercept': float(w[0]), 'slope': float(w[1])}


def reliability(y, p, bands):
    out = []
    for lo, hi in bands:
        m = (p >= lo) & (p < hi)
        if m.sum() == 0:
            continue
        out.append({'band': f'{lo:.2f}-{min(hi,1.0):.2f}', 'n': int(m.sum()),
                    'mean_p': float(p[m].mean()),
                    'observed': float(y[m].mean()),
                    'gap': float(p[m].mean() - y[m].mean()),
                    'auc_within': auc(y[m], p[m])})
    return out


def ece_mce(y, p, bins=10):
    idx = np.clip((p * bins).astype(int), 0, bins - 1)
    e = m = 0.0
    for b in range(bins):
        k = idx == b
        if k.sum() == 0:
            continue
        gap = abs(p[k].mean() - y[k].mean())
        e += k.sum() / len(y) * gap
        m = max(m, gap)
    return float(e), float(m)


def appearance_metrics(y, p):
    y = np.asarray(y, float); p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    e, mx = ece_mce(y, p)
    mid = (p >= MIDLO) & (p < MIDHI)
    ci = cal_slope_intercept(y, p)
    return {
        'n': int(len(y)), 'mean_p': float(p.mean()), 'observed': float(y.mean()),
        'bias': float(p.mean() - y.mean()),
        'brier': float(((p - y) ** 2).mean()),
        'log_loss': float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()),
        'auc': auc(y, p), 'pr_auc': pr_auc(y, p),
        'cal_intercept': ci['intercept'], 'cal_slope': ci['slope'],
        'ece': e, 'mce': mx,
        'n_mid': int(mid.sum()),
        'mid_auc': auc(y[mid], p[mid]) if mid.sum() > 30 else None,
        'mid_brier': float(((p[mid] - y[mid]) ** 2).mean()) if mid.sum() else None,
        'mid_gap': float(p[mid].mean() - y[mid].mean()) if mid.sum() else None,
        'reliability': reliability(y, p, BANDS),
        'reliability_p4c_bands': reliability(y, p, BANDS_P4C),
    }
