"""Proper scores, coverage, sharpness and a BASELINE COMPARISON, in one place.

WHY THIS MODULE EXISTS. Twelve research modules carry their own private `crps`
-- td1, q8 twice, p4c, same_day_retrospective, v4/p8, p4f, q9b, own9, rc1 and
more -- and Brier and log loss exist in exactly ONE place in the whole tree,
`nfl/research/v4/p1/cohort.py`. Nothing in `nfl/production/` or `nfl/product/`
scores a forecast at all. So "is this candidate better?" has been answered
twelve different ways and never against a baseline.

THE RULE THIS MODULE ENCODES, and it is the only opinion in it:

    A candidate is not better because it beats its predecessor. It is better
    when it beats a SIMPLE BASELINE on a proper score, out of sample.

`nfl/research/baselines/estimators.py` already holds the baseline family --
prior, in-season mean, season-to-date, recent-n, EWMA, shrunk, role average,
league prior. This module scores against them rather than re-deriving them.

WHAT IT REFUSES. Every function raises a NAMED error on empty input, on a
length mismatch, and on a probability outside [0, 1]. An evaluator that
silently returns 0.0 for an empty comparison is the defect class this project
pays for most often, and `nan` is not a score.

WHAT IT DOES NOT DO. It does not decide. It returns numbers and the intervals
around them; no function here returns a verdict, a threshold or the word
"better". Clustering is REQUIRED rather than optional, because games are not
independent observations and an iid interval on game-level data is too narrow
-- measured threefold too narrow on this project's own prop grading.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'nfl-evaluator-1'

#: Log loss is unbounded at 0 and 1, so a single confident miss would make the
#: whole score infinite and uninterpretable. The clip is DECLARED, reported on
#: every result, and the count of clipped rows is returned so a reader can see
#: whether the score depended on it.
LOG_EPS = 1e-6

#: Nominal interval levels. Coverage and sharpness are reported at all four
#: because a model can be right at the middle and wrong in the tails, and one
#: level hides that.
LEVELS = (0.50, 0.80, 0.90, 0.95)

#: Bootstrap resamples for every clustered interval in this module.
R_BOOT = 2000


class EvaluatorError(ValueError):
    """Named so a caller can tell a refusal from an arithmetic failure."""


def _binary(y, p):
    y = np.asarray(y, float).reshape(-1)
    p = np.asarray(p, float).reshape(-1)
    if y.size == 0:
        raise EvaluatorError('EVALUATOR_EMPTY: nothing to score. An empty '
                             'comparison is an error, not a score of zero.')
    if y.shape != p.shape:
        raise EvaluatorError(
            f'EVALUATOR_LENGTH_MISMATCH: {y.size} outcome(s) against '
            f'{p.size} prediction(s).')
    if not np.isfinite(p).all():
        raise EvaluatorError('EVALUATOR_NON_FINITE_PREDICTION')
    if (p < 0).any() or (p > 1).any():
        raise EvaluatorError(
            f'EVALUATOR_PROBABILITY_OUT_OF_RANGE: min {p.min():.6g}, '
            f'max {p.max():.6g}. A probability outside [0, 1] is not a '
            f'probability.')
    if not np.isin(y, (0.0, 1.0)).all():
        raise EvaluatorError(
            'EVALUATOR_OUTCOME_NOT_BINARY: Brier and log loss score a binary '
            'event; the outcomes are not all 0 or 1.')
    return y, p


def brier(y, p) -> float:
    """Mean squared error of a probability against a binary outcome."""
    y, p = _binary(y, p)
    return float(((p - y) ** 2).mean())


def log_loss(y, p) -> tuple:
    """(score, n_clipped). The clip count travels with the score, always."""
    y, p = _binary(y, p)
    n_clip = int(((p < LOG_EPS) | (p > 1 - LOG_EPS)).sum())
    q = np.clip(p, LOG_EPS, 1 - LOG_EPS)
    return float(-(y * np.log(q) + (1 - y) * np.log(1 - q)).mean()), n_clip


def interval_coverage(draws, y, levels=LEVELS) -> dict:
    """Empirical coverage of central predictive intervals against nominal.

    `draws` is (n_rows, n_draws); `y` is the realised value per row. Coverage
    alone says nothing about discrimination and this module does not pretend
    otherwise -- see `sharpness`, which is the other half.
    """
    D = np.asarray(draws, float)
    y = np.asarray(y, float).reshape(-1)
    if D.ndim != 2 or D.shape[0] != y.size or D.size == 0:
        raise EvaluatorError(
            f'EVALUATOR_SHAPE: draws {D.shape} against {y.size} outcome(s).')
    out = {}
    for lv in levels:
        lo = np.percentile(D, 100 * (1 - lv) / 2, axis=1)
        hi = np.percentile(D, 100 * (1 + lv) / 2, axis=1)
        out[float(lv)] = {'nominal': float(lv),
                          'empirical': float(((y >= lo) & (y <= hi)).mean()),
                          'n': int(y.size)}
    return out


def sharpness(draws, levels=LEVELS) -> dict:
    """Mean central-interval width. NEEDS NO OUTCOME, and that is the point.

    A model can reach nominal coverage by being uselessly wide. Coverage and
    sharpness are reported together or neither is interpretable.
    """
    D = np.asarray(draws, float)
    if D.ndim != 2 or D.size == 0:
        raise EvaluatorError(f'EVALUATOR_SHAPE: draws {D.shape}')
    out = {}
    for lv in levels:
        lo = np.percentile(D, 100 * (1 - lv) / 2, axis=1)
        hi = np.percentile(D, 100 * (1 + lv) / 2, axis=1)
        out[float(lv)] = {'mean_width': float((hi - lo).mean()),
                          'median_width': float(np.median(hi - lo))}
    return out


def clustered_delta(score_fn, y, p_a, p_b, clusters, r=R_BOOT,
                    seed=20260917) -> dict:
    """score(a) - score(b), with a CLUSTER bootstrap interval. Not optional.

    Games are not independent observations. Many markets on one player-game
    move together, and this project measured a naive binomial SE at 0.587pp
    against 1.359pp clustered by player-game and 1.653pp by game -- roughly
    threefold too narrow. `clusters` is therefore a required argument.
    """
    y = np.asarray(y, float).reshape(-1)
    a = np.asarray(p_a, float).reshape(-1)
    b = np.asarray(p_b, float).reshape(-1)
    c = np.asarray(clusters).reshape(-1)
    if not (y.size == a.size == b.size == c.size) or y.size == 0:
        raise EvaluatorError(
            f'EVALUATOR_LENGTH_MISMATCH: y {y.size}, a {a.size}, b {b.size}, '
            f'clusters {c.size}')
    keys = sorted(set(c.tolist()))
    if len(keys) < 2:
        raise EvaluatorError(
            f'EVALUATOR_TOO_FEW_CLUSTERS: {len(keys)}. A cluster bootstrap '
            f'over one cluster is not an interval.')
    idx = {k: np.where(c == k)[0] for k in keys}
    rng = np.random.default_rng(seed)
    d = np.empty(r, float)
    for i in range(r):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idx[keys[j]] for j in pick])
        d[i] = score_fn(y[sel], a[sel]) - score_fn(y[sel], b[sel])
    obs = score_fn(y, a) - score_fn(y, b)
    return {'delta': float(obs),
            'ci95_clustered': [float(np.percentile(d, 2.5)),
                               float(np.percentile(d, 97.5))],
            'p_a_better': float((d < 0).mean()),
            'n_rows': int(y.size), 'n_clusters': len(keys),
            'R': int(r), 'cluster_bootstrap': True}


def _brier_only(y, p):
    return float(((np.asarray(p, float) - np.asarray(y, float)) ** 2).mean())


def _logloss_only(y, p):
    q = np.clip(np.asarray(p, float), LOG_EPS, 1 - LOG_EPS)
    y = np.asarray(y, float)
    return float(-(y * np.log(q) + (1 - y) * np.log(1 - q)).mean())


SCORERS = {'brier': _brier_only, 'log_loss': _logloss_only}


def against_baseline(y, p_model, p_baseline, clusters,
                     baseline_name='baseline') -> Outcome:
    """THE GATE THIS MODULE EXISTS FOR, expressed as a measurement.

    Returns both proper scores for both arms and the clustered difference. It
    returns NO verdict: whether an interval excluding zero is enough to promote
    anything is a governance question with a pre-registration attached, not an
    arithmetic one, and this module deliberately stops short of it.
    """
    try:
        _binary(y, p_model)
        _binary(y, p_baseline)
    except EvaluatorError as e:
        return Outcome.blocked('EVALUATOR_REFUSED', str(e), cause=Cause.DATA)
    bm, bb = brier(y, p_model), brier(y, p_baseline)
    lm, nm = log_loss(y, p_model)
    lb, nb = log_loss(y, p_baseline)
    base_rate = float(np.asarray(y, float).mean())
    return Outcome.ok(
        'EVALUATOR_SCORED', spec_version=SPEC_VERSION,
        value={'model': {'brier': bm, 'log_loss': lm, 'n_clipped': nm},
               'baseline': {'brier': bb, 'log_loss': lb, 'n_clipped': nb}},
        baseline_name=baseline_name,
        base_rate=base_rate,
        # The no-skill reference, so a reader can see at once whether either
        # arm beats predicting the base rate for everyone.
        constant_brier=float(base_rate * (1 - base_rate)),
        brier=clustered_delta(SCORERS['brier'], y, p_model, p_baseline,
                              clusters),
        log_loss=clustered_delta(SCORERS['log_loss'], y, p_model, p_baseline,
                                 clusters),
        log_eps=LOG_EPS,
        governance='MEASUREMENT ONLY. No verdict is returned and no threshold '
                   'is applied here.',
        detail=f'model vs {baseline_name} on {len(np.asarray(y).reshape(-1))} '
               f'row(s)')
