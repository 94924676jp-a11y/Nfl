"""R1 ladder + downstream composition into the Stage 4 target pipeline."""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('p4c', 'p4e', 's2', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
sys.path.insert(0, '/home/user/nfl/sportsplatform')
import r1_lib as L, r1_fit as F                                # noqa: E402
import p4c_lib as CL, p4c_build as CB                          # noqa: E402
import s2_lib as SL, run_s4 as S4                              # noqa: E402

LADDER = [('R0', None), ('R_base', []), ('R_A', ['A']), ('R_B', ['B']),
          ('R_C', ['C']), ('R_D', ['D']), ('R_E', ['E']),
          ('R_AB', ['A', 'B']), ('R_ABC', ['A', 'B', 'C']),
          ('R_ABCD', ['A', 'B', 'C', 'D']),
          ('R_ABCDE', ['A', 'B', 'C', 'D', 'E'])]
SHAP_R = {2022: 0.4140, 2023: 0.4418, 2024: 0.4422, 2025: 0.4216}


def main():
    t0 = time.time()
    rows, sub = L.load()
    L.attach(sub, rows)
    pa = CB.appearance(rows)
    b0 = json.load(open(f'{HERE}/r1_block0.json'))
    K = {int(e): v for e, v in b0['shrinkage_constants'].items()}
    seasons = sorted({r['season'] for r in sub})

    def r0(r, ev):
        n = r['h_eff_n']
        b = r.get('h_ewma3_w')
        pr = r.get('h_pos_mean')
        if pr is None:
            return None
        if b is None:
            return pr
        k = K[ev]['ewma3_w']
        return (n * b + k * pr) / (n + k)

    OUT = {'ladder': [n for n, _ in LADDER], 'seasons': {}, 'fits': {},
           'R0_definition': 'empirical-Bayes shrinkage of the participation-'
                            'weighted EWMA half-life 3 toward the position '
                            'prior; k fitted on prior seasons only'}
    per = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    poolp = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    rowpred = collections.defaultdict(dict)
    for ev in L.EVAL:
        te = [r for r in sub if L.eligible(r, ev)]
        y = np.array([r['R_star'] for r in te], float)
        for name, blocks in LADDER:
            if blocks is None:
                p = np.array([r0(r, ev) for r in te], float)
            else:
                fit, fd = F.fit_rung(sub, ev, blocks, pa, seasons)
                p = F.predict_rung(fit, te, blocks, pa)
                OUT['fits'].setdefault(name, {})[str(ev)] = {
                    k: v for k, v in fd.items() if k != 'features'}
                if ev == L.EVAL[0]:
                    OUT['fits'][name]['features'] = fd['features']
            rowpred[ev][name] = p
            per[name][ev] = (p.tolist(), y.tolist())
            for pos in ('WR', 'TE', 'RB'):
                m = np.array([r['position'] == pos for r in te])
                poolp[name][pos][0].extend(p[m].tolist())
                poolp[name][pos][1].extend(y[m].tolist())
            poolp[name]['ALL'][0].extend(p.tolist())
            poolp[name]['ALL'][1].extend(y.tolist())
        OUT['seasons'][str(ev)] = {'n': len(te)}

    print('== R ladder: prediction of R itself ==')
    for pos in ('ALL', 'WR', 'TE', 'RB'):
        print(f'\n  --- {pos} ---')
        print(f"    {'rung':10s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} {'R2':>7s} "
              f"{'sdrat':>7s} {'vs R0':>8s}")
        base = None
        for name, _b in LADDER:
            p, yy = poolp[name][pos]
            m = L.metrics(p, yy)
            if name == 'R0':
                base = m['mae']
            OUT.setdefault('rung_metrics', {}).setdefault(pos, {})[name] = m
            print(f"    {name:10s} {m['mae']:7.4f} {m['rmse']:7.4f} "
                  f"{(m['r'] or float('nan')):7.3f} {(m['r2'] or float('nan')):7.3f} "
                  f"{(m['sd_ratio'] or float('nan')):7.3f} "
                  f"{100*(m['mae']-base)/base:+7.2f}%")
    # vs the pooled position mean, the pre-declared reference
    pm = {}
    for pos in ('ALL', 'WR', 'TE', 'RB'):
        pm[pos] = b0['block0'][pos]['pos_mean']['pooled']['mae']
    best = min((n for n, _b in LADDER),
               key=lambda n: OUT['rung_metrics']['ALL'][n]['mae'])
    OUT['best_rung'] = best
    print(f'\n  best rung by pooled MAE: {best}')
    print(f"  {'pos':5s} {'pos_mean':>9s} {'best':>9s} {'relative':>9s}")
    for pos in ('ALL', 'WR', 'TE', 'RB'):
        b = OUT['rung_metrics'][pos][best]['mae']
        print(f'  {pos:5s} {pm[pos]:9.4f} {b:9.4f} '
              f'{100*(pm[pos]-b)/pm[pos]:+8.2f}%')
        OUT.setdefault('vs_pos_mean', {})[pos] = {
            'pos_mean_mae': pm[pos], 'best_mae': b,
            'relative_gain': (pm[pos] - b) / pm[pos]}
    # per-season, against pos_mean
    seas_ok = 0
    OUT['per_season_vs_pos_mean'] = {}
    for ev in L.EVAL:
        pmm = b0['block0']['ALL']['pos_mean']['per_season_mae'][str(ev)]
        p, yy = per[best][ev]
        bm = L.metrics(p, yy)['mae']
        rel = (pmm - bm) / pmm
        OUT['per_season_vs_pos_mean'][str(ev)] = {'pos_mean': pmm,
                                                  'best': bm, 'relative': rel}
        seas_ok += 1 if rel >= 0.10 else 0
        print(f'    {ev}: pos_mean {pmm:.4f}  best {bm:.4f}  {100*rel:+.2f}%')
    OUT['seasons_ge_10pct'] = seas_ok
    json.dump(OUT, open(f'{HERE}/r1_ladder.json', 'w'), indent=1)

    # ---- downstream composition into the Stage 4 pipeline ---------------
    print('\n== downstream: substitute ONLY the R leg of Stage 4 ==')
    vol = CB.load_volume()
    _r2, sub2 = SL.load(); SL.attach(sub2)
    look = {(r['gsis_id'], r['ord'], r['team']): r for r in sub}
    down = {}
    crps_rows = collections.defaultdict(dict)
    clusters = {}
    for ev in L.EVAL:
        d = S4.build(rows, vol, pa, sub2, ev)
        te = [r for r in sub if L.eligible(r, ev)]
        idx = {(r['gsis_id'], r['ord'], r['team']): i for i, r in enumerate(te)}
        pred = rowpred[ev][best]
        n = d['n']
        Rmodel = np.array(d['Rhat'][:, 0], np.float64).copy()
        have = np.zeros(n, bool)
        for i, r in enumerate(d['te']):
            k = (r['gsis_id'], r['ord'], r['team'])
            if k in idx:
                Rmodel[i] = pred[idx[k]]
                have[i] = True
        clusters[ev] = [f"{r['team']}_{r['ord']}" for r in d['te']]
        base_draws = S4.corner_draws(d, frozenset())
        crps_rows[ev]['BASELINE'] = CL.crps_samples(base_draws, d['y'])
        # CENTRE substitution is the faithful one. The Stage 4 R leg is a DRAW
        # MATRIX with a coefficient of variation of 0.914 -- its dispersion is
        # as large as its mean. Overwriting it with a point estimate removes
        # all of that, which changes the predictive DISTRIBUTION rather than
        # R's central tendency, and is not what "substitute only the R leg"
        # means. So the model's value rescales the control's own draw pattern:
        #
        #     R_new[i, m] = R_model[i] * Rhat[i, m] / mean_m Rhat[i, m]
        #
        # This is the direct analogue of P4E and P4F changing a weight's centre
        # while keeping its residual draw structure. The point substitution is
        # kept as a clearly labelled SECONDARY result, because it answers a
        # different question -- what happens if R is treated as deterministic.
        Rmu = d['Rhat'].mean(axis=1)
        shape = np.divide(d['Rhat'], np.maximum(Rmu, 1e-9)[:, None],
                          out=np.ones_like(d['Rhat']),
                          where=Rmu[:, None] > 1e-9)
        for lbl, mask, kind in (('sub_centre', have, 'centre'),
                                ('sub_centre_all', np.ones(n, bool), 'centre'),
                                ('sub_point', have, 'point')):
            Rm = d['Rhat'].copy()
            if kind == 'centre':
                Rm[mask] = (Rmodel[mask][:, None]
                            * shape[mask]).astype(np.float32)
            else:
                Rm[mask] = Rmodel[mask][:, None]
            P = np.repeat(d['Pc'][:, None], CL.M_DRAWS, 1)
            Wm = (P * Rm).astype(np.float32)
            WA = Wm * d['A_pred']
            tot = CL.gsum(WA, d['starts'])
            tee = CL.gexp(tot, d['cg'])
            S = np.divide(WA * CL.gexp(d['avail_pred'], d['cg']), tee,
                          out=np.zeros_like(WA), where=tee > 1e-12)
            S, _nb = CL.waterfill(S, d['starts'], d['cg'], 1.0)
            draws = (CL.gexp(d['T_pred'], d['cg']) * S).astype(np.float32)
            crps_rows[ev][lbl] = CL.crps_samples(draws, d['y'])
            del draws, S, WA, Wm
        down[str(ev)] = {
            'n': n, 'n_substituted': int(have.sum()),
            'baseline_crps': float(crps_rows[ev]['BASELINE'].mean()),
            **{f'{k}_crps': float(crps_rows[ev][k].mean())
               for k in ('sub_centre', 'sub_centre_all', 'sub_point')}}
        b = down[str(ev)]
        print(f"  {ev}: baseline {b['baseline_crps']:.4f}  "
              f"centre(elig {b['n_substituted']}/{n}) {b['sub_centre_crps']:.4f} "
              f"({b['sub_centre_crps']-b['baseline_crps']:+.4f})  "
              f"centre(all) {b['sub_centre_all_crps']:.4f}  "
              f"point {b['sub_point_crps']:.4f}")
    allc = sum((clusters[e] for e in L.EVAL), [])
    basecat = np.concatenate([crps_rows[e]['BASELINE'] for e in L.EVAL])
    pooled = {}
    for lbl in ('sub_centre', 'sub_centre_all', 'sub_point'):
        cat = np.concatenate([crps_rows[e][lbl] for e in L.EVAL])
        bt = CL.block_boot(cat, basecat, allc)
        wins = sum(1 for e in L.EVAL
                   if crps_rows[e][lbl].mean() < crps_rows[e]['BASELINE'].mean())
        frac = float((basecat.mean() - cat.mean())
                     / np.mean([SHAP_R[e] for e in L.EVAL]))
        pooled[lbl] = {'pooled_crps': float(cat.mean()),
                       'delta_vs_baseline': float(cat.mean() - basecat.mean()),
                       'seasons_better': wins, 'block_bootstrap': bt,
                       'fraction_of_R_oracle_recovered': frac}
        print(f"\n  {lbl}: pooled {cat.mean():.4f} vs baseline "
              f"{basecat.mean():.4f}  delta {cat.mean()-basecat.mean():+.4f}  "
              f"seasons better {wins}/4")
        print(f"    95% CI [{bt['lo']:+.4f}, {bt['hi']:+.4f}] "
              f"clusters {bt['n_clusters']}")
        print(f"    model-family recovery of the measured R oracle "
              f"opportunity: {100*frac:+.2f}%")
    OUT['downstream'] = {'per_season': down, 'pooled': pooled,
                         'baseline_pooled_crps': float(basecat.mean())}
    json.dump(OUT, open(f'{HERE}/r1_ladder.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> r1_ladder.json')


if __name__ == '__main__':
    main()
