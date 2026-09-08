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
    ident = bool(np.array_equal(acc['oracle']['D'], acc['control']['D']))
    print(f"  draws bit-identical control vs oracle: {ident}")
    OUT['constant_rate_test'] = {
        'base_rates': L.BASE_P,
        'control': acc['control']['s'], 'oracle': acc['oracle']['s'],
        'candidate': acc['candidate']['s'],
        'oracle_minus_control': d_or, 'candidate_minus_control': d_ca,
        'draws_bit_identical': ident,
        'claim': ('a route rate that is a function of position only cancels '
                  'out of the candidate architecture'),
    }

    # ---- the necessity curve --------------------------------------------
    print('\n== s5: necessity curve -- CRPS vs game-to-game route dispersion ==')
    print(f"  {'CV':>5} {'control':>9} {'oracle':>9} {'cand':>9} "
          f"{'or-ctl':>10} {'95% CI':>22} {'cand-ctl':>10}")
    curve = []
    for cv in L.CV_GRID:
        rows = L.inject_routes([dict(r) for r in base], cv=cv)
        L.attach_history(rows)
        a = {}
        for arm in ('control', 'oracle', 'candidate'):
            Ds, ys, gs, ps = [], [], [], []
            for ev in L.EVAL:
                D, y, g, p = L.run_arm(rows, ev, arm)
                Ds.append(D); ys.append(y); gs += g; ps += p
            D = np.vstack(Ds); y = np.concatenate(ys)
            a[arm] = {'c': crps_matrix(D, y), 's': L.score(D, y),
                      'g': gs, 'pos': ps}
        do = L.clustered_delta(a['oracle']['c'], a['control']['c'], a['control']['g'])
        dc = L.clustered_delta(a['candidate']['c'], a['control']['c'], a['control']['g'])
        # realised dispersion, measured rather than assumed to equal the target
        pv = np.array([r['p_true'] for r in rows if r['season'] in L.EVAL])
        realised = float(pv.std() / pv.mean()) if pv.mean() else 0.0
        per_pos = {}
        pos = np.array(a['control']['pos'])
        for P in L.POSITIONS:
            msk = pos == P
            if msk.sum() < 50:
                continue
            per_pos[P] = {
                'n': int(msk.sum()),
                'control_crps': float(a['control']['c'][msk].mean()),
                'oracle_crps': float(a['oracle']['c'][msk].mean()),
                'oracle_gain': float(a['control']['c'][msk].mean()
                                     - a['oracle']['c'][msk].mean()),
                'candidate_gain': float(a['control']['c'][msk].mean()
                                        - a['candidate']['c'][msk].mean())}
        row = {'cv_target': cv, 'cv_realised_pooled': realised,
               'control_crps': a['control']['s']['crps'],
               'oracle_crps': a['oracle']['s']['crps'],
               'candidate_crps': a['candidate']['s']['crps'],
               'oracle_minus_control': do, 'candidate_minus_control': dc,
               'oracle_gain_pct': 100 * (-do['delta']) / a['control']['s']['crps'],
               'by_position': per_pos}
        curve.append(row)
        print(f"  {cv:5.2f} {a['control']['s']['crps']:9.5f} "
              f"{a['oracle']['s']['crps']:9.5f} {a['candidate']['s']['crps']:9.5f} "
              f"{do['delta']:+10.5f} [{do['lo']:+.5f},{do['hi']:+.5f}] "
              f"{dc['delta']:+10.5f}")
    OUT['necessity_curve'] = curve

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
