"""ROUTE-BB1: does a route denominator change the downstream target forecast?

THE STRUCTURE OF THE EXPERIMENT, AND WHY IT IS SHAPED THIS WAY

True routes run are unobservable in every source this project can reach. W4
established that `participation.route` is the TARGETED receiver's route -- one
scalar per play, 14 values, and air yards separate by 28 across the labels --
so no per-player route label exists to fit against or to score against.

That rules out the obvious experiment (fit an estimator, measure its accuracy)
and it rules it out for a real reason rather than a solvable one. So the
experiment runs the other way: INJECT a route participation rate whose
game-to-game dispersion is known and controlled, and measure what downstream
target CRPS does as a function of that dispersion.

The oracle arm -- where the injected rate is known at prediction time -- is an
UPPER BOUND on what any route dataset could buy, FTN's included. It is the
number a purchase decision should be read against.
"""
from __future__ import annotations

import csv
import gzip
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..'))
from rc1_lib import crps_matrix                                   # noqa: E402

PANEL = os.path.join(HERE, '..', 'inputs', 'panel_p3.csv.gz')
EVAL = [2022, 2023, 2024, 2025]
SEED = 20260908
K = 4.0
M_DRAWS = 400
POSITIONS = ('WR', 'TE', 'RB')
CV_GRID = (0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)

# Published-consensus route participation LEVELS by position. These are not
# fitted and are not FTN's -- they are the level term, and section 3 of the
# pre-registration predicts the level cancels exactly. They are here so the
# cancellation can be demonstrated rather than asserted.
BASE_P = {'WR': 0.90, 'TE': 0.70, 'RB': 0.40}


def load():
    rows = []
    for r in csv.DictReader(gzip.open(PANEL, 'rt')):
        if r['position'] not in POSITIONS:
            continue
        ps = float(r['pass_snaps'] or 0)
        if ps <= 0:
            continue
        rows.append({
            'season': int(r['season']), 'week': int(r['week']),
            'team': r['team'], 'gsis_id': r['gsis_id'],
            'game_id': r['game_id'], 'position': r['position'],
            'pass_snaps': ps,
            'targets': float(r['targets'] or 0),
            'team_db': float(r['team_dropbacks_part'] or 0),
            'off_snaps': float(r['offense_snaps'] or 0),
        })
    rows.sort(key=lambda r: (r['season'], r['week'], r['team'], r['gsis_id']))
    for i, r in enumerate(rows):
        r['ord'] = r['season'] * 100 + r['week']
    return rows


def attach_history(rows):
    """Prior-only history, strictly-earlier ordinal cut.

    The same bisect discipline as QB2: a player with two rows at one ordinal
    (a mid-week team change) must not see his own sibling row.
    """
    import bisect
    import collections
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in rows:
        pid = r['gsis_id']
        i = bisect.bisect_left(hord[pid], r['ord'])
        past = hist[pid][:i]
        r['h_games'] = len(past)
        r['h_snaps'] = sum(x['pass_snaps'] for x in past)
        r['h_targets'] = sum(x['targets'] for x in past)
        r['h_routes'] = sum(x.get('routes_true', 0.0) for x in past)
        r['h_p'] = [x['p_true'] for x in past if 'p_true' in x]
        hist[pid].append(r)
        hord[pid].append(r['ord'])
    return rows


def inject_routes(rows, cv, seed=SEED):
    """Give every player-game a TRUE route participation rate with a known
    game-to-game coefficient of variation, and the routes that follow from it.

    Per-row RNG seeded on the row, never a shared stream: a shared stream makes
    a change to one row shift every later row, which is a defect this project
    has already produced once.
    """
    for r in rows:
        base = BASE_P[r['position']]
        if cv <= 0:
            p = base
        else:
            rng = np.random.default_rng(
                [seed, int(r['ord']),
                 int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little'),
                 int(cv * 1000)])
            # lognormal keeps p > 0; clipped at 1 because a rate above 1 is not
            # a rate. Clipping is REPORTED by the caller, never silent.
            p = float(np.clip(base * np.exp(rng.normal(
                -0.5 * np.log1p(cv ** 2), np.sqrt(np.log1p(cv ** 2)))), 0.02, 1.0))
        r['p_true'] = p
        r['routes_true'] = r['pass_snaps'] * p
    return rows


def _draw(n_trials, rate, m, rng):
    """Binomial target draws. The denominator is whatever architecture supplies."""
    n = np.maximum(np.rint(n_trials), 0).astype(int)
    return rng.binomial(n, np.clip(rate, 0.0, 1.0))


def run_arm(rows, ev, arm, m=M_DRAWS, seed=SEED):
    """One evaluation season, one architecture.

    arm 'control'  -> denominator is pass_snaps
    arm 'oracle'   -> denominator is the TRUE injected routes (upper bound)
    arm 'candidate'-> denominator is a PRIOR-ONLY estimate of routes
    """
    e = [r for r in rows if r['season'] == ev and r['h_games'] >= 1]
    n = len(e)
    D = np.zeros((n, m))
    for i, r in enumerate(e):
        rng = np.random.default_rng(
            [seed, int(r['ord']),
             int.from_bytes(str(r['gsis_id']).encode()[-8:], 'little'),
             hash(arm) % 97])
        w = r['h_games'] / (r['h_games'] + K)
        pool = 0.16
        if arm == 'control':
            den_now = r['pass_snaps']
            hist_den = r['h_snaps']
        elif arm == 'oracle':
            den_now = r['routes_true']
            hist_den = r['h_routes']
        elif arm == 'candidate':
            # prior-only mean of the player's own route rate; falls back to the
            # positional level when he has no history of it
            p_hat = (float(np.mean(r['h_p'])) if r['h_p']
                     else BASE_P[r['position']])
            den_now = r['pass_snaps'] * p_hat
            hist_den = r['h_routes']
        else:
            raise ValueError(arm)
        rate = (w * (r['h_targets'] / max(hist_den, 1e-9))
                + (1 - w) * pool) if hist_den > 0 else pool
        D[i] = _draw(den_now, rate, m, rng)
    y = np.array([r['targets'] for r in e], float)
    g = [r['game_id'] for r in e]
    pos = [r['position'] for r in e]
    return D, y, g, pos


def score(D, y):
    p = D.mean(1)
    err = p - y
    out = {'n': int(len(y)),
           'crps': float(crps_matrix(D, y).mean()),
           'mae': float(np.abs(err).mean()),
           'rmse': float(np.sqrt(float((err * err).mean()))),
           'bias': float(err.mean()),
           'r': (float(np.corrcoef(p, y)[0, 1])
                 if p.std() > 1e-12 and y.std() > 1e-12 else None)}
    for lv in (50, 80, 90):
        lo = np.quantile(D, (100 - lv) / 200, axis=1)
        hi = np.quantile(D, 1 - (100 - lv) / 200, axis=1)
        out[f'cover{lv}'] = float(((y >= lo) & (y <= hi)).mean())
    return out


def clustered_delta(c_a, c_b, games, reps=400, seed=SEED):
    """Game-clustered bootstrap on the CRPS difference. Naive SEs forbidden."""
    import collections
    by = collections.defaultdict(list)
    for i, g in enumerate(games):
        by[g].append(i)
    keys = list(by)
    idx = [np.array(by[k]) for k in keys]
    rng = np.random.default_rng(seed)
    d = []
    for _ in range(reps):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idx[j] for j in pick])
        d.append(float(c_a[sel].mean() - c_b[sel].mean()))
    return {'delta': float(c_a.mean() - c_b.mean()),
            'lo': float(np.quantile(d, 0.025)),
            'hi': float(np.quantile(d, 0.975))}
