"""P4B shared: Monte Carlo assembly and scoring."""
import collections, math, os, sys
import numpy as np

M_DRAWS = 1000
SEED = 20260907
EVAL = [2022, 2023, 2024, 2025]
LEVELS = (0.50, 0.80, 0.90, 0.95)

# Denominator that each absolute target is a share OF.
TARGETS = {
    'snaps':       ('team_off_snaps',      ('WR', 'TE', 'RB')),
    'pass_snaps':  ('team_dropbacks_part', ('WR', 'TE', 'RB')),
    'targets':     ('team_targets',        ('WR', 'TE', 'RB')),
    'carries':     ('team_carries',        ('RB',)),
    'rz_carries':  ('team_rz_carries',     ('RB',)),
}

# PRE-DECLARED in predeclaration_p4b.md section 6, before any number existed.
# rz_carries has no pre-declared grid, so no exceedance calibration is reported
# for it. Inventing a grid now, after seeing the distribution, is exactly the
# move the pre-declaration exists to prevent.
THRESHOLDS = {
    'carries': [5.5, 9.5, 12.5, 15.5, 19.5],
    'targets': [2.5, 4.5, 6.5, 8.5, 10.5],
    'snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
    'pass_snaps': [10.5, 20.5, 30.5, 40.5, 50.5],
    'rz_carries': None,
}


def ewma(v, hl=3.0):
    if not v:
        return None
    lam = 0.5 ** (1 / hl)
    n = d = 0.0
    w = 1.0
    for x in reversed(v):
        n += w * x
        d += w
        w *= lam
    return n / d


def crps_samples(draws, y, chunk=2000):
    """CRPS from samples via the sorted-sample identity, chunked so a
    (n x 1000) float64 sort never has to exist all at once."""
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


def score(draws, y):
    """Every number the pre-declaration asks for, from one draw matrix."""
    y = np.asarray(y, float)
    mean = draws.mean(axis=1)
    e = y - mean
    sst = ((y - y.mean()) ** 2).sum()
    out = {
        'n': int(len(y)),
        'crps': float(crps_samples(draws, y).mean()),
        'mae': float(np.abs(e).mean()),
        'rmse': float(math.sqrt((e * e).mean())),
        'bias': float(e.mean()),
        'r': (float(np.corrcoef(y, mean)[0, 1]) if mean.std() > 0 else None),
        'r2': float(1 - (e * e).sum() / sst) if sst > 0 else None,
        'mean_pred': float(mean.mean()), 'mean_actual': float(y.mean()),
        'sd_pred': float(mean.std(ddof=1)), 'sd_actual': float(y.std(ddof=1)),
        'coverage': {}, 'pit': None,
    }
    for L in LEVELS:
        lo = np.percentile(draws, 100 * (1 - L) / 2, axis=1)
        hi = np.percentile(draws, 100 * (1 + L) / 2, axis=1)
        out['coverage'][str(int(L * 100))] = {
            'coverage': float(((y >= lo) & (y <= hi)).mean()),
            'mean_width': float((hi - lo).mean())}
    u = (draws < y.reshape(-1, 1)).mean(axis=1)
    h, _ = np.histogram(u, bins=10, range=(0, 1))
    exp = len(u) / 10.0
    out['pit'] = {'hist': h.tolist(), 'expected_per_bin': exp,
                  'chi2': float((((h - exp) ** 2) / exp).sum()), 'df': 9}
    return out


def thresholds(draws, y, grid):
    if not grid:
        return None
    y = np.asarray(y, float)
    out = {}
    for t in grid:
        p = (draws > t).mean(axis=1)
        o = (y > t).astype(float)
        bins = np.clip((p * 5).astype(int), 0, 4)
        rel = []
        for b in range(5):
            m = bins == b
            if m.sum() >= 30:
                rel.append({'bin': f'{b/5:.1f}-{(b+1)/5:.1f}', 'n': int(m.sum()),
                            'mean_p': float(p[m].mean()),
                            'observed': float(o[m].mean())})
        out[str(t)] = {'n': int(len(y)), 'mean_p': float(p.mean()),
                       'observed': float(o.mean()),
                       'calibration_in_the_large': float(p.mean() - o.mean()),
                       'brier': float(((p - o) ** 2).mean()),
                       'reliability': rel}
    return out


def block_boot(stat_a, stat_b, cluster, n=400, seed=SEED):
    """Difference in a per-row score, resampled by CLUSTER (team-game). Players
    on the same team-game share a volume draw and a game script; treating them
    as independent understates the SE, which is methodology fix #1 in the
    platform brief."""
    rng = np.random.default_rng(seed)
    idx = collections.defaultdict(list)
    for i, c in enumerate(cluster):
        idx[c].append(i)
    groups = [np.array(v) for v in idx.values()]
    sa = np.asarray(stat_a); sb = np.asarray(stat_b)
    ga = np.array([sa[g].sum() for g in groups])
    gb = np.array([sb[g].sum() for g in groups])
    gn = np.array([len(g) for g in groups], float)
    m = len(groups)
    if m < 5:
        return None
    pick = rng.integers(0, m, size=(n, m))
    d = (ga[pick].sum(1) - gb[pick].sum(1)) / gn[pick].sum(1)
    d = np.sort(d)
    return {'mean': float(d.mean()), 'lo': float(d[int(.025 * n)]),
            'hi': float(d[int(.975 * n)]), 'n_clusters': m}
