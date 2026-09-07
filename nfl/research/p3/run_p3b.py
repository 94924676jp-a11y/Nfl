"""P3 §5-6 role transition, all eight predeclared targets scored.

The winner is nominated by STABILITY across seasons among targets with a base
rate in [0.05, 0.40], not by best AUC -- the directive says not to choose a
threshold because it scores well, and predeclaration_p3.md §1 fixed that rule
before any of these numbers existed.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_features as F
import stage_a as A
from run_p3a import load_enriched

HERE = os.path.dirname(os.path.abspath(__file__))
POS = ('WR', 'TE', 'RB')


def targets(prior_mean, cur, position):
    d = cur - prior_mean
    return {
        'abs_10': int(abs(d) > 0.10),
        'abs_20': int(abs(d) > 0.20),
        'abs_30': int(abs(d) > 0.30),
        'up_20': int(d > 0.20),
        'down_20': int(d < -0.20),
        'to_starter': int(prior_mean < 0.50 and cur >= 0.50),
        'from_starter': int(prior_mean >= 0.50 and cur < 0.50),
        'pos_specific': int(abs(d) > (0.25 if position == 'RB' else 0.20)),
    }


def main():
    rows, _ = load_enriched()
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        h = [v for v in hist[r['gsis_id']] if v is not None]
        ss = r.get('snap_share')
        if len(h) >= 3 and ss is not None:
            pm = float(np.mean(h[-3:]))
            r['_prior_mean'] = pm
            r['_targets'] = targets(pm, ss, r['position'])
        else:
            r['_targets'] = None
        hist[r['gsis_id']].append(ss)

    cand = [r for r in rows if r['position'] in POS and r.get('_targets')
            and (r.get('f_n_prior') or 0) >= 4]
    print(f'role-transition population: {len(cand)}')
    ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
    out = {}
    for tname in ('abs_10', 'abs_20', 'abs_30', 'up_20', 'down_20',
                  'to_starter', 'from_starter', 'pos_specific'):
        per = {}
        for ev in A.EVAL:
            tr = [r for r in cand if r['season'] < ev]
            te = [r for r in cand if r['season'] == ev]
            if len(tr) < 500 or len(te) < 200:
                continue
            ui = ev <= 2024
            ytr = [r['_targets'][tname] for r in tr]
            yte = [r['_targets'][tname] for r in te]
            if sum(ytr) < 50 or sum(yte) < 30:
                continue
            m = A.fit_logistic([F.featurise_p3(r, ui, ALL) for r in tr], ytr)
            p = A.predict(m, [F.featurise_p3(r, ui, ALL) for r in te])
            base = float(np.mean(yte))
            k = max(int(round(base * len(te))), 1)
            thr = float(np.sort(p)[::-1][k - 1])
            pred = (p >= thr).astype(int); y = np.array(yte)
            tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
            fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
            per[ev] = {'n': len(te), 'base': base,
                       'brier_base': A.brier(yte, np.full(len(te), np.mean(ytr))),
                       'brier': A.brier(yte, p), 'auc': A.auc(yte, p),
                       'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
                       'precision': tp / (tp + fp) if tp + fp else None,
                       'recall': tp / (tp + fn) if tp + fn else None}
        if not per:
            continue
        aucs = [v['auc'] for v in per.values()]
        bases = [v['base'] for v in per.values()]
        out[tname] = {'per_season': per, 'auc_mean': float(np.mean(aucs)),
                      'auc_sd': float(np.std(aucs)),
                      'auc_range': float(max(aucs) - min(aucs)),
                      'base_mean': float(np.mean(bases))}
        print(f'{tname:<14} base={np.mean(bases):.3f} AUC mean={np.mean(aucs):.4f} '
              f'sd={np.std(aucs):.4f} range={max(aucs)-min(aucs):.4f}  '
              f'precision~{np.mean([v["precision"] or 0 for v in per.values()]):.3f} '
              f'recall~{np.mean([v["recall"] or 0 for v in per.values()]):.3f}')

    elig = {k: v for k, v in out.items() if 0.05 <= v['base_mean'] <= 0.40}
    if elig:
        primary = min(elig, key=lambda k: elig[k]['auc_sd'])
        out['_primary'] = primary
        out['_selection_rule'] = ('lowest across-season AUC sd among targets '
                                  'with base rate in [0.05, 0.40]; fixed in '
                                  'predeclaration_p3.md before scoring')
        print(f'\nPRIMARY (by predeclared stability rule): {primary} '
              f'(base {elig[primary]["base_mean"]:.3f}, AUC sd '
              f'{elig[primary]["auc_sd"]:.4f})')
        best_auc = max(out, key=lambda k: out[k]['auc_mean'] if k.startswith(('a','u','d','t','f','p')) and isinstance(out[k],dict) and 'auc_mean' in out[k] else -1)
        print(f'(best AUC would have been {best_auc} at '
              f'{out[best_auc]["auc_mean"]:.4f} -- not chosen, per the rule)')
    json.dump(out, open(f'{HERE}/p3_role_transition.json', 'w'), indent=1,
              default=float)


if __name__ == '__main__':
    main()
