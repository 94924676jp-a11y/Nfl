"""Stage 2 main run: participation adequacy, against the pre-declared rule."""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s2_lib as L                                             # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', 'p4c'))
import p4c_build as CB                                         # noqa: E402


def main():
    t0 = time.time()
    rows, sub = L.load()
    L.attach(sub)
    pa = CB.appearance(rows)
    OUT = {'estimand': L.TARGET,
           'estimand_note': ('share of team dropbacks on which the player was '
                             'on the field, conditional on appearance. An '
                             'UPPER BOUND on route participation, not routes '
                             'run.'),
           'coverage': {}, 'zeros': {}, 'by_season': {}, 'cohorts': {}}

    # ---- PA-4 coverage ---------------------------------------------------
    print('== PA-4 coverage and the zero/N-A question ==')
    for ev in L.EVAL:
        rs = [r for r in sub if r['season'] == ev]
        app = [r for r in rs if r['appeared']]
        have = [r for r in app if r.get(L.TARGET) is not None]
        zero = [r for r in have if r[L.TARGET] == 0.0]
        zero_real = [r for r in zero if (r.get('den') or {}).get(
            'team_dropbacks_part', 0) > 0]
        na = [r for r in app if r.get(L.TARGET) is None]
        OUT['coverage'][str(ev)] = {
            'appeared_player_games': len(app),
            'representation_present': len(have),
            'coverage': len(have) / max(len(app), 1),
            'true_zero_on_field_for_no_dropback': len(zero_real),
            'not_applicable_no_team_dropbacks': len(zero) - len(zero_real),
            'missing': len(na)}
        c = OUT['coverage'][str(ev)]
        print(f"  {ev}: appeared {c['appeared_player_games']:5d}  "
              f"present {c['coverage']:.3%}  true zeros {c['true_zero_on_field_for_no_dropback']:4d}  "
              f"N/A {c['not_applicable_no_team_dropbacks']:3d}  missing {c['missing']}")

    # ---- baselines, walk-forward ----------------------------------------
    print('\n== baselines, next-game participation share, appeared rows ==')
    per = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(lambda: ([], []))))
    pool = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    rowrec = []
    for ev in L.EVAL:
        for r in sub:
            if not L.eligible(r, ev):
                continue
            y = float(r[L.TARGET])
            p_app = pa.get(id(r))
            rec = {'ev': ev, 'pos': r['position'], 'y': y, 'r': r,
                   'p_app': p_app}
            for b in L.BASELINES:
                p = L.predict(b, r)
                if p is None:
                    continue
                rec[b] = p
                per[b][r['position']][ev][0].append(p)
                per[b][r['position']][ev][1].append(y)
                pool[b][r['position']][0].append(p)
                pool[b][r['position']][1].append(y)
                pool[b]['ALL'][0].append(p)
                pool[b]['ALL'][1].append(y)
            rowrec.append(rec)

    for pos in ('WR', 'TE', 'RB', 'ALL'):
        print(f'\n  --- {pos} ---')
        print(f"    {'baseline':18s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} "
              f"{'R2':>7s} {'sdratio':>8s} {'bias':>7s}   per-season MAE")
        for b in L.BASELINES:
            p, y = pool[b][pos]
            if not y:
                continue
            m = L.metrics(p, y)
            seas = []
            for ev in L.EVAL:
                if pos == 'ALL':
                    pp = sum((per[b][q][ev][0] for q in L.POS), [])
                    yy = sum((per[b][q][ev][1] for q in L.POS), [])
                else:
                    pp, yy = per[b][pos][ev]
                seas.append(L.metrics(pp, yy)['mae'] if yy else float('nan'))
            OUT['by_season'].setdefault(pos, {})[b] = {
                'pooled': m, 'per_season_mae': {str(e): s
                                                for e, s in zip(L.EVAL, seas)}}
            print(f"    {b:18s} {m['mae']:7.4f} {m['rmse']:7.4f} "
                  f"{(m['r'] or float('nan')):7.3f} {(m['r2'] or float('nan')):7.3f} "
                  f"{(m['sd_ratio'] or float('nan')):8.3f} {m['bias']:+7.4f}   "
                  + ' '.join(f'{s:.4f}' for s in seas))

    # ---- the best method, by pre-declared rule: pooled MAE per position --
    best = {}
    for pos in ('WR', 'TE', 'RB'):
        cand = {b: OUT['by_season'][pos][b]['pooled']['mae']
                for b in OUT['by_season'][pos]}
        best[pos] = min(cand, key=cand.get)
    OUT['best_method'] = best
    print(f'\n  best by pooled MAE: {best}')

    # ---- cohorts --------------------------------------------------------
    print('\n== cohorts (best method per position) ==')
    coh = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    for rec in rowrec:
        b = best[rec['pos']]
        if b not in rec:
            continue
        p, y = rec[b], rec['y']
        pa_ = rec['p_app']
        bands = [('prior_appeared_games', L.cohort_of(rec['r'],
                                                      'prior_appeared_games')),
                 ('role', L.cohort_of(rec['r'], 'role')),
                 ('appearance_probability',
                  None if pa_ is None else
                  '<0.25' if pa_ < .25 else '0.25-0.50' if pa_ < .50 else
                  '0.50-0.80' if pa_ < .80 else '0.80-0.95' if pa_ < .95
                  else '>=0.95')]
        for dim, lvl in bands:
            if lvl is None:
                continue
            coh[(rec['pos'], dim)][lvl][0].append(p)
            coh[(rec['pos'], dim)][lvl][1].append(y)
    for (pos, dim), d in sorted(coh.items()):
        pooled = OUT['by_season'][pos][best[pos]]['pooled']['mae']
        print(f'  {pos} / {dim}   (pooled MAE {pooled:.4f})')
        for lvl, (p, y) in sorted(d.items()):
            m = L.metrics(p, y)
            ratio = m['mae'] / pooled
            flag = '  <-- >2.5x' if (m['n'] >= 200 and ratio > 2.5) else ''
            OUT['cohorts'].setdefault(pos, {}).setdefault(dim, {})[lvl] = {
                **m, 'ratio_to_pooled_mae': ratio}
            print(f"    {lvl:12s} n={m['n']:5d}  MAE {m['mae']:.4f}  "
                  f"({ratio:4.2f}x)  r {(m['r'] or float('nan')):+.3f}  "
                  f"real {m['mean_real']:.3f}{flag}")
    json.dump(OUT, open(f'{HERE}/s2_results.json', 'w'), indent=1,
              default=lambda o: None)
    print(f'\ndone in {time.time()-t0:.0f}s -> s2_results.json')


if __name__ == '__main__':
    main()
