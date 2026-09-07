"""P4C shared: constrained joint allocation, and the diagnostics for it.

TWO ACCOUNTING MODES, because the measurement in accounting.py says there are
two and not one.

  'simplex'    targets / carries / rz_carries. Mutually exclusive events; the
               full-panel share sum is exactly 1. Components are the modelled
               players PLUS an explicit OTHER (for carries that is mostly the
               quarterback, 15% of the pie -- structural, not noise).

  'occupancy'  snaps / pass_snaps. Eleven players occupy every snap, so the
               modelled WR/TE/RB shares sum to K ~ 4.89, K is itself random,
               and each individual share is separately capped at 1. There is no
               simplex here and forcing one would be wrong by a factor of five.
"""
import collections, math, os
import numpy as np

M_DRAWS = 1000
SEED = 20260907
EVAL = [2022, 2023, 2024, 2025]
LEVELS = (0.50, 0.80, 0.90, 0.95)
MASS_POOL_EXCLUDE_SEASONS = (2020,)      # panel-edge artifact, see pre-declaration

CLASSES = {
    'snaps':      {'share': 's_snaps', 'y': 'y_snaps',
                   'den': 'team_off_snaps', 'pos': ('WR', 'TE', 'RB'),
                   'mode': 'occupancy'},
    'pass_snaps': {'share': 's_pass_snaps', 'y': 'y_pass_snaps',
                   'den': 'team_dropbacks_part', 'pos': ('WR', 'TE', 'RB'),
                   'mode': 'occupancy'},
    'targets':    {'share': 's_targets', 'y': 'y_targets',
                   'den': 'team_targets', 'pos': ('WR', 'TE', 'RB'),
                   'mode': 'simplex'},
    'carries':    {'share': 's_carries', 'y': 'y_carries',
                   'den': 'team_carries', 'pos': ('RB',),
                   'mode': 'simplex'},
    'rz_carries': {'share': 's_rz_carries', 'y': 'y_rz_carries',
                   'den': 'team_rz_carries', 'pos': ('RB',),
                   'mode': 'simplex'},
}

# P4B grids carried unchanged; rz_carries newly pre-declared in
# predeclaration_p4c.md section 6 BEFORE any P4C exceedance number existed.
THRESHOLDS = {
    'snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
    'pass_snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
    'targets': [2.5, 4.5, 6.5, 8.5, 10.5],
    'carries': [5.5, 9.5, 12.5, 15.5, 19.5],
    'rz_carries': [0.5, 1.5, 2.5, 3.5],
}

ELIGIBLE_SYSTEMS = ('A', 'B', 'C', 'C2', 'D_dir', 'D_sln', 'D_ln', 'D_emp')
DIAGNOSTIC_ONLY = ('E',)


def select_system(scores):
    """CRPS among ELIGIBLE systems only. E is the realised allocation oracle and
    is not in the tuple; a guard-deletion proof shows this line is what stops
    it."""
    cand = {k: v for k, v in scores.items() if k in ELIGIBLE_SYSTEMS}
    return min(cand, key=lambda k: cand[k]['crps']) if cand else None


# ---------------------------------------------------------------------------
def gsum(X, starts):
    return np.add.reduceat(X, starts, axis=0)


def gexp(G, counts):
    return np.repeat(G, counts, axis=0)


def waterfill(S, starts, counts, cap=1.0, iters=6):
    """Enforce S <= cap while preserving each group's total. Proportional
    scaling can push a share above 1, which is an IMPOSSIBLE allocation, so the
    excess is pushed back onto the unsaturated players rather than clipped
    away (clipping would silently destroy team mass)."""
    S = S.copy()
    n_bind = 0
    for _ in range(iters):
        over = S > cap
        if not over.any():
            break
        n_bind = max(n_bind, int(over.sum()))
        excess = gsum(np.where(over, S - cap, 0.0), starts)
        S = np.where(over, cap, S)
        free = np.where(over, 0.0, S)
        fs = gsum(free, starts)
        fse = gexp(fs, counts)
        add = np.divide(free * gexp(excess, counts), fse,
                        out=np.zeros_like(S), where=fse > 1e-12)
        S = S + add
    return S, n_bind


def allocate(W, A, starts, counts, mode, avail, w_other=None):
    """Turn nonnegative relative weights into shares that respect the class's
    accounting identity.

      simplex   : S_i = w_i A_i / (sum_g w A + w_other)          (total 1)
      occupancy : S_i = avail * w_i A_i / sum_g w A, then capped at 1

    `avail` is (G, M): the mass available to the MODELLED set. For simplex it
    is implied by w_other, so it is ignored there.
    """
    WA = W * A
    tot = gsum(WA, starts)
    if mode == 'simplex':
        tot = tot + w_other
        te = gexp(tot, counts)
        S = np.divide(WA, te, out=np.zeros_like(WA), where=te > 1e-12)
        other = np.divide(w_other, tot, out=np.zeros_like(tot), where=tot > 1e-12)
        return S, other, 0
    te = gexp(tot, counts)
    S = np.divide(WA * gexp(avail, counts), te,
                  out=np.zeros_like(WA), where=te > 1e-12)
    S, nb = waterfill(S, starts, counts, 1.0)
    return S, None, nb


# ---------------------------------------------------------------------------
def crps_samples(draws, y, chunk=2000):
    out = np.empty(len(y))
    m = draws.shape[1]
    i = np.arange(1, m + 1, dtype=np.float64).reshape(1, -1)
    for a in range(0, len(y), chunk):
        b = min(a + chunk, len(y))
        d = np.sort(draws[a:b].astype(np.float64), axis=1)
        yy = np.asarray(y[a:b], np.float64).reshape(-1, 1)
        w = m * (yy < d) - i + 0.5
        out[a:b] = (2.0 / (m * m)) * ((d - yy) * w).sum(axis=1)
    return out


def log_score(draws, y):
    """Discretised log score. These targets are integer counts, so P(Y = k) read
    off the draws is exactly valid -- no kernel and no density assumption. The
    floor 1/(2M) prevents -inf and its rate is reported, because a log score
    dominated by the floor is measuring the floor."""
    m = draws.shape[1]
    k = np.rint(np.asarray(y, float)).reshape(-1, 1)
    p = (np.abs(draws - k) < 0.5).mean(axis=1)
    floor = 1.0 / (2 * m)
    hit = p > 0
    p = np.maximum(p, floor)
    return {'log_score': float(-np.log(p).mean()),
            'floor_rate': float(1.0 - hit.mean())}


def rpit(draws, y, rng):
    y = np.asarray(y, float).reshape(-1, 1)
    lo = (draws < y).mean(axis=1)
    hi = (draws <= y).mean(axis=1)
    return lo + rng.random(len(lo)) * (hi - lo)


def pit_stats(u):
    h, _ = np.histogram(u, bins=10, range=(0, 1))
    exp = len(u) / 10.0
    return {'hist': h.tolist(), 'chi2': float((((h - exp) ** 2) / exp).sum()),
            'df': 9, 'chi2_crit_p001': 27.877, 'mean': float(u.mean())}


def score(draws, y, rng):
    y = np.asarray(y, float)
    mean = draws.mean(axis=1)
    e = y - mean
    sst = ((y - y.mean()) ** 2).sum()
    out = {'n': int(len(y)),
           'crps': float(crps_samples(draws, y).mean()),
           'mae': float(np.abs(e).mean()),
           'rmse': float(math.sqrt((e * e).mean())),
           'bias': float(e.mean()),
           'r': (float(np.corrcoef(y, mean)[0, 1]) if mean.std() > 0 else None),
           'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
           'sd_pred': float(mean.std(ddof=1)), 'sd_actual': float(y.std(ddof=1)),
           'coverage': {}}
    out.update(log_score(draws, y))
    for L in LEVELS:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 + L) / 2, axis=1)
        out['coverage'][str(int(L * 100))] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    out['randomised_pit'] = pit_stats(rpit(draws, y, rng))
    return out


def thresholds(draws, y, grid):
    y = np.asarray(y, float)
    out = {}
    for t in grid:
        p = (draws > t).mean(axis=1)
        o = (y > t).astype(float)
        out[str(t)] = {'mean_p': float(p.mean()), 'observed': float(o.mean()),
                       'calibration_in_the_large': float(p.mean() - o.mean()),
                       'brier': float(((p - o) ** 2).mean())}
    return out


def block_boot(a, b, cluster, n=400, seed=SEED):
    rng = np.random.default_rng(seed)
    idx = collections.defaultdict(list)
    for i, c in enumerate(cluster):
        idx[c].append(i)
    groups = [np.array(v) for v in idx.values()]
    a = np.asarray(a); b = np.asarray(b)
    ga = np.array([a[g].sum() for g in groups])
    gb = np.array([b[g].sum() for g in groups])
    gn = np.array([len(g) for g in groups], float)
    m = len(groups)
    if m < 5:
        return None
    pick = rng.integers(0, m, size=(n, m))
    d = np.sort((ga[pick].sum(1) - gb[pick].sum(1)) / gn[pick].sum(1))
    return {'mean': float(d.mean()), 'lo': float(d[int(.025 * n)]),
            'hi': float(d[int(.975 * n)]), 'n_clusters': m}
