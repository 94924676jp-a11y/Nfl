"""OWN-9: the A1 single-owner rushing architecture, and the A0 incumbent.

Research only. Nothing here is production and nothing is promoted.

A1's ownership graph, frozen by OWN-8's pre-registration (sha256 90f6ecc3...):

    team_carries                     D1 -- one level, one owner
      |- scrambles                   QB dropback process -- PRIOR CLAIM
      `- rush_play_budget = team_carries - scrambles
           |- kneels                 carry-owned
           |- designed QB rush       carry-owned  (A0 draws this on DROPBACKS)
           |- RB                     carry-owned
           |- WR / TE                carry-owned
           `- fringe                 named residual

BOTH ARMS ARE GIVEN THE SAME REALISED team_carries, dropbacks AND scrambles.
That is an oracle on the budgets, identical for both, and it is deliberate: the
question under test is the ALLOCATION architecture, and letting the budgets
differ between arms would confound it. Stated here rather than discovered.

Estimator family is P4C's, unchanged in kind: an ewma of prior shares with a
league prior for a unit with no history, plus an additive residual pool
resampled for spread. The only thing that changes is the DENOMINATOR and the
CATEGORY SET, which is what the new ownership graph mechanically requires.
No feature search, no sweep, nothing fitted toward any historical share.
"""
from __future__ import annotations

import bisect
import collections
import csv
import gzip
import math

import numpy as np

CATEGORIES = ('kneel', 'designed_qb', 'rb', 'wr', 'te', 'fringe')
# P4C's shrinkage constant, reused with its provenance rather than re-chosen.
K_SHRINK = 4.0
EWMA_HALFLIFE = 2.0          # Stage-2's accepted half-life, reused
EPS = 1e-9


def _i(v, d=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def build_frame(pbp_files, positions):
    """Per team-game: the budgets and every carry, classified exactly once.

    `positions` maps gsis_id -> position, from the panel. A rusher with no
    known position is FRINGE, which is a named category, not a silent drop.
    """
    passers = collections.defaultdict(set)
    rows = []
    for path in pbp_files:
        with gzip.open(path, 'rt') as fh:
            for r in csv.DictReader(fh):
                if r.get('season_type') != 'REG':
                    continue
                if _i(r.get('two_point_attempt')):
                    continue
                po = r.get('posteam') or ''
                if not po:
                    continue
                k = (_i(r.get('season')), _i(r.get('week')), po)
                if _i(r.get('qb_dropback')) and (r.get('passer_player_id') or ''):
                    passers[k].add(r['passer_player_id'])
                rows.append((k, r))
    tg = collections.defaultdict(collections.Counter)
    for k, r in rows:
        c = tg[k]
        if _i(r.get('qb_dropback')):
            c['dropbacks'] += 1
        if not _i(r.get('rush_attempt')):
            continue
        c['team_carries'] += 1
        rid = r.get('rusher_player_id') or ''
        if _i(r.get('qb_scramble')):
            c['scramble'] += 1
        elif _i(r.get('qb_kneel')):
            c['kneel'] += 1
        elif rid and rid in passers[k]:
            c['designed_qb'] += 1
        else:
            p = positions.get(rid)
            if p == 'RB':
                c['rb'] += 1
            elif p == 'WR':
                c['wr'] += 1
            elif p == 'TE':
                c['te'] += 1
            else:
                c['fringe'] += 1
    out = []
    for (season, week, team), c in sorted(tg.items()):
        budget = c['team_carries'] - c['scramble']
        out.append({'season': season, 'week': week, 'team': team,
                    'ord': season * 100 + week,
                    'dropbacks': c['dropbacks'],
                    'team_carries': c['team_carries'],
                    'scramble': c['scramble'],
                    'rush_play_budget': budget,
                    **{cat: c[cat] for cat in CATEGORIES}})
    return out


def attach_prior(frame):
    """Strictly-prior category shares per team. Ordinal prefix cut, never 'so far'."""
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in sorted(frame, key=lambda x: (x['ord'], x['team'])):
        t = r['team']
        i = bisect.bisect_left(hord[t], r['ord'])
        past = hist[t][:i]
        r['h_n'] = len(past)
        for cat in CATEGORIES:
            v = [x[cat] / x['rush_play_budget'] for x in past
                 if x['rush_play_budget'] > 0]
            r[f'h_{cat}'] = v
        hist[t].append(r)
        hord[t].append(r['ord'])
    return frame


def _ewma(vals, hl=EWMA_HALFLIFE):
    if not vals:
        return None
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den if den > 0 else None


def fit(frame, ev):
    """Category parameters from seasons STRICTLY BEFORE ev. No outcome at ev."""
    tr = [r for r in frame if r['season'] < ev and r['rush_play_budget'] > 0]
    if not tr:
        return None
    par = {'ev': ev, 'n_train': len(tr), 'league': {}, 'resid': {},
           'seasons_used': sorted({r['season'] for r in tr})}
    for cat in CATEGORIES:
        v = [r[cat] / r['rush_play_budget'] for r in tr]
        par['league'][cat] = float(np.mean(v))
    # additive share residuals against the team's own prior ewma, the P4C family
    res = collections.defaultdict(list)
    for r in tr:
        for cat in CATEGORIES:
            c = _ewma(r[f'h_{cat}'])
            if c is None:
                continue
            res[cat].append(r[cat] / r['rush_play_budget'] - c)
    par['resid'] = {cat: np.array(v, np.float32) for cat, v in res.items()}
    return par


def _centre(r, cat, par):
    """The team's own prior ewma shrunk toward the league share. n/(n+K)."""
    own = _ewma(r[f'h_{cat}'])
    lg = par['league'][cat]
    if own is None:
        return lg
    w = r['h_n'] / (r['h_n'] + K_SHRINK)
    return w * own + (1 - w) * lg


def draw_a1(r, par, rng, m):
    """A1: one per-draw partition of the SAME rush-play budget.

    Multinomial on shares drawn from the same estimator family, so the
    categories cannot collide: every carry lands in exactly one of them by
    construction rather than by reconciliation.
    """
    budget = int(r['rush_play_budget'])
    p = np.empty((len(CATEGORIES), m), np.float64)
    for j, cat in enumerate(CATEGORIES):
        c = _centre(r, cat, par)
        pool = par['resid'].get(cat)
        add = (pool[rng.integers(0, len(pool), m)] if pool is not None
               and len(pool) else np.zeros(m, np.float32))
        p[j] = np.maximum(c + add, 0.0)
    tot = p.sum(0)
    # A draw whose every category weight is zero has no partition to make.
    # Named, counted, and given to the fringe rather than silently rescaled.
    degenerate = tot <= EPS
    p[:, degenerate] = 0.0
    p[CATEGORIES.index('fringe'), degenerate] = 1.0
    tot = np.where(degenerate, 1.0, tot)
    p = p / tot
    out = np.empty((len(CATEGORIES), m), np.int64)
    for j in range(m):
        out[:, j] = rng.multinomial(budget, p[:, j])
    return {cat: out[j] for j, cat in enumerate(CATEGORIES)}, int(degenerate.sum())


def draw_a0(r, par, par_a0, rng, m):
    """A0 incumbent: designed QB rush on the DROPBACK denominator, RB block on
    the carry denominator, and no coupling between them -- which is the defect.
    """
    # m DRAWS, not one. A scalar here would give the incumbent arm a point
    # estimate where a distribution belongs -- the defect class this project
    # has now found five times, and it would have flattered A0's CRPS.
    dq = rng.binomial(int(r['dropbacks']),
                      min(max(par_a0['p_drush_db'], 0.0), 1.0), m)
    budget = int(r['rush_play_budget'])
    rest = [c for c in CATEGORIES if c != 'designed_qb']
    p = np.empty((len(rest), m), np.float64)
    for j, cat in enumerate(rest):
        c = _centre(r, cat, par)
        pool = par['resid'].get(cat)
        add = (pool[rng.integers(0, len(pool), m)] if pool is not None
               and len(pool) else np.zeros(m, np.float32))
        p[j] = np.maximum(c + add, 0.0)
    tot = np.where(p.sum(0) <= EPS, 1.0, p.sum(0))
    p = p / tot
    out = np.empty((len(rest), m), np.int64)
    for j in range(m):
        out[:, j] = rng.multinomial(budget, p[:, j])
    d = {cat: out[j] for j, cat in enumerate(rest)}
    d['designed_qb'] = dq
    return d, 0


def fit_a0(frame, ev):
    """A0's designed-rush control: per DROPBACK, as the incumbent has it."""
    tr = [r for r in frame if r['season'] < ev and r['dropbacks'] > 0]
    if not tr:
        return None
    n = sum(r['designed_qb'] for r in tr)
    d = sum(r['dropbacks'] for r in tr)
    return {'p_drush_db': (n / d) if d else 0.0, 'n_train': len(tr)}


def crps(draws, y):
    """CRPS of an empirical predictive sample against one observation."""
    d = np.sort(np.asarray(draws, np.float64))
    m = d.size
    i = np.arange(1, m + 1, dtype=np.float64)
    w = m * (float(y) < d) - i + 0.5
    return (2.0 / (m * m)) * float(((d - float(y)) * w).sum())
