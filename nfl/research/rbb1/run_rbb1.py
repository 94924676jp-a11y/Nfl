"""ROUTE-BB1 runner. EXPLORATORY. Nothing promoted, no production model touched."""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rbb1_lib as L                                              # noqa: E402
from rc1_lib import crps_matrix                                   # noqa: E402

PREREG = '8d7383bf7f2a7a909f501d9395abf365becb05cdd9d3f243287aa3daa0bc5512'


def main():
    OUT = {'prereg_sha256': PREREG,
           'ftn_sample_sha256':
               '56fc32e21cb130c1e14a8b3817f0c43491b310e69cfd4663b5bbd5d973ccffa4',
           'ftn_sample_used': False,
           'label': 'EXPLORATORY build-vs-buy. No FTN observation entered any '
                    'input, label, threshold or selection decision.'}
    base = L.load()
    print(f'panel: {len(base)} WR/TE/RB player-games with pass_snaps > 0')

    # ---- the predeclared algebraic claim, tested first -------------------
    print('\n== s3: does a POSITION-CONSTANT route rate change anything? ==')
    rows = L.inject_routes([dict(r) for r in base], cv=0.0)
    L.attach_history(rows)
    acc = {}
    for arm in ('control', 'oracle', 'candidate'):
        Ds, ys, gs, ps = [], [], [], []
        for ev in L.EVAL:
            D, y, g, p = L.run_arm(rows, ev, arm)
            Ds.append(D); ys.append(y); gs += g; ps += p
        D = np.vstack(Ds); y = np.concatenate(ys)
        acc[arm] = {'D': D, 'y': y, 'g': gs, 'pos': ps,
                    'c': crps_matrix(D, y), 's': L.score(D, y)}
        print(f"  {arm:10s} CRPS {acc[arm]['s']['crps']:.6f}  "
              f"MAE {acc[arm]['s']['mae']:.4f}  n={acc[arm]['s']['n']}")
    d_or = L.clustered_delta(acc['oracle']['c'], acc['control']['c'],
                             acc['control']['g'])
    d_ca = L.clustered_delta(acc['candidate']['c'], acc['control']['c'],
                             acc['control']['g'])
    print(f"  oracle - control    {d_or['delta']:+.6f} "
          f"[{d_or['lo']:+.6f}, {d_or['hi']:+.6f}]")
    print(f"  candidate - control {d_ca['delta']:+.6f} "
          f"[{d_ca['lo']:+.6f}, {d_ca['hi']:+.6f}]")
    sd = float(acc['control']['D'].std(1).mean())
    print(f"  per-row draw SD {sd:.4f} (0.0 would mean point masses again)")
    assert sd > 0.1, 'DISPERSION DEFECT: draws are point masses'
    assert abs(acc['control']['s']['crps']
               - acc['control']['s']['mae']) > 1e-3, \
        'CRPS equals MAE: the draws carry no spread'
    mudiff = float(np.abs(acc['oracle']['D'].mean(1)
                          - acc['control']['D'].mean(1)).mean())
    print(f"  mean |point-prediction difference| control vs oracle: {mudiff:.4f}")
    OUT['constant_rate_test'] = {
        'base_rates': L.BASE_P,
        'control': acc['control']['s'], 'oracle': acc['oracle']['s'],
        'candidate': acc['candidate']['s'],
        'oracle_minus_control': d_or, 'candidate_minus_control': d_ca,
        'per_row_draw_sd': sd,
        'mean_abs_point_prediction_difference': mudiff,
        'claim': ('a route rate that is a function of position only cancels '
                  'out of the candidate architecture'),
    }

    # ---- the necessity curve, REDESIGNED (see addendum s3) ---------------
    print('\n== s5: necessity curve -- what would route knowledge be WORTH? ==')
    print('   rho = fraction of the control architecture\'s residual error that')
    print('   perfect route knowledge would explain.\n')
    print(f"  {'rho':>5} {'ctl':>8} {'oracle':>8} {'gain':>8} {'gain%':>7} "
          f"{'95% CI':>22} {'viol%':>6} {'constr':>8} {'c-gain%':>8}")
    ctlD, ctly, ctlg, ctlpos = [], [], [], []
    for ev in L.EVAL:
        D, y, g, ps = L.run_arm(rows, ev, 'control')
        ctlD.append(D); ctly.append(y); ctlg += g; ctlpos += ps
    CD = np.vstack(ctlD); CY = np.concatenate(ctly)
    CC = crps_matrix(CD, CY); base_crps = float(CC.mean())
    curve = []
    for rho in L.RHO_GRID:
        Us, Cs, Ys, Gs, Ps = [], [], [], [], []
        tv = tn = 0; exc = []
        for ev in L.EVAL:
            Du, Dc, y, g, ps, v, n, ex = L.run_rho(rows, ev, rho)
            Us.append(Du); Cs.append(Dc); Ys.append(y); Gs += g; Ps += ps
            tv += v; tn += n; exc.append(ex)
        DU = np.vstack(Us); DC = np.vstack(Cs); Y = np.concatenate(Ys)
        cu = crps_matrix(DU, Y); cc = crps_matrix(DC, Y)
        du = L.clustered_delta(cu, CC, ctlg)
        dc = L.clustered_delta(cc, CC, ctlg)
        pos = np.array(Ps)
        per_pos = {}
        for P in L.POSITIONS:
            msk = pos == P
            if msk.sum() < 50:
                continue
            per_pos[P] = {'n': int(msk.sum()),
                          'control_crps': float(CC[msk].mean()),
                          'oracle_crps': float(cu[msk].mean()),
                          'gain': float(CC[msk].mean() - cu[msk].mean()),
                          'gain_pct': float(100 * (CC[msk].mean()
                                                   - cu[msk].mean())
                                            / CC[msk].mean())}
        row = {'rho': rho, 'control_crps': base_crps,
               'oracle_unconstrained_crps': float(cu.mean()),
               'oracle_constrained_crps': float(cc.mean()),
               'gain': -du['delta'], 'gain_pct': 100 * (-du['delta']) / base_crps,
               'gain_ci': du,
               'constrained_gain': -dc['delta'],
               'constrained_gain_pct': 100 * (-dc['delta']) / base_crps,
               'constrained_gain_ci': dc,
               'accounting_violations': tv, 'n': tn,
               'violation_pct': 100 * tv / max(tn, 1),
               'mean_excess_routes': float(np.mean(exc)),
               'by_position': per_pos}
        curve.append(row)
        print(f"  {rho:5.2f} {base_crps:8.5f} {cu.mean():8.5f} "
              f"{-du['delta']:+8.5f} {100*(-du['delta'])/base_crps:6.2f}% "
              f"[{-du['hi']:+.5f},{-du['lo']:+.5f}] "
              f"{100*tv/max(tn,1):5.1f}% {cc.mean():8.5f} "
              f"{100*(-dc['delta'])/base_crps:7.2f}%")
    OUT['necessity_curve'] = {
        'design': ('rho is the fraction of the CONTROL residual that perfect '
                   'route knowledge explains. Redesigned after the first '
                   'design was found not to measure information value; see '
                   'addendum_rbb1_defects.md.'),
        'control_crps': base_crps, 'rows': curve}

    # ---- accounting ------------------------------------------------------
    print('\n== s7: accounting ==')
    rows = L.inject_routes([dict(r) for r in base], cv=0.20)
    bad_neg = sum(1 for r in rows if r['routes_true'] < 0)
    bad_gt = sum(1 for r in rows if r['routes_true'] > r['pass_snaps'] + 1e-9)
    clipped = sum(1 for r in rows if r['p_true'] >= 1.0 - 1e-12)
    OUT['accounting'] = {
        'n_rows': len(rows), 'routes_negative': bad_neg,
        'routes_exceeding_pass_snaps': bad_gt,
        'rate_clipped_at_1': clipped,
        'note': ('routes <= pass_snaps holds by construction because routes '
                 'are pass_snaps x p with p <= 1. Clipping at p = 1 is '
                 'COUNTED and reported rather than hidden.')}
    print(f"  rows {len(rows)}  routes<0 {bad_neg}  routes>pass_snaps {bad_gt}"
          f"  p clipped at 1: {clipped}")

    json.dump(OUT, open(f'{HERE}/rbb1_results.json', 'w'), indent=1,
              default=str)
    print('\nwrote rbb1_results.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
