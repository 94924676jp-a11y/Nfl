"""Mean-preserving rectification of additive share draws. P4F section 2.

P4C draws `W = clip(C + eps, 0, 1)`. Clipping at the lower boundary throws away
negative residual mass and keeps positive mass, so the draw mean sits ABOVE the
centre it was built around -- by 62% to 123% for running backs with under ten
prior carries, and by under 1% for backs with a hundred or more. The estimator
stops being mean-unbiased exactly where the least is known.

This solves a deterministic shift that puts the mean back where it was asked to
be. It reads no outcome, fits nothing, and has no tuning constant: the only
numbers in it are a bracket derived from the draws themselves, an iteration
count and a tolerance, all fixed in predeclaration_p4f.md section 2.

What it is NOT: a correction to the centre. `C` is untouched. What changes is
where the DRAWS sit relative to it.
"""
from __future__ import annotations

import numpy as np

TOL = 1e-9
ITERS = 80
DEGENERATE_EDGE = 1e-12


class InfeasibleRectification(ValueError):
    """A row whose requested mean cannot be produced by any shift."""


def _prepare(centre, resid, lo, hi):
    C = np.asarray(centre, np.float64).reshape(-1)
    E = np.asarray(resid, np.float64)
    if E.ndim != 2 or E.shape[0] != C.shape[0]:
        raise InfeasibleRectification(
            f'SHAPE_MISMATCH: centre {C.shape} against residuals {E.shape}')
    if hi <= lo:
        raise InfeasibleRectification(f'DEGENERATE_RANGE: [{lo}, {hi}]')
    bad_c = ~np.isfinite(C) | (C < lo - 1e-12) | (C > hi + 1e-12)
    bad_e = ~np.isfinite(E).all(axis=1)
    return C, E, bad_c, bad_e


def rectify(centre, resid, lo=0.0, hi=1.0, tol=TOL, iters=ITERS):
    """Return corrected draws, the shift, and an honest report of what happened.

    `g(delta) = mean_m clip(C + eps - delta, lo, hi)` is continuous and
    non-increasing. At `delta = C + min eps - hi` every draw is at `hi`, so
    `g = hi >= C`; at `delta = C + max eps - lo` every draw is at `lo`, so
    `g = lo <= C`. A root therefore exists for every feasible `C` by the
    intermediate value theorem, and bisection on that bracket cannot miss it.

    Rows that are infeasible are REPORTED, never quietly moved into range.
    """
    C, E, bad_c, bad_e = _prepare(centre, resid, lo, hi)
    n, m = E.shape
    bad = bad_c | bad_e
    Emin = np.where(bad, 0.0, np.nanmin(np.where(np.isfinite(E), E, np.inf), 1))
    Emax = np.where(bad, 0.0, np.nanmax(np.where(np.isfinite(E), E, -np.inf), 1))
    a = (C + Emin - (hi - lo)).reshape(-1, 1)     # g(a) = hi
    b = (C + Emax).reshape(-1, 1)                 # g(b) = lo
    Cc = C.reshape(-1, 1)
    for _ in range(iters):
        d = 0.5 * (a + b)
        g = np.clip(Cc + E - d, lo, hi).mean(axis=1, keepdims=True)
        high = g > Cc                             # root lies to the RIGHT
        a = np.where(high, d, a)
        b = np.where(high, b, d)
    delta = (0.5 * (a + b)).reshape(-1)
    W = np.clip(Cc + E - delta.reshape(-1, 1), lo, hi)
    achieved = W.mean(axis=1)
    err = np.abs(achieved - C)
    # a row that could not be solved keeps P4C's untouched draws, and says so
    if bad.any():
        W[bad] = np.clip(Cc[bad] + E[bad], lo, hi)
        delta[bad] = np.nan
    degenerate = (~bad) & ((C <= lo + DEGENERATE_EDGE) | (C >= hi - DEGENERATE_EDGE))
    over = (~bad) & (err > tol)
    report = {
        'n': int(n), 'm': int(m), 'tolerance': float(tol), 'iterations': int(iters),
        'max_abs_centre_error_float64': float(err[~bad].max()) if (~bad).any() else None,
        'mean_abs_centre_error_float64': float(err[~bad].mean()) if (~bad).any() else None,
        'rows_within_tolerance': int((~bad & ~over).sum()),
        'rows_outside_tolerance': int(over.sum()),
        'rows_degenerate_solution_set': int(degenerate.sum()),
        'rows_infeasible': int(bad.sum()),
        'infeasible_centre': int(bad_c.sum()),
        'infeasible_residual': int(bad_e.sum()),
        'delta_mean': float(np.nanmean(delta)) if (~bad).any() else None,
        'delta_min': float(np.nanmin(delta)) if (~bad).any() else None,
        'delta_max': float(np.nanmax(delta)) if (~bad).any() else None,
        'state': ('PASS' if (not over.any() and not bad.any())
                  else 'FAIL' if over.any() else 'PASS_WITH_INFEASIBLE'),
        'flags': {'DEGENERATE_SOLUTION_SET': int(degenerate.sum()),
                  'INFEASIBLE_ROW': int(bad.sum())},
    }
    return W, delta, report


def recentre_only(centre, resid, lo=0.0, hi=1.0):
    """The CONFOUND CONTROL of predeclaration section 3, system MC_ONLY.

    Mean-preserving rectification does two things at once: it removes the
    rectification bias, and it removes the Monte-Carlo error in the sample mean
    of the draws. The second would improve a proper score on its own with no
    bias fix in it at all. This removes only the second -- the residuals are
    recentred to zero sample mean and then clipped exactly as P4C clips -- so
    the difference between the two isolates the bias fix.
    """
    C, E, bad_c, bad_e = _prepare(centre, resid, lo, hi)
    Ec = E - E.mean(axis=1, keepdims=True)
    return np.clip(C.reshape(-1, 1) + Ec, lo, hi)


def clipped_expectation(centre, resid, lo=0.0, hi=1.0):
    """P4C's own E[W], for the bias table. No correction applied."""
    C, E, _bc, _be = _prepare(centre, resid, lo, hi)
    return np.clip(C.reshape(-1, 1) + E, lo, hi).mean(axis=1)


def recover_residuals(W, centre, delta, lo=0.0, hi=1.0):
    """AUDIT: the raw residual identity, for every draw not at a boundary.

    Returns (eps_hat, interior_mask). On the interior the identity
    `eps = W - C + delta` holds exactly, so the transformation is invertible
    wherever it did not clip, and the clipped fraction is itself reportable.
    """
    C = np.asarray(centre, np.float64).reshape(-1, 1)
    d = np.asarray(delta, np.float64).reshape(-1, 1)
    W = np.asarray(W, np.float64)
    interior = (W > lo + 0.0) & (W < hi - 0.0)
    return W - C + d, interior
