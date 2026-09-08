"""TD2: baselines, the closed ladder, and persistence.

Pre-registration sha256
31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83.

EXPLORATORY. 2022-2025 heavily mined. Nothing may be promoted.
"""
import collections, json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import td2_lib as T                                            # noqa: E402

PREREG = '31e75d823c0027a9a4f623670a2cf104de6a1eccde8adf4027ae3d2b0f250f83'
BASELINES = ('B_league', 'B_pos', 'B_loc', 'B_pos_loc')
RUNGS = ('L0', 'L1', 'L2', 'L3', 'L4')


def loc_bucket(r):
    """Prior-only opportunity-location mix. NEVER the current game."""
    if not r['h_all_opp']:
        return 'unknown'
    z = r['h_rz'] / r['h_all_opp']
    return 'hi_rz' if z >= 0.20 else 'mid_rz' if z >= 0.10 else 'lo_rz'


def hist_bucket(r):
    n = r['h_games']
    return '<4' if n < 4 else '4-9' if n < 10 else '10-24' if n < 25 else '25+'


def fit(rs, ev):
    """Everything estimated on season < ev ONLY."""
    tr = [r for r in rs if r['season'] < ev and T.eligible(r)]
    assert all(r['season'] < ev for r in tr), 'TRAINING LEAKED THE EVAL SEASON'
    agg = lambda key: {k: (v[0] / v[1] if v[1] else 0.0) for k, v in key.items()}
    league = [0, 0]
    pos = collections.defaultdict(lambda: [0, 0])
    loc = collections.defaultdict(lambda: [0, 0])
    posloc = collections.defaultdict(lambda: [0, 0])
    for r in tr:
        league[0] += r['n_td']; league[1] += r['n_opp']
        for d, k in ((pos, r['position']), (loc, loc_bucket(r)),
                     (posloc, (r['position'], loc_bucket(r)))):
            d[k][0] += r['n_td']; d[k][1] += r['n_opp']
    B = {'B_league': league[0] / league[1] if league[1] else 0.0,
         'B_pos': agg(pos), 'B_loc': agg(loc), 'B_pos_loc': agg(posloc)}

    # empirical-Bayes beta prior, method of moments on TRAINING rows only
    rates = np.array([r['h_k'] / r['h_n'] for r in tr if r['h_n'] >= 5])
    if len(rates) > 50:
        m, v = float(rates.mean()), float(rates.var())
        if 0 < v < m * (1 - m):
            kappa = m * (1 - m) / v - 1
        else:
            kappa = 50.0
        kappa = float(min(max(kappa, 1.0), 500.0))
    else:
        m, kappa = B['B_league'], 50.0
    B['_eb'] = {'mean': m, 'kappa': kappa}
    # L4 logistic on PIT-safe features, fitted on training rows
    B['_l4'] = fit_logistic(tr, B)
    return B


def _feat(r, B):
    p0 = B['B_pos_loc'].get((r['position'], loc_bucket(r)),
                            B['B_pos'].get(r['position'], B['B_league']))
    p0 = min(max(p0, 1e-6), 1 - 1e-6)
    own = (r['h_k'] / r['h_n']) if r['h_n'] > 0 else p0
    return np.array([
        1.0,
        math.log(p0 / (1 - p0)),
        own - p0,
        math.log1p(r['h_n']),
        math.log1p(r['h_opp_per_game'] or 0.0),
        1.0 if hist_bucket(r) in ('<4', '4-9') else 0.0,
    ], float)


def fit_logistic(tr, B, iters=25):
    X = np.array([_feat(r, B) for r in tr])
    n = np.array([r['n_opp'] for r in tr], float)
    k = np.array([r['n_td'] for r in tr], float)
    w = np.zeros(X.shape[1]); w[1] = 1.0
    for _ in range(iters):
        z = X @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        g = X.T @ (k - n * p)
        W = n * p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(X.shape[1])
        try:
            w = w + np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            break
    return w


def predict(arm, r, B):
    p0 = B['B_pos_loc'].get((r['position'], loc_bucket(r)),
                            B['B_pos'].get(r['position'], B['B_league']))
    if arm == 'B_league':
        return B['B_league']
    if arm == 'B_pos':
        return B['B_pos'].get(r['position'], B['B_league'])
    if arm == 'B_loc':
        return B['B_loc'].get(loc_bucket(r), B['B_league'])
    if arm in ('B_pos_loc', 'L0'):
        return p0
    if arm == 'L1':
        m, kap = B['_eb']['mean'], B['_eb']['kappa']
        return (r['h_k'] + kap * p0) / (r['h_n'] + kap) if True else p0
    if arm == 'L2':
        e = T.ewma(r['h_rates'])
        return e if e is not None else p0
    if arm == 'L3':
        e = T.ewma(r['h_rates'])
        if e is None:
            return p0
        w = r['h_n'] / (r['h_n'] + B['_eb']['kappa'])
        return w * e + (1 - w) * p0
    if arm == 'L4':
        z = float(_feat(r, B) @ B['_l4'])
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
    raise ValueError(arm)


def main():
    OUT = {'prereg_sha256': PREREG,
           'label': 'EXPLORATORY -- heavily mined; no promotion possible',
           'primary_estimand': T.PRIMARY, 'estimands': {}}
    for kind in ('rec', 'rush'):
        for label, opp, td in T.ESTIMANDS[kind]:
            rs = T.load(kind, opp, td)
            arms = list(BASELINES) + list(RUNGS)
            P = {a: [] for a in arms}
            N, K, ROWS = [], [], []
            for ev in T.EVAL:
                B = fit(rs, ev)
                ev_rows = [r for r in rs if T.eligible(r, ev)]
                if not ev_rows:
                    continue
                for a in arms:
                    P[a] += [predict(a, r, B) for r in ev_rows]
                N += [r['n_opp'] for r in ev_rows]
                K += [r['n_td'] for r in ev_rows]
                ROWS += ev_rows
            N = np.array(N, float); K = np.array(K, float)
            res = {a: T.metrics(N, K, np.array(P[a])) for a in arms}
            best_base = min(BASELINES, key=lambda a: res[a]['log_loss'])
            bb = res[best_base]
            for a in arms:
                res[a]['ll_rel_pct_vs_best_baseline'] = (
                    100 * (bb['log_loss'] - res[a]['log_loss']) / bb['log_loss'])
                res[a]['resolution_gain_vs_best_baseline'] = (
                    res[a]['resolution'] - bb['resolution'])
            best_rung = min(RUNGS, key=lambda a: res[a]['log_loss'])
            key = f'{kind}|{label}'
            OUT['estimands'][key] = {
                'kind': kind, 'denominator': label,
                'is_primary': label == T.PRIMARY[kind],
                'n_rows': len(ROWS), 'best_baseline': best_base,
                'best_rung': best_rung, 'arms': res}
            tag = 'PRIMARY' if label == T.PRIMARY[kind] else 'secondary'
            print(f'\n== {key}  ({tag})  n_opp {int(N.sum())}  TD {int(K.sum())}  '
                  f'base {K.sum()/N.sum():.5f} ==')
            for a in arms:
                m = res[a]
                print(f"   {a:<10} LL {m['log_loss']:.6f}  Brier {m['brier']:.6f}  "
                      f"res {m['resolution']:.3e}  AUC {m['auc']:.4f}  "
                      f"sdP {m['sd_pred']:.5f}  rel-vs-base {m['ll_rel_pct_vs_best_baseline']:+.3f}%")
            print(f'   best baseline {best_base}; best rung {best_rung}  '
                  f'({res[best_rung]["ll_rel_pct_vs_best_baseline"]:+.3f}% LL, '
                  f'resolution gain {res[best_rung]["resolution_gain_vs_best_baseline"]:+.3e})')
            if label == T.PRIMARY[kind]:
                ci = T.cluster_bootstrap(
                    ROWS, N, K, {a: np.array(P[a]) for a in (best_base, best_rung)},
                    lambda n, k, p: T.metrics(n, k, p)['log_loss'], B=300)
                OUT['estimands'][key]['bootstrap_log_loss'] = ci
                print(f'   game-clustered 95% CI on LL: {best_base} '
                      f'[{ci[best_base]["lo"]:.6f}, {ci[best_base]["hi"]:.6f}]  '
                      f'{best_rung} [{ci[best_rung]["lo"]:.6f}, {ci[best_rung]["hi"]:.6f}]')
    json.dump(OUT, open(f'{HERE}/td2_ladder.json', 'w'), indent=1, default=str)
    print('\nwrote td2_ladder.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
