"""P2 repair 3: the 2025 starting-QB cohort, rebuilt from the H1 harness.

NOTHING HERE REBUILDS THE FRAME OR THE ELIGIBILITY RULE. `h1_frame.build`,
`qb2_lib.attach` and `h1_run.eligible` are imported and called unmodified, so
this module reaches the same 540 rows the prior study established rather than a
second opinion about what "a 2025 starting-QB game" means. What is added here
is only what the prior study did not need: a chi-square tail probability (there
is no scipy in this environment), a randomized PIT that is safe on an atom, and
a block bootstrap over whole games.

WHY A RANDOMIZED PIT AND NOT THE PUBLISHED ONE. 78.89% of the 540 realised
shares are EXACTLY 1.0 -- the quarterback took every one of his team's
dropbacks. A share is therefore a ratio of integers with a very large atom, and
`h1_run.score` scored it with `discrete=False`, i.e. the mid-PIT
`P(X < y) + 0.5 P(X = y)`. The mid-PIT is not uniform for an atomic predictive
distribution even under a perfect forecast, so a large chi-square from it is
partly the instrument. Both are reported here, always, and neither is dropped.
"""
from __future__ import annotations

import collections
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'rc1'),
           str(_REPO / 'nfl' / 'research' / 'p4b'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import h1_frame as FR                                             # noqa: E402
import h1_run as RUN                                              # noqa: E402
import qb2_lib as Q                                               # noqa: E402

EVAL_SEASON = RUN.EVAL_SEASON
RUNG = RUN.RUNG
SEED = RUN.SEED
M = RUN.M
PIT_SEED = RUN.PIT_SEED
BOOT_SEED = 20260915
N_BOOT = 2000


def cohort():
    """The 540 eligible 2025 starting-QB rows, plus the whole frame.

    Returns (keep, allrows, pools). `keep` is exactly `h1_run.eligible`'s
    output, which on this frame is 540 rows all carrying `_frame == 'PRIMARY'`.
    An empty or short cohort raises: this frame is a fixed 540 and a different
    number means the inputs moved, which is an error and not a result.
    """
    rows, fmeta = FR.build()
    Q.attach(rows)
    keep, emeta = RUN.eligible(rows)
    if len(keep) != 540:
        raise SystemExit(
            f'P2_COHORT_SIZE_CHANGED: {len(keep)} rows, expected the 540 the '
            f'defect was established on. Refusing to score a different frame '
            f'under the same name.')
    po = Q.pools(rows, EVAL_SEASON)
    return keep, rows, po, {'frame': fmeta, 'eligibility': emeta}


# ------------------------------------------------------------------ statistics
def chi2_sf(x, df):
    """P(chi2_df > x), by the regularized upper incomplete gamma Q(df/2, x/2).

    There is no scipy in this environment. The recursion is the standard one,
    Q(a+1, z) = Q(a, z) + z**a * exp(-z) / Gamma(a+1), started at
    Q(1/2, z) = erfc(sqrt(z)) for odd df and Q(1, z) = exp(-z) for even df.
    Self-tested in nfl/tests/test_qb_share_calibration.py against published
    chi-square table values rather than trusted.
    """
    if x <= 0:
        return 1.0
    z = x / 2.0
    if df % 2:
        a, q = 0.5, math.erfc(math.sqrt(z))
    else:
        a, q = 1.0, math.exp(-z)
    while a < df / 2.0 - 1e-9:
        q += z ** a * math.exp(-z) / math.gamma(a + 1.0)
        a += 1.0
    return min(max(q, 0.0), 1.0)


def pit_chi2(u, bins=10):
    """The prior study's own uniformity statistic: a 10-bin chi-square."""
    u = np.asarray(u, float)
    h, _ = np.histogram(u, bins=bins, range=(0, 1))
    e = len(u) / float(bins)
    return float((((h - e) ** 2) / e).sum()), h.tolist(), bins - 1


def randomized_pit(draws, y, rng):
    """h1_run.rpit, imported rather than re-derived."""
    return RUN.rpit(draws, y, rng)


def mid_pit(draws, y):
    """h1_run.cpit -- what the published share PIT actually used."""
    return RUN.cpit(draws, y)


def block_boot(values, keys, stat, n=N_BOOT, seed=BOOT_SEED):
    """Resample whole GAMES with replacement. Games are not independent rows.

    `values` is a list of per-row records, `keys` the game id of each. Returns
    the bootstrap distribution of `stat(list_of_records)`.
    """
    by = collections.defaultdict(list)
    for v, k in zip(values, keys):
        by[k].append(v)
    gk = sorted(by)
    rng = np.random.default_rng(seed)
    out = np.empty(n, float)
    for i in range(n):
        pick = rng.integers(0, len(gk), len(gk))
        rs = [r for j in pick for r in by[gk[j]]]
        out[i] = stat(rs)
    return out, gk


def ci95(d):
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def tost(point, boot, margin):
    """Two one-sided tests against a PREDECLARED margin, clustered SE.

    Returns the verdict and never the word "calibrated": failure to reject is
    reported as NOT_SHOWN_EQUIVALENT, which is what it is.
    """
    se = float(np.std(boot, ddof=1))
    if se <= 0:
        return {'margin': margin, 'clustered_se': se,
                'verdict': 'DEGENERATE_SE'}
    lo, hi = point - 1.645 * se, point + 1.645 * se
    inside = bool(lo > -margin and hi < margin)
    return {'margin': margin, 'clustered_se': se, 'ci90': [lo, hi],
            'equivalence_ci90_inside_margin': inside,
            'verdict': 'EQUIVALENT_WITHIN_MARGIN' if inside
                       else 'NOT_SHOWN_EQUIVALENT'}
