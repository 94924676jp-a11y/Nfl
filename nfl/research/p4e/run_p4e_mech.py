"""P4E section 7 / section 14: WHY do low-history backs receive too much?

The ladder says better share features do not fix it -- they make it worse. So
the cause is not the prior's content. This isolates the actual mechanism and
then tests a repair for it, clearly labelled EXPLORATORY because it is not on
the pre-declared ladder.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4c_build as CB                                         # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import run_p4e as R                                            # noqa: E402

BLOCKS_ABC = ['A', 'B', 'C']


def mean_preserving(centre, resid, lo=0.0, hi=1.0, iters=40):
    """Shift each row's residual draws so the CLIPPED weight has mean `centre`.

    P4C builds W = clip(C + eps, 0, 1). Rectification at zero is asymmetric, so
    E[W] > C whenever C is small relative to the spread of eps -- the estimator
    stops being mean-unbiased exactly for the players who have the least
    history. This solves delta_i in
        mean_m clip(C_i + eps_im - delta_i, 0, 1) = C_i
    by bisection. It is monotone decreasing in delta, so bisection is exact to
    machine tolerance and needs no tuning constant. NOTHING is fitted here and
    no outcome is read.
    """
    c = centre.astype(np.float64)[:, None]
    e = resid.astype(np.float64)
    a = np.full((len(centre), 1), -1.0)
    b = np.full((len(centre), 1), 1.0)
    for _ in range(iters):
        d = 0.5 * (a + b)
        m = np.clip(c + e - d, lo, hi).mean(axis=1, keepdims=True)
        too_high = m > c
        a = np.where(too_high, d, a)
        b = np.where(too_high, b, d)
    d = 0.5 * (a + b)
    return np.clip(c + e - d, lo, hi).astype(np.float32), d[:, 0]


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    OUT = {'note': 'section 7 mechanism; the X_ rungs are EXPLORATORY and are '
                   'NOT eligible for promotion under predeclaration_p4e.md'}

    # ---- 1. the rectification diagnosis --------------------------------
    print('== rectification diagnosis: E[W] against its own centre C ==')
    print('   (P4C builds W = clip(C + residual, 0, 1); nothing here is fitted)')
    diag = {}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        Wm = c['W_ctrl'].mean(1)
        pc = np.array([r.get('g_car_career') or 0.0 for r in c['te']])
        d = {}
        for lbl, m in (('<10', pc < 10), ('10-24', (pc >= 10) & (pc < 25)),
                       ('25-49', (pc >= 25) & (pc < 50)),
                       ('50-99', (pc >= 50) & (pc < 100)), ('100+', pc >= 100)):
            if m.sum() == 0:
                continue
            cc = float(c['C_pre'][m].mean()); ww = float(Wm[m].mean())
            d[lbl] = {'n': int(m.sum()), 'centre_C': cc, 'E_W': ww,
                      'inflation_abs': ww - cc,
                      'inflation_pct': 100 * (ww - cc) / max(cc, 1e-9)}
        diag[str(ev)] = d
        if ev == B.EVAL[0]:
            print(f"   {ev}  {'cohort':8s} {'n':>5s} {'centre C':>9s} "
                  f"{'E[W]':>8s} {'inflation':>10s}")
        for lbl, v in d.items():
            print(f"   {ev}  {lbl:8s} {v['n']:5d} {v['centre_C']:9.4f} "
                  f"{v['E_W']:8.4f} {v['inflation_pct']:+9.1f}%")
    OUT['rectification_diagnosis'] = diag

    # ---- 2. exploratory repair -----------------------------------------
    print('\n== EXPLORATORY: mean-preserving rectification ==')
    res = {}
    crps_rows = collections.defaultdict(dict)
    clusters = {}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        clusters[ev] = c['cluster']
        par = c['par']
        pos = [r['position'] for r in c['te']]
        allp = np.concatenate(list(par['add_pool'].values()))
        eps = CB._resample(par['add_pool'], pos, c['n'], CL.M_DRAWS,
                           np.random.default_rng(CL.SEED + 3034), allp)
        systems = {}
        systems['P4C'] = c['W_ctrl']
        Wm, dm = mean_preserving(c['C_pre'], eps)
        systems['X_mpr'] = Wm
        fit, pool, fd = F.fit_centre(sub, ev, BLOCKS_ABC, seasons)
        Wabc, mu = F.weights(c, fit, pool, BLOCKS_ABC,
                             np.random.default_rng(CL.SEED + 3034))
        systems['E_ABC'] = Wabc
        eps2 = CB._resample(pool, pos, c['n'], CL.M_DRAWS,
                            np.random.default_rng(CL.SEED + 3034),
                            np.concatenate(list(pool.values())))
        Wabcm, _ = mean_preserving(mu, eps2)
        systems['X_ABC_mpr'] = Wabcm
        print(f'\n  {ev} n={c["n"]}  mean shift applied to low-history rows: '
              f'{float(dm[np.array([(r.get("g_car_career") or 0) < 25 for r in c["te"]])].mean()):+.5f}')
        pc = np.array([r.get('g_car_career') or 0.0 for r in c['te']])
        for name, W in systems.items():
            Y, S = B.counts_from_weights(c, W)
            sc = CL.score(Y, c['y'], np.random.default_rng(CL.SEED + 31))
            cr = CL.crps_samples(Y, c['y'])
            crps_rows[ev][name] = cr
            pred = Y.mean(1)
            lo = pc < 25
            res.setdefault(name, {})[str(ev)] = {
                'crps': sc['crps'], 'mae': sc['mae'], 'bias': sc['bias'],
                'rpit_chi2': sc['randomised_pit']['chi2'],
                'low_history_bias': float((pred[lo] - c['y'][lo]).mean()),
                'low_history_pred': float(pred[lo].mean()),
                'low_history_real': float(c['y'][lo].mean()),
                'established_bias': float((pred[~lo] - c['y'][~lo]).mean()),
                'joint': R.joint(c, S, Y, pred),
            }
            v = res[name][str(ev)]
            j = v['joint']['RB1-RB2']
            print(f"    {name:11s} CRPS {sc['crps']:.4f}  rPIT {sc['randomised_pit']['chi2']:6.1f}  "
                  f"low-hist bias {v['low_history_bias']:+.3f} "
                  f"(pred {v['low_history_pred']:.3f} vs real {v['low_history_real']:.3f})  "
                  f"estab bias {v['established_bias']:+.3f}  "
                  f"RB1-RB2 sim {j['sim_share_corr_within_teamgame']:+.3f} "
                  f"real {j['realised_share_corr_across_teamgames']:+.3f}")
            del Y, S
    OUT['exploratory'] = res
    allc = sum((clusters[e] for e in B.EVAL), [])
    pooled = {}
    base = np.concatenate([crps_rows[e]['P4C'] for e in B.EVAL])
    print('\n== pooled (EXPLORATORY, not promotable under this pre-declaration) ==')
    for name in ('P4C', 'X_mpr', 'E_ABC', 'X_ABC_mpr'):
        cat = np.concatenate([crps_rows[e][name] for e in B.EVAL])
        bt = None if name == 'P4C' else CL.block_boot(cat, base, allc)
        wins = sum(1 for e in B.EVAL
                   if crps_rows[e][name].mean() < crps_rows[e]['P4C'].mean())
        frac = float((base.mean() - cat.mean())
                     / np.mean([R.SHAP_S[e] for e in B.EVAL]))
        pooled[name] = {'pooled_crps': float(cat.mean()),
                        'delta_vs_P4C': float(cat.mean() - base.mean()),
                        'seasons_better': wins, 'boot': bt,
                        'shapley_fraction_recovered': frac}
        ci = '' if bt is None else f"  95% [{bt['lo']:+.4f}, {bt['hi']:+.4f}]"
        print(f"  {name:11s} pooled {cat.mean():.4f}  delta {cat.mean()-base.mean():+.4f}  "
              f"seasons better {wins}/4  shapley recovered {100*frac:+.2f}%{ci}")
    OUT['exploratory_pooled'] = pooled
    json.dump(OUT, open(f'{HERE}/p4e_mechanism.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4e_mechanism.json')


if __name__ == '__main__':
    main()
