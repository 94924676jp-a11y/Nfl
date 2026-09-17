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

# CRPS AND PIT ARE IMPORTED, NEVER REIMPLEMENTED.
#
# Twelve private `crps` implementations already exist in `nfl/research/**`, and
# a thirteenth here would be the duplication this module was supposed to end.
# `nfl/product/evaluator.py` is the WIRED postgame scorer -- reached through
# `nfl/tools/score_game.py` from `research/postgame.py`,
# `research/same_day_retrospective.py` and two `prospective/q9shadow` modules --
# and it already carries an exact empirical CRPS and a non-randomised PIT.
#
# THE DEPENDENCY RUNS ONE WAY, product <- production, and never back. `product`
# scores ONE SEALED FORECAST against ONE FINISHED GAME and owns the ledger and
# the seal verification. This module scores A PANEL against A BASELINE. They
# answer different questions and share the primitives.
from nfl.product.evaluator import crps, pit  # noqa: E402,F401

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

#: A predictor whose spread is below this multiple of the outcome's spread is
#: treated as constant. See `calibration_slope`.
DEGENERATE_PRED_SD_RATIO = 1e-10


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
    # A PREDICTION IS ONE-PER-ROW OR A DRAW MATRIX PER ROW, and the row axis is
    # the first one either way. The first version reshaped predictions to 1-D,
    # which is right for a probability and silently flattens a (rows, draws)
    # CRPS matrix into 60,000 scalars against 120 outcomes. Only `y` and
    # `clusters` are flattened; a prediction keeps its shape and is indexed on
    # axis 0.
    y = np.asarray(y, float).reshape(-1)
    a = np.asarray(p_a, float)
    b = np.asarray(p_b, float)
    c = np.asarray(clusters).reshape(-1)
    n = y.size
    if not (a.shape[0] == b.shape[0] == c.size == n) or n == 0:
        raise EvaluatorError(
            f'EVALUATOR_LENGTH_MISMATCH: y {n}, a rows {a.shape[0] if a.size else 0}, '
            f'b rows {b.shape[0] if b.size else 0}, clusters {c.size}')
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


def _crps_only(y, x_rows):
    """Mean CRPS over rows. `x_rows` is (n_rows, n_draws); `y` is (n_rows,).

    Signature matches the binary scorers -- (outcome, prediction) -- so
    `clustered_delta` can take any scorer without knowing which it holds.
    """
    Y = np.asarray(y, float).reshape(-1)
    X = np.asarray(x_rows, float)
    if X.ndim != 2 or X.shape[0] != Y.size or X.size == 0:
        raise EvaluatorError(
            f'EVALUATOR_SHAPE: draws {X.shape} against {Y.size} outcome(s).')
    return float(np.mean([crps(X[i], Y[i]) for i in range(Y.size)]))


def _mae_only(y, p):
    """Mean absolute error, for a CONTINUOUS target.

    ADDED FOR OAS1, which regresses a continuous per-play EPA. Every scorer
    above is for a binary outcome or a draw matrix, so a continuous point
    forecast had nowhere to be scored and the alternative was scoring it
    outside the evaluator -- which is how a candidate and a baseline end up
    measured by two different functions.
    """
    Y = np.asarray(y, float).reshape(-1)
    P = np.asarray(p, float).reshape(-1)
    if Y.size == 0 or P.size != Y.size:
        raise EvaluatorError(
            f'EVALUATOR_SHAPE: {P.size} prediction(s) against {Y.size} '
            f'outcome(s).')
    return float(np.abs(Y - P).mean())


def _rmse_only(y, p):
    """Root mean squared error, for a CONTINUOUS target."""
    Y = np.asarray(y, float).reshape(-1)
    P = np.asarray(p, float).reshape(-1)
    if Y.size == 0 or P.size != Y.size:
        raise EvaluatorError(
            f'EVALUATOR_SHAPE: {P.size} prediction(s) against {Y.size} '
            f'outcome(s).')
    return float(np.sqrt(((Y - P) ** 2).mean()))


def calibration_slope(y, p) -> dict:
    """OLS slope of realised on predicted. Target 1.0.

    THE METRIC THIS PROJECT HAS ALREADY BEEN BURNED BY. Prior team-plays
    baselines showed slopes of 0.1416, 0.0384 and 0.2549 against a target of
    1.0 while still producing a plausible MAE. A slope near zero with a decent
    MAE is the signature of a model that has learned the league mean and
    nothing else, and MAE alone cannot tell you that.

    Returns a dict rather than a bare float because a DEGENERATE predictor --
    zero variance in `p`, which B0 has by construction -- has no slope at all,
    and returning 0.0 for that would be a measurement where there is none.
    """
    Y = np.asarray(y, float).reshape(-1)
    P = np.asarray(p, float).reshape(-1)
    if Y.size == 0 or P.size != Y.size:
        raise EvaluatorError(
            f'EVALUATOR_SHAPE: {P.size} prediction(s) against {Y.size} '
            f'outcome(s).')
    vp = float(P.var())
    # A CONSTANT-IN-INTENT PREDICTOR IS NOT EXACTLY CONSTANT IN FLOAT, AND A
    # LIVE CHAIN PROVED IT. The first version guarded on `vp <= 0.0`. B0
    # emits one repeated value, but building it as `mu + f() + f()` leaves a
    # variance of about 4.8e-35 rather than exactly zero, the guard let it
    # through, and the chain reported a B0 calibration slope of -0.8153 beside
    # a `pred_sd` of 0.00000. That is a regression of the outcome on
    # rounding noise, presented as a measurement.
    #
    # The test is therefore RELATIVE to the outcome's own scale: a predictor
    # whose spread is a ten-billionth of the target's carries no calibration
    # information whatever its exact variance.
    sp, sy = float(np.std(P)), float(np.std(Y))
    if vp <= 0.0 or sp <= DEGENERATE_PRED_SD_RATIO * max(sy, 1e-12):
        return {'slope': None, 'intercept': None, 'n': int(Y.size),
                'predictor_variance': vp, 'predictor_sd': sp,
                'outcome_sd': sy,
                'degenerate_ratio_threshold': DEGENERATE_PRED_SD_RATIO,
                'why_none': 'the predictor is constant to within floating '
                            'point, so no slope is identified. A constant '
                            'forecast is not a badly calibrated one; it is '
                            'uncalibratable, and reporting a number fitted '
                            'to rounding noise would be worse than '
                            'reporting none.'}
    b = float(np.cov(P, Y, ddof=1)[0, 1] / vp)
    a = float(Y.mean() - b * P.mean())
    return {'slope': b, 'intercept': a, 'n': int(Y.size),
            'predictor_variance': vp, 'target_slope': 1.0}


#: Every scorer takes (outcome, prediction) and returns a scalar where LOWER IS
#: BETTER, which is what lets `clustered_delta` be indifferent to which it has.
#: `crps` is the imported product implementation; nothing here re-derives it,
#: and `mae`/`rmse` were added for OAS1's continuous target rather than scored
#: outside this module.
SCORERS = {'brier': _brier_only, 'log_loss': _logloss_only,
           'crps': _crps_only, 'mae': _mae_only, 'rmse': _rmse_only}


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
