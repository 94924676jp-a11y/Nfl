"""FTN-M10 analysis. Ten games, used for characterization and effect size.

NOT confirmatory. Ten games from four repeated teams are development data and
every number here is labelled OBSERVED_IN_THIS_SAMPLE unless stated otherwise.
Intervals are game-clustered, because plays inside a game are not independent
observations.
"""
import collections, json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import ALIGN, DEFCLASS, ROUTE_ROLES, load, resolve_targets

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'raw', 'extracted')
SEED = 20260909


def route_frame():
    ev, plays, mus = load(RAW)
    st = resolve_targets(plays, mus)
    by_play = {p['play_id']: p for p in plays}
    rows = []
    for m in mus:
        p = by_play.get(m['play_id'])
        if p is None or p['play_type'] != 'pass':
            continue
        if m['off_role'] not in ROUTE_ROLES:
            continue                      # only players actually running a route
        if p['p_kind'] not in ('target', 'no_target', 'sack', 'spike'):
            continue
        rows.append({
            'event_id': m['event_id'], 'play_id': m['play_id'],
            'off_id': m['off_id'], 'off_name': m['off_name'],
            'off_team': m['off_team'],
            'align': ALIGN.get(m['off_pos'], 'OTHER'),
            'off_pos': m['off_pos'], 'role': m['off_role'],
            'def_id': m['def_id'], 'def_name': m['def_name'],
            'defclass': DEFCLASS.get(m['def_pos'], 'OTHER'),
            'def_pos': m['def_pos'],
            'targeted': int(p.get('target_off_id') == m['off_id']),
            'complete': int(bool(p.get('p_complete'))
                            and p.get('target_off_id') == m['off_id']),
            'yards': (p.get('p_yards')
                      if p.get('target_off_id') == m['off_id'] else None),
            'depth': (p.get('p_depth')
                      if p.get('target_off_id') == m['off_id'] else None),
        })
    return ev, plays, mus, rows, st


def clustered_ci(vals, clusters, stat=np.mean, B=2000, seed=SEED):
    """Game-clustered bootstrap. Plays within a game move together."""
    vals = np.asarray(vals, float)
    cl = np.asarray(clusters)
    uc = np.unique(cl)
    idx = {c: np.where(cl == c)[0] for c in uc}
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        pick = rng.choice(uc, size=len(uc), replace=True)
        s = np.concatenate([idx[c] for c in pick])
        out.append(stat(vals[s]))
    return float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))


def rate_table(rows, key):
    out = {}
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    base = np.mean([r['targeted'] for r in rows])
    for k, g in sorted(groups.items()):
        y = [r['targeted'] for r in g]
        cl = [r['event_id'] for r in g]
        lo, hi = clustered_ci(y, cl)
        out[k] = {'n_route_plays': len(g), 'n_targets': int(sum(y)),
                  'target_rate': float(np.mean(y)),
                  'ci95_clustered': [lo, hi],
                  'rate_ratio_vs_all': float(np.mean(y) / base) if base else None}
    out['_ALL'] = {'n_route_plays': len(rows),
                   'n_targets': int(sum(r['targeted'] for r in rows)),
                   'target_rate': float(base)}
    return out
