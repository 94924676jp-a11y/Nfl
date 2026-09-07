"""P4D: the fixed-band test, the calibration-versus-ranking decomposition,
subgroups, and block ablations.

THE ONE STATISTIC THAT SETTLES THE QUESTION, named in the pre-declaration
before it was computed: AUC inside the 0.25-0.80 region with the region defined
by the INCUMBENT's probability. A monotone recalibration cannot change it --
the row set is fixed and a monotone map preserves within-set order -- so any
movement in it is a ranking change and nothing else.

The `mid_auc` reported by the appearance run uses each system's OWN band
membership, which recalibration changes, so those numbers are NOT comparable
across systems. That is why this second statistic exists.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4d_lib as L                                            # noqa: E402
import p3_features as F                                        # noqa: E402
from run_p4d_app import load, fit_predict, oof_pairs, choose_family, NEWBLOCKS

OUT = {}


def main():
    t0 = time.time()
    rows, cand = load()
    probs = pickle.load(open(f'{HERE}/p4d_probs.pkl', 'rb'))
    byk = {}
    for (name, ev), d in probs.items():
        for k, p in zip(d['keys'], d['p']):
            byk.setdefault((name, ev), {})[k] = float(p)
    lookup = {r['gsis_id'] + '|' + str(r['ord']) + '|' + r['team']: r
              for r in cand}
    systems = sorted({n for n, _e in probs})

    # ---- fixed-band analysis, bands assigned by the INCUMBENT --------------
    fixed = {}
    for ev in L.EVAL:
        base = byk.get(('A', ev))
        if not base:
            continue
        keys = list(base)
        pA = np.array([base[k] for k in keys])
        y = np.array([1.0 if lookup[f'{k[0]}|{k[1]}|{k[2]}']['appeared'] else 0.0
                      for k in keys])
        for name in systems:
            d = byk.get((name, ev))
            if not d:
                continue
            p = np.array([d.get(k, np.nan) for k in keys])
            ok = ~np.isnan(p)
            e = {}
            for lo, hi in L.BANDS:
                m = ok & (pA >= lo) & (pA < hi)
                if m.sum() < 60:
                    continue
                e[f'{lo:.2f}-{min(hi,1.0):.2f}'] = {
                    'n': int(m.sum()), 'mean_p': float(p[m].mean()),
                    'observed': float(y[m].mean()),
                    'gap': float(p[m].mean() - y[m].mean()),
                    'auc_within': L.auc(y[m], p[m]),
                    'brier': float(((p[m] - y[m]) ** 2).mean())}
            mid = ok & (pA >= L.MIDLO) & (pA < L.MIDHI)
            fixed.setdefault(name, {})[ev] = {
                'bands_by_incumbent_p': e,
                'mid_n': int(mid.sum()),
                'MID_AUC_FIXED_BAND': L.auc(y[mid], p[mid]),
                'mid_gap': float(p[mid].mean() - y[mid].mean()),
                'mid_brier': float(((p[mid] - y[mid]) ** 2).mean()),
                'mid_log_loss': float(-(y[mid] * np.log(np.clip(p[mid], 1e-9, 1))
                                        + (1 - y[mid]) * np.log(
                                            np.clip(1 - p[mid], 1e-9, 1))).mean()),
            }
    OUT['fixed_band'] = fixed
    print('== MID_AUC on the INCUMBENT-defined 0.25-0.80 band '
          '(monotone maps cannot move this) ==')
    for name in systems:
        if name not in fixed:
            continue
        print(f'  {name:9s} ' + '  '.join(
            f'{ev}: {fixed[name][ev]["MID_AUC_FIXED_BAND"]:.4f} '
            f'(n={fixed[name][ev]["mid_n"]}, gap '
            f'{fixed[name][ev]["mid_gap"]:+.4f})'
            for ev in L.EVAL if ev in fixed[name]))

    # ---- subgroups ---------------------------------------------------------
    sub = {}
    for ev in L.EVAL:
        base = byk.get(('A', ev))
        keys = list(base)
        rs = [lookup[f'{k[0]}|{k[1]}|{k[2]}'] for k in keys]
        y = np.array([1.0 if r['appeared'] else 0.0 for r in rs])
        pA = np.array([base[k] for k in keys])
        def band(p):
            return ('p<0.25' if p < .25 else 'p 0.25-0.50' if p < .5
                    else 'p 0.50-0.80' if p < .8
                    else 'p 0.80-0.95' if p < .95 else 'p>=0.95')
        splits = {
            'position': [r['position'] for r in rs],
            'role_stability': ['role_change' if r.get('role_change') == 1
                               else 'stable' for r in rs],
            'information_quality': [r.get('info_quality') or 'UNKNOWN' for r in rs],
            'prior_history_depth': ['n_prior<4' if (r.get('f_n_prior') or 0) < 4
                                    else 'n_prior 4-11' if (r.get('f_n_prior') or 0) < 12
                                    else 'n_prior>=12' for r in rs],
            'injury_feature': ['injury_available' if r.get('f_inj_available')
                               else 'injury_unavailable' for r in rs],
            'incumbent_band': [band(p) for p in pA],
        }
        for name in systems:
            d = byk.get((name, ev))
            p = np.array([d.get(k, np.nan) for k in keys])
            ok = ~np.isnan(p)
            for sname, lab in splits.items():
                lab = np.array(lab)
                for u in sorted(set(lab.tolist())):
                    m = ok & (lab == u)
                    if m.sum() < 60:
                        continue
                    pp = np.clip(p[m], 1e-9, 1 - 1e-9)
                    sub.setdefault(sname, {}).setdefault(u, {}).setdefault(
                        name, {})[ev] = {
                        'n': int(m.sum()),
                        'brier': float(((pp - y[m]) ** 2).mean()),
                        'log_loss': float(-(y[m] * np.log(pp)
                                            + (1 - y[m]) * np.log(1 - pp)).mean()),
                        'auc': L.auc(y[m], pp),
                        'gap': float(pp.mean() - y[m].mean())}
    OUT['subgroups'] = sub

    # ---- feature-block ablations for R -------------------------------------
    abl = {}
    for ev in L.EVAL:
        te, pfull, _m = fit_predict(cand, ev, NEWBLOCKS, True)
        y = np.array([r['y_app'] for r in te], float)
        full = L.appearance_metrics(y, pfull)
        abl.setdefault('R_full', {})[ev] = {
            'log_loss': full['log_loss'], 'brier': full['brier'],
            'auc': full['auc']}
        for b in L.FEATURE_BLOCKS:
            _te, p, _mm = fit_predict(cand, ev, NEWBLOCKS - {b}, True)
            mm = L.appearance_metrics(y, p)
            abl.setdefault(f'minus_{b}', {})[ev] = {
                'log_loss': mm['log_loss'], 'brier': mm['brier'],
                'auc': mm['auc'],
                'd_log_loss': mm['log_loss'] - full['log_loss'],
                'd_auc': (mm['auc'] - full['auc'])}
        _te, p0, _mm = fit_predict(cand, ev, set(), True)
        m0 = L.appearance_metrics(y, p0)
        abl.setdefault('no_new_blocks_A1', {})[ev] = {
            'log_loss': m0['log_loss'], 'brier': m0['brier'], 'auc': m0['auc'],
            'd_log_loss': m0['log_loss'] - full['log_loss'],
            'd_auc': m0['auc'] - full['auc']}
        print(f'  ablation {ev} done')
    OUT['ablations'] = abl
    json.dump(OUT, open(f'{HERE}/p4d_decomp.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4d_decomp.json')


if __name__ == '__main__':
    main()
