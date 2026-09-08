"""P4F main run. DEVELOPMENT RESEARCH ONLY.

2022-2025 have already exposed the exploratory mean-preserving result, so
nothing computed here can promote anything. Every predictive number below is
labelled as a previously exposed development sample.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4f_common as K                                         # noqa: E402
import p4e_build as B                                          # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import p4f_mpr as M                                            # noqa: E402
from governance import artifact_reference as AR                # noqa: E402
from governance.outcome import State                           # noqa: E402

LABEL = ('previously exposed development sample -- not confirmatory and not '
         'promotion-eligible')


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    # Key renamed from 'status'. The forbidden-identifier scan flagged it,
    # because `weekly_rosters.status` is a banned field and a token scan
    # cannot tell my own output key from a data read. Narrowing the guard
    # to let my code through would be the wrong way round, so the code
    # moves instead of the guard.
    OUT = {'research_phase': 'DEVELOPMENT RESEARCH ONLY',
           'sample_label': LABEL,
           'systems': list(K.SYSTEMS), 'seasons': {}}

    # ---- 5. baseline reproduction, through Rule 006 ---------------------
    print('== baseline reproduction (Rule 006: value read from the artifact) ==')
    repro = {}
    cells, crps_rows, clusters = {}, collections.defaultdict(dict), {}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        cells[ev] = c
        clusters[ev] = c['cluster']
        obs = float(CL.crps_samples(
            B.counts_from_weights(c, c['W_ctrl'])[0], c['y']).mean())
        o = AR.assert_gate(obs, B.RESULTS_PATH,
                           ('carries', str(ev), 'scores', 'C', 'crps'),
                           tolerance=0.0, code='P4F_BASELINE')
        repro[str(ev)] = o.as_dict()
        print(f'  {ev}: {o.state.value:4s} observed {obs:.12f}  '
              f'artifact {o.evidence.get("expected")}  '
              f'sha256 {str(o.evidence.get("sha256"))[:12]}')
        if o.state is not State.PASS:
            print(f'\nSTOP: {o.code} -- {o.detail}')
            sys.exit(2)
    OUT['baseline_reproduction'] = repro
    print('  all four reproduce at tolerance 0.0\n')

    # ---- 6-8. the five systems ------------------------------------------
    for ev in B.EVAL:
        c = cells[ev]
        pc = np.array([r.get('g_car_career') or 0.0 for r in c['te']])
        hb = np.array([K.band(v, K.HIST_BANDS) for v in pc])
        ab = np.array([K.band(float(v), K.APP_BANDS) for v in c['p_app']])
        systems, centres, epss, audit, fitd = K.build_systems(sub, c, ev, seasons)
        print(f'== {ev}  n={c["n"]}  G={c["G"]} ==   {LABEL}')
        print(f'  residual-draw audit: {audit}')
        sres = {'_meta': {'n': c['n'], 'G': c['G'], 'audit': audit,
                          'abc_fit': {k: v for k, v in fitd.items()
                                      if k != 'features'}}}
        for name in K.SYSTEMS:
            W, delta, rep = systems[name]
            Y, S = B.counts_from_weights(c, W)
            sc = CL.score(Y, c['y'], np.random.default_rng(CL.SEED + 31))
            cr = CL.crps_samples(Y, c['y'])
            crps_rows[ev][name] = cr
            pred = Y.mean(1)
            cen = np.asarray(centres[name], np.float64)
            eps = epss['abc'] if name.startswith('ABC') else epss['ctrl']
            pre = M.clipped_expectation(cen, eps)
            post = np.asarray(W, np.float64).mean(1)
            share = {}
            for lbl, _lo, _hi in K.HIST_BANDS:
                m = hb == lbl
                if not m.any():
                    continue
                share[lbl] = {
                    'n': int(m.sum()), 'centre_C': float(cen[m].mean()),
                    'pre_rectification_EW': float(pre[m].mean()),
                    'post_rectification_EW': float(post[m].mean()),
                    'centre_preservation_error': float((post[m] - cen[m]).mean()),
                    'clipping_probability': float(
                        ((np.asarray(W)[m] <= 1e-12) | (np.asarray(W)[m] >= 1 - 1e-12)).mean()),
                    'delta_mean': (None if delta is None
                                   else float(np.nanmean(delta[m]))),
                    'carry_bias': float((pred[m] - c['y'][m]).mean()),
                    'crps': float(cr[m].mean())}
            two = {}
            for hl, _a, _b in K.HIST_BANDS:
                for al, _x, _y in K.APP_BANDS:
                    m = (hb == hl) & (ab == al)
                    if m.sum() < 20:
                        continue
                    two[f'{hl}|{al}'] = {
                        'n': int(m.sum()),
                        'bias': float((pred[m] - c['y'][m]).mean()),
                        'crps': float(cr[m].mean()),
                        'pred': float(pred[m].mean()),
                        'real': float(c['y'][m].mean())}
            sres[name] = {
                'scores': sc, 'thresholds': CL.thresholds(Y, c['y'], K.GRID),
                'share_diagnostics_by_history_band': share,
                'history_x_appearance': two,
                'joint_matched': K.joint_matched(c, S, Y, pred),
                'solver_report': rep,
                'low_history_bias': float(
                    (pred[pc < 25] - c['y'][pc < 25]).mean()),
                'established_bias': float(
                    (pred[pc >= 25] - c['y'][pc >= 25]).mean())}
            j = sres[name]['joint_matched']['RB1-RB2']
            print(f"  {name:9s} CRPS {sc['crps']:.4f}  MAE {sc['mae']:.3f}  "
                  f"rPIT {sc['randomised_pit']['chi2']:6.1f}  "
                  f"lowhist bias {sres[name]['low_history_bias']:+.3f}  "
                  f"RB1-RB2 model r {j.get('model_median_r', float('nan')):+.3f} "
                  f"[{j.get('model_ci95',[float('nan')]*2)[0]:+.3f},"
                  f"{j.get('model_ci95',[float('nan')]*2)[1]:+.3f}] "
                  f"real {j.get('realised_r', float('nan')):+.3f} "
                  f"z {j.get('z', float('nan')):+.2f} "
                  f"{'IN' if j.get('realised_inside_ci95') else 'OUT'}")
            if rep is not None:
                print(f"  {'':9s}   solver {rep['state']}  max|mean-C| "
                      f"{rep['max_abs_centre_error_float64']:.2e}  "
                      f"degenerate {rep['rows_degenerate_solution_set']}  "
                      f"infeasible {rep['rows_infeasible']}")
            del Y, S
        for name in K.SYSTEMS:
            if name != 'P4C':
                sres[name]['boot_vs_P4C'] = CL.block_boot(
                    crps_rows[ev][name], crps_rows[ev]['P4C'], c['cluster'])
        OUT['seasons'][str(ev)] = sres
        json.dump(OUT, open(f'{HERE}/p4f_results.json', 'w'), indent=1)

    # ---- pooled ---------------------------------------------------------
    allc = sum((clusters[e] for e in B.EVAL), [])
    base = np.concatenate([crps_rows[e]['P4C'] for e in B.EVAL])
    pooled = {}
    for name in K.SYSTEMS:
        cat = np.concatenate([crps_rows[e][name] for e in B.EVAL])
        bt = None if name == 'P4C' else CL.block_boot(cat, base, allc)
        pooled[name] = {
            'pooled_crps': float(cat.mean()),
            'per_season_crps': {str(e): float(crps_rows[e][name].mean())
                                for e in B.EVAL},
            'delta_vs_P4C': float(cat.mean() - base.mean()),
            'seasons_better': sum(1 for e in B.EVAL if crps_rows[e][name].mean()
                                  < crps_rows[e]['P4C'].mean()),
            'block_bootstrap': bt,
            'bootstrap_caveat': ('describes sampling variability WITHIN a '
                                 'previously exposed development sample; it is '
                                 'not independent confirmation and no p-value '
                                 'is offered as one')}
    # the mechanism decomposition the confound control exists for
    pooled['_mechanism'] = {
        'MC_ONLY_minus_P4C_is_the_monte_carlo_artifact':
            pooled['MC_ONLY']['delta_vs_P4C'],
        'MPR_ONLY_minus_MC_ONLY_is_the_bias_fix':
            pooled['MPR_ONLY']['pooled_crps'] - pooled['MC_ONLY']['pooled_crps'],
        'MPR_ONLY_minus_P4C_is_both':
            pooled['MPR_ONLY']['delta_vs_P4C']}
    OUT['pooled'] = pooled
    print(f'\n== pooled ==   {LABEL}')
    for name in K.SYSTEMS:
        p = pooled[name]
        bt = p['block_bootstrap']
        ci = '' if bt is None else f"  95% [{bt['lo']:+.4f}, {bt['hi']:+.4f}]"
        print(f"  {name:9s} pooled {p['pooled_crps']:.4f}  "
              f"delta {p['delta_vs_P4C']:+.4f}  "
              f"seasons better {p['seasons_better']}/4{ci}")
    m = pooled['_mechanism']
    print(f"\n  mechanism split:")
    print(f"    Monte-Carlo artifact (MC_ONLY - P4C)      "
          f"{m['MC_ONLY_minus_P4C_is_the_monte_carlo_artifact']:+.4f}")
    print(f"    bias fix          (MPR_ONLY - MC_ONLY)    "
          f"{m['MPR_ONLY_minus_MC_ONLY_is_the_bias_fix']:+.4f}")
    print(f"    both              (MPR_ONLY - P4C)        "
          f"{m['MPR_ONLY_minus_P4C_is_both']:+.4f}")
    json.dump(OUT, open(f'{HERE}/p4f_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4f_results.json')


if __name__ == '__main__':
    main()
