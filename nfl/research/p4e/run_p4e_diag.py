"""P4E items 3 and 5: baseline reproduction, then the low-history diagnosis."""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p5a_lib as PL                                           # noqa: E402
import p4c_lib as CL                                           # noqa: E402

OUT = {}


def main():
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)

    # ---- 3. BASELINE REPRODUCTION, a hard gate -------------------------
    print('== baseline reproduction (P4C system C) ==')
    print(f'  control artifact {B.RESULTS_PATH}')
    print(f'  sha256           {B.PUBLISHED_SHA256}')
    cells, repro = {}, {}
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        cells[ev] = c
        cnt, _S = B.counts_from_weights(c, c['W_ctrl'])
        # P4C's OWN scorer, because the control must be reproduced with the
        # control's instrument. (p5a_lib.crps_samples is the same identity at a
        # different chunk size; it was tested and gives identical values here,
        # so chunking is not a live risk -- but the control's own scorer is
        # still the right one to use.)
        crps = float(CL.crps_samples(cnt, c['y']).mean())
        d = abs(crps - B.PUBLISHED[ev])
        repro[ev] = {'p4e': crps, 'published': B.PUBLISHED[ev], 'abs_diff': d}
        print(f'  {ev}: P4E {crps:.12f}  published {B.PUBLISHED[ev]:.12f}  '
              f'|diff| {d:.2e}')
    OUT['baseline_reproduction'] = {
        'source_artifact': B.RESULTS_PATH, 'sha256': B.PUBLISHED_SHA256,
        'per_season': repro}
    worst = max(v['abs_diff'] for v in repro.values())
    if worst > 1e-9:
        print(f'\nSTOP: baseline does not reproduce (worst {worst:.2e})')
        sys.exit(2)
    print(f'  reproduces exactly, worst |diff| {worst:.2e}\n')

    # ---- 5. LOW-HISTORY DIAGNOSIS --------------------------------------
    print('== low-history diagnosis ==')
    diag = {}
    allrows = []
    for ev in B.EVAL:
        c = cells[ev]
        cnt, S = B.counts_from_weights(c, c['W_ctrl'])
        pred = cnt.mean(axis=1)
        Wm = c['W_ctrl'].mean(axis=1)
        for i, r in enumerate(c['te']):
            allrows.append({
                'ev': ev, 'r': r, 'pred': float(pred[i]),
                'real': float(c['y'][i]), 'W': float(Wm[i]),
                'C_pre': float(c['C_pre'][i]), 'p_app': float(c['p_app'][i]),
                'S_share': float(S[i].mean()), 'Sstar': float(c['Sstar'][i]),
                'appeared': float(c['A_star'][i]),
                'prior_car': float(r.get('g_car_career') or 0.0),
                'n_games': int(r.get('g_n_games') or 0),
                'rank': r.get('g_prev_rank'),
                'absent_run': int(r.get('g_absent_run') or 0),
                'sh_ewma': r.get('g_sh_ewma'),
            })
    lo = [x for x in allrows if x['prior_car'] < 25]
    hi = [x for x in allrows if x['prior_car'] >= 25]
    print(f'  <25 prior carries: n={len(lo)}  predicted '
          f'{np.mean([x["pred"] for x in lo]):.3f} vs realised '
          f'{np.mean([x["real"] for x in lo]):.3f}')
    print(f'  >=25 prior carries: n={len(hi)} predicted '
          f'{np.mean([x["pred"] for x in hi]):.3f} vs realised '
          f'{np.mean([x["real"] for x in hi]):.3f}')

    # where does the mass come from? decompose the weight
    print('\n  the weight itself, before reconciliation:')
    for lbl, g in (('<25 prior carries', lo), ('>=25', hi)):
        print(f'    {lbl}: mean C_pre {np.mean([x["C_pre"] for x in g]):.4f}  '
              f'mean W {np.mean([x["W"] for x in g]):.4f}  '
              f'mean p_app {np.mean([x["p_app"] for x in g]):.4f}  '
              f'mean allocated share {np.mean([x["S_share"] for x in g]):.4f}  '
              f'mean realised share {np.mean([x["Sstar"] for x in g]):.4f}')

    # what is the fallback prior doing?
    nohist = [x for x in allrows if x['sh_ewma'] is None or x['n_games'] == 0]
    fallback = [x for x in allrows if x['prior_car'] == 0]
    print(f'\n  rows with ZERO prior carries: n={len(fallback)}  '
          f'mean C_pre {np.mean([x["C_pre"] for x in fallback]):.4f}  '
          f'realised share {np.mean([x["Sstar"] for x in fallback]):.4f}  '
          f'predicted carries {np.mean([x["pred"] for x in fallback]):.3f}  '
          f'realised {np.mean([x["real"] for x in fallback]):.3f}')

    # ---- the sub-populations the directive names ------------------------
    def bucket(x):
        r = x['r']
        if x['prior_car'] >= 25:
            return 'established'
        if x['n_games'] == 0:
            return 'first_history'
        if x['appeared'] == 0 and x['real'] == 0:
            return 'fringe_nonappearance'
        if x['absent_run'] >= 2:
            return 'returning_from_absence'
        if x['prior_car'] < 25 and x['n_games'] >= 8:
            return 'veteran_low_recent_usage'
        if x['real'] >= 5:
            return 'true_emerging'
        return 'low_history_other'
    bk = collections.defaultdict(list)
    for x in allrows:
        bk[bucket(x)].append(x)
    print('\n  sub-populations of the low-history cohort '
          '(bucket assignment uses the outcome ONLY to LABEL, never to model):')
    print(f"    {'bucket':26s} {'n':>6s} {'C_pre':>7s} {'p_app':>6s} "
          f"{'pred':>6s} {'real':>6s} {'bias':>7s} {'S_alloc':>8s} {'S_real':>7s}")
    sp = {}
    for k, g in sorted(bk.items(), key=lambda kv: -len(kv[1])):
        sp[k] = {'n': len(g),
                 'C_pre': float(np.mean([x['C_pre'] for x in g])),
                 'p_app': float(np.mean([x['p_app'] for x in g])),
                 'pred': float(np.mean([x['pred'] for x in g])),
                 'real': float(np.mean([x['real'] for x in g])),
                 'S_alloc': float(np.mean([x['S_share'] for x in g])),
                 'S_real': float(np.mean([x['Sstar'] for x in g]))}
        v = sp[k]
        print(f"    {k:26s} {v['n']:6d} {v['C_pre']:7.4f} {v['p_app']:6.3f} "
              f"{v['pred']:6.2f} {v['real']:6.2f} {v['pred']-v['real']:+7.2f} "
              f"{v['S_alloc']:8.4f} {v['S_real']:7.4f}")
    diag['sub_populations'] = sp

    # ---- is the prior too generous, or is it the reconciliation? --------
    print('\n  where the surplus comes from -- team-game mass accounting:')
    for ev in B.EVAL[:1]:
        c = cells[ev]
        cnt, S = B.counts_from_weights(c, c['W_ctrl'])
        lo_m = np.array([1.0 if (r.get('g_car_career') or 0) < 25 else 0.0
                         for r in c['te']])
        alloc_lo = float((S.mean(axis=1) * lo_m).sum() / len(c['starts']))
        alloc_hi = float((S.mean(axis=1) * (1 - lo_m)).sum() / len(c['starts']))
        real_lo = float((c['Sstar'] * c['A_star'] * lo_m).sum() / len(c['starts']))
        real_hi = float((c['Sstar'] * c['A_star'] * (1 - lo_m)).sum()
                        / len(c['starts']))
        print(f'    {ev}: allocated share per team-game  low-history '
              f'{alloc_lo:.4f} vs realised {real_lo:.4f}; established '
              f'{alloc_hi:.4f} vs realised {real_hi:.4f}')
        diag['mass_accounting_2022'] = {
            'alloc_low': alloc_lo, 'real_low': real_lo,
            'alloc_established': alloc_hi, 'real_established': real_hi}
    OUT['low_history'] = diag
    json.dump(OUT, open(f'{HERE}/p4e_diag.json', 'w'), indent=1)
    print('\nwrote p4e_diag.json')


if __name__ == '__main__':
    main()
