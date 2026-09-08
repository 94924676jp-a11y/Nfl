"""P4F section 10: recompute the allocation oracle decomposition UNDER the
candidate, rather than dividing a CRPS gain by the old P4C component.

That division was P4E debt #4. It answers "how big is this gain against a
number computed for a different allocation", which is not the question. The
question is what allocation error REMAINS once the candidate is in place, and
only a re-run of the 2^3 factorial with the candidate in the baseline corner
answers it.

The construction is P4C-CARRY's, unchanged, and the P4C baseline corner is
asserted against p4cc_results.json through Rule 006 before anything is read
off the new corners.
"""
import itertools, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4f_common as K                                         # noqa: E402
import p4e_build as B                                          # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import p5a_lib as PL                                           # noqa: E402
from governance import artifact_reference as AR                # noqa: E402
from governance.outcome import State                           # noqa: E402

P4CC = os.path.abspath(os.path.join(HERE, '..', 'p4cc'))
P4CC_RESULTS = os.path.join(P4CC, 'p4cc_results.json')
COMPONENTS = ('T', 'S', 'A')
CORNERS = [frozenset(c) for r in range(4)
           for c in itertools.combinations(COMPONENTS, r)]


def cname(s):
    return 'A_baseline' if not s else 'O_' + '_'.join(sorted(s))


def shapley(v):
    n, fact = 3, {0: 1, 1: 1, 2: 2, 3: 6}
    out = {}
    for i in COMPONENTS:
        rest = [c for c in COMPONENTS if c != i]
        tot = 0.0
        for r in range(3):
            for sub in itertools.combinations(rest, r):
                Ss = frozenset(sub)
                w = fact[len(Ss)] * fact[n - len(Ss) - 1] / fact[n]
                tot += w * (v[Ss | {i}] - v[Ss])
        out[i] = tot
    return out


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    OUT = {'note': 'allocation oracle decomposition recomputed under each '
                   'system; closes P4E debt #4',
           'sample_label': K and 'previously exposed development sample -- not '
                                 'confirmatory and not promotion-eligible',
           'seasons': {}}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        systems, centres, epss, audit, _fd = K.build_systems(sub, c, ev, seasons)
        store = c['store']
        gti = np.array([store['index'][(r['team'], r['ord'])] for r in c['te']])[c['starts']]
        T_pred = store['B'][gti]
        Tstar = c['Tstar']
        avail_pred = c['avail']
        mstar = CL.gsum((c['Sstar'] * c['A_star'])[:, None], c['starts'])[:, 0]
        A_pred = c['Ad']
        A_star = c['A_star']
        Sstar = c['Sstar']
        y = c['y']
        res = {}
        for name in K.SYSTEMS:
            W_pred = np.asarray(systems[name][0], np.float32)
            vals = {}
            for cs in CORNERS:
                T = (np.repeat(Tstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                     if 'T' in cs else T_pred)
                AV = (np.repeat(mstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                      if 'T' in cs else avail_pred)
                Wm = (np.repeat(Sstar[:, None], CL.M_DRAWS, 1).astype(np.float32)
                      if 'S' in cs else W_pred)
                Ad = (np.repeat(A_star[:, None], CL.M_DRAWS, 1).astype(bool)
                      if 'A' in cs else A_pred)
                WA = Wm * Ad
                tot = CL.gsum(WA, c['starts'])
                te_ = CL.gexp(tot, c['cg'])
                S = np.divide(WA * CL.gexp(AV, c['cg']), te_,
                              out=np.zeros_like(WA), where=te_ > 1e-12)
                S, _nb = CL.waterfill(S, c['starts'], c['cg'], 1.0)
                draws = (CL.gexp(T, c['cg']) * S).astype(np.float32)
                vals[cname(cs)] = float(PL.crps_samples(draws, y).mean())
                del draws, S, WA
            if name == 'P4C':
                o = AR.assert_gate(
                    vals['A_baseline'], P4CC_RESULTS,
                    (str(ev), 'corners', 'A_baseline', 'crps'),
                    tolerance=1e-9, code='P4F_ORACLE_BASELINE')
                res['_p4cc_gate'] = o.as_dict()
                print(f'  {ev} P4C baseline corner vs p4cc_results.json: '
                      f'{o.state.value} |diff| '
                      f'{o.evidence.get("abs_diff", float("nan")):.2e} '
                      f'sha256 {str(o.evidence.get("sha256"))[:12]}')
                if o.state is not State.PASS:
                    print(f'  STOP: {o.code} -- {o.detail}')
                    sys.exit(2)
            base = vals['A_baseline']
            v = {cs: base - vals[cname(cs)] for cs in CORNERS}
            sh = shapley(v)
            res[name] = {
                'corners_crps': vals,
                'baseline_crps': base,
                'total_reduction': v[frozenset(COMPONENTS)],
                'shapley': sh,
                'shapley_pct_of_total': {
                    k: 100 * val / v[frozenset(COMPONENTS)] for k, val in sh.items()},
                'residual_allocation_ceiling_crps': sh['S'],
                'allocation_only_oracle_gain': v[frozenset(['S'])],
            }
        p4c_S = res['P4C']['shapley']['S']
        for name in K.SYSTEMS:
            r = res[name]
            r['raw_gain_vs_P4C_crps'] = res['P4C']['baseline_crps'] - r['baseline_crps']
            r['old_style_fraction_of_P4C_allocation_shapley'] = (
                r['raw_gain_vs_P4C_crps'] / p4c_S)
            r['allocation_shapley_reduction_vs_P4C'] = p4c_S - r['shapley']['S']
        OUT['seasons'][str(ev)] = res
        print(f'\n== {ev} ==')
        print(f"  {'system':10s} {'baseline':>9s} {'shapS':>8s} {'pctS':>6s} "
              f"{'pctT':>6s} {'pctA':>6s} {'gain':>8s} {'shapS drop':>11s}")
        for name in K.SYSTEMS:
            r = res[name]
            print(f"  {name:10s} {r['baseline_crps']:9.4f} "
                  f"{r['shapley']['S']:8.4f} "
                  f"{r['shapley_pct_of_total']['S']:5.1f}% "
                  f"{r['shapley_pct_of_total']['T']:5.1f}% "
                  f"{r['shapley_pct_of_total']['A']:5.1f}% "
                  f"{r['raw_gain_vs_P4C_crps']:+8.4f} "
                  f"{r['allocation_shapley_reduction_vs_P4C']:+11.4f}")
        json.dump(OUT, open(f'{HERE}/p4f_oracle.json', 'w'), indent=1)

    pooled = {}
    for name in K.SYSTEMS:
        pooled[name] = {
            'mean_baseline_crps': float(np.mean(
                [OUT['seasons'][str(e)][name]['baseline_crps'] for e in B.EVAL])),
            'mean_allocation_shapley': float(np.mean(
                [OUT['seasons'][str(e)][name]['shapley']['S'] for e in B.EVAL])),
            'mean_raw_gain_vs_P4C': float(np.mean(
                [OUT['seasons'][str(e)][name]['raw_gain_vs_P4C_crps'] for e in B.EVAL])),
        }
        p = pooled[name]
        p['residual_allocation_ceiling_pct_of_P4C'] = 100 * p['mean_allocation_shapley'] / pooled['P4C']['mean_allocation_shapley']
    OUT['pooled'] = pooled
    OUT['interpretation'] = (
        'The recomputed allocation Shapley component is the allocation error '
        'that REMAINS under each system. It is reported alongside the raw gain '
        'and is NOT used to define a promotion threshold: P4F has no promotion '
        'decision, and the 5% rule is neither applied nor relaxed here.')
    print('\n== pooled ==')
    for name in K.SYSTEMS:
        p = pooled[name]
        print(f"  {name:10s} mean baseline {p['mean_baseline_crps']:.4f}  "
              f"mean allocation Shapley {p['mean_allocation_shapley']:.4f}  "
              f"({p['residual_allocation_ceiling_pct_of_P4C']:5.1f}% of P4C's)  "
              f"raw gain {p['mean_raw_gain_vs_P4C']:+.4f}")
    json.dump(OUT, open(f'{HERE}/p4f_oracle.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4f_oracle.json')


if __name__ == '__main__':
    main()
