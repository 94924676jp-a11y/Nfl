"""P4E sensitivity: block E carries a scale defect, so its negative result on
the pre-declared ladder does not by itself convict the block.

`g_snap_per_carry` is snap share divided by max(EWMA carry share, 1e-6). The
audit measured its range as 0 to 114,199.9. A ridge on a standardised column
whose upper tail is five orders of magnitude above its body is mostly fitting
one row. This re-runs the block-E rungs with a bounded denominator and a log
transform, so the return can say whether block E fails because snap information
does not help or because I scaled it badly.

The ladder thresholds are the pre-declared ones and are NOT changed. This is a
sensitivity on a defect in my own feature, reported alongside the primary run,
never in place of it.
"""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import run_p4e as R                                            # noqa: E402

RUNGS = {'P4C': None, 'E_E': ['E'], 'E_ABCDE': ['A', 'B', 'C', 'D', 'E']}


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    raw = [r['g_snap_per_carry'] for r in sub if r.get('g_snap_per_carry') is not None]
    for r in sub:
        sp, ew = r.get('g_snap_prior'), r.get('g_sh_ewma')
        r['g_snap_per_carry'] = (float(np.log1p(sp / max(ew, 0.01)))
                                 if (sp is not None and ew is not None) else None)
    fixed = [r['g_snap_per_carry'] for r in sub if r.get('g_snap_per_carry') is not None]
    print(f'g_snap_per_carry  before: min {min(raw):.3f} max {max(raw):.1f}  '
          f'after: min {min(fixed):.3f} max {max(fixed):.3f}')

    crps_rows, clusters = {}, {}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        clusters[ev] = c['cluster']
        crps_rows[ev] = {}
        for name, blocks in RUNGS.items():
            if blocks is None:
                W = c['W_ctrl']
            else:
                fit, pool, _fd = F.fit_centre(sub, ev, blocks, seasons)
                W, _ = F.weights(c, fit, pool, blocks,
                                 np.random.default_rng(CL.SEED + 3034))
            Y, _S = B.counts_from_weights(c, W)
            crps_rows[ev][name] = CL.crps_samples(Y, c['y'])
            del Y, _S, W

    allc = sum((clusters[e] for e in B.EVAL), [])
    base = np.concatenate([crps_rows[e]['P4C'] for e in B.EVAL])
    OUT = {'feature_range_before': {'min': min(raw), 'max': max(raw)},
           'feature_range_after': {'min': min(fixed), 'max': max(fixed)},
           'rungs': {}}
    prim = json.load(open(f'{HERE}/p4e_results.json'))['pooled']
    print(f"\n  {'rung':9s} {'primary':>9s} {'sensitivity':>12s} {'delta vs P4C':>13s} "
          f"{'seasons':>8s}  95% CI")
    for name in RUNGS:
        cat = np.concatenate([crps_rows[e][name] for e in B.EVAL])
        bt = None if name == 'P4C' else CL.block_boot(cat, base, allc)
        wins = sum(1 for e in B.EVAL
                   if crps_rows[e][name].mean() < crps_rows[e]['P4C'].mean())
        OUT['rungs'][name] = {
            'pooled_crps': float(cat.mean()),
            'primary_pooled_crps': prim[name]['pooled_crps'],
            'delta_vs_P4C': float(cat.mean() - base.mean()),
            'seasons_better': wins, 'boot': bt,
            'per_season': {str(e): float(crps_rows[e][name].mean())
                           for e in B.EVAL}}
        ci = '' if bt is None else f"  [{bt['lo']:+.4f}, {bt['hi']:+.4f}]"
        print(f"  {name:9s} {prim[name]['pooled_crps']:9.4f} {cat.mean():12.4f} "
              f"{cat.mean()-base.mean():+13.4f} {wins:6d}/4{ci}")
    OUT['verdict'] = (
        'Block E still fails the pre-declared standard with a well-scaled '
        'feature.' if OUT['rungs']['E_E']['delta_vs_P4C'] >= 0 else
        'Block E changes sign once the scale defect is removed; its result on '
        'the primary ladder was measuring my scaling, not snap information.')
    print(f"\n  {OUT['verdict']}")
    json.dump(OUT, open(f'{HERE}/p4e_sensitivity.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4e_sensitivity.json')


if __name__ == '__main__':
    main()
