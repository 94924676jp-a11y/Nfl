"""RC2 diagnosis: WHERE do the receiving baseline's bias and over-coverage come from?

RC1 measured bias +2.18 yards and coverage 0.650/0.883/0.943/0.969 against
nominal 0.50/0.80/0.90/0.95. This locates the mechanism BEFORE any repair
family is predeclared, because section 2.3 requires repairs to be supported by
diagnosis rather than chosen by interval squeezing.

Diagnosis inspects the BASELINE's own behaviour. It is not a repair result, and
no repair has been run or scored at this point.
"""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'rc1'))
import rc1_lib as L                                            # noqa: E402
import rc1_sim as S                                            # noqa: E402


def main():
    rows, sub = L.load()
    L.attach_prior(sub)
    OUT = {'purpose': 'locate the mechanism of bias and over-coverage',
           'not_a_repair_result': True, 'by_season': {}}

    allrows, allY, allD = [], [], []
    comp = {'T': ([], []), 'R': ([], []), 'V': ([], [])}
    for ev in L.EVAL:
        rs = [r for r in sub if L.eligible(r, ev)]
        y = np.array([r['Y'] for r in rs], float)
        D = S.simulate(rs, ev, sub)
        allrows += rs
        allY.append(y)
        allD.append(D)
        # component marginals: simulate each primitive alone
        pT, pV, prate = S.pools(sub, ev)
        for r in rs:
            w = r['h_n'] / (r['h_n'] + L.K_SHRINK)
            own = np.asarray(r['h_T'], float)
            pool = pT.get(r['position'], np.array([0.0]))
            mT = w * (own.mean() if len(own) else 0.0) + (1 - w) * pool.mean()
            comp['T'][0].append(mT); comp['T'][1].append(r['T'])
            own_rate = (r['h_rec'] / r['h_tgt']) if r['h_tgt'] > 0 else None
            c = (w * own_rate + (1 - w) * prate.get(r['position'], 0.0)
                 if own_rate is not None else prate.get(r['position'], 0.0))
            comp['R'][0].append(mT * c); comp['R'][1].append(r['R'])
            ov = np.asarray(r.get('h_V_flat') or [], float)
            pv = pV.get(r['position'], np.array([0.0]))
            mV = w * (ov.mean() if len(ov) else pv.mean()) + (1 - w) * pv.mean()
            comp['V'][0].append(mV)
            comp['V'][1].append((r['Y'] / r['R']) if r['R'] > 0 else np.nan)

    Y = np.concatenate(allY)
    D = np.concatenate(allD)
    P = D.mean(1)

    print('== 1. mean-location bias, decomposed by component ==')
    OUT['component_bias'] = {}
    for k, (pred, act) in comp.items():
        p = np.array(pred, float); a = np.array(act, float)
        m = ~np.isnan(a)
        OUT['component_bias'][k] = {
            'mean_pred': float(p[m].mean()), 'mean_actual': float(a[m].mean()),
            'bias': float((p[m] - a[m]).mean()),
            'rel_bias_pct': float(100 * (p[m] - a[m]).mean() / a[m].mean()),
            'n': int(m.sum())}
        b = OUT['component_bias'][k]
        print(f"   {k}: pred {b['mean_pred']:8.4f}  actual {b['mean_actual']:8.4f}  "
              f"bias {b['bias']:+8.4f}  ({b['rel_bias_pct']:+6.2f}%)  n={b['n']}")
    OUT['Y_bias'] = float((P - Y).mean())
    print(f"   Y: pred {P.mean():8.4f}  actual {Y.mean():8.4f}  "
          f"bias {(P-Y).mean():+8.4f}")

    print('\n== 2. dispersion: is the forecast wider than the outcome? ==')
    within = float(D.std(1).mean())          # mean within-row predictive SD
    between = float(P.std(ddof=1))           # spread of the conditional means
    tot_pred = float(np.sqrt(within ** 2 + between ** 2))
    OUT['dispersion'] = {
        'mean_within_row_sd': within, 'between_row_sd_of_means': between,
        'implied_total_pred_sd': tot_pred, 'actual_sd': float(Y.std(ddof=1)),
        'ratio_total': float(tot_pred / Y.std(ddof=1))}
    print(f"   within-row predictive SD (mean) {within:8.4f}")
    print(f"   between-row SD of means         {between:8.4f}")
    print(f"   implied total predictive SD     {tot_pred:8.4f}")
    print(f"   actual SD of Y                  {Y.std(ddof=1):8.4f}")
    print(f"   ratio total/actual              {tot_pred/Y.std(ddof=1):8.4f}")
    resid_sd = float((Y - P).std(ddof=1))
    OUT['dispersion']['residual_sd'] = resid_sd
    OUT['dispersion']['within_over_residual'] = within / resid_sd
    print(f"   residual SD (Y - pred mean)     {resid_sd:8.4f}")
    print(f"   within-row SD / residual SD     {within/resid_sd:8.4f}   "
          f"(>1 means the intervals are wider than the errors)")

    print('\n== 3. the pool-mixture hypothesis ==')
    # w = h_n/(h_n+K). Low-history rows lean on the POSITION POOL, which spans
    # every player at that position -- so a pool draw carries BETWEEN-PLAYER
    # variance into a WITHIN-PLAYER forecast.
    ws = np.array([r['h_n'] / (r['h_n'] + L.K_SHRINK) for r in allrows])
    OUT['pool_weight'] = {'mean_w_own': float(ws.mean()),
                          'mean_pool_weight': float((1 - ws).mean()),
                          'rows_with_pool_weight_gt_0.2': int((1 - ws > 0.2).sum())}
    print(f"   mean weight on the player's own history {ws.mean():.4f}")
    print(f"   mean weight on the POSITION POOL        {(1-ws).mean():.4f}")
    for lo, hi in ((0.0, 0.1), (0.1, 0.2), (0.2, 0.4), (0.4, 1.01)):
        m = ((1 - ws) >= lo) & ((1 - ws) < hi)
        if m.sum() < 50:
            continue
        cov = float(((Y[m] >= np.quantile(D[m], 0.25, axis=1))
                     & (Y[m] <= np.quantile(D[m], 0.75, axis=1))).mean())
        print(f"     pool weight [{lo:.1f},{hi:.1f}): n={int(m.sum()):5d}  "
              f"bias {float((P[m]-Y[m]).mean()):+7.3f}  "
              f"nominal-50% coverage {cov:.3f}  "
              f"within-SD {float(D[m].std(1).mean()):6.2f}")
        OUT.setdefault('by_pool_weight', {})[f'{lo}-{hi}'] = {
            'n': int(m.sum()), 'bias': float((P[m] - Y[m]).mean()),
            'cover50': cov, 'within_sd': float(D[m].std(1).mean())}

    print('\n== 4. zero-target / zero-catch mixture ==')
    T = np.array([r['T'] for r in allrows]); R = np.array([r['R'] for r in allrows])
    pz_actual = float((Y == 0).mean())
    pz_pred = float((D == 0).mean())
    OUT['zero_mass'] = {'actual_P_Y0': pz_actual, 'predicted_P_Y0': pz_pred,
                        'actual_P_T0': float((T == 0).mean()),
                        'actual_P_R0': float((R == 0).mean())}
    print(f"   P(Y = 0) actual {pz_actual:.4f}   predicted {pz_pred:.4f}   "
          f"{'UNDER' if pz_pred < pz_actual else 'OVER'}-predicted")
    print(f"   P(T = 0) actual {float((T==0).mean()):.4f}  "
          f"P(R = 0) actual {float((R==0).mean()):.4f}")

    print('\n== 5. by position and volume ==')
    OUT['by_group'] = {}
    for dim, fn in (('position', lambda r: r['position']),
                    ('volume', lambda r: 'high' if (r.get('h_mean_T') or 0) >= 2.4
                     else 'low')):
        labs = np.array([fn(r) for r in allrows])
        for lab in sorted(set(labs.tolist())):
            m = labs == lab
            cov = {}
            for lvl in (50, 90):
                a = (100 - lvl) / 200
                cov[lvl] = float(((Y[m] >= np.quantile(D[m], a, axis=1))
                                  & (Y[m] <= np.quantile(D[m], 1 - a, axis=1))).mean())
            OUT['by_group'][f'{dim}:{lab}'] = {
                'n': int(m.sum()), 'bias': float((P[m] - Y[m]).mean()),
                'cover50': cov[50], 'cover90': cov[90],
                'within_sd': float(D[m].std(1).mean()),
                'residual_sd': float((Y[m] - P[m]).std(ddof=1))}
            g = OUT['by_group'][f'{dim}:{lab}']
            print(f"   {dim:<9}{lab:<6} n={g['n']:5d}  bias {g['bias']:+7.3f}  "
                  f"cov50 {g['cover50']:.3f}  cov90 {g['cover90']:.3f}  "
                  f"withinSD {g['within_sd']:6.2f}  residSD {g['residual_sd']:6.2f}  "
                  f"ratio {g['within_sd']/g['residual_sd']:.3f}")

    json.dump(OUT, open(f'{HERE}/rc2_diagnosis.json', 'w'), indent=1)
    print('\nwrote rc2_diagnosis.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
