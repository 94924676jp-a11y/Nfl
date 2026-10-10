"""Week-5 roster status of every projected slate player across every full roster capture still on disk."""
import csv, gzip, json, sys
REPO = '/home/user/nfl/'
SNAPS = [('20261007T165720Z..20261008T021007Z', 'nfl_vintage/raw/weekly_rosters.efd424c87b892728.csv'),
         ('20261008T123409Z..20261009T013656Z', 'nfl_vintage/raw/weekly_rosters.dba8eeff1f9c0878.csv'),
         ('UNIVERSE SLICE 046ebaf4 (used by the research universe)', 'nfl/dfs/salaries/raw/classic_early_2026W5/superseded/NFLVERSE_ROSTER_WEEKLY_2026.046ebaf4bdee3c23.slate16.csv.gz'),
         ('20261009T192103Z..20261009T213051Z', 'nfl_vintage/raw/weekly_rosters.7d4b399e4f2b8a92.csv'),
         ('20261010T074137Z', 'nfl_vintage/raw/weekly_rosters.8729b73ef500cdf9.csv')]
proj = json.load(gzip.open(REPO + sys.argv[1]))['rows']
clubs = {r['team'] for r in proj.values()}
want = {r['gsis_id']: r for r in proj.values() if r.get('gsis_id')}
hist = {g: [] for g in want}
other_team = {g: [] for g in want}
for label, path in SNAPS:
    op = gzip.open if path.endswith('.gz') else open
    seen = {}
    for r in csv.DictReader(op(REPO + path, 'rt')):
        if r.get('week') == '5' and r.get('gsis_id') in want:
            seen[r['gsis_id']] = (r['status'], r['team'])
    for g in want:
        st, tm = seen.get(g, ('ABSENT', None))
        hist[g].append(st)
        other_team[g].append(tm)
rows = []
for g, r in want.items():
    h = hist[g]
    stable = len(set(h)) == 1 and h[0] == 'ACT'
    team_ok = all(t in (None, r['team']) for t in other_team[g])
    rows.append({'name': r['name'], 'team': r['team'], 'pos': r['position'], 'gsis_id': g, 'dk_points_sat': r['dk_points'],
                 'status_history': h, 'stable_ACT': stable, 'team_consistent': team_ok,
                 'verdict': 'STABLE_ACT' if stable and team_ok else 'UNRESOLVED_ROSTER_HISTORY'})
flag = [x for x in rows if x['verdict'] != 'STABLE_ACT']
out = {'snapshots': [s[0] for s in SNAPS], 'n_players': len(rows), 'n_stable_act': len(rows) - len(flag),
       'unresolved': sorted(flag, key=lambda x: -(x['dk_points_sat'] or 0)),
       'RULE': 'A single roster snapshot does not prove game-day eligibility. Any player whose week-5 status is not ACT in '
               'every capture is UNRESOLVED_ROSTER_HISTORY and is blocked from upload-ready portfolios until an official '
               'game-day document (inactives) or a dated transaction resolves him.'}
json.dump(out, open(sys.argv[2], 'w'), indent=1)
print(out['n_players'], 'players;', out['n_stable_act'], 'stable ACT;', len(flag), 'unresolved')
for x in out['unresolved']:
    print(f"  {x['name']:<24}{x['team']:<4}{x['pos']:<4} dk={x['dk_points_sat']}  {x['status_history']}  team_ok={x['team_consistent']}")
