"""Minimum-viable production joint coupling.

THIS IS A PRODUCTION BASELINE, NOT A CLAIM ABOUT OPTIMAL DEPENDENCE.

What it does:
  * preserves the accepted MARGINALS -- reconciliation rescales, it never
    re-models;
  * reconciles team totals so player draws sum to a coherent team game;
  * eliminates physically impossible player/team combinations;
  * couples QB passing outcomes with receiver outcomes through the shared team
    pass volume;
  * couples carry allocations through the shared team carry volume.

What it deliberately does NOT do:
  * invent a correlation structure the evidence does not support. Where the
    dependence is a known open debt -- WR1<->RB1 and TE1<->RB1 coupling, the
    2024 carry rank1<->rank2 anomaly -- the coupling is left NEUTRAL rather
    than fitted to a historical anomaly. Tuning to those specific anomalies is
    forbidden.

THE MARGINAL-PRESERVATION RULE IS THE LOAD-BEARING ONE. Reconciliation that
cosmetically improves physical validity while silently degrading marginal
calibration is the failure mode Stage 3 diagnostics already flagged, so the
degradation is MEASURED and returned rather than assumed absent.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

NEUTRAL_COUPLINGS = (
    'WR1<->RB1 target/carry dependence -- Stage 3 found it not well modelled',
    'TE1<->RB1 dependence -- same',
    '2024 carry rank1<->rank2 anomaly -- registered as OQ-2024-RB1RB2, '
    'explicitly NOT tuned to',
)


def reconcile_team_total(draws: np.ndarray, team_total: np.ndarray,
                         tol: float = 1e-9) -> Outcome:
    """Scale player draws so each draw index sums to that draw's team total.

    Per DRAW INDEX, not on the mean: a mean-level reconciliation leaves
    individual draws incoherent, and those are what a joint artifact is for.
    """
    D = np.asarray(draws, float)          # (n_players, n_draws)
    T = np.asarray(team_total, float)     # (n_draws,)
    if D.ndim != 2 or T.ndim != 1 or D.shape[1] != T.shape[0]:
        return Outcome.fail(
            'JOINT_SHAPE_MISMATCH',
            f'draws {D.shape} against team totals {T.shape}')
    s = D.sum(0)
    before = float(np.abs(s - T).mean())
    scale = np.where(s > tol, T / np.maximum(s, tol), 0.0)
    R = D * scale[None, :]
    after = float(np.abs(R.sum(0) - T).mean())
    # marginal preservation, measured
    m0, m1 = D.mean(1), R.mean(1)
    shift = float(np.abs(m1 - m0).mean())
    rel = float(np.abs(m1 - m0).sum() / max(np.abs(m0).sum(), 1e-9))
    return Outcome.ok(
        'TEAM_TOTAL_RECONCILED', value=R,
        detail=f'residual {before:.4f} -> {after:.4f}; mean marginal shift '
               f'{shift:.6f} ({100 * rel:.4f}% of total mass)',
        residual_before=before, residual_after=after,
        marginal_mean_shift=shift, marginal_rel_shift_pct=100 * rel)


def enforce_possible(draws: dict, orderings=(('receptions', 'targets'),
                                             ('completions', 'attempts'))) -> Outcome:
    """Remove impossible combinations PER DRAW, and report how many there were.

    Clipping silently would convert a measurable defect into an invisible one,
    so the count is returned and a caller that ignores it is the one at fault.
    """
    fixed = {k: np.array(v, float) for k, v in draws.items()}
    n_bad = 0
    for lo, hi in orderings:
        if lo in fixed and hi in fixed:
            m = fixed[lo] > fixed[hi]
            n_bad += int(m.sum())
            fixed[lo] = np.where(m, fixed[hi], fixed[lo])
    for k, v in fixed.items():
        neg = v < 0
        n_bad += int(neg.sum())
        fixed[k] = np.where(neg, 0.0, v)
    return Outcome.ok('IMPOSSIBLE_COMBINATIONS_REMOVED', value=fixed,
                      detail=f'{n_bad} impossible draw cell(s) corrected',
                      n_corrected=n_bad)


def couple_through_volume(player_shares: np.ndarray,
                          team_volume: np.ndarray) -> Outcome:
    """The only coupling this baseline asserts: players share a team volume.

    Every player's draw i uses team volume draw i, so a high-volume game lifts
    all of them together. That is a mechanism, not a fitted correlation.
    """
    S = np.asarray(player_shares, float)
    V = np.asarray(team_volume, float)
    if S.ndim != 2 or V.ndim != 1 or S.shape[1] != V.shape[0]:
        return Outcome.fail('JOINT_SHAPE_MISMATCH',
                            f'shares {S.shape} against volume {V.shape}')
    return Outcome.ok('COUPLED_THROUGH_VOLUME', value=S * V[None, :],
                      detail=f'{S.shape[0]} players coupled through a shared '
                             f'team volume over {V.shape[0]} draws')
