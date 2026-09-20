"""Postgame calibration reports. Measurement only -- nothing here fits.

THREE RULES THIS FILE OBEYS

1. GAMES ARE NOT INDEPENDENT OBSERVATIONS. Many markets per player and many
   players per game move together, so a naive binomial SE on 263 prop rows
   overstates precision. Every headline rate carries a SE clustered BY GAME
   alongside the naive one, and the two are printed together so the gap is
   visible rather than assumed away.
2. CALIBRATION AND DISCRIMINATION ARE DIFFERENT PROPERTIES. Passing one says
   nothing about the other, and neither is reported as though it were the
   other.
3. NOTHING IS CALLED UNBIASED, STABLE OR CORRECT. No equivalence margin was
   predeclared for this slate, so a failure to reject is reported as a
   failure to reject.
"""
from __future__ import annotations

import collections
import math

BUCKETS = ((0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70),
           (0.70, 0.75), (0.75, 0.80), (0.80, 1.01))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def cluster_se(units, by):
    """SE of a mean, clustered on `by`. units: list of (value, cluster)."""
    vals = [v for v, _ in units]
    n = len(vals)
    if n < 2:
        return None, None, 0
    m = sum(vals) / n
    naive = math.sqrt(sum((v - m) ** 2 for v in vals) / (n * (n - 1)))
    g = collections.defaultdict(list)
    for v, c in units:
        g[c].append(v)
    k = len(g)
    if k < 2:
        return naive, None, k
    # Cluster-robust variance of the mean: sum of squared cluster score
    # totals, scaled. With few clusters this is noisy, which is the point --
    # it reports the uncertainty a naive SE hides.
    s = sum((sum(v - m for v in vs)) ** 2 for vs in g.values())
    var = s / (n ** 2) * (k / max(k - 1, 1))
    return naive, math.sqrt(var), k
    del by


def prop_metrics(rows):
    """Brier, log loss, buckets and the calibration curve on graded props."""
    g = [r for r in rows if r['row_type'] == 'PLAYER_PROP_MARKET'
         and r['grade_state'] == 'GRADED' and r['settlement'] in
         ('WIN', 'LOSS') and r.get('model_probability') is not None]
    out = {'n_graded': len(g), 'n_push': sum(
        1 for r in rows if r.get('settlement') == 'PUSH')}
    if not g:
        out['refused'] = 'NO_GRADED_PROP_ROWS'
        return out
    ys = [(1.0 if r['settlement'] == 'WIN' else 0.0) for r in g]
    ps = [float(r['model_probability']) for r in g]
    qs = [None if r.get('novig_probability') is None
          else float(r['novig_probability']) for r in g]
    out['brier_model'] = round(
        sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(g), 6)
    bq = [(q, y) for q, y in zip(qs, ys) if q is not None]
    out['brier_book_novig'] = (round(
        sum((q - y) ** 2 for q, y in bq) / len(bq), 6) if bq else None)
    eps = 1e-12
    out['log_loss_model'] = round(-sum(
        y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps))
        for p, y in zip(ps, ys)) / len(g), 6)
    out['log_loss_book_novig'] = (round(-sum(
        y * math.log(max(q, eps)) + (1 - y) * math.log(max(1 - q, eps))
        for q, y in bq) / len(bq), 6) if bq else None)
    out['mean_predicted_probability'] = round(_mean(ps), 6)
    out['realized_hit_rate'] = round(_mean(ys), 6)
    naive, clus, k = cluster_se([(y, r['game_id']) for y, r in zip(ys, g)],
                                'game_id')
    out['hit_rate_se_naive'] = round(naive, 6) if naive else None
    out['hit_rate_se_clustered_by_game'] = round(clus, 6) if clus else None
    out['n_game_clusters'] = k
    out['se_inflation_factor'] = (round(clus / naive, 3)
                                  if naive and clus else None)
    buckets = []
    for lo, hi in BUCKETS:
        sel = [(p, y, r) for p, y, r in zip(ps, ys, g) if lo <= p < hi]
        if not sel:
            buckets.append({'bucket': f'{lo:.2f}-{hi:.2f}', 'n': 0})
            continue
        n2, c2, k2 = cluster_se(
            [(y, r['game_id']) for _, y, r in sel], 'game_id')
        buckets.append({
            'bucket': f'{lo:.2f}-{hi:.2f}', 'n': len(sel),
            'mean_predicted': round(_mean([p for p, _, _ in sel]), 4),
            'realized': round(_mean([y for _, y, _ in sel]), 4),
            'gap': round(_mean([y for _, y, _ in sel])
                         - _mean([p for p, _, _ in sel]), 4),
            'se_naive': round(n2, 4) if n2 else None,
            'se_clustered_by_game': round(c2, 4) if c2 else None,
            'n_game_clusters': k2})
    out['probability_buckets'] = buckets
    fam = collections.defaultdict(list)
    for p, y, r in zip(ps, ys, g):
        fam[r['market']].append((p, y, r))
    families = []
    for m, sel in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        n2, c2, k2 = cluster_se(
            [(y, r['game_id']) for _, y, r in sel], 'game_id')
        eg = [r['raw_edge'] for _, _, r in sel if r.get('raw_edge') is not None]
        families.append({
            'market': m, 'n': len(sel),
            'mean_predicted': round(_mean([p for p, _, _ in sel]), 4),
            'realized': round(_mean([y for _, y, _ in sel]), 4),
            'gap': round(_mean([y for _, y, _ in sel])
                         - _mean([p for p, _, _ in sel]), 4),
            'se_clustered_by_game': round(c2, 4) if c2 else None,
            'n_game_clusters': k2,
            'mean_raw_edge': round(_mean(eg), 4) if eg else None,
            'brier': round(sum((p - y) ** 2 for p, y, _ in sel) / len(sel), 4)})
    out['by_market_family'] = families
    sides = collections.Counter(r['side'] for _, _, r in
                                zip(ps, ys, g) or [])
    out['side_counts'] = dict(collections.Counter(r['side'] for r in g))
    del sides
    edges = [(r['raw_edge'], y) for y, r in zip(ys, g)
             if r.get('raw_edge') is not None]
    if edges:
        edges.sort()
        half = len(edges) // 2
        out['edge_vs_outcome'] = {
            'low_edge_half': {'n': half,
                              'mean_edge': round(_mean(
                                  [e for e, _ in edges[:half]]), 4),
                              'hit_rate': round(_mean(
                                  [y for _, y in edges[:half]]), 4)},
            'high_edge_half': {'n': len(edges) - half,
                               'mean_edge': round(_mean(
                                   [e for e, _ in edges[half:]]), 4),
                               'hit_rate': round(_mean(
                                   [y for _, y in edges[half:]]), 4)}}
    return out


def projection_metrics(rows):
    """DK mean error, quantile coverage and threshold-probability calibration."""
    g = [r for r in rows if r['row_type'] == 'PLAYER_GAME_PROJECTION'
         and r['grade_state'] == 'GRADED'
         and r.get('actual_dk_points') is not None
         and r.get('proj_dk_mean') is not None]
    out = {'n_graded': len(g)}
    if not g:
        out['refused'] = 'NO_GRADED_PROJECTION_ROWS'
        return out
    err = [r['actual_dk_points'] - r['proj_dk_mean'] for r in g]
    out['mean_bias_actual_minus_projected'] = round(_mean(err), 4)
    out['mae'] = round(_mean([abs(e) for e in err]), 4)
    out['rmse'] = round(math.sqrt(_mean([e * e for e in err])), 4)
    n, c, k = cluster_se([(e, r['game_id']) for e, r in zip(err, g)],
                         'game_id')
    out['bias_se_naive'] = round(n, 4) if n else None
    out['bias_se_clustered_by_game'] = round(c, 4) if c else None
    out['n_game_clusters'] = k
    out['sd_projected_mean'] = round(_sd([r['proj_dk_mean'] for r in g]), 4)
    out['sd_actual'] = round(_sd([r['actual_dk_points'] for r in g]), 4)
    out['sd_ratio_projected_over_actual'] = (
        round(out['sd_projected_mean'] / out['sd_actual'], 4)
        if out['sd_actual'] else None)
    out['pearson_r'] = _pearson([r['proj_dk_mean'] for r in g],
                                [r['actual_dk_points'] for r in g])
    cov = {}
    for q in ('p50', 'p90', 'p95'):
        sel = [r for r in g if r.get(f'proj_dk_{q}') is not None]
        if sel:
            cov[q] = {'n': len(sel), 'nominal': float(q[1:]) / 100.0,
                      'realized_at_or_below': round(_mean(
                          [1.0 if r['actual_dk_points'] <= r[f'proj_dk_{q}']
                           else 0.0 for r in sel]), 4)}
    out['quantile_coverage'] = cov
    thr = {}
    for t, key in ((10, 'proj_dk_p_ge_10'), (15, 'proj_dk_p_ge_15'),
                   (20, 'proj_dk_p_ge_20'), (30, 'proj_dk_p_ge_30')):
        sel = [r for r in g if r.get(key) is not None]
        if not sel:
            continue
        ys = [1.0 if r['actual_dk_points'] >= t else 0.0 for r in sel]
        _, c2, k2 = cluster_se(
            [(y, r['game_id']) for y, r in zip(ys, sel)], 'game_id')
        thr[f'P(DK>={t})'] = {
            'n': len(sel),
            'mean_predicted': round(_mean([r[key] for r in sel]), 4),
            'realized': round(_mean(ys), 4),
            'gap': round(_mean(ys) - _mean([r[key] for r in sel]), 4),
            'se_clustered_by_game': round(c2, 4) if c2 else None,
            'n_game_clusters': k2}
    out['threshold_probability_calibration'] = thr
    return out


def _sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    return round(num / (da * db), 4) if da and db else None


def workload_metrics(rows):
    """Per-quantity projected-vs-realised error on graded players."""
    g = [r for r in rows if r['row_type'] == 'PLAYER_GAME_PROJECTION'
         and r['grade_state'] == 'GRADED']
    out = {}
    for short in ('targets', 'receptions', 'receiving_yards', 'carries',
                  'rushing_yards', 'att', 'cmp', 'pyds', 'ptd', 'int'):
        sel = [r for r in g if r.get(f'proj_{short}_mean') is not None
               and r.get(f'actual_{short}') is not None]
        if not sel:
            continue
        err = [r[f'actual_{short}'] - r[f'proj_{short}_mean'] for r in sel]
        _, c, k = cluster_se([(e, r['game_id']) for e, r in zip(err, sel)],
                             'game_id')
        out[short] = {
            'n': len(sel),
            'mean_projected': round(_mean(
                [r[f'proj_{short}_mean'] for r in sel]), 4),
            'mean_actual': round(_mean([r[f'actual_{short}'] for r in sel]), 4),
            'mean_bias_actual_minus_projected': round(_mean(err), 4),
            'mae': round(_mean([abs(e) for e in err]), 4),
            'rmse': round(math.sqrt(_mean([e * e for e in err])), 4),
            'bias_se_clustered_by_game': round(c, 4) if c else None,
            'n_game_clusters': k}
    return out
