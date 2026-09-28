#!/usr/bin/env python3.12
"""The metric battery. Pure functions over (predicted, actual) so each one is testable alone.

WHAT EACH ONE ANSWERS, because using the wrong one is how a bad model looks good.

  MAE, RMSE          average error size. RMSE punishes the big misses, which in DFS is where the
                     money is; MAE is the one to read for typical accuracy.
  bias               systematic level error. A model can have excellent MAE and be uniformly 15 per
                     cent low, which is invisible in MAE and fatal to a value calculation.
  calibration slope  regress actual on predicted. A slope of 1 means a one-point rise in the
                     projection really is worth a point. A slope below 1 means the model is
                     over-spread; above 1, under-spread.
  Pearson r          linear association, dominated by the top of the board.
  Spearman rho       RANK association, which is what a lineup actually consumes -- an optimiser
                     cares who is above whom, not by how much.
  quantile coverage  of the predictive distribution. A nominal 80 per cent interval should contain
                     the outcome 80 per cent of the time. Under-coverage means false confidence.
  PIT                the probability integral transform. If the distribution is right, the outcome's
                     own quantile is UNIFORM. This is the sharpest distributional test available and
                     it catches errors coverage misses.
  CRPS               a proper score for the whole distribution, computed from an empirical sample.
                     Lower is better and it cannot be improved by hedging.
  Brier / log loss   for EVENT probabilities, such as P(20+ DK points). Log loss punishes a confident
                     wrong call far harder than Brier does; both are reported because they disagree
                     in a way that matters.
  ceiling calibration how often the outcome reaches the predicted high quantile. A tournament model
                     lives on this and it is NOT the same as mean accuracy.

CALIBRATION AND DISCRIMINATION ARE DIFFERENT PROPERTIES AND PASSING ONE SAYS NOTHING ABOUT THE OTHER.
That is a standing rule in this project and it is why both are always reported side by side.
"""
from __future__ import annotations

import math
import statistics


def _pairs(pred, actual):
    return [(float(p), float(a)) for p, a in zip(pred, actual)
            if p is not None and a is not None
            and not (isinstance(p, float) and p != p)
            and not (isinstance(a, float) and a != a)]


def point_metrics(pred, actual):
    xy = _pairs(pred, actual)
    n = len(xy)
    if n < 3:
        return {'state': 'TOO_FEW', 'n': n}
    xs = [p for p, _ in xy]
    ys = [a for _, a in xy]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    mae = sum(abs(p - a) for p, a in xy) / n
    rmse = math.sqrt(sum((p - a) ** 2 for p, a in xy) / n)
    sxy = sum((p - mx) * (a - my) for p, a in xy)
    sxx = sum((p - mx) ** 2 for p in xs)
    syy = sum((a - my) ** 2 for a in ys)
    r = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None
    slope = sxy / sxx if sxx > 0 else None
    intercept = (my - slope * mx) if slope is not None else None
    return {
        'state': 'OK', 'n': n,
        'mae': round(mae, 5), 'rmse': round(rmse, 5),
        'bias': round(mx - my, 5),
        'bias_pct_of_actual': round((mx - my) / my, 5) if my else None,
        'mean_pred': round(mx, 5), 'mean_actual': round(my, 5),
        'sd_pred': round(statistics.pstdev(xs), 5) if n > 1 else None,
        'sd_actual': round(statistics.pstdev(ys), 5) if n > 1 else None,
        'sd_ratio_pred_over_actual': (round(statistics.pstdev(xs) / statistics.pstdev(ys), 5)
                                      if n > 1 and statistics.pstdev(ys) else None),
        'pearson_r': round(r, 5) if r is not None else None,
        'spearman_rho': spearman(xs, ys),
        'calibration_slope': round(slope, 5) if slope is not None else None,
        'calibration_intercept': round(intercept, 5) if intercept is not None else None,
        'SD_RATIO_READING': ('this is the spread of PREDICTED means against the spread of realised '
                             'outcomes. It is NOT evidence about predictive interval width, and a '
                             'low value is not by itself a correlation ceiling.'),
    }


def spearman(xs, ys):
    if len(xs) < 3:
        return None

    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    n = len(rx)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    return round(sxy / math.sqrt(sxx * syy), 5) if sxx > 0 and syy > 0 else None


def interval_coverage(lows, highs, actual, nominal):
    """Empirical coverage of a nominal interval, with a binomial standard error."""
    n = hit = 0
    for lo, hi, a in zip(lows, highs, actual):
        if lo is None or hi is None or a is None:
            continue
        n += 1
        if lo <= a <= hi:
            hit += 1
    if not n:
        return {'state': 'NO_DATA'}
    p = hit / n
    # A DEGENERATE RATE HAS NO USABLE STANDARD ERROR. At p exactly 0 or 1 the binomial error is
    # zero, and dividing a gap by it produced 4,472,135 standard errors in a test -- a number that
    # looks like overwhelming evidence and means the opposite. The Agresti-Coull adjustment is used
    # for the error at the boundary, and the boundary is flagged.
    degenerate = (hit == 0 or hit == n)
    pa = (hit + 2) / (n + 4)
    se = math.sqrt(pa * (1 - pa) / (n + 4)) if degenerate else math.sqrt(p * (1 - p) / n)
    return {'state': 'OK', 'nominal': nominal, 'empirical': round(p, 5), 'n': n,
            'binomial_se': round(se, 6),
            'rate_is_degenerate': degenerate,
            'gap_in_se': (round((p - nominal) / se, 3) if se > 1e-9 else None),
            'NAIVE_SE_WARNING': ('this binomial error treats player-weeks as independent. They are '
                                 'not -- players share games -- so the true error is larger. Read a '
                                 'gap of one or two of these as suggestive, never as a result.')}


def pit(samples_fn, actual):
    """Probability integral transform values, and a uniformity test on them.

    samples_fn(i) must return the sorted predictive sample for observation i.
    """
    vals = []
    for i, a in enumerate(actual):
        if a is None:
            continue
        s = samples_fn(i)
        if not s:
            continue
        below = sum(1 for x in s if x < a)
        ties = sum(1 for x in s if x == a)
        vals.append((below + 0.5 * ties) / len(s))
    if len(vals) < 20:
        return {'state': 'TOO_FEW', 'n': len(vals)}
    vals.sort()
    n = len(vals)
    # Kolmogorov-Smirnov distance from uniform
    ks = max(max(abs((i + 1) / n - v), abs(v - i / n)) for i, v in enumerate(vals))
    deciles = [0] * 10
    for v in vals:
        deciles[min(9, int(v * 10))] += 1
    expect = n / 10
    chi2 = sum((d - expect) ** 2 / expect for d in deciles)
    return {'state': 'OK', 'n': n, 'ks_distance_from_uniform': round(ks, 5),
            'ks_critical_95': round(1.36 / math.sqrt(n), 5),
            'uniform_rejected_at_95': ks > 1.36 / math.sqrt(n),
            'decile_counts': deciles, 'chi2_vs_uniform': round(chi2, 3),
            'mean_pit': round(statistics.fmean(vals), 5),
            'READING': ('if the predictive distribution is right, these are uniform. A mean above '
                        '0.5 means outcomes land high in the distribution, so the model is '
                        'projecting low. Deciles piled at the ends mean the distribution is too '
                        'narrow.')}


def crps_empirical(samples, a):
    """CRPS for one observation from an empirical sample. Lower is better.

    Uses the energy form: E|X-a| - 0.5*E|X-X'|, computed exactly on the sorted sample.
    """
    if not samples or a is None:
        return None
    s = sorted(samples)
    n = len(s)
    t1 = sum(abs(x - a) for x in s) / n
    # E|X-X'| via the sorted-sample identity, O(n)
    acc = 0.0
    for i, x in enumerate(s):
        acc += x * (2 * i - n + 1)
    t2 = 2.0 * acc / (n * n)
    return t1 - 0.5 * t2


def brier(probs, outcomes):
    p = [(float(x), 1.0 if y else 0.0) for x, y in zip(probs, outcomes) if x is not None]
    if not p:
        return {'state': 'NO_DATA'}
    n = len(p)
    b = sum((x - y) ** 2 for x, y in p) / n
    base = statistics.fmean([y for _x, y in p])
    ref = base * (1 - base)
    return {'state': 'OK', 'n': n, 'brier': round(b, 6), 'base_rate': round(base, 5),
            'brier_skill_vs_base_rate': (round(1 - b / ref, 5) if ref > 0 else None)}


def log_loss(probs, outcomes, eps=1e-6):
    p = [(min(1 - eps, max(eps, float(x))), 1.0 if y else 0.0)
         for x, y in zip(probs, outcomes) if x is not None]
    if not p:
        return {'state': 'NO_DATA'}
    n = len(p)
    ll = -sum(y * math.log(x) + (1 - y) * math.log(1 - x) for x, y in p) / n
    base = statistics.fmean([y for _x, y in p])
    base = min(1 - eps, max(eps, base))
    bl = -(base * math.log(base) + (1 - base) * math.log(1 - base))
    return {'state': 'OK', 'n': n, 'log_loss': round(ll, 6),
            'log_loss_of_base_rate': round(bl, 6),
            'skill_vs_base_rate': round(1 - ll / bl, 5) if bl > 0 else None,
            'WHY_BOTH': ('log loss punishes a confident wrong call far harder than Brier. They '
                         'disagree when a model is overconfident, which is exactly when it matters.')}


def ceiling_calibration(predicted_high, actual, nominal):
    """How often the outcome reaches a predicted high quantile. A tournament model lives here."""
    n = hit = 0
    for q, a in zip(predicted_high, actual):
        if q is None or a is None:
            continue
        n += 1
        if a >= q:
            hit += 1
    if not n:
        return {'state': 'NO_DATA'}
    p = hit / n
    degenerate = (hit == 0 or hit == n)
    pa = (hit + 2) / (n + 4)
    se = math.sqrt(pa * (1 - pa) / (n + 4)) if degenerate else math.sqrt(p * (1 - p) / n)
    return {'state': 'OK', 'rate_is_degenerate': degenerate,
            'nominal_exceedance': round(1 - nominal, 5),
            'empirical_exceedance': round(p, 5), 'n': n, 'binomial_se': round(se, 6),
            'READING': ('a tournament needs the high tail right. Exceeding a nominal 90th '
                        'percentile should happen 10 per cent of the time; more often means the '
                        'ceiling is too low, less means it is fantasy.')}
