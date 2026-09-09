"""QB3: the QB dropback allocation. Estimand `s_dropbacks`.

Every rate here is empirical and every parameter is a resampled pool. There is
no fitted constant, and there is no point estimate where a distribution belongs
-- the share is RESAMPLED from its cell's empirical distribution, which is the
defect class this project has now hit four times.

Chronology: for evaluation season Y every rate comes from seasons < Y, and the
previous-primary feature uses a strictly-earlier ORDINAL prefix cut. A team can
carry two rows at one ordinal after a mid-week move, so "everything so far" is
not the same as "strictly earlier" and `bisect` is what enforces it.
"""
from __future__ import annotations

import bisect
import collections
import csv
import gzip
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
PANEL = os.path.join(REPO, 'nfl', 'research', 'inputs', 'panel_p3.csv.gz')
DC = os.path.join(REPO, 'nfl', 'research', 'inputs', 'dc_%d.csv.gz')
DC_SEASONS = range(2020, 2025)
EVAL = [2022, 2023, 2024, 2025]
SEED = 20260909
M_DRAWS = 400


# ---------------------------------------------------------------- inputs
def load_depth():
    """(season, week, team) -> {gsis_id: best QB rank}."""
    out = collections.defaultdict(dict)
    for y in DC_SEASONS:
        p = DC % y
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(gzip.open(p, 'rt')):
            if r.get('game_type') != 'REG':
                continue
            if (r.get('depth_position') or r.get('position') or '').upper() != 'QB':
                continue
            if not r.get('gsis_id'):
                continue
            try:
                d = int(r['depth_team'])
            except (ValueError, TypeError, KeyError):
                continue
            k = (int(r['season']), int(r['week']),
                 r.get('club_code') or r.get('team'))
            if out[k].get(r['gsis_id'], 99) > d:
                out[k][r['gsis_id']] = d
    return dict(out)


def load_qb_panel():
    rows = []
    for r in csv.DictReader(gzip.open(PANEL, 'rt')):
        if r['position'] != 'QB':
            continue
        rows.append({'season': int(r['season']), 'week': int(r['week']),
                     'team': r['team'], 'pid': r['gsis_id'],
                     'name': r['player_name'],
                     'db': int(float(r.get('dropbacks_as_passer') or 0)),
                     'ord': int(r['season']) * 100 + int(r['week'])})
    return rows


def team_games(rows):
    tg = collections.defaultdict(list)
    for r in rows:
        tg[(r['team'], r['ord'])].append(r)
    return tg


def primary_of(v):
    a = sorted([x for x in v if x['db'] >= 1], key=lambda x: -x['db'])
    return a[0]['pid'] if a else None


def build_frame(rows, depth):
    """One row per (team-week, DEPTH-CHARTED quarterback) with his realised share.

    THE FRAME COMES FROM THE DEPTH CHART, NOT THE PANEL, AND THAT IS THE WHOLE
    POINT. `panel_p3` holds only quarterbacks who took a snap, so fitting on it
    conditions on having played and drives P(share = 0) to nearly zero -- the
    first version of this function did exactly that and reported
    P(primary | rank 1, was previous primary) = 0.976 against a true 0.905.

    Production faces a QB ROOM, not a list of men who played. So does this.
    """
    tg = team_games(rows)
    prim, ords_by_team = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        prim[(t, o)] = primary_of(v)
        ords_by_team[t].append(o)
    for t in ords_by_team:
        ords_by_team[t].sort()
    played = {(r['team'], r['ord'], r['pid']): r['db'] for r in rows}
    out = []
    for (season, week, team), room in depth.items():
        o = season * 100 + week
        v = tg.get((team, o))
        if v is None:
            continue                      # no panel row: team-week not in frame
        tot = sum(x['db'] for x in v)
        if tot <= 0:
            continue
        oo = ords_by_team[team]
        i = bisect.bisect_left(oo, o)     # STRICTLY earlier
        prev = prim.get((team, oo[i - 1])) if i > 0 else None
        for pid, rank in room.items():
            db = played.get((team, o, pid), 0)
            out.append({'season': season, 'week': week, 'team': team,
                        'pid': pid, 'ord': o, 'rank': rank, 'db': db,
                        'team_db': tot, 'share': db / tot,
                        'prev_primary': prev,
                        'was_prev_primary': int(prev is not None
                                                and pid == prev),
                        'is_primary': int(prim[(team, o)] == pid)})
    return out


CELL_RANKS = (1, 2, 3)


def cell_of(rank, was_prev):
    """The declared cells. Rank >= 2 is POOLED when was_prev is 1 (prereg s.4)."""
    r = 1 if rank == 1 else (2 if rank == 2 else 3)
    if was_prev and r >= 2:
        return ('2+', 1)
    return (r if r == 1 else r, int(was_prev))


def fit(frame, ev):
    """Cell -> empirical share pool and P(primary), from seasons < ev only."""
    pools = collections.defaultdict(list)
    prim = collections.defaultdict(lambda: [0, 0])
    for r in frame:
        if r['season'] >= ev:
            continue
        c = cell_of(r['rank'], r['was_prev_primary'])
        pools[c].append(r['share'])
        p = prim[c]
        p[0] += 1
        p[1] += r['is_primary']
    return {'share_pool': {k: np.asarray(v, float) for k, v in pools.items()},
            'p_primary': {k: (v[1] / v[0] if v[0] else 0.0)
                          for k, v in prim.items()},
            'n': {k: v[0] for k, v in prim.items()},
            'trained_on_seasons_before': ev}


def allocate(par, team_qbs, m=M_DRAWS, seed=SEED, ordinal=0, team=''):
    """One team's QB dropback shares, (n_qb, m), summing to 1 in every draw.

    `team_qbs` is a list of (pid, rank, was_prev_primary).
    """
    n = len(team_qbs)
    if n == 0:
        return np.zeros((0, m))
    rng = np.random.default_rng(
        [seed, int(ordinal),
         int.from_bytes(str(team).encode()[-8:].ljust(8, b'0'), 'little')])
    cells = [cell_of(r, w) for _, r, w in team_qbs]
    pp = np.array([max(par['p_primary'].get(c, 0.0), 1e-9) for c in cells])
    # 1. primary identity per draw
    who = rng.choice(n, size=m, p=pp / pp.sum())
    S = np.zeros((n, m))
    # 2. the primary's share, RESAMPLED from his cell's empirical pool
    for i in range(n):
        sel = np.where(who == i)[0]
        if not len(sel):
            continue
        pool = par['share_pool'].get(cells[i])
        if pool is None or not len(pool):
            S[i, sel] = 1.0
            continue
        S[i, sel] = pool[rng.integers(0, len(pool), len(sel))]
    # 3. the remainder among the others, in proportion to their cell weight
    tot = S.sum(0)
    rem = np.maximum(1.0 - tot, 0.0)
    if n > 1:
        w = np.tile(pp[:, None], (1, m))
        w[who, np.arange(m)] = 0.0
        ws = w.sum(0)
        with np.errstate(invalid='ignore', divide='ignore'):
            frac = np.where(ws > 0, w / np.maximum(ws, 1e-12), 0.0)
        S = S + frac * rem[None, :]
    else:
        S[0] = 1.0
    # closure: whatever rounding leaves, put on the drawn primary
    resid = 1.0 - S.sum(0)
    S[who, np.arange(m)] += resid
    return np.clip(S, 0.0, 1.0)


# ---------------------------------------------------------------- scoring
def crps_sample(draws, y):
    d = np.sort(np.asarray(draws, float))
    n = len(d)
    if n == 0:
        return float('nan')
    t1 = np.abs(d - y).mean()
    t2 = np.abs(d[:, None] - d[None, :]).mean() if n <= 800 else _crps_fast(d)
    return float(t1 - 0.5 * t2)


def _crps_fast(d):
    n = len(d)
    i = np.arange(1, n + 1)
    return float(2 * (np.sum((2 * i - n - 1) * d)) / (n * n))


def clustered_ci(diffs, clusters, B=2000, seed=SEED):
    """Team-game clustered bootstrap. One team-game is one observation."""
    d = np.asarray(diffs, float)
    cl = np.asarray(clusters)
    uc = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in uc}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        pick = rng.choice(uc, size=len(uc), replace=True)
        s = np.concatenate([idx[c] for c in pick])
        out.append(d[s].mean())
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))
