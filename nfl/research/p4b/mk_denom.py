"""P4B step 1: build the TEAM DENOMINATOR panel.

WHY THIS IS NOT P4's team_panel.csv, and the decision matters.

The oracle decomposition in the directive requires that
    realized_volume x realized_share == realized_player_opportunity
holds EXACTLY. If the denominator series comes from a different build than the
share definition, the identity breaks by a few percent and every "cost of not
knowing the pie" number silently absorbs that mismatch. So each denominator is
the exact quantity the corresponding share is divided by, aggregated from the
identifier-repaired player panel itself. p4/team_panel.csv is joined only for
`coach`, `home`, `rest`, `div_game` -- context, never a denominator.
"""
import collections, csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.abspath(os.path.join(HERE, '..', 'p1'))
P3 = os.path.abspath(os.path.join(HERE, '..', 'p3'))
P2 = os.path.abspath(os.path.join(HERE, '..', 'p2'))
P4 = os.path.abspath(os.path.join(HERE, '..', 'p4'))
for p in (P1, P2, P3, P4, '/home/user/nfl'):
    sys.path.insert(0, p)
import model as M                                              # noqa: E402

M.SP = P1
rows = []
for r in csv.DictReader(open(f'{P1}/panel_p3.csv')):
    r['season'] = int(r['season']); r['week'] = int(r['week'])
    for k in ('targets', 'carries', 'rz_targets', 'rz_carries', 'gl_carries',
              'third_targets', 'pass_snaps', 'team_plays', 'team_dropbacks',
              'team_pass_att', 'team_rush_att', 'team_rz_rush', 'team_gl_rush',
              'team_dropbacks_part', 'dropbacks_as_passer', 'pass_att_as_passer',
              'scrambles', 'designed_rushes'):
        r[k] = int(float(r.get(k) or 0))
    r['offense_snaps'] = int(float(r.get('offense_snaps') or 0))
    r['offense_pct'] = float(r['offense_pct']) if r['offense_pct'] else None
    r['ord'] = r['season'] * 100 + r['week']
    rows.append(r)
print(f'panel_p3 rows read: {len(rows)}')

# ---- team offensive snaps: DERIVED, and the derivation is checked ----------
# MEASURED FIRST, not assumed: snap_counts.offense_pct carries exactly 101
# distinct values (0.00..1.00), i.e. it is rounded to a whole percent. So
# offense_snaps/offense_pct is a usable denominator estimate only for players
# with a LARGE share -- at pct=0.02 the rounding admits a 50% error, which is
# why the first version of this file measured a p95 spread of 0.397. Restricted
# to players at pct>=0.75 the spread collapses to p95 0.0100.
#
# CONSEQUENCE, stated rather than hidden: because offense_pct is rounded,
# offense_pct * team_off_snaps does NOT reproduce offense_snaps. The snap share
# used from here on is therefore RECOMPUTED as offense_snaps/team_off_snaps, so
# the oracle identity realized_volume x realized_share == realized opportunity
# holds exactly, as it already does for targets and carries.
imp = collections.defaultdict(list)
for r in rows:
    if r['offense_pct'] and r['offense_pct'] >= 0.75 and r['offense_snaps'] > 0:
        imp[(r['team'], r['ord'])].append(r['offense_snaps'] / r['offense_pct'])
snaps_denom, spread = {}, []
for k, v in imp.items():
    v = sorted(v)
    med = v[len(v) // 2]
    snaps_denom[k] = round(med)
    if len(v) >= 3 and med > 0:
        spread.append((v[-1] - v[0]) / med)
spread.sort()
print(f'team-games with a derived snap denominator: {len(snaps_denom)}')
print(f'  implied-denominator spread among pct>=0.75 players: median '
      f'{spread[len(spread)//2]:.4f} p95 {spread[int(.95*len(spread))]:.4f} '
      f'max {spread[-1]:.4f} (n={len(spread)})')

agg = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    k = (r['team'], r['ord'])
    a = agg[k]
    a['team_targets'] += r['targets']
    a['team_carries'] += r['carries']
    a['team_rz_carries'] += r['rz_carries']
    a['team_dropbacks_part'] = max(a['team_dropbacks_part'], r['team_dropbacks_part'])
    a['team_plays'] = max(a['team_plays'], r['team_plays'])
    a['season'] = r['season']; a['week'] = r['week']

ctx = {}
for r in csv.DictReader(open(f'{P4}/team_panel.csv')):
    ctx[(r['team'], int(r['season']) * 100 + int(r['week']))] = r

out, no_ctx = [], 0
for k, a in sorted(agg.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    tm, o = k
    c = ctx.get(k)
    if not c:
        no_ctx += 1
    out.append({
        'season': a['season'], 'week': a['week'], 'team': tm, 'ord': o,
        'team_off_snaps': snaps_denom.get(k, 0),
        'team_dropbacks_part': a['team_dropbacks_part'],
        'team_targets': a['team_targets'],
        'team_carries': a['team_carries'],
        'team_rz_carries': a['team_rz_carries'],
        'coach': (c or {}).get('coach') or '?',
        'opponent': (c or {}).get('opponent') or '?',
        'home': (c or {}).get('home') or '',
        'rest': (c or {}).get('rest') or '',
        'div_game': (c or {}).get('div_game') or '',
    })
print(f'team-games built: {len(out)}; without P4 context row: {no_ctx}')

DEN = ('team_off_snaps', 'team_dropbacks_part', 'team_targets', 'team_carries',
       'team_rz_carries')
zero = {d: sum(1 for r in out if not r[d]) for d in DEN}
print('zero-valued denominators (Rule: zeros are errors until explained):', zero)
for d in DEN:
    v = sorted(r[d] for r in out if r[d])
    print(f'  {d:22s} n={len(v):5d} min={v[0]:4d} p50={v[len(v)//2]:4d} max={v[-1]:4d}')

w = csv.DictWriter(open(f'{HERE}/denom_panel.csv', 'w', newline=''),
                   fieldnames=list(out[0]))
w.writeheader(); w.writerows(out)
json.dump({'n_team_games': len(out), 'zero_denominators': zero,
           'snap_denominator_spread_p95': spread[int(.95 * len(spread))],
           'snap_denominator_spread_max': spread[-1],
           'team_games_without_p4_context': no_ctx},
          open(f'{HERE}/denom_diag.json', 'w'), indent=1)
print('wrote', f'{HERE}/denom_panel.csv')
