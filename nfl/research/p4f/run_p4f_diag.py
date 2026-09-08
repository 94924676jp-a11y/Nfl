"""P4F sections 7 and 8: does the correction fix the mechanical inflation
WITHOUT flattening genuine emerging backs, and where does appearance still
dominate?

P4E established that the low-history cohort is not one population: fringe
non-appearers are over-predicted and true emerging backs are under-predicted by
much more. A correction that improves the band average by pushing both toward
the middle is a worse answer than the band average makes it look, so the
sub-populations are carried through every system rather than summarised away.

The bucket labels use the outcome to LABEL ONLY. Nothing here models it.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4f_common as K                                         # noqa: E402
import p4e_build as B                                          # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import p4f_mpr as M                                            # noqa: E402


def bucket(r, appeared, real, prior_car):
    if prior_car >= 25:
        return 'established'
    if (r.get('g_n_games') or 0) == 0:
        return 'first_history'
    if appeared == 0 and real == 0:
        return 'fringe_nonappearance'
    if (r.get('g_absent_run') or 0) >= 2:
        return 'returning_from_absence'
    if (r.get('g_n_games') or 0) >= 8:
        return 'veteran_low_recent_usage'
    if real >= 5:
        return 'true_emerging'
    return 'low_history_other'


def main():
    t0 = time.time()
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})
    acc = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {'n': 0, 'pred': 0.0, 'real': 0.0, 'crps': 0.0, 'C': 0.0,
                 'pre': 0.0, 'post': 0.0, 'delta': [], 'clip': 0.0}))
    two = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {'n': 0, 'pred': 0.0, 'real': 0.0, 'crps': 0.0}))
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        systems, centres, epss, _a, _f = K.build_systems(sub, c, ev, seasons)
        pc = np.array([r.get('g_car_career') or 0.0 for r in c['te']])
        bk = np.array([bucket(r, c['A_star'][i], c['y'][i], pc[i])
                       for i, r in enumerate(c['te'])])
        ab = np.array([K.band(float(v), K.APP_BANDS) for v in c['p_app']])
        hb = np.array([K.band(v, K.HIST_BANDS) for v in pc])
        for name in K.SYSTEMS:
            W, delta, _rep = systems[name]
            Y, _S = B.counts_from_weights(c, W)
            cr = CL.crps_samples(Y, c['y'])
            pred = Y.mean(1)
            cen = np.asarray(centres[name], np.float64)
            eps = epss['abc'] if name.startswith('ABC') else epss['ctrl']
            pre = M.clipped_expectation(cen, eps)
            post = np.asarray(W, np.float64).mean(1)
            Wa = np.asarray(W, np.float64)
            clip = ((Wa <= 1e-12) | (Wa >= 1 - 1e-12)).mean(1)
            for lbl in set(bk):
                m = bk == lbl
                a = acc[name][lbl]
                a['n'] += int(m.sum())
                a['pred'] += float(pred[m].sum()); a['real'] += float(c['y'][m].sum())
                a['crps'] += float(cr[m].sum()); a['C'] += float(cen[m].sum())
                a['pre'] += float(pre[m].sum()); a['post'] += float(post[m].sum())
                a['clip'] += float(clip[m].sum())
                if delta is not None:
                    a['delta'].append(delta[m][np.isfinite(delta[m])])
            for hl in set(hb):
                for al in set(ab):
                    m = (hb == hl) & (ab == al)
                    if not m.any():
                        continue
                    t = two[name][f'{hl} | {al}']
                    t['n'] += int(m.sum())
                    t['pred'] += float(pred[m].sum())
                    t['real'] += float(c['y'][m].sum())
                    t['crps'] += float(cr[m].sum())
            del Y, _S

    OUT = {'sample_label': 'previously exposed development sample -- not '
                           'confirmatory and not promotion-eligible',
           'sub_populations': {}, 'history_x_appearance': {}}
    order = ['established', 'fringe_nonappearance', 'veteran_low_recent_usage',
             'low_history_other', 'returning_from_absence', 'true_emerging',
             'first_history']
    print('== sub-populations (outcome used to LABEL only) ==')
    print(f"  {'bucket':26s} {'n':>5s} " +
          ' '.join(f'{s:>10s}' for s in K.SYSTEMS))
    for metric, fmt in (('bias', '{:+10.3f}'), ('crps', '{:10.4f}')):
        print(f'  --- {metric} ---')
        for lbl in order:
            if acc['P4C'][lbl]['n'] == 0:
                continue
            row = []
            for name in K.SYSTEMS:
                a = acc[name][lbl]
                v = ((a['pred'] - a['real']) / a['n'] if metric == 'bias'
                     else a['crps'] / a['n'])
                row.append(fmt.format(v))
            print(f"  {lbl:26s} {acc['P4C'][lbl]['n']:5d} " + ' '.join(row))
    for name in K.SYSTEMS:
        OUT['sub_populations'][name] = {}
        for lbl, a in acc[name].items():
            d = np.concatenate(a['delta']) if a['delta'] else None
            OUT['sub_populations'][name][lbl] = {
                'n': a['n'], 'pred': a['pred'] / a['n'], 'real': a['real'] / a['n'],
                'bias': (a['pred'] - a['real']) / a['n'], 'crps': a['crps'] / a['n'],
                'centre_C': a['C'] / a['n'],
                'pre_rectification_EW': a['pre'] / a['n'],
                'post_rectification_EW': a['post'] / a['n'],
                'clipping_probability': a['clip'] / a['n'],
                'delta_mean': (None if d is None or not len(d) else float(d.mean())),
                'delta_p05': (None if d is None or not len(d) else float(np.percentile(d, 5))),
                'delta_p95': (None if d is None or not len(d) else float(np.percentile(d, 95)))}

    print('\n== E[W] against its own centre, by sub-population ==')
    print(f"  {'bucket':26s} {'C':>7s} {'P4C E[W]':>9s} {'MPR E[W]':>9s} "
          f"{'MPR delta':>10s} {'clip P4C':>9s}")
    for lbl in order:
        a, b = acc['P4C'][lbl], acc['MPR_ONLY'][lbl]
        if a['n'] == 0:
            continue
        d = np.concatenate(b['delta']) if b['delta'] else np.array([np.nan])
        print(f"  {lbl:26s} {a['C']/a['n']:7.4f} {a['pre']/a['n']:9.4f} "
              f"{b['post']/b['n']:9.4f} {float(d.mean()):10.4f} "
              f"{a['clip']/a['n']:9.4f}")

    print('\n== history x appearance, carry bias (n >= 40 only) ==')
    keys = sorted(k for k in two['P4C'] if two['P4C'][k]['n'] >= 40)
    print(f"  {'cell':26s} {'n':>5s} " + ' '.join(f'{s:>10s}' for s in K.SYSTEMS))
    for k in keys:
        row = [f"{(two[n][k]['pred'] - two[n][k]['real'])/two[n][k]['n']:+10.3f}"
               for n in K.SYSTEMS]
        print(f"  {k:26s} {two['P4C'][k]['n']:5d} " + ' '.join(row))
    for name in K.SYSTEMS:
        OUT['history_x_appearance'][name] = {
            k: {'n': v['n'], 'pred': v['pred'] / v['n'], 'real': v['real'] / v['n'],
                'bias': (v['pred'] - v['real']) / v['n'], 'crps': v['crps'] / v['n']}
            for k, v in two[name].items()}
    json.dump(OUT, open(f'{HERE}/p4f_diagnostics.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4f_diagnostics.json')


if __name__ == '__main__':
    main()
