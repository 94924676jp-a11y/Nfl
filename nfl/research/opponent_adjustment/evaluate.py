#!/usr/bin/env python3.12
"""OPP-ADJUST-1 evaluation, exactly as PREREGISTRATION_OPP_ADJUST_1.md (+A1). Research only."""
import json, pickle, pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build_frame import estimate_k, shrunk  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent
F = pickle.load(open(OUT / 'frame.pkl', 'rb'))
club, grp, pgd, ug = F['club'], F['grp'], F['pgd'], F['ug']
B, SEED = 2000, 20261009
FULL = ['D2', 'D3', 'D4', 'D5', 'D6', 'D7']
FOLDS = {'F1': ([2021, 2022, 2023], 2024), 'F2': ([2021, 2022, 2023, 2024], 2025)}
SUPP = {'F3': ([2021, 2022, 2023, 2024, 2025], 2026)}
assert not ((club.season == 2026) & (club.week >= 5)).any()

# attach components to fantasy frames
compcols = ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'OWNP']
cm = club[['game_id', 'club', 'is_home', 'subset'] + compcols]
grp = grp.merge(cm, on=['game_id', 'club'], how='left')
pgd = pgd.merge(cm, on=['game_id', 'club'], how='left')
for d in (club, grp, pgd):
    d['wkey'] = d.season.astype(int) * 100 + d.week.astype(int)


def feats(df, ks):
    X = {}
    for v in compcols:
        k = ks.get(v)
        if k is None:
            X[v] = np.zeros(len(df)); continue
        X[v] = np.array([shrunk(*c, k) if isinstance(c, tuple) else 0.0 for c in df[v]])
    X = pd.DataFrame(X, index=df.index)
    X['OLX'] = X['OWNP'] * X['D4']
    return X


def ols(Xtr, ytr):
    A = np.column_stack([np.ones(len(Xtr)), Xtr])
    beta, *_ = np.linalg.lstsq(A, ytr, rcond=None)
    return beta


def pred(beta, X):
    return np.column_stack([np.ones(len(X)), X]) @ beta


def crps_ens(pred_, y, res):
    """exact CRPS of ensemble pred + res (res = training residuals)."""
    r = np.sort(res); R = len(r); cs = np.concatenate([[0], np.cumsum(r)])
    z = y - pred_
    j = np.searchsorted(r, z)
    e1 = (z * j - cs[j] + (cs[R] - cs[j]) - z * (R - j)) / R
    i = np.arange(R)
    e2 = 2 * np.sum((2 * i - R + 1) * r) / (R * R)   # E|X-X'|
    return e1 - 0.5 * e2


def run_target(df, ycol, inccol, folds, ks_by_fold, extra_models=True):
    rows = []
    coefs = {}
    for fname, (tr_s, te_s) in folds.items():
        d = df[df[ycol].notna() & df[inccol].notna()]
        X = feats(d, ks_by_fold[fname])
        tr = d.season.isin(tr_s).values; te = (d.season == te_s).values
        y = d[ycol].values.astype(float); inc = d[inccol].values.astype(float); home = d.is_home.astype(float).values
        base = np.column_stack([inc, home])
        models = {'INC_R': base, 'CAND_FULL': np.column_stack([base, X[FULL].values])}
        if extra_models:
            for v in ['D1'] + FULL:
                models['X_' + v] = np.column_stack([base, X[[v]].values])
            models['X_CAND_OL'] = np.column_stack([base, X[FULL + ['OWNP', 'OLX']].values])
        out = pd.DataFrame({'season': d.season.values[te], 'wkey': d.wkey.values[te], 'game_id': d.game_id.values[te],
                            'club': d.club.values[te], 'subset': d.subset.values[te], 'y': y[te], 'fold': fname})
        # INC_RAW: no refit
        res = y[tr] - inc[tr]
        out['pred_INC_RAW'] = inc[te]; out['crps_INC_RAW'] = crps_ens(inc[te], y[te], res)
        for m, A in models.items():
            b = ols(A[tr], y[tr]); p_tr = pred(b, A[tr]); p_te = pred(b, A[te])
            out['pred_' + m] = p_te; out['crps_' + m] = crps_ens(p_te, y[te], y[tr] - p_tr)
            if m in ('INC_R', 'CAND_FULL'):
                names = ['const', 'inc', 'home'] + (FULL if m == 'CAND_FULL' else [])
                coefs[(fname, m)] = dict(zip(names, np.round(b, 4).tolist()))
        out['n_train'] = int(tr.sum())
        rows.append(out)
    return pd.concat(rows, ignore_index=True), coefs


def boot_mean_diff(dvals, clusters, level, rng):
    """paired cluster bootstrap CI for the mean of dvals."""
    cl = pd.Series(dvals).groupby(pd.Series(clusters).values)
    s, n = cl.sum().values, cl.size().values
    C = len(s)
    idx = rng.integers(0, C, size=(B, C))
    m = s[idx].sum(1) / n[idx].sum(1)
    a = (1 - level) / 2
    return float(np.quantile(m, a)), float(np.quantile(m, 1 - a))


def ci_all(dvals, sub, level):
    out = {}
    for sch, col in (('week', 'wkey'), ('game', 'game_id'), ('club', 'club')):
        rng = np.random.default_rng(SEED)
        out[sch] = boot_mean_diff(dvals, sub[col].values, level, rng)
    widest = max(out.values(), key=lambda x: x[1] - x[0])
    out['widest'] = widest
    out['widest_upper'] = max(v[1] for k, v in out.items() if k != 'widest')
    return out


def calib(sub, pcol, rng_seed=SEED):
    y, p = sub.y.values, sub[pcol].values
    A = np.column_stack([np.ones(len(p)), p]); b = np.linalg.lstsq(A, y, rcond=None)[0]
    rng = np.random.default_rng(rng_seed)
    wk = sub.wkey.values; uw = np.unique(wk); groups = [np.where(wk == w)[0] for w in uw]
    sl = []
    for _ in range(1000):
        ii = np.concatenate([groups[j] for j in rng.integers(0, len(uw), len(uw))])
        Ai = A[ii]; sl.append(np.linalg.lstsq(Ai, y[ii], rcond=None)[0][1])
    return {'slope': round(float(b[1]), 4), 'intercept': round(float(b[0]), 4),
            'slope_ci95': [round(float(np.quantile(sl, .025)), 4), round(float(np.quantile(sl, .975)), 4)],
            'mean_resid_actual_minus_pred': round(float(np.mean(y - p)), 4), 'mean_actual': round(float(np.mean(y)), 4)}


def summarise(res, level_a1, extra=True):
    ev = {}
    ae = lambda s, m: np.abs(s.y - s['pred_' + m])
    pooled = res
    ev['n_heldout'] = int(len(pooled))
    ev['by_season'] = {}
    for s, sub in pooled.groupby('season'):
        dC = (sub.crps_CAND_FULL - sub.crps_INC_R).values
        dM = (ae(sub, 'CAND_FULL') - ae(sub, 'INC_R')).values
        ev['by_season'][int(s)] = {
            'n': int(len(sub)), 'MAE_INC_RAW': round(float(ae(sub, 'INC_RAW').mean()), 4),
            'MAE_INC_R': round(float(ae(sub, 'INC_R').mean()), 4), 'MAE_CAND': round(float(ae(sub, 'CAND_FULL').mean()), 4),
            'CRPS_INC_RAW': round(float(sub.crps_INC_RAW.mean()), 4),
            'CRPS_INC_R': round(float(sub.crps_INC_R.mean()), 4), 'CRPS_CAND': round(float(sub.crps_CAND_FULL.mean()), 4),
            'dCRPS': round(float(dC.mean()), 4), 'dCRPS_ci95': ci_all(dC, sub, .95),
            'dMAE': round(float(dM.mean()), 4), 'dMAE_ci95': ci_all(dM, sub, .95)}
    dC = (pooled.crps_CAND_FULL - pooled.crps_INC_R).values
    dM = (ae(pooled, 'CAND_FULL') - ae(pooled, 'INC_R')).values
    ev['pooled'] = {'MAE_INC_RAW': round(float(ae(pooled, 'INC_RAW').mean()), 4),
                    'MAE_INC_R': round(float(ae(pooled, 'INC_R').mean()), 4),
                    'MAE_CAND': round(float(ae(pooled, 'CAND_FULL').mean()), 4),
                    'CRPS_INC_RAW': round(float(pooled.crps_INC_RAW.mean()), 4),
                    'CRPS_INC_R': round(float(pooled.crps_INC_R.mean()), 4),
                    'CRPS_CAND': round(float(pooled.crps_CAND_FULL.mean()), 4),
                    'dCRPS': round(float(dC.mean()), 4), 'dCRPS_ci_bonf': ci_all(dC, pooled, level_a1),
                    'dCRPS_ci95': ci_all(dC, pooled, .95),
                    'dMAE': round(float(dM.mean()), 4), 'dMAE_ci95': ci_all(dM, pooled, .95),
                    'dCRPS_rel_pct': round(100 * float(dC.mean() / pooled.crps_INC_R.mean()), 3)}
    ev['subsets'] = {}
    for lab in ('STABLE', 'QB_CHANGE'):
        sub = pooled[pooled.subset == lab]
        if len(sub) < 100:
            ev['subsets'][lab] = {'n': int(len(sub)), 'state': 'NOT_EVALUABLE'}; continue
        dM = (ae(sub, 'CAND_FULL') - ae(sub, 'INC_R')).values
        dC = (sub.crps_CAND_FULL - sub.crps_INC_R).values
        mae_inc = float(ae(sub, 'INC_R').mean())
        ev['subsets'][lab] = {'n': int(len(sub)), 'MAE_INC_R': round(mae_inc, 4), 'MAE_CAND': round(float(ae(sub, 'CAND_FULL').mean()), 4),
                              'dMAE': round(float(dM.mean()), 4), 'dMAE_ci95': ci_all(dM, sub, .95),
                              'margin': round(0.02 * mae_inc, 4), 'dCRPS': round(float(dC.mean()), 4),
                              'dCRPS_ci95': ci_all(dC, sub, .95)}
    ev['calibration'] = {'CAND_FULL': calib(pooled, 'pred_CAND_FULL'), 'INC_R': calib(pooled, 'pred_INC_R'),
                         'INC_RAW': calib(pooled, 'pred_INC_RAW')}
    if extra:
        ev['exploratory_dCRPS_vs_INC_R'] = {}
        for c in [c for c in pooled.columns if c.startswith('crps_X_')]:
            d = (pooled[c] - pooled.crps_INC_R).values
            ev['exploratory_dCRPS_vs_INC_R'][c[5:]] = {'d': round(float(d.mean()), 4), 'ci95_week': [round(x, 4) for x in ci_all(d, pooled, .95)['week']]}
    # verdicts
    p = ev['pooled']; A = {}
    A['A1'] = 'PASS' if p['dCRPS_ci_bonf']['widest_upper'] < 0 else 'FAIL'
    A['A2'] = 'PASS' if all(v['dCRPS'] < 0 for v in ev['by_season'].values()) and p['dMAE'] < 0 else 'FAIL'
    a3 = []
    for lab, v in ev['subsets'].items():
        if v.get('state') == 'NOT_EVALUABLE':
            a3.append('NOT_EVALUABLE')
        else:
            a3.append('PASS' if v['dMAE_ci95']['widest_upper'] < v['margin'] else 'FAIL')
    A['A3'] = 'FAIL' if 'FAIL' in a3 else ('NOT_EVALUABLE' if 'NOT_EVALUABLE' in a3 else 'PASS')
    c = ev['calibration']['CAND_FULL']
    A['A4'] = 'PASS' if 0.8 <= c['slope'] <= 1.2 and abs(c['mean_resid_actual_minus_pred']) <= 0.05 * abs(c['mean_actual']) else 'FAIL'
    A['OVERALL'] = 'PASS' if all(A[k] == 'PASS' for k in ('A1', 'A2', 'A3', 'A4')) else (
        'NOT_EVALUABLE' if 'NOT_EVALUABLE' in A.values() and 'FAIL' not in A.values() else 'FAIL')
    ev['verdict'] = A
    return ev


def ks_for(seasons, kfix=None):
    ks, diag = {}, {}
    for v in compcols:
        if kfix is not None:
            ks[v] = kfix; continue
        k, t2, s2 = estimate_k(ug[v], seasons)
        ks[v] = k
        diag[v] = {'k_games': None if k is None else round(k, 2), 'tau2': t2, 'sigma2_game': s2,
                   'reliability_17g': None if k is None else round(17 / (17 + k), 3),
                   'state': 'NO_RESOLVABLE_SIGNAL' if k is None else 'ESTIMATED'}
    return ks, diag


def main():
    R = {'ARTIFACT': 'OPP_ADJUST_1_RESULTS', 'prereg': 'PREREGISTRATION_OPP_ADJUST_1.md + AMENDMENT_A1',
         'PRODUCTION_CHANGED': False, 'shrinkage': {}, 'club': {}, 'club_supplementary_2026w1_4': {},
         'position_group': {}, 'player': {}, 'coefficients': {}, 'sensitivity_k': {}}
    allf = {**FOLDS, **SUPP}
    KS = {}
    for f, (tr, te) in allf.items():
        KS[f], R['shrinkage'][f] = ks_for(tr)
    # coverage check
    cov = {}
    for te in (2024, 2025):
        d = club[club.season == te]
        ok = d.points.notna() & d.inc_points.notna() & d.pass_attempts.notna() & d.inc_pass_attempts.notna()
        cov[te] = round(float(ok.mean()), 4)
    R['coverage_heldout'] = cov
    assert all(v >= 0.95 for v in cov.values()), cov
    lvl_club = 1 - 0.05 / 3
    for y in ('pass_attempts', 'rush_attempts', 'points'):
        res, co = run_target(club, y, 'inc_' + y, FOLDS, KS)
        R['club'][y] = summarise(res, lvl_club)
        R['coefficients'][y] = {f'{a}|{b}': v for (a, b), v in co.items()}
        res3, co3 = run_target(club, y, 'inc_' + y, SUPP, KS, extra_models=False)
        s3 = summarise(res3, .95, extra=False); s3['verdict'] = 'NO_VERDICT (supplementary, declared)'
        R['club_supplementary_2026w1_4'][y] = s3
        R['coefficients'][y].update({f'{a}|{b}': v for (a, b), v in co3.items()})
        for kf in (4.0, 17.0):
            KSf = {f: ks_for(tr, kf)[0] for f, (tr, te) in FOLDS.items()}
            rf, _ = run_target(club, y, 'inc_' + y, FOLDS, KSf, extra_models=False)
            d = (rf.crps_CAND_FULL - rf.crps_INC_R).values
            R['sensitivity_k'][f'{y}|k={kf}'] = {'dCRPS': round(float(d.mean()), 4),
                                                 'ci95_week': [round(x, 4) for x in ci_all(d, rf, .95)['week']]}
        print(y, R['club'][y]['pooled']['dCRPS'], R['club'][y]['pooled']['dCRPS_ci_bonf']['widest'], R['club'][y]['verdict'])
    lvl_pos = 1 - 0.05 / 4
    for P in ('QB', 'RB', 'WR', 'TE'):
        res, co = run_target(grp, P, 'inc_' + P, FOLDS, KS)
        R['position_group'][P] = summarise(res, lvl_pos)
        R['coefficients']['group_' + P] = {f'{a}|{b}': v for (a, b), v in co.items()}
        print('group', P, R['position_group'][P]['pooled']['dCRPS'], R['position_group'][P]['verdict'])
        sub = pgd[pgd.pos == P]
        res, co = run_target(sub, 'dk_points_current_rules', 'inc_player', FOLDS, KS)
        R['player'][P] = summarise(res, lvl_pos)
        R['coefficients']['player_' + P] = {f'{a}|{b}': v for (a, b), v in co.items()}
        print('player', P, R['player'][P]['pooled']['dCRPS'], R['player'][P]['verdict'])
    json.dump(R, open(OUT / 'OPP_ADJUST_1_RESULTS.json', 'w'), indent=1, default=lambda o: o if not isinstance(o, tuple) else list(o))


if __name__ == '__main__':
    main()
