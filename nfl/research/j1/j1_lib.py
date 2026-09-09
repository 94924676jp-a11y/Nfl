"""J1: four architectures for the joint rushing opportunity. Team level.

Every arm shares ONE base: the frozen D1/P4B baseline and residual machinery.
The arms differ only in how the draw is assembled, so a difference between them
is a difference in architecture and not in fit.
"""
from __future__ import annotations

import collections, csv, gzip, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, REPO)
for _q in ('p4b', 'p4c'):
    sys.path.insert(0, os.path.join(REPO, 'nfl', 'research', _q))

DENOM = os.path.join(REPO, 'nfl', 'research', 'inputs', 'denom_panel.csv.gz')
PANEL = os.path.join(REPO, 'nfl', 'research', 'inputs', 'panel_p3.csv.gz')
METRICS = ('team_off_snaps', 'team_dropbacks_part', 'team_targets',
           'team_carries', 'team_rz_carries')
EVAL = [2022, 2023, 2024, 2025]
SEED = 20260909
M = 300


def load():
    """Team-game rows with the D1 metrics plus the rushing decomposition."""
    den = {}
    for r in csv.DictReader(gzip.open(DENOM, 'rt')):
        k = (r['team'], int(r['ord']))
        den[k] = {'team': r['team'], 'ord': int(r['ord']),
                  'season': int(r['season']), 'week': int(r['week']),
                  'coach': r.get('coach'),
                  **{m: int(r[m]) for m in METRICS}}
    agg = collections.defaultdict(collections.Counter)
    for r in csv.DictReader(gzip.open(PANEL, 'rt')):
        k = (r['team'], int(r['season']) * 100 + int(r['week']))
        c = int(float(r.get('carries') or 0))
        if r['position'] == 'QB':
            agg[k]['scr'] += int(float(r.get('scrambles') or 0))
            agg[k]['drush'] += int(float(r.get('designed_rushes') or 0))
        elif r['position'] in ('RB', 'FB'):
            agg[k]['rb'] += c
        elif r['position'] in ('WR', 'TE'):
            agg[k]['wr'] += c
    out = []
    for k, d in den.items():
        a = agg.get(k)
        if a is None or d['team_carries'] <= 0 or d['team_off_snaps'] <= 0:
            continue
        d = dict(d)
        d['scr'], d['drush'] = a['scr'], a['drush']
        d['rb'], d['wr'] = a['rb'], a['wr']
        d['qb_rush'] = a['scr'] + a['drush']
        d['designed'] = d['team_carries'] - a['scr']
        out.append(d)
    out.sort(key=lambda r: (r['ord'], r['team']))
    return out


def baselines(rows, ev):
    """Prior-only per-metric baseline: the team's own mean over earlier games,
    shrunk to the league mean. Deliberately simple and IDENTICAL across arms --
    the experiment is about the draw, not the point forecast."""
    hist = [r for r in rows if r['season'] < ev]
    lm = {m: float(np.mean([r[m] for r in hist])) for m in METRICS}
    for extra in ('qb_rush', 'designed', 'rb', 'wr', 'scr', 'drush'):
        lm[extra] = float(np.mean([r[extra] for r in hist]))
    by_team = collections.defaultdict(list)
    for r in hist:
        by_team[r['team']].append(r)
    K = 8.0                     # declared shrinkage, not fitted
    base = {}
    for t, v in by_team.items():
        n = len(v)
        w = n / (n + K)
        base[t] = {m: w * float(np.mean([x[m] for x in v])) + (1 - w) * lm[m]
                   for m in list(METRICS) + ['qb_rush', 'designed', 'rb',
                                             'wr', 'scr', 'drush']}
    return base, lm, hist


def residual_table(hist, base, lm):
    """Per historical team-game, the residual of every quantity. Indexed so an
    arm can resample the VECTOR rather than each entry separately."""
    keys = list(METRICS) + ['qb_rush', 'designed', 'rb', 'wr', 'scr', 'drush']
    R = np.zeros((len(hist), len(keys)))
    for i, r in enumerate(hist):
        b = base.get(r['team'], lm)
        for j, k in enumerate(keys):
            R[i, j] = r[k] - b.get(k, lm[k])
    return R, {k: j for j, k in enumerate(keys)}


# ------------------------------------------------------------------ arms
def _b(base, lm, team, key):
    return base.get(team, lm).get(key, lm[key])


def arm_A0(row, base, lm, R, ix, rng, m=M):
    """CONTROL -- the status quo: every metric resampled independently."""
    n = len(R)
    db = _b(base, lm, row['team'], 'team_dropbacks_part') + \
        R[rng.integers(0, n, m), ix['team_dropbacks_part']]
    tc = _b(base, lm, row['team'], 'team_carries') + \
        R[rng.integers(0, n, m), ix['team_carries']]
    qb = _b(base, lm, row['team'], 'qb_rush') + \
        R[rng.integers(0, n, m), ix['qb_rush']]
    db, tc, qb = (np.maximum(x, 0.0) for x in (db, tc, qb))
    wr = np.maximum(_b(base, lm, row['team'], 'wr')
                    + R[rng.integers(0, n, m), ix['wr']], 0.0)
    rb = np.maximum(tc - qb - wr, 0.0)          # what the RB simplex sees
    clipped = int((tc - qb - wr < 0).sum())
    return {'db': db, 'tc': tc, 'qb': qb, 'rb': rb, 'wr': wr,
            'clipped': clipped}


def arm_A1(row, base, lm, R, ix, rng, m=M):
    """Carve QB first: subtract the QB rush draw, allocate the remainder."""
    d = arm_A0(row, base, lm, R, ix, rng, m)
    qb = np.minimum(d['qb'], d['tc'])           # cannot exceed the team
    carved = int((d['qb'] > d['tc']).sum())
    rest = d['tc'] - qb
    wr_share = _b(base, lm, row['team'], 'wr') / max(
        _b(base, lm, row['team'], 'team_carries')
        - _b(base, lm, row['team'], 'qb_rush'), 1e-9)
    wr = np.clip(rest * wr_share, 0, rest)
    return {'db': d['db'], 'tc': d['tc'], 'qb': qb, 'rb': rest - wr, 'wr': wr,
            'clipped': carved}


def arm_A3(row, base, lm, R, ix, rng, m=M):
    """JOINT residual resampling: one historical team-game index per draw, so
    every marginal fit is untouched and the cross-metric structure rides along."""
    n = len(R)
    sel = rng.integers(0, n, m)                 # ONE index, all quantities
    g = lambda k: _b(base, lm, row['team'], k) + R[sel, ix[k]]
    db = np.maximum(g('team_dropbacks_part'), 0.0)
    scr = np.maximum(g('scr'), 0.0)
    dru = np.maximum(g('drush'), 0.0)
    rb = np.maximum(g('rb'), 0.0)
    wr = np.maximum(g('wr'), 0.0)
    qb = scr + dru
    tc = qb + rb + wr                           # DERIVED, never drawn
    return {'db': db, 'tc': tc, 'qb': qb, 'rb': rb, 'wr': wr, 'clipped': 0}


def arm_A2(row, base, lm, R, ix, rng, m=M, hist=None, pools=None):
    """Causal split: snaps -> (dropbacks, designed) -> scrambles -> allocation."""
    n = len(R)
    snaps = np.maximum(_b(base, lm, row['team'], 'team_off_snaps')
                       + R[rng.integers(0, n, m), ix['team_off_snaps']], 1.0)
    sel = rng.integers(0, len(pools['designed_share']), m)
    dshare = pools['designed_share'][sel]
    play = snaps * pools['play_frac']            # snaps that are db or designed
    designed = np.maximum(play * dshare, 0.0)
    db = np.maximum(play - designed, 0.0)
    srate = pools['scr_rate'][rng.integers(0, len(pools['scr_rate']), m)]
    scr = rng.binomial(np.maximum(np.rint(db), 0).astype(int),
                       np.clip(srate, 0, 1)).astype(float)
    a = pools['designed_alloc'][rng.integers(0, len(pools['designed_alloc']), m)]
    rb = designed * a[:, 0]
    qdes = designed * a[:, 1]
    wr = designed * a[:, 2]
    qb = qdes + scr
    tc = designed + scr                          # DERIVED
    return {'db': db, 'tc': tc, 'qb': qb, 'rb': rb, 'wr': wr, 'clipped': 0}


def a2_pools(hist):
    """Prior-only empirical pools for the causal split."""
    ds, sr, al, pf = [], [], [], []
    for r in hist:
        play = r['team_dropbacks_part'] + r['designed']
        if play <= 0 or r['team_off_snaps'] <= 0:
            continue
        ds.append(r['designed'] / play)
        pf.append(play / r['team_off_snaps'])
        if r['team_dropbacks_part'] > 0:
            sr.append(r['scr'] / r['team_dropbacks_part'])
        d = r['designed']
        if d > 0:
            al.append([r['rb'] / d, r['drush'] / d, r['wr'] / d])
    al = np.asarray(al, float)
    al = al / np.maximum(al.sum(1, keepdims=True), 1e-9)
    return {'designed_share': np.asarray(ds, float),
            'scr_rate': np.asarray(sr, float),
            'designed_alloc': al,
            'play_frac': float(np.mean(pf))}


# --------------------------------------------------------------- scoring
def crps(draws, y):
    d = np.sort(np.asarray(draws, float))
    n = len(d)
    i = np.arange(1, n + 1)
    return float(np.abs(d - y).mean() - (np.sum((2 * i - n - 1) * d) / (n * n)))


def energy_score(X, y, rng, sub=120):
    """Strictly proper multivariate score. X is (m, d)."""
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    t1 = float(np.linalg.norm(X - y, axis=1).mean())
    idx = rng.integers(0, len(X), (2, sub))
    t2 = float(np.linalg.norm(X[idx[0]] - X[idx[1]], axis=1).mean())
    return t1 - 0.5 * t2


def clustered_ci(d, cl, B=2000, seed=SEED):
    d = np.asarray(d, float)
    cl = np.asarray(cl)
    uc = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in uc}
    rng = np.random.default_rng(seed)
    o = [d[np.concatenate([idx[c] for c in rng.choice(uc, len(uc), True)])].mean()
         for _ in range(B)]
    return float(np.quantile(o, 0.025)), float(np.quantile(o, 0.975))
