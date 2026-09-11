"""Track 1 step 2: the causal mechanism, estimated rather than assumed.

THE CHAIN, IN THE ORDER THE DIRECTIVE FIXES IT.

    pregame team strength / environment
      -> simulated score differential by game phase
      -> pace, pass tendency, possession response
      -> team plays / dropbacks / rush attempts
      -> existing player allocation layers

Every arrow here is estimated from historical play-by-play on training data
only. Nothing in this module reads a realised score for the game being
forecast, a closing spread, a sportsbook total, or any postgame quantity. The
panel it consumes was built with the market columns never read.

WHY THE CONDITIONING VARIABLE IS THE QUARTER-BOUNDARY DIFFERENTIAL.

Because a within-quarter differential is partly CAUSED by the plays being
counted. Regressing a quarter's play count on a differential that those plays
moved would report the consequence as the cause and would look like a strong
mechanism. The differential entering the quarter is fixed before any of those
plays happen.

WHY THE RESPONSE IS A MULTIPLIER AND NEVER A LEVEL.

`plays` in this panel counts offensive play ROWS. The baseline forecasts
`team_off_snaps`, a snap-count quantity that includes penalty-nullified plays
appearing here as separate rows. They are different quantities. A ratio to the
same quantity's own neutral-state mean is comparable across that difference; a
level is not. So Track 1 multiplies whatever the baseline produced and never
substitutes a level into it.

WHY THE BUCKETS ARE THESE BUCKETS.

Predeclared on football grounds, before any response was estimated: a
three-point game is one field goal, and eleven points is two scores. The
boundaries are +/-3.5 and +/-10.5 for that reason and not because a grid
search preferred them. Five buckets over three quarters is sixteen cells
including the degenerate first quarter, which is the level of detail 13,093
team-quarters can carry. Dozens of brittle score-state cells is the failure
mode this is avoiding.

WHAT IS NOT TREATED, AND SAID RATHER THAN HIDDEN.

`team_rz_carries` has no response curve here: red-zone boundary conventions
were never reconciled against this panel, so its multiplier is exactly 1.0 and
Track 1 leaves it alone. A metric passed through unchanged is a declared
boundary, not a silent omission.
"""
from __future__ import annotations

import collections
import csv
import gzip
import json
import math
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

HERE = _REPO / 'nfl' / 'research' / 'track1'
SPEC_VERSION = 'track1-response-1'

# Predeclared on football grounds. See the module docstring.
BUCKET_EDGES = (-10.5, -3.5, 3.5, 10.5)
BUCKET_LABELS = ('<=-11', '-10..-4', '-3..+3', '+4..+10', '>=+11')
NEUTRAL = 2                      # index of '-3..+3'
QUARTERS = (1, 2, 3, 4)

# Half-life grid for the team-strength EWMA. Selected INSIDE the training
# window by leave-one-season-out error on margin, never on evaluation data.
HALF_LIFE_GRID = (2.0, 4.0, 8.0, 16.0)

# Which baseline metric each response drives. `team_rz_carries` is absent by
# declaration -- see the docstring.
METRIC_DRIVER = {
    'team_off_snaps': 'plays',
    'team_dropbacks_part': 'dropbacks',
    'team_targets': 'pass_att',
    'team_carries': 'designed_rush',
}
UNTREATED = ('team_rz_carries',)

_INT = ('season', 'week', 'qtr', 'diff_at_quarter_start', 'plays',
        'dropbacks', 'pass_att', 'sacks', 'scrambles', 'designed_rush',
        'pass_yards', 'home', 'home_final', 'away_final', 'final_margin_home',
        'attempts')


def _load(path):
    with gzip.open(path, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in list(r):
            if k in _INT or k.startswith('margin_home_start_q'):
                r[k] = int(r[k]) if str(r[k]).strip() not in ('', 'None') else None
    return rows


def load_panels():
    return {
        'team_quarter': _load(HERE / 'state_team_quarter.csv.gz'),
        'game': _load(HERE / 'state_game.csv.gz'),
        'qb_game': _load(HERE / 'state_qb_game.csv.gz'),
    }


def bucket_index(d):
    """Which differential bucket a value falls in. Vectorised."""
    return np.searchsorted(np.asarray(BUCKET_EDGES, float),
                           np.asarray(d, float), side='left')


# ------------------------------------------------------- response curves
def _eb_weights(dev, var_of_mean):
    """Empirical-Bayes shrinkage weights, ESTIMATED not chosen.

    `dev` are the cell deviations from 1.0 and `var_of_mean` their sampling
    variances. The between-cell signal variance tau^2 is what is left of the
    observed spread once the sampling noise is removed; a cell is trusted in
    proportion to tau^2 / (tau^2 + its own sampling variance). Where the data
    carry no signal tau^2 is zero and every cell shrinks to 1.0, which is the
    correct behaviour and not a failure.
    """
    dev = np.asarray(dev, float)
    v = np.asarray(var_of_mean, float)
    tau2 = float(max(0.0, np.mean(dev ** 2) - np.mean(v)))
    if tau2 <= 0:
        return np.zeros_like(dev), 0.0
    return tau2 / (tau2 + v), tau2


def _count_response(rows, field):
    """Response of a per-quarter COUNT (plays) to the entering differential."""
    by_q = collections.defaultdict(list)
    for r in rows:
        if r['qtr'] in QUARTERS:
            by_q[r['qtr']].append(r)
    rho, cells = {}, {}
    for q in QUARTERS:
        rs = by_q.get(q) or []
        if not rs:
            continue
        vals = np.array([r[field] for r in rs], float)
        mq = float(vals.mean())
        if mq <= 0:
            continue
        s2 = float(vals.var(ddof=1))
        bi = bucket_index([r['diff_at_quarter_start'] for r in rs])
        dev, vom, ns, keys = [], [], [], []
        for b in range(len(BUCKET_LABELS)):
            sel = bi == b
            n = int(sel.sum())
            if n == 0:
                continue
            dev.append(float(vals[sel].mean()) / mq - 1.0)
            vom.append(s2 / (n * mq * mq))
            ns.append(n)
            keys.append(b)
        if not keys:
            continue
        w, tau2 = _eb_weights(dev, vom)
        for j, b in enumerate(keys):
            rho[(q, b)] = 1.0 + float(w[j]) * float(dev[j])
            cells[f'{q}|{BUCKET_LABELS[b]}'] = {
                'n': ns[j], 'raw_ratio': round(1.0 + dev[j], 5),
                'shrunk_ratio': round(rho[(q, b)], 5),
                'shrinkage_weight': round(float(w[j]), 5)}
        cells[f'{q}|_quarter'] = {'mean': round(mq, 4), 'tau2': round(tau2, 8),
                                  'n': len(rs)}
    return rho, cells


def _rate_response(rows, num, den='plays'):
    """Response of a RATE (dropbacks per play) to the entering differential.

    The sampling variance is the cluster-linearised variance of a ratio
    estimator, with the team-quarter as the cluster. Plays inside one team's
    quarter are not independent draws and a binomial standard error would
    understate the noise -- the same understatement the prop-grading layer
    refuses elsewhere in this project.
    """
    by_q = collections.defaultdict(list)
    for r in rows:
        if r['qtr'] in QUARTERS and r[den] > 0:
            by_q[r['qtr']].append(r)
    rho, cells = {}, {}
    for q in QUARTERS:
        rs = by_q.get(q) or []
        if not rs:
            continue
        d = np.array([r[num] for r in rs], float)
        p = np.array([r[den] for r in rs], float)
        rq = float(d.sum() / p.sum())
        if rq <= 0:
            continue
        bi = bucket_index([r['diff_at_quarter_start'] for r in rs])
        dev, vom, ns, keys = [], [], [], []
        for b in range(len(BUCKET_LABELS)):
            sel = bi == b
            n = int(sel.sum())
            if n < 2:
                continue
            dn, pn = d[sel], p[sel]
            rate = float(dn.sum() / pn.sum())
            u = (dn - rate * pn) / pn.sum()
            var = float((u ** 2).sum())
            dev.append(rate / rq - 1.0)
            vom.append(var / (rq * rq))
            ns.append(n)
            keys.append(b)
        if not keys:
            continue
        w, tau2 = _eb_weights(dev, vom)
        for j, b in enumerate(keys):
            rho[(q, b)] = 1.0 + float(w[j]) * float(dev[j])
            cells[f'{q}|{BUCKET_LABELS[b]}'] = {
                'n': ns[j], 'raw_ratio': round(1.0 + dev[j], 5),
                'shrunk_ratio': round(rho[(q, b)], 5),
                'shrinkage_weight': round(float(w[j]), 5)}
        cells[f'{q}|_quarter'] = {'rate': round(rq, 5), 'tau2': round(tau2, 8),
                                  'n': len(rs)}
    return rho, cells


def fit_response(tq_rows):
    """Every conditional response curve, from TRAINING team-quarters only."""
    rows = [r for r in tq_rows if r['qtr'] in QUARTERS]
    if not rows:
        raise ValueError('TRACK1_NO_TRAINING_TEAM_QUARTERS')
    plays_rho, plays_cells = _count_response(rows, 'plays')
    fit = {'spec_version': SPEC_VERSION, 'n_team_quarters': len(rows),
           'plays': plays_rho, 'cells': {'plays': plays_cells}}
    for name, num in (('dropbacks', 'dropbacks'), ('pass_att', 'pass_att'),
                      ('designed_rush', 'designed_rush')):
        rho, cells = _rate_response(rows, num)
        fit[name + '_rate'] = rho
        fit['cells'][name + '_rate'] = cells
    # quarter weights and league rates, the neutral baseline the multiplier
    # is expressed relative to
    wq, rq = {}, collections.defaultdict(dict)
    tot = sum(r['plays'] for r in rows)
    for q in QUARTERS:
        rs = [r for r in rows if r['qtr'] == q]
        pq = sum(r['plays'] for r in rs)
        wq[q] = pq / tot if tot else 0.0
        for name in ('dropbacks', 'pass_att', 'designed_rush'):
            rq[name][q] = (sum(r[name] for r in rs) / pq) if pq else 0.0
    fit['quarter_weight'] = wq
    fit['quarter_rate'] = {k: dict(v) for k, v in rq.items()}
    return fit


def _rho_at(rho, q, b):
    return rho.get((q, int(b)), 1.0)


def multipliers(buckets_by_quarter, fit):
    """Per-draw multipliers for every treated driver.

    `buckets_by_quarter` is an (n_draws, 4) integer array of bucket indices,
    one per quarter, quarter 1 always neutral by construction. Returns a dict
    driver -> (n_draws,) multiplier with neutral value 1.0.
    """
    B = np.asarray(buckets_by_quarter, int)
    n = B.shape[0]
    wq = fit['quarter_weight']
    out = {}
    # plays: sum_q w_q rho_plays(q, b_q)
    m_plays = np.zeros(n)
    for j, q in enumerate(QUARTERS):
        r = np.array([_rho_at(fit['plays'], q, b) for b in range(len(BUCKET_LABELS))])
        m_plays += wq[q] * r[B[:, j]]
    out['plays'] = m_plays
    for name in ('dropbacks', 'pass_att', 'designed_rush'):
        rate = fit['quarter_rate'][name]
        num = np.zeros(n)
        den = 0.0
        for j, q in enumerate(QUARTERS):
            rp = np.array([_rho_at(fit['plays'], q, b)
                           for b in range(len(BUCKET_LABELS))])
            rr = np.array([_rho_at(fit[name + '_rate'], q, b)
                           for b in range(len(BUCKET_LABELS))])
            num += wq[q] * rate[q] * rp[B[:, j]] * rr[B[:, j]]
            den += wq[q] * rate[q]
        out[name] = num / den if den else np.ones(n)
    return out


def response_summary(fit):
    """A readable table of what the mechanism actually says."""
    out = {}
    for name in ('plays', 'dropbacks_rate', 'pass_att_rate',
                 'designed_rush_rate'):
        out[name] = fit['cells'][name]
    return out
