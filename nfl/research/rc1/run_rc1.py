"""RC1: baseline, oracle decomposition, Shapley, subgroups.

EXPLORATORY. 2022-2025 are heavily mined. Nothing here may be promoted.
"""
import itertools, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '..', '..', '..')))
import rc1_lib as L                                            # noqa: E402
import rc1_sim as S                                            # noqa: E402

SUBSETS = [frozenset(c) for k in range(4)
           for c in itertools.combinations(S.COMPONENTS, k)]


def main():
    t0 = time.time()
    rows, sub = L.load()
    L.attach_prior(sub)
    OUT = {'estimand': 'Y = receiving yards per player-game',
           'identity': 'Y = T x C x V, with Y = 0 when T = 0 or R = 0',
           'label': 'EXPLORATORY -- 2022-2025 are heavily mined; '
                    'diagnosis and recoverability only, never confirmation',
           'prereg_sha256': '34f8ac10be7bc0c5b39ee0e89340a3061'
                            'ff0910dca803d4975887b8811c02cdd',
           'seasons': {}, 'subsets': {}}

    # MEMORY. Eight coalitions x 22.5k rows x 2000 draws is ~2.9 GB if the
    # matrices are all held. Each matrix is therefore reduced to per-row
    # summaries -- CRPS, the point mean, and the interval bounds -- and then
    # discarded. The bootstrap needs only the per-row CRPS, because the mean
    # CRPS over a resample IS the mean of the per-row values; resampling those
    # is exact, not an approximation of resampling the draws.
    per = {fs: [] for fs in SUBSETS}       # per-row CRPS
    pnt = {fs: [] for fs in SUBSETS}       # per-row point mean
    cov = {fs: {l: [] for l in (50, 80, 90, 95)} for fs in SUBSETS}
    ALLR, YS, GS = [], [], []

    for ev in L.EVAL:
        rs = [r for r in sub if L.eligible(r, ev)]
        y = np.array([r['Y'] for r in rs], float)
        games = [r['game_id'] for r in rs]
        d = {'n': len(rs), 'mean_Y': float(y.mean()),
             'sd_Y': float(y.std(ddof=1)),
             'n_zero_target': int(sum(1 for r in rs if r['T'] == 0)),
             'n_zero_yards': int((y == 0).sum()),
             'n_games': len(set(games))}
        for fs in SUBSETS:
            D = S.simulate(rs, ev, sub, oracle=tuple(sorted(fs)))
            key = '+'.join(sorted(fs)) or 'baseline'
            d[key] = L.score(D, y)
            per[fs].append(L.crps_matrix(D, y))
            pnt[fs].append(D.mean(1))
            for lvl in (50, 80, 90, 95):
                a = (100 - lvl) / 200.0
                lo = np.quantile(D, a, axis=1); hi = np.quantile(D, 1 - a, axis=1)
                cov[fs][lvl].append(((y >= lo) & (y <= hi)).astype(float))
            if fs == frozenset(S.COMPONENTS):
                d['identity_max_abs_error'] = float(np.abs(D.mean(1) - y).max())
                d['identity_max_draw_spread'] = float(D.std(1).max())
                d['identity_valid'] = bool(d['identity_max_abs_error'] < 1e-9
                                           and d['identity_max_draw_spread'] < 1e-9)
            del D
        ALLR += rs; YS.append(y); GS += games
        OUT['seasons'][ev] = d
        print(f"  {ev}: n={d['n']:5d} games={d['n_games']:3d}  "
              f"baseline CRPS {d['baseline']['crps']:7.4f}  "
              f"identity |err| {d['identity_max_abs_error']:.2e} "
              f"spread {d['identity_max_draw_spread']:.2e} -> "
              f"{'VALID' if d['identity_valid'] else 'INVALID'}")

    Y = np.concatenate(YS)
    C = {fs: np.concatenate(per[fs]) for fs in SUBSETS}
    P = {fs: np.concatenate(pnt[fs]) for fs in SUBSETS}
    CV = {fs: {l: np.concatenate(cov[fs][l]) for l in (50, 80, 90, 95)}
          for fs in SUBSETS}

    print('\n== pooled oracle decomposition ==')
    base = float(C[frozenset()].mean())
    vals = {fs: base - float(C[fs].mean()) for fs in SUBSETS}
    phi = S.shapley(vals)
    tot = sum(phi.values())
    OUT['pooled'] = {
        'n': int(len(Y)), 'n_games': len(set(GS)), 'baseline_crps': base,
        'mean_Y': float(Y.mean()), 'sd_Y': float(Y.std(ddof=1)),
        'coalition_crps_reduction': {'+'.join(sorted(k)) or 'baseline': v
                                     for k, v in vals.items()},
        'coalition_crps': {'+'.join(sorted(k)) or 'baseline': float(C[k].mean())
                           for k in SUBSETS},
        'shapley_crps': phi,
        'shapley_pct': {k: 100.0 * v / tot for k, v in phi.items()},
        'efficiency_check': {'sum_shapley': tot,
                             'grand_coalition': vals[frozenset(S.COMPONENTS)],
                             'gap': tot - vals[frozenset(S.COMPONENTS)]}}
    OUT['pooled']['baseline_full'] = {
        'crps': base,
        'mae': float(np.abs(P[frozenset()] - Y).mean()),
        'rmse': float(np.sqrt(((P[frozenset()] - Y) ** 2).mean())),
        'bias': float((P[frozenset()] - Y).mean()),
        'r': float(np.corrcoef(P[frozenset()], Y)[0, 1]),
        'sd_pred_mean': float(P[frozenset()].std(ddof=1)),
        'sd_actual': float(Y.std(ddof=1)),
        'sd_ratio': float(P[frozenset()].std(ddof=1) / Y.std(ddof=1)),
        **{f'cover{l}': float(CV[frozenset()][l].mean()) for l in (50, 80, 90, 95)}}
    for k in S.COMPONENTS:
        print(f'  {k}: Shapley CRPS reduction {phi[k]:8.4f}   '
              f'{100*phi[k]/tot:6.2f}%')
    print(f'  efficiency gap {tot - vals[frozenset(S.COMPONENTS)]:.2e}')
    bf = OUT['pooled']['baseline_full']
    print(f"  baseline: CRPS {bf['crps']:.4f}  MAE {bf['mae']:.3f}  "
          f"RMSE {bf['rmse']:.3f}  r {bf['r']:.4f}  sd_ratio {bf['sd_ratio']:.4f}")
    print(f"  coverage 50/80/90/95: {bf['cover50']:.3f} {bf['cover80']:.3f} "
          f"{bf['cover90']:.3f} {bf['cover95']:.3f}")

    # ---- game-clustered bootstrap ---------------------------------------
    print('\n== game-clustered bootstrap, 1000 resamples ==')
    import collections as _c
    rng = np.random.default_rng(L.SEED)
    by = _c.defaultdict(list)
    for i, g in enumerate(GS):
        by[g].append(i)
    keys = list(by)
    idxs = [np.array(by[k]) for k in keys]
    boot = {c: [] for c in S.COMPONENTS}
    bootbase = []
    for _ in range(1000):
        pick = rng.integers(0, len(keys), len(keys))
        sel = np.concatenate([idxs[j] for j in pick])
        b = float(C[frozenset()][sel].mean())
        v = {fs: b - float(C[fs][sel].mean()) for fs in SUBSETS}
        p = S.shapley(v)
        bootbase.append(b)
        for c in S.COMPONENTS:
            boot[c].append(p[c])
    OUT['pooled']['baseline_crps_ci'] = {
        'lo': float(np.quantile(bootbase, 0.025)),
        'hi': float(np.quantile(bootbase, 0.975))}
    OUT['pooled']['shapley_ci'] = {}
    for c in S.COMPONENTS:
        a = np.array(boot[c])
        OUT['pooled']['shapley_ci'][c] = {
            'lo': float(np.quantile(a, 0.025)), 'hi': float(np.quantile(a, 0.975)),
            'pct_lo': float(np.quantile(a, 0.025)) / tot * 100,
            'pct_hi': float(np.quantile(a, 0.975)) / tot * 100}
        print(f'  {c}: CRPS reduction {phi[c]:7.4f}  95% CI '
              f'[{np.quantile(a,0.025):7.4f}, {np.quantile(a,0.975):7.4f}]')

    # ---- subgroups -------------------------------------------------------
    print('\n== subgroups ==')
    trvals = [r['h_mean_T'] for r in sub
              if r['season'] < min(L.EVAL) and r['appeared']
              and r.get('h_mean_T') is not None]
    tr_med = float(np.median(trvals)) if trvals else 0.0
    OUT['subgroup_split_prior_targets_median_TRAIN_ONLY'] = tr_med
    print(f'  prior-target median from TRAINING seasons only: {tr_med:.3f}')

    def cohort(r, dim):
        if dim == 'position':
            return r['position']
        if dim == 'target_volume':
            v = r.get('h_mean_T')
            return 'unknown' if v is None else ('high' if v >= tr_med else 'low')
        if dim == 'history':
            n = r.get('q_n_prior_app') or 0
            return '<4' if n < 4 else '4-9' if n < 10 else '10-24' if n < 25 else '25+'
        if dim == 'role_change':
            return r['h_role']
        return '?'

    OUT['subgroups'] = {}
    for dim in ('position', 'target_volume', 'history', 'role_change'):
        OUT['subgroups'][dim] = {}
        labs = np.array([cohort(r, dim) for r in ALLR])
        for lab in sorted(set(labs.tolist())):
            m = labs == lab
            if m.sum() < 100:
                continue
            b = float(C[frozenset()][m].mean())
            v = {fs: b - float(C[fs][m].mean()) for fs in SUBSETS}
            p = S.shapley(v)
            t = sum(p.values())
            OUT['subgroups'][dim][lab] = {
                'n': int(m.sum()), 'baseline_crps': b,
                'mean_Y': float(Y[m].mean()), 'sd_Y': float(Y[m].std(ddof=1)),
                'shapley_crps': p,
                'shapley_pct': {k: 100.0 * x / t for k, x in p.items()}}
            print(f'  {dim:<14}{lab:<10} n={int(m.sum()):5d} baseCRPS {b:7.3f} '
                  f'meanY {Y[m].mean():5.1f}  '
                  + '  '.join(f'{k} {100*p[k]/t:5.1f}%' for k in S.COMPONENTS))

    OUT['runtime_s'] = time.time() - t0
    json.dump(OUT, open(f'{HERE}/rc1_results.json', 'w'), indent=1, default=str)
    print(f"\nwrote rc1_results.json  ({OUT['runtime_s']:.0f}s)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
