"""P2 §7: six redistribution rules x six opportunity classes.

The directive's instruction is the whole design: do not assume one mechanism
serves every opportunity type. Snaps, routes, targets, carries, third-down work
and red-zone work are tested SEPARATELY, and the winning rule is allowed to
differ between them.

Event: a teammate at the same position who appeared last week, with prior share
>= THRESH, does not appear this week. Everything used to form a prediction is
prior-game.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_a as A

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = {'snap_share': 0.20, 'rpr': 0.20, 'target_share': 0.15,
           'carry_share': 0.20, 'rz_carry_share': 0.20,
           'third_target_share': 0.15}


def add_third(rows):
    tt = collections.Counter()
    for r in rows:
        tt[(r['team'], r['ord'])] += r.get('third_targets', 0) or 0
    for r in rows:
        d = tt[(r['team'], r['ord'])]
        r['third_target_share'] = ((r.get('third_targets', 0) or 0) / d
                                   if d else None)


def main():
    kick = A.kickoffs(); inj, _ = A.injuries(kick); dep = A.depth()
    rows = A.build(kick, inj, dep)
    add_third(rows)
    by_tw = collections.defaultdict(list)
    for r in rows:
        by_tw[(r['team'], r['ord'])].append(r)
    team_ords = collections.defaultdict(list)
    for (tm, o) in by_tw:
        team_ords[tm].append(o)
    for tm in team_ords:
        team_ords[tm].sort()

    out = {}
    for cls, thresh in CLASSES.items():
        # team-specific absorbed fraction, learned on 2020-2021 only
        learn = collections.defaultdict(list)
        events = []
        for tm, ords in team_ords.items():
            for i in range(1, len(ords)):
                prev, cur = by_tw[(tm, ords[i - 1])], by_tw[(tm, ords[i])]
                pb = {x['gsis_id']: x for x in prev}
                cb = {x['gsis_id']: x for x in cur}
                gone = [x for x in prev
                        if x['appeared'] and (x.get(cls) or 0) >= thresh
                        and (x['gsis_id'] not in cb
                             or not cb[x['gsis_id']]['appeared'])]
                if not gone:
                    continue
                for pos in {x['position'] for x in gone}:
                    vac = sum((x.get(cls) or 0) for x in gone
                              if x['position'] == pos)
                    surv = [x for x in prev
                            if x['gsis_id'] in cb and cb[x['gsis_id']]['appeared']
                            and x.get(cls) is not None
                            and cb[x['gsis_id']].get(cls) is not None
                            and x['gsis_id'] not in {g['gsis_id'] for g in gone}]
                    if not surv or vac <= 0:
                        continue
                    same = [x for x in surv if x['position'] == pos]
                    base_all = sum((x.get(cls) or 0) for x in surv)
                    base_same = sum((x.get(cls) or 0) for x in same)
                    season = cur[0]['season']
                    gained = sum(cb[x['gsis_id']][cls] - x[cls] for x in same)
                    if season <= 2021 and vac > 0:
                        learn[tm].append(gained / vac)
                        learn['__ALL__'].append(gained / vac)
                    events.append({'season': season, 'team': tm, 'pos': pos,
                                   'vac': vac, 'surv': surv, 'same': same,
                                   'cb': cb, 'base_all': base_all,
                                   'base_same': base_same})
        gl = float(np.mean(learn['__ALL__'])) if learn['__ALL__'] else 0.0
        team_frac = {t: float(np.mean(v)) for t, v in learn.items()
                     if t != '__ALL__' and len(v) >= 5}

        errs = collections.defaultdict(list)
        n_ev = 0
        for e in events:
            if e['season'] <= 2021:
                continue                      # 2020-21 are the learning years
            n_ev += 1
            vac, surv, same, cb = e['vac'], e['surv'], e['same'], e['cb']
            tf = team_frac.get(e['team'], gl)
            for x in surv:
                prior = x[cls]; actual = cb[x['gsis_id']][cls]
                in_pos = x in same
                preds = {
                    'none': prior,
                    'proportional': prior * (1 + vac / e['base_all'])
                    if e['base_all'] > 0 else prior,
                    'within_position': (prior * (1 + vac / e['base_same'])
                                        if in_pos and e['base_same'] > 0
                                        else prior),
                    'equal_within_position': (prior + vac / len(same)
                                              if in_pos and same else prior),
                    'backup_weighted': (
                        prior + vac * ((1 - prior) / sum(1 - y[cls] for y in same))
                        if in_pos and same
                        and sum(1 - y[cls] for y in same) > 0 else prior),
                    'team_learned': (prior + tf * vac * (prior / e['base_same'])
                                     if in_pos and e['base_same'] > 0 else prior),
                }
                for k, v in preds.items():
                    errs[k].append(abs(actual - min(max(v, 0.0), 1.0)))
        if not errs['none']:
            continue
        res = {k: float(np.mean(v)) for k, v in errs.items()}
        best = min(res, key=res.get)
        wins = {k: float(np.mean([a < b for a, b in zip(errs[k], errs['none'])]))
                for k in errs if k != 'none'}
        out[cls] = {'n_events': n_ev, 'n_player_games': len(errs['none']),
                    'mae': res, 'best': best,
                    'win_rate_vs_none': wins,
                    'global_absorbed_fraction': gl,
                    'n_teams_with_own_rate': len(team_frac)}
        print(f'\n{cls}  events={n_ev} player-games={len(errs["none"])} '
              f'(learned absorbed fraction {gl:.3f})')
        for k in sorted(res, key=res.get):
            mark = ' <-- best' if k == best else ''
            wr = f'  beats none on {wins[k]*100:.1f}%' if k != 'none' else ''
            print(f'   {k:<24} MAE={res[k]:.4f}{wr}{mark}')
    json.dump(out, open(f'{HERE}/redistribution_results.json', 'w'), indent=1,
              default=float)


if __name__ == '__main__':
    main()
