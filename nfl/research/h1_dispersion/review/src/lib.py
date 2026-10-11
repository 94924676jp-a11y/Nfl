"""Independent re-implementation of PREREG_H1_DISPERSION.md sections 4-5 (reviewer's own code).

Written from the prereg text, not from eval_h2.py. Uses numpy/pandas; percentile and bootstrap
choices are documented where the prereg is silent.
"""
import gzip
import numpy as np
import pandas as pd

R = '/tmp/claude-0/h1review'
PROD = '1.0|2.0'
POS = ('QB', 'RB', 'WR', 'TE')


def load(path, arm=PROD):
    df = pd.read_csv(path, dtype={'gsis': str})
    df = df[df['arm'] == arm].copy()
    df['wk'] = list(zip(df['season'], df['week']))
    weeks = sorted(set(df['wk']))
    df['widx'] = df['wk'].map({w: i for i, w in enumerate(weeks)})
    df = df.reset_index(drop=True)
    return df, weeks


def q75_nearest(vals):
    """The prereg says 'the 75th percentile'. Primary convention reproduced here as the
    order statistic at floor(0.75 n) (0-based) -- one valid percentile convention."""
    v = np.sort(np.asarray(vals))
    return v[int(np.floor(0.75 * len(v)))]


def q75_linear(vals):
    return float(np.percentile(vals, 75))  # numpy 'linear' (Hyndman-Fan type 7)


def mark_top(df, qfun=q75_nearest, mode='threshold', q=0.75, rng=None):
    """Top-quartile membership per (week, pos) using ONLY the week's pool projections.
    mode: 'threshold' p >= q-th percentile; 'strict' p > q75; 'rank' top ceil((1-q)n) by rank,
    ties broken at random (rng) or by order."""
    top = np.zeros(len(df), bool)
    thr = np.zeros(len(df))
    for (_, _), idx in df.groupby(['widx', 'pos']).groups.items():
        idx = np.asarray(idx)
        p = df.loc[idx, 'proj'].to_numpy()
        if mode in ('threshold', 'strict'):
            if q == 0.75:
                t = qfun(p)
            else:
                v = np.sort(p); t = v[int(np.floor(q * len(v)))]
            top[idx] = (p >= t) if mode == 'threshold' else (p > t)
            thr[idx] = t
        elif mode == 'rank':
            k = int(np.ceil((1 - q) * len(p)))
            key = rng.random(len(p)) if rng is not None else np.zeros(len(p))
            order = np.lexsort((key, -p))  # by -p, ties by random key
            sel = order[:k]
            m = np.zeros(len(p), bool); m[sel] = True
            top[idx] = m
            thr[idx] = p[sel].min()
    return top, thr


def candidate(df, top, thr, min_weeks=8):
    """Frozen candidate, section 4. c_pos,w from strictly earlier weeks' top-quartile players who
    played; >= 8 earlier weeks else 1; capped at 1. p' = min(p, max(q75, c p)) for top rows."""
    cand = df['proj'].to_numpy().copy()
    c_arr = np.ones(len(df))
    fitted = df['widx'].to_numpy() >= min_weeks
    proj = df['proj'].to_numpy(); act = df['actual_dk'].to_numpy(); app = df['appeared'].to_numpy() == 1
    widx = df['widx'].to_numpy(); pos = df['pos'].to_numpy()
    nW = widx.max() + 1
    for ps in POS:
        mpos = pos == ps
        fit_mask = mpos & top & app
        # cumulative sums by week, strictly earlier
        sa = np.bincount(widx[fit_mask], weights=act[fit_mask], minlength=nW)
        sp = np.bincount(widx[fit_mask], weights=proj[fit_mask], minlength=nW)
        csa = np.concatenate([[0], np.cumsum(sa)[:-1]])
        csp = np.concatenate([[0], np.cumsum(sp)[:-1]])
        for w in range(nW):
            rows = mpos & (widx == w)
            if w >= min_weeks and csp[w] > 0:
                c = min(csa[w] / csp[w], 1.0)
            else:
                c = 1.0
            c_arr[rows] = c
            t = rows & top
            cand[t] = np.minimum(proj[t], np.maximum(thr[t], c * proj[t]))
    return cand, c_arr, fitted


def week_boot_idx(widx_unique, B, seed):
    rng = np.random.default_rng(seed)
    n = len(widx_unique)
    return rng.integers(0, n, size=(B, n))


def boot_stat(df_rows, stat, B=4000, seed=20261011):
    """Week-block bootstrap: resample weeks with replacement, pool their rows, recompute stat.
    stat(sub_df) -> float. Returns (point, lo2.5, hi97.5, sd)."""
    groups = {w: g for w, g in df_rows.groupby('widx')}
    ws = sorted(groups)
    draws = week_boot_idx(ws, B, seed)
    vals = np.empty(B)
    for b in range(B):
        sub = pd.concat([groups[ws[i]] for i in draws[b]], ignore_index=True)
        vals[b] = stat(sub)
    pt = stat(df_rows)
    return pt, np.percentile(vals, 2.5), np.percentile(vals, 97.5), vals.std(ddof=1)


def fast_ratio_boot(df_rows, num='proj', den='actual_dk', B=4000, seed=20261011):
    """Ratio of sums with week-block bootstrap, vectorised via per-week sums."""
    g = df_rows.groupby('widx')[[num, den]].sum()
    a, b = g[num].to_numpy(), g[den].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(B, len(a)))
    r = a[idx].sum(1) / b[idx].sum(1)
    return a.sum() / b.sum(), np.percentile(r, 2.5), np.percentile(r, 97.5), r.std(ddof=1), len(df_rows), len(a)


def fast_diff_boot(df_rows, x='cand_err', y='prod_err', B=4000, seed=20261011, rel=False):
    """Pooled mean(x) - mean(y) (or relative % change) with week-block bootstrap via week sums."""
    g = df_rows.groupby('widx').agg(sx=(x, 'sum'), sy=(y, 'sum'), n=(x, 'size'))
    sx, sy, n = g['sx'].to_numpy(), g['sy'].to_numpy(), g['n'].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(sx), size=(B, len(sx)))
    if rel:
        v = (sx[idx].sum(1) - sy[idx].sum(1)) / sy[idx].sum(1) * 100
        pt = (sx.sum() - sy.sum()) / sy.sum() * 100
    else:
        v = (sx[idx].sum(1) - sy[idx].sum(1)) / n[idx].sum(1)
        pt = (sx.sum() - sy.sum()) / n.sum()
    return pt, np.percentile(v, 2.5), np.percentile(v, 97.5), v.std(ddof=1)


def weekly_paired(df_rows, x='cand_err', y='prod_err'):
    """Mean over weeks of per-week (mean x - mean y), normal interval -- 'paired by week'."""
    g = df_rows.groupby('widx').agg(mx=(x, 'mean'), my=(y, 'mean'))
    d = (g['mx'] - g['my']).to_numpy()
    m, se = d.mean(), d.std(ddof=1) / np.sqrt(len(d))
    return m, m - 1.96 * se, m + 1.96 * se, len(d)


def deciles(df_rows, col='proj'):
    """Equal-count projection deciles over pooled rows (ties broken by stable order)."""
    order = np.argsort(df_rows[col].to_numpy(), kind='stable')
    n = len(order)
    lab = np.empty(n, int)
    for k in range(10):
        lab[order[k * n // 10:(k + 1) * n // 10]] = k
    return lab
