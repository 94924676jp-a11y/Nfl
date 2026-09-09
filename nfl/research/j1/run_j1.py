"""J1 walk-forward. Scoring and acceptance fixed in predeclaration_j1.md."""
import collections, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import j1_lib as J

PREREG = '85ff7c9cfe3f5aef2367e584c0835ccba56fa7a9c9a81db9d418200189afbf18'
ARMS = ('A0_control', 'A1_carve_qb_first', 'A2_causal_split',
        'A3_joint_residual')
VEC = ('db', 'tc', 'qb', 'rb')


def invariants(d, tol=1e-6):
    """The five predeclared accounting invariants, per draw."""
    tc_sum = d['qb'] + d['rb'] + d['wr']
    return {
        'components_sum_to_team_carries': float(
            np.mean(np.abs(tc_sum - d['tc']) > tol)),
        'qb_rush_within_team_carries': float(np.mean(d['qb'] > d['tc'] + tol)),
        'any_component_negative': float(np.mean(
            (d['qb'] < -tol) | (d['rb'] < -tol) | (d['wr'] < -tol)
            | (d['tc'] < -tol) | (d['db'] < -tol))),
        'scrambles_within_dropbacks': float(np.mean(d['qb'] > d['db'] + d['tc'])),
        'clipped_draws': float(d.get('clipped', 0)) / len(d['tc']),
    }


def main():
    t0 = time.time()
    rows = J.load()
    OUT = {'artifact': 'J1_RESULTS', 'prereg_sha256': PREREG,
           'label': 'EXPLORATORY -- 2022-2025 are development data. Nothing '
                    'is promoted.',
           'n_team_games': len(rows), 'arms': list(ARMS), 'seasons': {},
           'evaluation_seasons_run': [], 'evaluation_seasons_skipped': []}
    pooled_es = collections.defaultdict(list)
    pooled_crps = collections.defaultdict(lambda: collections.defaultdict(list))
    pooled_inv = collections.defaultdict(lambda: collections.defaultdict(list))
    clusters = []
    for ev in J.EVAL:
        te = [r for r in rows if r['season'] == ev]
        base, lm, hist = J.baselines(rows, ev)
        if not te or len(hist) < 200:
            OUT['evaluation_seasons_skipped'].append(
                {'season': ev, 'cause': 'INSUFFICIENT_HISTORY_OR_NO_TEST_ROWS',
                 'n_test': len(te), 'n_hist': len(hist)})
            print(f'{ev}: SKIPPED', flush=True)
            continue
        OUT['evaluation_seasons_run'].append(ev)
        R, ix = J.residual_table(hist, base, lm)
        pools = J.a2_pools(hist)
        srow = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in te:
            y = np.array([r['team_dropbacks_part'], r['team_carries'],
                          r['qb_rush'], r['rb']], float)
            for arm in ARMS:
                rng = np.random.default_rng(
                    [J.SEED, r['ord'], hash(r['team']) % 9973,
                     hash(arm) % 7919])
                if arm == 'A0_control':
                    d = J.arm_A0(r, base, lm, R, ix, rng)
                elif arm == 'A1_carve_qb_first':
                    d = J.arm_A1(r, base, lm, R, ix, rng)
                elif arm == 'A2_causal_split':
                    d = J.arm_A2(r, base, lm, R, ix, rng, hist=hist,
                                 pools=pools)
                else:
                    d = J.arm_A3(r, base, lm, R, ix, rng)
                X = np.stack([d[k] for k in VEC], axis=1)
                srow[arm]['es'].append(J.energy_score(X, y, rng))
                for j, k in enumerate(VEC):
                    srow[arm][f'crps_{k}'].append(J.crps(d[k], y[j]))
                for iv, v in invariants(d).items():
                    srow[arm][f'inv_{iv}'].append(v)
                # reproduced coupling
                srow[arm]['corr_tc_db'].append(
                    float(np.corrcoef(d['tc'], d['db'])[0, 1])
                    if d['tc'].std() > 0 and d['db'].std() > 0 else 0.0)
            clusters.append(f'{r["team"]}_{r["ord"]}')
        row = {}
        for arm in ARMS:
            row[arm] = {k: float(np.nanmean(v)) for k, v in srow[arm].items()}
            pooled_es[arm].extend(srow[arm]['es'])
            for k in VEC:
                pooled_crps[arm][k].extend(srow[arm][f'crps_{k}'])
            for iv in ('components_sum_to_team_carries',
                       'qb_rush_within_team_carries', 'any_component_negative',
                       'clipped_draws'):
                pooled_inv[arm][iv].extend(srow[arm][f'inv_{iv}'])
        row['n_team_games'] = len(te)
        OUT['seasons'][str(ev)] = row
        print(f'{ev}: n={len(te):4d} ' + '  '.join(
            f'{a.split("_")[0]} ES {row[a]["es"]:.4f}' for a in ARMS),
            flush=True)
    if not OUT['evaluation_seasons_run']:
        raise SystemExit('NO_FOLD_RAN')
    hist_corr = -0.393
    OUT['pooled'] = {a: {'energy_score': float(np.mean(pooled_es[a])),
                         **{f'crps_{k}': float(np.mean(pooled_crps[a][k]))
                            for k in VEC},
                         **{f'inv_{iv}': float(np.mean(v))
                            for iv, v in pooled_inv[a].items()},
                         'mean_corr_tc_db': float(np.mean(
                             [OUT['seasons'][str(e)][a]['corr_tc_db']
                              for e in OUT['evaluation_seasons_run']]))}
                     for a in ARMS}
    for a in ARMS:
        OUT['pooled'][a]['abs_corr_error_vs_historical'] = abs(
            OUT['pooled'][a]['mean_corr_tc_db'] - hist_corr)
    OUT['historical_corr_tc_db'] = hist_corr
    base_es = np.asarray(pooled_es['A0_control'])
    OUT['contrasts'] = {}
    for a in ARMS[1:]:
        d = np.asarray(pooled_es[a]) - base_es
        lo, hi = J.clustered_ci(d, clusters)
        cons = sum(1 for e in OUT['evaluation_seasons_run']
                   if OUT['seasons'][str(e)][a]['es']
                   < OUT['seasons'][str(e)]['A0_control']['es'])
        worst = max((OUT['pooled'][a][f'crps_{k}']
                     / max(OUT['pooled']['A0_control'][f'crps_{k}'], 1e-9) - 1)
                    for k in VEC)
        inv_ok = all(OUT['pooled'][a][f'inv_{iv}']
                     <= OUT['pooled']['A0_control'][f'inv_{iv}'] + 1e-12
                     for iv in ('components_sum_to_team_carries',
                                'qb_rush_within_team_carries',
                                'any_component_negative', 'clipped_draws'))
        OUT['contrasts'][f'{a}_minus_A0'] = {
            'mean_energy_score_diff': float(d.mean()),
            'clustered_ci95': [lo, hi], 'ci_excludes_zero': bool(hi < 0 or lo > 0),
            'folds_better': f'{cons} of {len(OUT["evaluation_seasons_run"])}',
            'worst_marginal_crps_relative_change': float(worst),
            'no_marginal_worse_than_2pct': bool(worst <= 0.02),
            'invariants_no_worse': inv_ok,
            'meets_acceptance_rule': bool(
                d.mean() < 0 and hi < 0 and cons >= 3 and worst <= 0.02
                and inv_ok)}
    OUT['runtime_s'] = round(time.time() - t0, 1)
    json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'j1_results.json'), 'w'), indent=1)
    print('\npooled energy score (lower better):')
    for a in ARMS:
        p = OUT['pooled'][a]
        print(f'  {a:22s} ES {p["energy_score"]:.4f}  corr(tc,db) '
              f'{p["mean_corr_tc_db"]:+.4f}  |err vs -0.393| '
              f'{p["abs_corr_error_vs_historical"]:.4f}')
    print('\ninvariant violation rates (lower better):')
    for a in ARMS:
        p = OUT['pooled'][a]
        print(f'  {a:22s} sum {p["inv_components_sum_to_team_carries"]:.4f}  '
              f'qb>tc {p["inv_qb_rush_within_team_carries"]:.4f}  '
              f'neg {p["inv_any_component_negative"]:.4f}  '
              f'clipped {p["inv_clipped_draws"]:.4f}')
    print('\ncontrasts vs A0 (negative = better):')
    for k, v in OUT['contrasts'].items():
        print(f'  {k}: {v["mean_energy_score_diff"]:+.4f} '
              f'CI [{v["clustered_ci95"][0]:+.4f},{v["clustered_ci95"][1]:+.4f}] '
              f'{v["folds_better"]}  worstCRPS {v["worst_marginal_crps_relative_change"]:+.3f}  '
              f'inv_ok {v["invariants_no_worse"]}  '
              f'RULE {"MET" if v["meets_acceptance_rule"] else "NOT MET"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
