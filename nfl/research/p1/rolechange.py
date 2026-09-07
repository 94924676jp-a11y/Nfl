"""Role-change diagnostic. Directive P1 §ROLE CHANGE.

The question is not "is prediction worse when roles change" -- of course it is.
It is HOW MUCH worse, for which trigger, and specifically whether vacated
opportunity transfers proportionally to backups. The directive says do not
assume it. So the last section measures it.
"""
import collections, statistics, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as M

rows = M.load()
rows, _ = M.extend_with_zeros(rows)
rows = M.add_shares(rows)
rows = M.role_flag(rows)

EV = [2022, 2023, 2024, 2025]
POS = ('WR', 'TE', 'RB')

# --- build per-player history for trigger labelling -------------------------
hist = collections.defaultdict(list)
for r in sorted(rows, key=lambda x: x['ord']):
    r['_hist'] = list(hist[r['gsis_id']])
    hist[r['gsis_id']].append(r)

def prior_snap(r, k=1):
    h = [x for x in r['_hist'] if x.get('snap_share') is not None]
    return h[-k].get('snap_share') if len(h) >= k else None

def triggers(r):
    """Every trigger is computed from games strictly before r."""
    out = []
    h = [x for x in r['_hist']]
    p1 = prior_snap(r, 1)
    if len(h) < 2:
        out.append('low_history(<2 prior)')
        return out
    # returning from absence: previous game had no appearance
    if h[-1].get('did_not_appear') == 1:
        out.append('returning_from_absence')
    # workload jump already visible last week
    p2 = prior_snap(r, 2)
    if p1 is not None and p2 is not None and p1 - p2 > 0.20:
        out.append('workload_jump_prior_week')
    if p1 is not None and p2 is not None and p2 - p1 > 0.20:
        out.append('workload_drop_prior_week')
    # team change
    prev_teams = [x['team'] for x in h[-3:]]
    if prev_teams and r['team'] not in prev_teams:
        out.append('team_change')
    if len(h) < 4:
        out.append('low_history(<4 prior)')
    if not out:
        out.append('stable')
    return out


for target in ('snap_share', 'target_share', 'rpr'):
    print(f'\n=== {target} — MAE by pregame trigger, eval seasons {EV}')
    train = [r for r in rows if r['season'] < min(EV)]
    prior = {}
    for p in POS:
        v = [r[target] for r in train
             if r['position'] == p and r.get(target) is not None]
        if v:
            prior[(p, target)] = statistics.mean(v)
    recs = M.build_predictions(rows, target, POS, prior)
    recs = [x for x in recs if x['row']['season'] in EV]
    buckets = collections.defaultdict(list)
    for x in recs:
        for t in triggers(x['row']):
            buckets[t].append(x)
        buckets['ALL'].append(x)
    for name in ('ALL', 'stable', 'workload_jump_prior_week',
                 'workload_drop_prior_week', 'returning_from_absence',
                 'team_change', 'low_history(<2 prior)',
                 'low_history(<4 prior)'):
        sel = buckets.get(name, [])
        if len(sel) < 30:
            print(f'  {name:<28} n={len(sel):<6} (too few to report)')
            continue
        m1 = M.metrics([(x['y'], x['preds']['lag1']) for x in sel])
        m3 = M.metrics([(x['y'], x['preds']['ewma3']) for x in sel])
        mp = M.metrics([(x['y'], x['preds']['prior']) for x in sel])
        print(f'  {name:<28} n={len(sel):<6} lag1={m1["mae"]:.4f} '
              f'ewma3={m3["mae"]:.4f} prior={mp["mae"]:.4f} '
              f'r(lag1)={m1["r"]:.3f}')

# --- does vacated opportunity transfer proportionally? ----------------------
print('\n=== VACATED OPPORTUNITY: does it transfer proportionally?')
print('Event: a player with prior-game target_share >= 0.20 does not appear.')
print('For each such event, compare each surviving teammate\'s actual change in')
print('target_share against the proportional-redistribution prediction.')

by_tw = collections.defaultdict(list)
for r in rows:
    by_tw[(r['team'], r['ord'])].append(r)
team_ords = collections.defaultdict(list)
for (tm, o) in by_tw:
    team_ords[tm].append(o)
for tm in team_ords:
    team_ords[tm].sort()

errs_prop, errs_naive, n_ev = [], [], 0
for tm, ords in team_ords.items():
    for idx in range(1, len(ords)):
        prev, cur = ords[idx - 1], ords[idx]
        pr = {r['gsis_id']: r for r in by_tw[(tm, prev)]}
        cu = {r['gsis_id']: r for r in by_tw[(tm, cur)]}
        gone = [p for p, r in pr.items()
                if (r.get('target_share') or 0) >= 0.20
                and (p not in cu or cu[p].get('did_not_appear') == 1)]
        if not gone:
            continue
        vac = sum(pr[p]['target_share'] for p in gone)
        surv = [p for p in pr
                if p not in gone and p in cu
                and cu[p].get('did_not_appear') != 1
                and pr[p].get('target_share') is not None
                and cu[p].get('target_share') is not None]
        base = sum(pr[p]['target_share'] for p in surv)
        if not surv or base <= 0 or vac <= 0:
            continue
        n_ev += 1
        for p in surv:
            actual = cu[p]['target_share']
            # proportional: everyone grows in proportion to prior share
            prop = pr[p]['target_share'] * (1 + vac / base)
            naive = pr[p]['target_share']          # no redistribution at all
            errs_prop.append(abs(actual - prop))
            errs_naive.append(abs(actual - naive))

print(f'  events={n_ev}  surviving player-games={len(errs_prop)}')
if errs_prop:
    print(f'  MAE, proportional redistribution : {statistics.mean(errs_prop):.4f}')
    print(f'  MAE, assume no redistribution    : {statistics.mean(errs_naive):.4f}')
    better = sum(1 for a, b in zip(errs_prop, errs_naive) if a < b)
    print(f'  proportional beats naive on {better}/{len(errs_prop)} '
          f'({100*better/len(errs_prop):.1f}%) of player-games')
