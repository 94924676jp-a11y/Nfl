"""P5A: conversion families, the compound carry->yards draw, and metrics.

The predictive distribution for a player-game is a COMPOUND: draw the carry
count from the accepted P4C joint allocation, then draw that many per-carry
outcomes. It is not a game-level Gaussian, and the per-carry audit is why --
skew 3.6-4.2 and excess kurtosis 25-32 on 140,678 carries.
"""
import collections, math, os
import numpy as np

M_DRAWS = 1000
SEED = 20260907
EVAL = [2022, 2023, 2024, 2025]
LEVELS = (0.50, 0.80, 0.90, 0.95)
EXPLOSIVE = 10.0
# Pre-declared in predeclaration_p5a.md section 4, before any result existed.
THRESHOLDS = [9.5, 19.5, 39.5, 59.5, 79.5, 99.5]
FAMILIES = ('emp_shift', 'emp_tilt', 'mix2', 'mix3')
ELIGIBLE_SYSTEMS = ('A', 'B', 'C', 'D', 'E')
DIAGNOSTIC_ONLY = ('O_carries', 'O_eff', 'O_explosive', 'O_context', 'O_all')


def select_system(scores):
    """CRPS among ELIGIBLE systems only. No oracle is in the tuple; a
    guard-deletion proof shows this line is what stops them."""
    c = {k: v for k, v in scores.items() if k in ELIGIBLE_SYSTEMS}
    return min(c, key=lambda k: c[k]['crps']) if c else None


# ---------------------------------------------------------------------------
class Pool:
    """The pooled per-carry outcome distribution, estimated on prior seasons."""

    def __init__(self, yards):
        y = np.asarray(yards, np.float32)
        self.y = y
        self.mean = float(y.mean())
        self.body = y[(y > 0) & (y < EXPLOSIVE)]
        self.stuff = y[y <= 0]
        self.exp = y[y >= EXPLOSIVE]
        self.p_stuff = float((y <= 0).mean())
        self.p_exp = float((y >= EXPLOSIVE).mean())
        self.p_body = 1.0 - self.p_stuff - self.p_exp
        self.m_body = float(self.body.mean())
        self.m_stuff = float(self.stuff.mean())
        self.m_exp = float(self.exp.mean())
        # integer support for the tilted family
        lo, hi = int(np.floor(y.min())), int(np.ceil(y.max()))
        self.support = np.arange(lo, hi + 1, dtype=np.float32)
        cnt = np.bincount((y - lo).astype(int), minlength=len(self.support))
        self.pmf = cnt.astype(np.float64) / cnt.sum()


def tilt_pmf(pool, target_mean, tol=1e-7, iters=60):
    """Exponential tilt of the pooled pmf to a target mean. Keeps the shape and
    the support; the alternative (a location shift) moves mass off the integer
    support and can produce impossible yardage."""
    s = pool.support.astype(np.float64)
    lo, hi = -1.0, 1.0
    for _ in range(60):
        if (np.exp(lo * s) * pool.pmf).sum() and \
           ((np.exp(lo * s) * pool.pmf) @ s) / (np.exp(lo * s) * pool.pmf).sum() <= target_mean:
            break
        lo *= 2
        if lo < -50:
            break
    for _ in range(60):
        w = np.exp(hi * s) * pool.pmf
        if w.sum() and (w @ s) / w.sum() >= target_mean:
            break
        hi *= 2
        if hi > 50:
            break
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        w = np.exp(mid * s) * pool.pmf
        m = (w @ s) / w.sum()
        if abs(m - target_mean) < tol:
            break
        if m < target_mean:
            lo = mid
        else:
            hi = mid
    w = np.exp(mid * s) * pool.pmf
    return w / w.sum()


def draw_carry_yards(family, pool, n_draw, par, rng):
    """`par` holds this row's conversion parameters. Returns n_draw samples."""
    if family == 'emp_shift':
        return pool.y[rng.integers(0, len(pool.y), n_draw)] + par['shift']
    if family == 'emp_tilt':
        cdf = par['cdf']
        u = rng.random(n_draw)
        return pool.support[np.searchsorted(cdf, u)]
    if family == 'mix2':
        u = rng.random(n_draw)
        is_exp = u < par['p_exp']
        out = np.empty(n_draw, np.float32)
        ne = int(is_exp.sum())
        out[is_exp] = pool.exp[rng.integers(0, len(pool.exp), ne)]
        out[~is_exp] = pool.body_or_stuff[rng.integers(
            0, len(pool.body_or_stuff), n_draw - ne)]
        return out
    if family == 'mix3':
        u = rng.random(n_draw)
        out = np.empty(n_draw, np.float32)
        m_st = u < par['p_stuff']
        m_ex = u >= 1.0 - par['p_exp']
        m_bo = ~(m_st | m_ex)
        for m, src in ((m_st, pool.stuff), (m_bo, pool.body), (m_ex, pool.exp)):
            k = int(m.sum())
            if k:
                out[m] = src[rng.integers(0, len(src), k)]
        return out
    raise ValueError(family)


def compound(counts, family, pool, pars, seed):
    """counts (n, M) integer carry counts; returns (n, M) rushing-yard sums.

    Every carry is drawn independently from its row's conversion distribution,
    and the CARRY COUNTS come from the accepted joint allocation -- they are
    never regenerated here."""
    rng = np.random.default_rng(seed)
    n, M = counts.shape
    out = np.zeros((n, M), np.float32)
    for i in range(n):
        c = counts[i]
        tot = int(c.sum())
        if tot == 0:
            continue
        s = draw_carry_yards(family, pool, tot, pars[i], rng)
        cs = np.concatenate([[np.float32(0)], np.cumsum(s, dtype=np.float64)])
        ends = np.cumsum(c)
        out[i] = (cs[ends] - cs[ends - c]).astype(np.float32)
    return out


# ---------------------------------------------------------------------------
def crps_samples(draws, y, chunk=1500):
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


def rpit(draws, y, rng):
    y = np.asarray(y, float).reshape(-1, 1)
    lo = (draws < y).mean(axis=1)
    hi = (draws <= y).mean(axis=1)
    return lo + rng.random(len(lo)) * (hi - lo)


def pit_stats(u):
    h, _ = np.histogram(u, bins=10, range=(0, 1))
    e = len(u) / 10.0
    return {'hist': h.tolist(), 'chi2': float((((h - e) ** 2) / e).sum()),
            'df': 9, 'chi2_crit_p001': 27.877}


def log_score(draws, y):
    m = draws.shape[1]
    k = np.rint(np.asarray(y, float)).reshape(-1, 1)
    p = (np.abs(draws - k) < 0.5).mean(axis=1)
    floor = 1.0 / (2 * m)
    hit = p > 0
    return {'log_score': float(-np.log(np.maximum(p, floor)).mean()),
            'floor_rate': float(1.0 - hit.mean())}


def score(draws, y, rng):
    y = np.asarray(y, float)
    mean = draws.mean(axis=1)
    e = y - mean
    sst = ((y - y.mean()) ** 2).sum()
    o = {'n': int(len(y)), 'crps': float(crps_samples(draws, y).mean()),
         'mae': float(np.abs(e).mean()),
         'rmse': float(math.sqrt((e * e).mean())), 'bias': float(e.mean()),
         'r': (float(np.corrcoef(y, mean)[0, 1]) if mean.std() > 0 else None),
         'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
         'sd_pred': float(mean.std(ddof=1)), 'sd_actual': float(y.std(ddof=1)),
         'coverage': {}}
    o.update(log_score(draws, y))
    for L in LEVELS:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 + L) / 2, axis=1)
        o['coverage'][str(int(L * 100))] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    o['randomised_pit'] = pit_stats(rpit(draws, y, rng))
    # ---- tail, reported separately and never hidden behind the mean --------
    o['tail'] = {
        'q95_pred_mean': float(np.percentile(draws, 95, axis=1).mean()),
        'q99_pred_mean': float(np.percentile(draws, 99, axis=1).mean()),
        'exceed_q95': float((y > np.percentile(draws, 95, axis=1)).mean()),
        'exceed_q99': float((y > np.percentile(draws, 99, axis=1)).mean()),
        'upper_tail_target_q95': 0.05, 'upper_tail_target_q99': 0.01,
    }
    return o


def thresholds(draws, y):
    y = np.asarray(y, float)
    out = {}
    for t in THRESHOLDS:
        p = (draws > t).mean(axis=1)
        ob = (y > t).astype(float)
        out[str(t)] = {'mean_p': float(p.mean()), 'observed': float(ob.mean()),
                       'calibration_in_the_large': float(p.mean() - ob.mean()),
                       'brier': float(((p - ob) ** 2).mean())}
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
