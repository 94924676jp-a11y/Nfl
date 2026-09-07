"""P5A items 16-17: R6's missed-tackle and yards-after-contact hypotheses.

WHAT THIS CAN AND CANNOT DO, stated first. PFR advanced weekly rushing exists
in this checkout for 2024 ONLY -- 2,359 player-games, 335 players. So there is
no across-season walk-forward test available; what IS available is a
WITHIN-SEASON walk-forward test (weeks < w predict week w) and a within-season
split-half persistence test, on one season. That is preliminary evidence and
the return calls it that. It is not confirmation and it is not rejection.

The identifier join is EXACT, not fuzzy: players.csv carries a gsis_id <->
pfr_id bijection (22,653 players, 0 pfr_id mapping to more than one gsis_id and
0 the other way). This is NOT the weekly_rosters.pfr_id bridge P3 rejected as
non-injective at 77.51%.
"""
import collections, csv, json, math, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.abspath(os.path.join(HERE, '..'))
P1 = os.path.abspath(os.path.join(HERE, '..', 'p1'))
YEAR = 2024
OUT = {}


def wcorr(x, y, w=None):
    x = np.asarray(x, float); y = np.asarray(y, float)
    w = np.ones(len(x)) if w is None else np.asarray(w, float)
    mx = np.average(x, weights=w); my = np.average(y, weights=w)
    cx, cy = x - mx, y - my
    den = math.sqrt(np.average(cx * cx, weights=w) * np.average(cy * cy, weights=w))
    return float(np.average(cx * cy, weights=w) / den) if den > 0 else None


# ---- exact identifier bridge ----------------------------------------------
xw, dup_p, dup_g = {}, 0, 0
seen_p, seen_g = {}, {}
for r in csv.DictReader(open(f'{P1}/players.csv')):
    g, p = r.get('gsis_id'), r.get('pfr_id')
    if not g or not p:
        continue
    if p in seen_p and seen_p[p] != g:
        dup_p += 1
    if g in seen_g and seen_g[g] != p:
        dup_g += 1
    seen_p[p] = g; seen_g[g] = p
    xw[p] = g
OUT['crosswalk'] = {'pairs': len(xw), 'pfr_id_to_multiple_gsis': dup_p,
                    'gsis_id_to_multiple_pfr': dup_g, 'source': 'players.csv'}
print(f'crosswalk: {len(xw)} pfr_id->gsis_id pairs; '
      f'non-injective either way: {dup_p}/{dup_g}')

# ---- PFR weekly rushing ----------------------------------------------------
pf = []
unmapped = 0
for r in csv.DictReader(open(f'{SP}/pfr_advstats_week_rush_{YEAR}.csv')):
    if r.get('game_type') != 'REG':
        continue
    g = xw.get(r['pfr_player_id'])
    if not g:
        unmapped += 1
        continue
    ca = float(r['carries'] or 0)
    if ca <= 0:
        continue
    pf.append({'week': int(r['week']), 'gsis_id': g, 'team': r['team'],
               'carries': ca,
               'ybc': float(r['rushing_yards_before_contact'] or 0),
               'yac': float(r['rushing_yards_after_contact'] or 0),
               'bt': float(r['rushing_broken_tackles'] or 0)})
print(f'PFR rows used: {len(pf)}; unmapped pfr_player_id: {unmapped} '
      f'({100*unmapped/(len(pf)+unmapped):.2f}%)')
OUT['pfr_rows'] = {'used': len(pf), 'unmapped': unmapped, 'season': YEAR}

# ---- join to the P5A player-game table ------------------------------------
D = pickle.load(open(f'{HERE}/pg.pkl', 'rb'))
pg = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in D['pg']}
joined, nomatch, cmis = [], 0, 0
for r in pf:
    q = pg.get((YEAR, r['week'], r['team'], r['gsis_id']))
    if q is None:
        nomatch += 1
        continue
    if abs(q['carries'] - r['carries']) > 0:
        cmis += 1
    joined.append({**r, 'ypc': q['rush_yards'] / q['carries'],
                   'rush_yards': q['rush_yards'], 'pbp_carries': q['carries'],
                   'n_explosive': q['n_explosive']})
print(f'joined player-games: {len(joined)}; no pbp match: {nomatch}; '
      f'carry-count disagreements: {cmis} '
      f'({100*cmis/max(len(joined),1):.2f}%)')
OUT['join'] = {'joined': len(joined), 'no_match': nomatch,
               'carry_count_disagreements': cmis}

# ---- split-half persistence WITHIN 2024 -----------------------------------
byp = collections.defaultdict(list)
for r in sorted(joined, key=lambda x: x['week']):
    byp[r['gsis_id']].append(r)
mets = {'yac_att': lambda r: r['yac'] / r['carries'],
        'ybc_att': lambda r: r['ybc'] / r['carries'],
        'bt_att': lambda r: r['bt'] / r['carries'],
        'ypc': lambda r: r['ypc']}
sh = {}
for m, fn in mets.items():
    a, b, w = [], [], []
    for pid, rs in byp.items():
        odd = [x for i, x in enumerate(rs) if i % 2 == 0]
        even = [x for i, x in enumerate(rs) if i % 2 == 1]
        ca = sum(x['carries'] for x in odd); cb = sum(x['carries'] for x in even)
        if ca < 30 or cb < 30:
            continue
        a.append(sum(fn(x) * x['carries'] for x in odd) / ca)
        b.append(sum(fn(x) * x['carries'] for x in even) / cb)
        w.append(min(ca, cb))
    if len(a) < 20:
        continue
    r_ = wcorr(a, b)
    sh[m] = {'n_players': len(a), 'r_half': r_,
             'spearman_brown': 2 * r_ / (1 + r_) if r_ is not None else None}
OUT['split_half_2024'] = sh
print('\n== within-2024 split-half persistence (>=30 carries each half) ==')
for m, v in sh.items():
    print(f'  {m:8s} n={v["n_players"]:3d} r_half={v["r_half"]:+.4f} '
          f'Spearman-Brown={v["spearman_brown"]:+.4f}')

# ---- within-season walk-forward: does PFR add to next-game YPC? -----------
pool_ypc = float(np.average([r['ypc'] for r in joined],
                            weights=[r['carries'] for r in joined]))
acc = collections.defaultdict(lambda: collections.defaultdict(float))
recs = []
for r in sorted(joined, key=lambda x: x['week']):
    a = acc[r['gsis_id']]
    if a['n'] >= 25:
        recs.append({'n': a['n'], 'ypc_hist': a['y'] / a['n'],
                     'yac_hist': a['yac'] / a['n'], 'ybc_hist': a['ybc'] / a['n'],
                     'bt_hist': a['bt'] / a['n'], 'act': r['ypc'],
                     'carries': r['carries']})
    a['n'] += r['carries']; a['y'] += r['ypc'] * r['carries']
    a['yac'] += r['yac']; a['ybc'] += r['ybc']; a['bt'] += r['bt']
print(f'\nwithin-season walk-forward rows (>=25 prior carries): {len(recs)}')


def arm(pred):
    p = np.array(pred); a = np.array([r['act'] for r in recs])
    w = np.array([r['carries'] for r in recs], float)
    return {'wmse': float(np.average((a - p) ** 2, weights=w)),
            'r': wcorr(p, a, w)}


K = 60          # the EB constant the main study fitted on prior seasons (40-80)
arms = {'pool': arm([pool_ypc] * len(recs))}
for name, key in (('ypc_eb', 'ypc_hist'), ('yac_eb', 'yac_hist'),
                  ('ybc_eb', 'ybc_hist'), ('bt_eb', 'bt_hist')):
    if key == 'ypc_hist':
        arms[name] = arm([(r['n'] * r[key] + K * pool_ypc) / (r['n'] + K)
                          for r in recs])
    else:
        base = float(np.average([r[key] for r in recs],
                                weights=[r['n'] for r in recs]))
        x = np.array([(r['n'] * r[key] + K * base) / (r['n'] + K) for r in recs])
        a = np.array([r['act'] for r in recs])
        w = np.array([r['carries'] for r in recs], float)
        mx = np.average(x, weights=w)
        beta = (np.average((x - mx) * (a - np.average(a, weights=w)), weights=w)
                / max(np.average((x - mx) ** 2, weights=w), 1e-12))
        arms[name] = arm(pool_ypc + beta * (x - mx))
        arms[name]['beta'] = float(beta)
base = arms['pool']['wmse']
for k in arms:
    arms[k]['pct_vs_pool'] = 100 * (arms[k]['wmse'] - base) / base
OUT['within_season_next_game'] = {'n': len(recs), 'pool_ypc': pool_ypc,
                                  'k_used': K, 'arms': arms,
                                  'CAVEAT': 'ONE SEASON, WITHIN-SEASON ONLY; '
                                            'the beta is fitted in-sample on '
                                            'the same 2024 rows, so these '
                                            'numbers are OPTIMISTIC and are '
                                            'reported as an upper bound, not '
                                            'as an out-of-sample result'}
print('\n== within-2024 next-game YPC (beta fitted IN SAMPLE -> upper bound) ==')
for k, v in arms.items():
    print(f'  {k:8s} wMSE={v["wmse"]:.5f} ({v["pct_vs_pool"]:+6.2f}% vs pool) '
          f'r={(v["r"] or 0):+.4f}' + (f' beta={v["beta"]:+.4f}' if 'beta' in v else ''))

json.dump(OUT, open(f'{HERE}/p5a_pfr.json', 'w'), indent=1)
print('\nwrote p5a_pfr.json')
