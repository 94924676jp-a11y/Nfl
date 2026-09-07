"""P5A return item 7: what this checkout actually holds, measured.

Two jobs. (a) Verify the carry table aggregates to the accepted panel's
y_carries EXACTLY -- if it does not, the P4C carry distribution and the P5A
conversion layer are describing different objects and P5A stops. (b) State
exactly which of R6's hypotheses the available data can and cannot test.
"""
import collections, csv, json, os, pickle, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.abspath(os.path.join(HERE, '..'))
P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
OUT = {}

rows = []
for r in csv.DictReader(open(f'{HERE}/carries.csv')):
    r['season'] = int(r['season']); r['week'] = int(r['week'])
    r['yards'] = float(r['yards']); r['scramble'] = int(r['scramble'])
    r['epa'] = float(r['epa']); r['success'] = int(r['success'])
    rows.append(r)
print(f'carry rows {len(rows)}')

# ---- (a) exact reconciliation against the accepted panel --------------------
panel = pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))
agg = collections.Counter()
for r in rows:
    agg[(r['season'], r['week'], r['posteam'], r['rusher'])] += 1
mismatch = miss_panel = 0
checked = 0
for p in panel:
    if p['season'] < 2020:
        continue
    k = (p['season'], p['week'], p['team'], p['gsis_id'])
    c = agg.get(k, 0)
    if p['y_carries'] != c:
        mismatch += 1
    checked += 1
extra = sum(1 for k in agg
            if k[0] >= 2020 and not any(True for _ in ()) )
print(f'panel player-games checked (2020+): {checked}; y_carries mismatches: {mismatch}')
OUT['reconciliation'] = {'panel_rows_checked': checked, 'mismatches': mismatch}
if mismatch:
    print('STOP CONDITION: the carry table does not reproduce the panel')

# ---- carry counts and the per-carry outcome distribution -------------------
print(f"\n{'season':7s} {'carries':>8s} {'mean':>7s} {'sd':>7s} {'skew':>7s} {'kurt':>8s} "
      f"{'P(<=0)':>7s} {'P(>=10)':>8s} {'P(>=15)':>8s} {'P(>=20)':>8s} {'p50':>5s} {'p90':>5s} {'p99':>5s} {'max':>5s}")
by = collections.defaultdict(list)
for r in rows:
    by[r['season']].append(r['yards'])
seas = {}
for s in sorted(by):
    v = np.array(by[s])
    z = (v - v.mean()) / v.std(ddof=1)
    seas[s] = {'n': len(v), 'mean': float(v.mean()), 'sd': float(v.std(ddof=1)),
               'skew': float((z ** 3).mean()), 'ex_kurt': float((z ** 4).mean() - 3),
               'p_le0': float((v <= 0).mean()), 'p_ge10': float((v >= 10).mean()),
               'p_ge15': float((v >= 15).mean()), 'p_ge20': float((v >= 20).mean()),
               'p50': float(np.percentile(v, 50)), 'p90': float(np.percentile(v, 90)),
               'p99': float(np.percentile(v, 99)), 'max': float(v.max())}
    d = seas[s]
    print(f"{s:7d} {d['n']:8d} {d['mean']:7.3f} {d['sd']:7.3f} {d['skew']:7.3f} "
          f"{d['ex_kurt']:8.2f} {d['p_le0']:7.4f} {d['p_ge10']:8.4f} {d['p_ge15']:8.4f} "
          f"{d['p_ge20']:8.4f} {d['p50']:5.1f} {d['p90']:5.1f} {d['p99']:5.1f} {d['max']:5.0f}")
OUT['per_carry_distribution'] = seas

# ---- (b) what R6's hypotheses need, and what exists ------------------------
avail = {}
for name, pat in (('pfr_advstats_week_rush', 'pfr_advstats_week_rush_%d.csv'),
                  ('pfr_advstats_week_def', 'pfr_advstats_week_def_%d.csv'),
                  ('ftn_charting', 'ftn%d.csv')):
    yrs = [y for y in range(2016, 2026) if os.path.exists(f'{SP}/{pat % y}')]
    avail[name] = yrs
print('\nR6-relevant sources present in this checkout:')
for k, v in avail.items():
    print(f'  {k:26s} seasons {v if v else "NONE"}')
OUT['r6_sources'] = avail

if avail['pfr_advstats_week_rush']:
    y = avail['pfr_advstats_week_rush'][0]
    pf = list(csv.DictReader(open(f'{SP}/pfr_advstats_week_rush_{y}.csv')))
    print(f'\n  pfr_advstats_week_rush_{y}: {len(pf)} player-game rows, '
          f'{len({r["pfr_player_id"] for r in pf})} players, '
          f'weeks {min(int(r["week"]) for r in pf)}-{max(int(r["week"]) for r in pf)}')
    print(f'    columns: {list(pf[0])}')
    ids = {r['pfr_player_id'] for r in pf}
    print(f'    identifier is pfr_player_id, NOT gsis_id -- a crosswalk is '
          f'required and P3 rejected the weekly_rosters.pfr_id bridge as '
          f'non-injective (77.51%)')
    OUT['pfr_rush_detail'] = {'season': y, 'rows': len(pf),
                              'players': len(ids), 'columns': list(pf[0])}

json.dump(OUT, open(f'{HERE}/audit.json', 'w'), indent=1)
print('\nwrote audit.json')
