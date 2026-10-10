"""Where did a ruled-out player's volume go? Friday rebuild vs Saturday designations build, per club, from PROJ means."""
import gzip, json, sys, collections
A, B, OUT = sys.argv[1:4]
pa = json.load(gzip.open(A))['rows']; pb = json.load(gzip.open(B))['rows']
F = ('targets', 'carries', 'pass_attempts', 'receptions', 'rec_yards', 'rush_yards', 'pass_yards')
def v(r, f): return float(r.get(f) or 0.0)
clubs = collections.defaultdict(list)
for k in pa:
    clubs[pa[k]['team']].append(k)
report = {}
for c, ks in sorted(clubs.items()):
    outs = [k for k in ks if pb[k].get('projection_state') == 'NOT_PLAYING_REPORTED_INACTIVE'
            and pa[k].get('projection_state') != 'NOT_PLAYING_REPORTED_INACTIVE']
    if not outs:
        continue
    tot = {f: (round(sum(v(pa[k], f) for k in ks), 2), round(sum(v(pb[k], f) for k in ks), 2)) for f in F}
    lost = {f: round(sum(v(pa[k], f) for k in outs), 2) for f in ('targets', 'carries')}
    gains = []
    for k in ks:
        if k in outs: continue
        dt, dc = v(pb[k], 'targets') - v(pa[k], 'targets'), v(pb[k], 'carries') - v(pa[k], 'carries')
        if abs(dt) >= 0.15 or abs(dc) >= 0.15:
            gains.append({'name': pa[k]['name'], 'pos': pa[k]['position'], 'd_targets': round(dt, 2), 'd_carries': round(dc, 2),
                          'dk': (pa[k]['dk_points'], pb[k]['dk_points']), 'band': (pa[k].get('role_band'), pb[k].get('role_band'))})
    by_pos = collections.defaultdict(lambda: [0.0, 0.0])
    for g in gains:
        by_pos[g['pos']][0] += g['d_targets']; by_pos[g['pos']][1] += g['d_carries']
    report[c] = {'out': [{'name': pa[k]['name'], 'pos': pa[k]['position'], 'targets_fri': round(v(pa[k], 'targets'), 2),
                          'carries_fri': round(v(pa[k], 'carries'), 2), 'dk_sat': pb[k]['dk_points']} for k in outs],
                 'team_totals_fri_sat': tot, 'volume_lost': lost,
                 'regained_by_position': {p: {'targets': round(t, 2), 'carries': round(cc, 2)} for p, (t, cc) in by_pos.items()},
                 'movers': sorted(gains, key=lambda g: -(abs(g['d_targets']) + abs(g['d_carries'])))}
json.dump(report, open(OUT, 'w'), indent=1)
for c, r in report.items():
    print(f"\n{c}: OUT {[(o['name'], o['pos'], o['targets_fri'], o['carries_fri']) for o in r['out']]}")
    print('  team totals fri->sat', {f: r['team_totals_fri_sat'][f] for f in ('targets', 'carries', 'pass_attempts')})
    print('  lost', r['volume_lost'], ' regained by pos', r['regained_by_position'])
    for g in r['movers'][:7]:
        print(f"    {g['name']:<22}{g['pos']:<3} tgt {g['d_targets']:+.2f} car {g['d_carries']:+.2f}  dk {g['dk'][0]:.2f}->{g['dk'][1]:.2f} {g['band'][0]}->{g['band'][1]}")
