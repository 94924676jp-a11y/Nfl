"""DraftKings NFL classic scoring. A deterministic adapter, never a model.

EVERY NUMBER HERE IS A PUBLISHED PLATFORM RULE, not a fitted quantity. That is
why they are constants and why they are all in one place: a scoring adapter is
a CONVENTION, and changing platform must not change a single simulated event.
Nothing in this file estimates anything.

THE RULE THIS ENFORCES: fantasy points are RECOVERABLE from the football stats.
Given a player's simulated passing, rushing, receiving and kicking draws, his
DK points are a pure function of them, computed per draw so the distribution is
the distribution of the football, not a separate model of the points.
"""
from __future__ import annotations

import numpy as np

SPEC_VERSION = 'dk-nfl-classic-1'

PASS_YD = 0.04
PASS_TD = 4.0
INTERCEPTION = -1.0
PASS_300_BONUS = 3.0
RUSH_YD = 0.1
RUSH_TD = 6.0
RUSH_100_BONUS = 3.0
REC_YD = 0.1
REC_TD = 6.0
RECEPTION = 1.0          # full PPR
REC_100_BONUS = 3.0
FUMBLE_LOST = -1.0
FG_UNDER_40 = 3.0
FG_40_49 = 4.0
FG_50_PLUS = 5.0
EXTRA_POINT = 1.0


def _a(x, n):
    if x is None:
        return np.zeros(n)
    return np.asarray(x, dtype=float)


def skill_points(n, *, pass_yds=None, pass_td=None, ints=None,
                 rush_yds=None, rush_td=None, rec=None, rec_yds=None,
                 rec_td=None, fumbles_lost=None):
    """DK points per draw for a non-kicker, from his own simulated stats."""
    py, pt, it = _a(pass_yds, n), _a(pass_td, n), _a(ints, n)
    ry, rt = _a(rush_yds, n), _a(rush_td, n)
    rc, cy, ct = _a(rec, n), _a(rec_yds, n), _a(rec_td, n)
    fl = _a(fumbles_lost, n)
    p = (py * PASS_YD + pt * PASS_TD + it * INTERCEPTION
         + ry * RUSH_YD + rt * RUSH_TD
         + rc * RECEPTION + cy * REC_YD + ct * REC_TD
         + fl * FUMBLE_LOST)
    # THE BONUSES ARE PER DRAW, which is the whole point of holding the
    # distribution: a 100-yard bonus is a property of a WORLD, and applying it
    # to a mean would award a fraction of a bonus nobody can score.
    p = p + (py >= 300) * PASS_300_BONUS
    p = p + (ry >= 100) * RUSH_100_BONUS
    p = p + (cy >= 100) * REC_100_BONUS
    return p


def kicker_points(band_made: dict, xpm) -> np.ndarray:
    """DK points per draw for a kicker, from made field goals BY BAND."""
    keys = list(band_made)
    n = len(band_made[keys[0]]) if keys else len(xpm)
    pts = np.zeros(n)
    for band, made in band_made.items():
        if band.startswith('_'):
            continue
        v = np.asarray(made, dtype=float)
        if band in ('FG<20', 'FG20s', 'FG30s'):
            pts += v * FG_UNDER_40
        elif band == 'FG40s':
            pts += v * FG_40_49
        elif band == 'FG50+':
            pts += v * FG_50_PLUS
    return pts + np.asarray(xpm, dtype=float) * EXTRA_POINT


def summarise(x, thresholds=()):
    """mean / median / P10 / P25 / P75 / P90, MCSE, and threshold masses."""
    x = np.asarray(x, dtype=float)
    n = x.shape[0]
    q = np.percentile(x, [10, 25, 50, 75, 90])
    out = {'mean': float(x.mean()), 'median': float(q[2]),
           'p10': float(q[0]), 'p25': float(q[1]),
           'p75': float(q[3]), 'p90': float(q[4]),
           'sd': float(x.std(ddof=1)) if n > 1 else 0.0,
           'n_draws': int(n),
           # MCSE OF THE MEAN. Reported beside the mean so nobody has to guess
           # how much of a difference between two players is simulation noise.
           'mcse': float(x.std(ddof=1) / np.sqrt(n)) if n > 1 else 0.0,
           'p_zero': float((x <= 0).mean())}
    if thresholds:
        out['thresholds'] = [{'threshold': float(t),
                              'p_over': float((x > t).mean()),
                              'mcse': float(np.sqrt(
                                  max((x > t).mean() * (1 - (x > t).mean()), 0)
                                  / n))}
                             for t in thresholds]
    return out
