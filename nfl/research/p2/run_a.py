import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_a as A

kick = A.kickoffs(); inj, st = A.injuries(kick); dep = A.depth()
rows = A.build(kick, inj, dep)
POS = ('WR', 'TE', 'RB', 'QB')
cand = [r for r in rows if r['position'] in POS and (r.get('f_n_prior') or 0) >= 1]
print(f'candidate player-games: {len(cand)}  '
      f'base appearance rate: {np.mean([r["appeared"] for r in cand]):.4f}')
json.dump({f'{k[0]}_{k[1]}': v for k, v in st.items()},
          open(f'{os.path.dirname(os.path.abspath(__file__))}/injury_chronology.json', 'w'),
          indent=1)

results = {}
for thr in A.THRESHOLDS:
    for r in cand:
        ss = r.get('snap_share')
        r['y'] = 1 if (r['appeared'] and ss is not None and ss > thr) else 0
    per_season = {}
    for ev in A.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500 or len(te) < 200:
            continue
        ytr = [r['y'] for r in tr]; yte = [r['y'] for r in te]
        base = float(np.mean(ytr))
        # prev_game as an EMPIRICAL conditional rate, not a hand-picked pair.
        # The first version used 0.95/0.15, which is a strawman: at the >0.50
        # threshold it scored worse than the base rate, and beating a strawman
        # is not evidence for the logistic model.
        p1 = float(np.mean([r['y'] for r in tr if r.get('f_prev_appeared')])
                   ) if any(r.get('f_prev_appeared') for r in tr) else base
        p0 = float(np.mean([r['y'] for r in tr
                            if not r.get('f_prev_appeared')])
                   ) if any(not r.get('f_prev_appeared') for r in tr) else base
        preds = {
            'base_rate': np.full(len(te), base),
            'prev_game': np.array([p1 if r.get('f_prev_appeared') else p0
                                   for r in te]),
            'rate3': np.array([r.get('f_rate3') if r.get('f_rate3') is not None
                               else base for r in te]),
            'rate5': np.array([r.get('f_rate5') if r.get('f_rate5') is not None
                               else base for r in te]),
            'rate_ewma': np.array([r.get('f_rate_ewma')
                                   if r.get('f_rate_ewma') is not None else base
                                   for r in te]),
        }
        # shrink the empirical-rate baselines off the 0/1 boundary so log loss
        # is finite; a rate baseline that asserts certainty is not a fair
        # comparison and would score infinitely badly on one miss.
        # The trailing-rate baselines estimate P(appears at all). At a share
        # THRESHOLD they are not on the right scale, so each is recalibrated on
        # the training seasons by binning its own value against the realised
        # target. Without this the rate baselines are being asked the wrong
        # question and losing for that reason rather than on merit.
        def recal(name, getter):
            xs_tr = np.array([(getter(r) if getter(r) is not None else base)
                              for r in tr])
            ys_tr = np.array([r['y'] for r in tr], float)
            edges = np.linspace(0, 1, 11)
            table = []
            for i in range(10):
                m = (xs_tr >= edges[i]) & (xs_tr <= edges[i + 1] if i == 9
                                           else xs_tr < edges[i + 1])
                table.append(float(ys_tr[m].mean()) if m.sum() >= 30 else None)
            xs_te = np.array([(getter(r) if getter(r) is not None else base)
                              for r in te])
            idx = np.clip((xs_te * 10).astype(int), 0, 9)
            return np.array([table[i] if table[i] is not None else base
                             for i in idx])
        preds['prev_game'] = np.clip(preds['prev_game'], 0.02, 0.98)
        preds['rate3'] = recal('rate3', lambda r: r.get('f_rate3'))
        preds['rate5'] = recal('rate5', lambda r: r.get('f_rate5'))
        preds['rate_ewma'] = recal('rate_ewma', lambda r: r.get('f_rate_ewma'))
        preds['snap_ewma'] = recal('snap_ewma', lambda r: r.get('f_snap_ewma'))
        for k in ('prev_game', 'rate3', 'rate5', 'rate_ewma', 'snap_ewma'):
            preds[k] = np.clip(preds[k], 0.01, 0.99)

        m = A.fit_logistic([A.featurise(r, False) for r in tr], ytr)
        preds['logistic'] = A.predict(m, [A.featurise(r, False) for r in te])

        # injury-augmented: train and test only where the feature can exist
        tr_i = [r for r in tr if r['season'] <= 2024]
        te_i = [r for r in te if r['season'] <= 2024]
        if len(tr_i) > 500 and len(te_i) > 200:
            mi = A.fit_logistic([A.featurise(r, True) for r in tr_i],
                                [r['y'] for r in tr_i])
            pi = A.predict(mi, [A.featurise(r, True) for r in te_i])
            yi = [r['y'] for r in te_i]
            mn = A.fit_logistic([A.featurise(r, False) for r in tr_i],
                                [r['y'] for r in tr_i])
            pn = A.predict(mn, [A.featurise(r, False) for r in te_i])
            inj_cmp = {'n': len(te_i),
                       'logistic_no_injury': {'brier': A.brier(yi, pn),
                                              'logloss': A.logloss(yi, pn),
                                              'auc': A.auc(yi, pn)},
                       'logistic_with_injury': {'brier': A.brier(yi, pi),
                                                'logloss': A.logloss(yi, pi),
                                                'auc': A.auc(yi, pi)}}
        else:
            inj_cmp = None

        per = {}
        for name, p in preds.items():
            per[name] = {'brier': A.brier(yte, p), 'logloss': A.logloss(yte, p),
                         'auc': A.auc(yte, p), 'n': len(te)}
        best = min(per, key=lambda k: per[k]['brier'])
        per_season[ev] = {'per_model': per, 'best': best,
                          'injury_comparison': inj_cmp,
                          'calibration_best': A.calibration(yte, preds[best]),
                          'base_rate_test': float(np.mean(yte))}
    results[thr] = per_season

json.dump(results, open(f'{os.path.dirname(os.path.abspath(__file__))}/stage_a_results.json', 'w'),
          indent=1, default=float)

for thr, per_season in results.items():
    print(f'\n=== threshold snap_share > {thr:.2f}')
    for ev, d in per_season.items():
        p = d['per_model']
        line = '  '.join(f'{k}={p[k]["brier"]:.4f}' for k in
                         ('base_rate', 'prev_game', 'rate3', 'rate5',
                          'rate_ewma', 'snap_ewma', 'logistic'))
        print(f' {ev} n={p["logistic"]["n"]:6d} base={d["base_rate_test"]:.3f} '
              f'best={d["best"]:<10} AUC={p[d["best"]]["auc"]:.4f} '
              f'logloss={p[d["best"]]["logloss"]:.4f}')
        print(f'      brier: {line}')
        ic = d['injury_comparison']
        if ic:
            print(f'      injury arm (<=2024, n={ic["n"]}): '
                  f'no_inj brier={ic["logistic_no_injury"]["brier"]:.4f} '
                  f'AUC={ic["logistic_no_injury"]["auc"]:.4f}  ->  '
                  f'with_inj brier={ic["logistic_with_injury"]["brier"]:.4f} '
                  f'AUC={ic["logistic_with_injury"]["auc"]:.4f}')
