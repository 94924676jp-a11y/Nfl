"""P downstream: substitute ONLY P into Stage 4, draw-preserving, then the
P/R diagnostic factorial and the Stage 3 joint diagnostic.

R1's lesson applied: in Stage 4, W = Pc x Rhat where Rhat is a DRAW MATRIX.
Substituting P is W_new = P_new[:, None] * Rhat, which leaves every bit of the
draw structure in Rhat untouched. No draw distribution is replaced by a point
estimate and no new distribution is introduced.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('s2', 'p4c', 'p4e', 's4', 'r1', 's3'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import p_lib as L, p_fit as F                                  # noqa: E402
import s2_lib as SL                                            # noqa: E402
import p4c_build as CB, p4c_lib as CL                          # noqa: E402
import run_s4 as S4                                            # noqa: E402
import r1_lib as RL, r1_fit as RF                              # noqa: E402

SHAP_P = {2022: 0.2849, 2023: 0.2638, 2024: 0.2548, 2025: 0.2627}
P_FLOOR = S4.P_FLOOR


def main():
    t0 = time.time()
    rows, sub = L.load()
    pa = CB.appearance(rows)
    L.attach(sub, pa)
    vol = CB.load_volume()
    st = json.load(open(f'{HERE}/p_study.json'))
    best = st['best_rung']
    best_simple = st['best_simple']
    K = {int(e): v for e, v in st['shrinkage_k'].items()}
    print(f'candidate = {best} (best simple = {best_simple})')

    # R1's model, DIAGNOSTIC ONLY -- not accepted, not promoted
    _rr, rsub = RL.load(); RL.attach(rsub, _rr)
    rseasons = sorted({r['season'] for r in rsub})
    rlook = {(r['gsis_id'], r['ord'], r['team']): r for r in rsub}

    def p_candidate(r, ev):
        if best == 'P0':
            v = r.get('p_ewma1') if best_simple == 'ewma_hl1' else None
            if v is None:
                v = r.get('q_pos_mean')
            return None if v is None else float(min(max(v, 0.0), 1.0))
        raise ValueError(f'unhandled rung {best}')

    OUT = {'candidate': best, 'candidate_simple': best_simple,
           'substitution_rule': 'W_new = P_new[:, None] * Rhat -- draw '
                                'structure preserved, R1 lesson applied'}
    crps = collections.defaultdict(dict)
    clusters, cohorts = {}, collections.defaultdict(
        lambda: collections.defaultdict(lambda: ([], [])))
    per = {}
    for ev in L.EVAL:
        d = S4.build(rows, vol, pa, sub, ev)
        n = d['n']
        clusters[ev] = [f"{r['team']}_{r['ord']}" for r in d['te']]
        look = {(r['gsis_id'], r['ord'], r['team']): r for r in sub}
        Pnew = d['Pc'].copy()
        have = np.zeros(n, bool)
        for i, r in enumerate(d['te']):
            q = look.get((r['gsis_id'], r['ord'], r['team']))
            if q is None or not L.eligible(q, ev):
                continue
            v = p_candidate(q, ev)
            if v is None:
                continue
            Pnew[i] = max(v, P_FLOOR)
            have[i] = True
        # R1's R model, diagnostic
        rfit, _fd = RF.fit_rung(rsub, ev, ['A', 'B', 'C', 'D'], pa, rseasons)
        relig = [r for r in rsub if RL.eligible(r, ev)]
        ridx = {(r['gsis_id'], r['ord'], r['team']): i
                for i, r in enumerate(relig)}
        rpred = RF.predict_rung(rfit, relig, ['A', 'B', 'C', 'D'], pa)
        Rmu = d['Rhat'].mean(axis=1)
        shape = np.divide(d['Rhat'], np.maximum(Rmu, 1e-9)[:, None],
                          out=np.ones_like(d['Rhat']),
                          where=Rmu[:, None] > 1e-9)
        R_r1 = d['Rhat'].copy()
        rhave = np.zeros(n, bool)
        for i, r in enumerate(d['te']):
            k = (r['gsis_id'], r['ord'], r['team'])
            if k in ridx:
                R_r1[i] = (rpred[ridx[k]] * shape[i]).astype(np.float32)
                rhave[i] = True

        def compose(Pv, Rm):
            Wm = (Pv[:, None] * Rm).astype(np.float32)
            WA = Wm * d['A_pred']
            tot = CL.gsum(WA, d['starts'])
            tee = CL.gexp(tot, d['cg'])
            Sv = np.divide(WA * CL.gexp(d['avail_pred'], d['cg']), tee,
                           out=np.zeros_like(WA), where=tee > 1e-12)
            Sv, _nb = CL.waterfill(Sv, d['starts'], d['cg'], 1.0)
            return (CL.gexp(d['T_pred'], d['cg']) * Sv).astype(np.float32), Sv

        cells = {
            'P_control_x_R_control': (d['Pc'], d['Rhat']),
            'P_candidate_x_R_control': (Pnew, d['Rhat']),
            'P_control_x_R_R1': (d['Pc'], R_r1),
            'P_candidate_x_R_R1': (Pnew, R_r1)}
        for lbl, (Pv, Rm) in cells.items():
            draws, Sv = compose(Pv, Rm)
            crps[ev][lbl] = CL.crps_samples(draws, d['y'])
            if lbl == 'P_candidate_x_R_control':
                # cohort deltas, control vs candidate
                base = crps[ev]['P_control_x_R_control']
                for i, r in enumerate(d['te']):
                    q = look.get((r['gsis_id'], r['ord'], r['team']))
                    if q is None:
                        continue
                    pa_ = pa.get(id(q))
                    role = q.get('p_role') or 'stable'
                    hist = ('<4' if (q.get('p_n') or 0) < 4 else '4-9'
                            if (q.get('p_n') or 0) < 10 else '10-24'
                            if (q.get('p_n') or 0) < 25 else '25+')
                    hc = ('high_confidence_starter'
                          if (pa_ or 0) >= 0.95 else 'other')
                    for dim, lvl in (('role_transition', role),
                                     ('history', hist),
                                     ('confidence', hc)):
                        cohorts[dim][lvl][0].append(float(base[i]))
                        cohorts[dim][lvl][1].append(float(crps[ev][lbl][i]))
            del draws, Sv
        per[str(ev)] = {lbl: float(crps[ev][lbl].mean()) for lbl in cells}
        per[str(ev)]['n_substituted'] = int(have.sum())
        per[str(ev)]['n'] = n
        b = per[str(ev)]
        print(f"  {ev}: control {b['P_control_x_R_control']:.4f}  "
              f"P-cand {b['P_candidate_x_R_control']:.4f} "
              f"({b['P_candidate_x_R_control']-b['P_control_x_R_control']:+.4f})"
              f"  subst {b['n_substituted']}/{n}")
    OUT['per_season'] = per

    allc = sum((clusters[e] for e in L.EVAL), [])
    base = np.concatenate([crps[e]['P_control_x_R_control'] for e in L.EVAL])
    print(f'\n== downstream, pooled (baseline {base.mean():.4f}) ==')
    OUT['pooled'] = {}
    for lbl in ('P_candidate_x_R_control', 'P_control_x_R_R1',
                'P_candidate_x_R_R1'):
        cat = np.concatenate([crps[e][lbl] for e in L.EVAL])
        bt = CL.block_boot(cat, base, allc)
        wins = sum(1 for e in L.EVAL
                   if crps[e][lbl].mean()
                   < crps[e]['P_control_x_R_control'].mean())
        frac = float((base.mean() - cat.mean())
                     / np.mean([SHAP_P[e] for e in L.EVAL]))
        OUT['pooled'][lbl] = {
            'pooled_crps': float(cat.mean()),
            'delta': float(cat.mean() - base.mean()),
            'seasons_better': wins, 'block_bootstrap': bt,
            'fraction_of_P_oracle_recovered': frac}
        print(f"  {lbl:26s} {cat.mean():.4f}  delta {cat.mean()-base.mean():+.4f}"
              f"  seasons better {wins}/4  95% CI [{bt['lo']:+.4f}, "
              f"{bt['hi']:+.4f}]")
        print(f"    model-family recovery of the currently measured P oracle "
              f"opportunity: {100*frac:+.2f}%")
    print('\n== P/R diagnostic factorial (R_R1 is NOT accepted) ==')
    OUT['factorial'] = {}
    for lbl in ('P_control_x_R_control', 'P_candidate_x_R_control',
                'P_control_x_R_R1', 'P_candidate_x_R_R1'):
        cat = np.concatenate([crps[e][lbl] for e in L.EVAL])
        OUT['factorial'][lbl] = float(cat.mean())
        print(f'  {lbl:26s} {cat.mean():.4f}  '
              f'{cat.mean()-base.mean():+.4f}')
    f = OUT['factorial']
    unlock = ((f['P_control_x_R_R1'] - f['P_control_x_R_control'])
              - (f['P_candidate_x_R_R1'] - f['P_candidate_x_R_control']))
    OUT['R1_unlocked_by_better_P'] = unlock
    print(f'  R1 cost under control P : '
          f'{f["P_control_x_R_R1"]-f["P_control_x_R_control"]:+.4f}')
    print(f'  R1 cost under candidate P: '
          f'{f["P_candidate_x_R_R1"]-f["P_candidate_x_R_control"]:+.4f}')
    print(f'  interaction (positive = a better P unlocks R1): {unlock:+.4f}')

    print('\n== downstream cohort deltas (candidate P vs control P) ==')
    OUT['downstream_cohorts'] = {}
    for dim, d_ in cohorts.items():
        print(f'  --- {dim} ---')
        OUT['downstream_cohorts'][dim] = {}
        for lvl, (b_, c_) in sorted(d_.items()):
            if len(b_) < 100:
                continue
            bb, cc = float(np.mean(b_)), float(np.mean(c_))
            OUT['downstream_cohorts'][dim][lvl] = {
                'n': len(b_), 'control': bb, 'candidate': cc, 'delta': cc - bb}
            print(f'    {lvl:24s} n={len(b_):5d}  {bb:.4f} -> {cc:.4f}  '
                  f'{cc-bb:+.4f}')
    json.dump(OUT, open(f'{HERE}/p_downstream.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p_downstream.json')


if __name__ == '__main__':
    main()
