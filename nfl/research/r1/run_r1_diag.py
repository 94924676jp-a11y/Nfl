"""R1 diagnostics: what reconciliation actually consumes, cohorts, P/R coupling.

The downstream result forces a question the marginal metrics cannot answer.
Reconciliation divides each player's weight by the team-game total, so only the
WITHIN-TEAM-GAME relative pattern of R survives composition. A model can improve
absolute R and buy nothing downstream if it does not improve that.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('p4c', 'p4e', 's2', 's4'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import r1_lib as L, r1_fit as F                                # noqa: E402
import p4c_build as CB, p4c_lib as CL                          # noqa: E402
import s2_lib as SL, run_s4 as S4                              # noqa: E402


def within_group_center(vals, groups):
    out = np.array(vals, float).copy()
    for g, idx in groups.items():
        if len(idx) < 2:
            out[idx] = np.nan
            continue
        out[idx] -= out[idx].mean()
    return out


def main():
    t0 = time.time()
    rows, sub = L.load(); L.attach(sub, rows)
    pa = CB.appearance(rows)
    vol = CB.load_volume()
    _r2, sub2 = SL.load(); SL.attach(sub2)
    b0 = json.load(open(f'{HERE}/r1_block0.json'))
    lad = json.load(open(f'{HERE}/r1_ladder.json'))
    K = {int(e): v for e, v in b0['shrinkage_constants'].items()}
    best = lad['best_rung']
    seasons = sorted({r['season'] for r in sub})
    OUT = {'best_rung': best}

    def r0(r, ev):
        n, b, pr = r['h_eff_n'], r.get('h_ewma3_w'), r.get('h_pos_mean')
        if pr is None:
            return None
        if b is None:
            return pr
        k = K[ev]['ewma3_w']
        return (n * b + k * pr) / (n + k)

    # ---- 1. ABSOLUTE vs WITHIN-TEAM-GAME (relative) accuracy -------------
    print('== what reconciliation consumes: absolute vs within-team-game R ==')
    abs_acc, rel_acc = collections.defaultdict(lambda: ([], [])), \
        collections.defaultdict(lambda: ([], []))
    pr_err = {'P': [], 'R': []}
    coh = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    for ev in L.EVAL:
        d = S4.build(rows, vol, pa, sub2, ev)
        te_all = d['te']
        look = {(r['gsis_id'], r['ord'], r['team']): r for r in sub}
        elig = [r for r in sub if L.eligible(r, ev)]
        eidx = {(r['gsis_id'], r['ord'], r['team']): i
                for i, r in enumerate(elig)}
        fit, _fd = F.fit_rung(sub, ev, ['A', 'B', 'C', 'D'], pa, seasons)
        pmod = F.predict_rung(fit, elig, ['A', 'B', 'C', 'D'], pa)
        p0 = np.array([r0(r, ev) for r in elig], float)
        # team-game groups over the ELIGIBLE rows
        groups = collections.defaultdict(list)
        for i, r in enumerate(elig):
            groups[(r['team'], r['ord'])].append(i)
        groups = {g: np.array(v) for g, v in groups.items()}
        y = np.array([r['R_star'] for r in elig], float)
        s4c = np.zeros(len(elig))
        for i, r in enumerate(te_all):
            k = (r['gsis_id'], r['ord'], r['team'])
            if k in eidx:
                s4c[eidx[k]] = float(d['Rhat'][i].mean())
        for lbl, p in (('S4_control', s4c), ('R0', p0), (best, pmod)):
            abs_acc[lbl][0].extend(p.tolist())
            abs_acc[lbl][1].extend(y.tolist())
            cp = within_group_center(p, groups)
            cy = within_group_center(y, groups)
            m = np.isfinite(cp) & np.isfinite(cy)
            rel_acc[lbl][0].extend(cp[m].tolist())
            rel_acc[lbl][1].extend(cy[m].tolist())
        # P/R error coupling
        for i, r in enumerate(elig):
            q = next((x for x in sub2
                      if x['gsis_id'] == r['gsis_id'] and x['ord'] == r['ord']
                      and x['team'] == r['team']), None) if False else None
        Pfore = np.array([(r.get('h_P_ewma2') if r.get('h_P_ewma2') is not None
                           else 0.0) for r in elig], float)
        Pstar = np.array([r['P_star'] for r in elig], float)
        pr_err['P'].extend((Pfore - Pstar).tolist())
        pr_err['R'].extend((pmod - y).tolist())
        # cohorts
        for i, r in enumerate(elig):
            pa_ = pa.get(id(r))
            pe = r.get('h_P_ewma2') or 0.0
            tc = r.get('h_team_conc') or 'unknown'
            car = r.get('h_targets_career') or 0.0
            bands = [
                ('position', r['position']),
                ('prior_games', '<4' if r['h_n'] < 4 else '4-9'
                 if r['h_n'] < 10 else '10-24' if r['h_n'] < 25 else '25+'),
                ('appearance', 'unknown' if pa_ is None else
                 '<0.25' if pa_ < .25 else '0.25-0.50' if pa_ < .50 else
                 '0.50-0.80' if pa_ < .80 else '0.80-0.95' if pa_ < .95
                 else '>=0.95'),
                ('participation', 'low' if pe < 0.25 else 'medium'
                 if pe < 0.60 else 'high'),
                ('role', r.get('h_role') or 'stable'),
                ('target_volume', 'low' if car < 25 else 'medium'
                 if car < 100 else 'high'),
                ('team_concentration', tc)]
            for dim, lvl in bands:
                coh[(dim, lvl)]['pred'][0].append(float(pmod[i])) if False else None
                coh[dim][lvl][0].append(float(pmod[i]))
                coh[dim][lvl][1].append(float(y[i]))
    print(f"  {'estimator':12s} {'ABS MAE':>9s} {'ABS r':>7s} | "
          f"{'REL MAE':>9s} {'REL r':>7s}   (REL = within-team-game centred)")
    OUT['absolute_vs_relative'] = {}
    for lbl in ('S4_control', 'R0', best):
        a = L.metrics(*abs_acc[lbl])
        rr = L.metrics(*rel_acc[lbl])
        OUT['absolute_vs_relative'][lbl] = {'absolute': a, 'relative': rr}
        print(f"  {lbl:12s} {a['mae']:9.4f} {(a['r'] or float('nan')):7.3f} | "
              f"{rr['mae']:9.4f} {(rr['r'] or float('nan')):7.3f}")
    OUT['interpretation_absolute_vs_relative'] = (
        'Reconciliation divides by the team-game total, so only the '
        'within-team-game pattern survives composition. Compare the REL column '
        'across estimators: that, not the ABS column, is what the downstream '
        'CRPS responds to.')

    # ---- 2. P/R error coupling ------------------------------------------
    pe = np.array(pr_err['P']); re_ = np.array(pr_err['R'])
    m = np.isfinite(pe) & np.isfinite(re_)
    c = float(np.corrcoef(pe[m], re_[m])[0, 1])
    OUT['P_R_error_coupling'] = {
        'corr': c, 'n': int(m.sum()),
        'P_error_mean': float(pe[m].mean()), 'R_error_mean': float(re_[m].mean()),
        'interpretation': (
            'R is defined conditional on P, so a P error and an R error are not '
            'independent by construction. The measured correlation is reported '
            'as a dependency finding; the simulator is NOT redesigned here.')}
    print(f'\n== P/R error coupling ==\n  corr(P error, R error) = {c:+.4f} '
          f'on n={int(m.sum())}')

    # ---- 3. cohorts ------------------------------------------------------
    print('\n== cohorts (best rung) ==')
    OUT['cohorts'] = {}
    for dim in ('position', 'prior_games', 'appearance', 'participation',
                'role', 'target_volume', 'team_concentration'):
        print(f'  --- {dim} ---')
        OUT['cohorts'][dim] = {}
        for lvl, (p, y) in sorted(coh[dim].items()):
            if len(y) < 50:
                continue
            mm = L.metrics(p, y)
            OUT['cohorts'][dim][lvl] = mm
            print(f"    {lvl:14s} n={mm['n']:5d}  MAE {mm['mae']:.4f}  "
                  f"r {(mm['r'] or float('nan')):+.3f}  "
                  f"bias {mm['bias']:+.4f}  real {mm['mean_real']:.4f}")
    json.dump(OUT, open(f'{HERE}/r1_diagnostics.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> r1_diagnostics.json')


if __name__ == '__main__':
    main()
