"""P4D Experiments 1 and 2: recalibration, ranking, and the decomposition.

Walk-forward throughout. The calibrator is fitted on POOLED OUT-OF-FOLD pairs
from seasons strictly before the evaluation season, produced by models that
themselves saw only seasons before the season being calibrated. The family is
chosen on the inner season Y-1. Nothing here reads an evaluation-season
outcome.
"""
import collections, json, os, pickle, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4d_lib as L                                            # noqa: E402
import p3_features as F                                        # noqa: E402
import stage_a as A                                            # noqa: E402

P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
GROUPS = set(F.FEATURE_GROUPS) - {'p2_base'}
NEWBLOCKS = set(L.FEATURE_BLOCKS)


def load():
    rows = pickle.load(open(f'{P4B}/panel_enriched.pkl', 'rb'))
    cand = [r for r in rows if r['position'] in L.POSALL
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y_app'] = 1 if r['appeared'] else 0
    L.attach_p4d_features(rows)
    return rows, cand


def design(rs, ev_season, blocks):
    ui = ev_season <= 2024          # 2025 injury artifact has no date_modified
    return np.array([L.featurise_p4d(r, ui, GROUPS, blocks) for r in rs], float)


def fit_predict(cand, ev, blocks, converged, train_max=None):
    """Train on seasons < (train_max or ev); predict season ev."""
    tmax = ev if train_max is None else train_max
    tr = [r for r in cand if r['season'] < tmax]
    te = [r for r in cand if r['season'] == ev]
    if len(tr) < 500 or not te:
        return None, None, None
    ytr = np.array([r['y_app'] for r in tr], float)
    Xtr, Xte = design(tr, ev, blocks), design(te, ev, blocks)
    m = (L.fit_logistic_converged(Xtr, ytr) if converged
         else A.fit_logistic(Xtr.tolist(), ytr.tolist()))
    return te, np.array(L.predict(m, Xte), float), m


def oof_pairs(cand, ev, blocks, converged):
    """(p_hat, y) for every season 2021 <= s < ev, each produced by a model
    trained on seasons strictly before s. Never touches ev."""
    P, Y = [], []
    for s in range(2021, ev):
        te, p, _m = fit_predict(cand, s, blocks, converged)
        if te is None:
            continue
        P.append(p); Y.append(np.array([r['y_app'] for r in te], float))
    if not P:
        return None, None
    return np.concatenate(P), np.concatenate(Y)


def choose_family(cand, ev, blocks, converged):
    """Family chosen by log loss on the INNER season ev-1, with the calibrator
    fitted on out-of-fold pairs from seasons before ev-1."""
    inner = ev - 1
    p_tr, y_tr = oof_pairs(cand, inner, blocks, converged)
    te, p_va, _m = fit_predict(cand, inner, blocks, converged)
    if p_tr is None or te is None:
        return 'platt', None
    y_va = np.array([r['y_app'] for r in te], float)
    best, bll = None, None
    scores = {}
    for name, fn in L.CAL_FAMILIES.items():
        q = np.clip(L.apply_cal(fn(p_tr, y_tr), p_va), 1e-9, 1 - 1e-9)
        ll = float(-(y_va * np.log(q) + (1 - y_va) * np.log(1 - q)).mean())
        scores[name] = ll
        if bll is None or ll < bll:
            best, bll = name, ll
    return best, scores


def main():
    t0 = time.time()
    rows, cand = load()
    print(f'candidate rows {len(cand)}')
    OUT = {'systems': {}, 'family_choice': {}, 'coefficients': {}}
    store = {}

    SYS = [
        ('A',        dict(blocks=set(),    conv=False, cal=None)),
        ('A+P',      dict(blocks=set(),    conv=False, cal='platt')),
        ('A+I',      dict(blocks=set(),    conv=False, cal='isotonic')),
        ('A+S',      dict(blocks=set(),    conv=False, cal='spline')),
        ('A1',       dict(blocks=set(),    conv=True,  cal=None)),
        ('A1+cal',   dict(blocks=set(),    conv=True,  cal='BEST')),
        ('R',        dict(blocks=NEWBLOCKS, conv=True, cal=None)),
        ('R+cal',    dict(blocks=NEWBLOCKS, conv=True, cal='BEST')),
        ('X_depth',  dict(blocks=NEWBLOCKS | {'DEPTH_CHART_DIAGNOSTIC'},
                          conv=True, cal=None)),     # DIAGNOSTIC ONLY
    ]
    for ev in L.EVAL:
        for name, cfg in SYS:
            te, p, m = fit_predict(cand, ev, cfg['blocks'], cfg['conv'])
            if te is None:
                continue
            y = np.array([r['y_app'] for r in te], float)
            cal = None
            if cfg['cal'] is not None:
                fam = cfg['cal']
                if fam == 'BEST':
                    fam, sc = choose_family(cand, ev, cfg['blocks'], cfg['conv'])
                    OUT['family_choice'][f'{name}_{ev}'] = {
                        'chosen': fam, 'inner_season': ev - 1,
                        'inner_log_loss': sc}
                p_tr, y_tr = oof_pairs(cand, ev, cfg['blocks'], cfg['conv'])
                if p_tr is not None:
                    cal = L.CAL_FAMILIES[fam](p_tr, y_tr)
            q = L.apply_cal(cal, p)
            OUT['systems'].setdefault(name, {})[ev] = L.appearance_metrics(y, q)
            store[(name, ev)] = {'keys': [(r['gsis_id'], r['ord'], r['team'])
                                          for r in te],
                                 'p': q.astype(np.float32)}
            if name in ('A', 'A1', 'R'):
                OUT['coefficients'].setdefault(name, {})[ev] = {
                    'n_features': int(len(m['w'])),
                    'coef_norm': float(np.linalg.norm(m['w']))}
        # oracle, computed last and never offered to anything
        te = [r for r in cand if r['season'] == ev]
        y = np.array([r['y_app'] for r in te], float)
        store[('O', ev)] = {'keys': [(r['gsis_id'], r['ord'], r['team'])
                                     for r in te],
                            'p': np.clip(y, 1e-6, 1 - 1e-6).astype(np.float32)}
        row = OUT['systems']
        print(f'\n{ev}: ' + '  '.join(
            f'{k}: LL={row[k][ev]["log_loss"]:.5f} Br={row[k][ev]["brier"]:.5f} '
            f'AUC={row[k][ev]["auc"]:.4f} midAUC='
            f'{(row[k][ev]["mid_auc"] or float("nan")):.4f}'
            for k, _c in SYS if k in row and ev in row[k]))
    json.dump(OUT, open(f'{HERE}/p4d_appearance.json', 'w'), indent=1)
    with open(f'{HERE}/p4d_probs.pkl', 'wb') as f:
        pickle.dump(store, f, protocol=4)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4d_appearance.json, p4d_probs.pkl')


if __name__ == '__main__':
    main()
