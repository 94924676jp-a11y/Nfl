"""Stage 3 joint diagnostic, consumer only: control P vs candidate P.

The scaffold may report. It may not fix the simulator, promote P, choose
features, or produce a combined score.
"""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('s2', 'p4c', 'p4e', 's4', 's3'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import p_lib as L                                              # noqa: E402
import p4c_build as CB, p4c_lib as CL                          # noqa: E402
import run_s4 as S4                                            # noqa: E402
import joint as J                                              # noqa: E402


def main():
    t0 = time.time()
    rows, sub = L.load()
    pa = CB.appearance(rows)
    L.attach(sub, pa)
    vol = CB.load_volume()
    st = json.load(open(f'{HERE}/p_study.json'))
    OUT = {'scope': 'DIAGNOSTIC ONLY -- reports, decides nothing',
           'seasons': {}}
    for ev in (2024, 2025):
        d = S4.build(rows, vol, pa, sub, ev)
        n = d['n']
        look = {(r['gsis_id'], r['ord'], r['team']): r for r in sub}
        Pnew = d['Pc'].copy()
        for i, r in enumerate(d['te']):
            q = look.get((r['gsis_id'], r['ord'], r['team']))
            if q is None or not L.eligible(q, ev):
                continue
            v = q.get('p_ewma1')
            if v is None:
                v = q.get('q_pos_mean')
            if v is not None:
                Pnew[i] = max(float(min(max(v, 0.0), 1.0)), S4.P_FLOOR)
        cell = {}
        for lbl, Pv in (('control_P', d['Pc']), ('candidate_P', Pnew)):
            W = (Pv[:, None] * d['Rhat']).astype(np.float32)
            WA = W * d['A_pred']
            tot = CL.gsum(WA, d['starts'])
            tee = CL.gexp(tot, d['cg'])
            S = np.divide(WA * CL.gexp(d['avail_pred'], d['cg']), tee,
                          out=np.zeros_like(WA), where=tee > 1e-12)
            S, _nb = CL.waterfill(S, d['starts'], d['cg'], 1.0)
            jd = J.JointDraws('targets', ev, d['te'], d['starts'], d['cg'],
                              CL.gexp(d['T_pred'], d['cg']), d['A_pred'], W,
                              S.astype(np.float32), d['y'], d['Sstar'],
                              d['A_star'], cap=1.0, group_cap=1.0,
                              marginal_id={'system': 'P4C-C', 'P_leg': lbl},
                              mode='simplex')
            cell[lbl] = J.diagnose(jd, purpose='diagnostic')
        OUT['seasons'][str(ev)] = cell
        print(f'\n== targets {ev}  n={n} ==')
        print(f"  {'quantity':38s} {'control PRE':>12s} {'control POST':>12s} "
              f"{'cand PRE':>12s} {'cand POST':>12s}")
        for key, path in (
                ('impossible share > cap',
                 ('accounting_coherence', 'impossible_share_gt_cap')),
                ('group sum > physical max (rate)',
                 ('accounting_coherence', 'team_group_sum_gt_cap_rate')),
                ('group sum max',
                 ('accounting_coherence', 'team_group_sum_max')),
                ('modelled mass mean',
                 ('accounting_coherence', 'modelled_mass_mean')),
                ('over-allocation %',
                 ('accounting_coherence', 'over_allocation_pct')),
                ('target CRPS', ('marginal_calibration', 'crps')),
                ('MAE', ('marginal_calibration', 'mae')),
                ('bias', ('marginal_calibration', 'bias'))):
            vals = []
            for lbl in ('control_P', 'candidate_P'):
                for stage in ('pre', 'post'):
                    vals.append(cell[lbl][path[0]][stage][path[1]])
            print(f'  {key:38s} ' + ' '.join(f'{v:12.4f}' for v in
                                             (vals[0], vals[1], vals[2], vals[3])))
        for lbl in ('control_P', 'candidate_P'):
            mp = cell[lbl]['marginal_calibration']
            print(f"  {lbl:16s} randomised PIT  pre "
                  f"{mp['pre']['randomised_pit']['chi2']:8.1f}  post "
                  f"{mp['post']['randomised_pit']['chi2']:8.1f}  (crit 27.877)")
        for lbl in ('control_P', 'candidate_P'):
            jp = cell[lbl]['joint_dependence']['post']['pairs']
            r12 = jp.get('rank1-rank2', {})
            if r12.get('state') == 'PASS':
                print(f"  {lbl:16s} rank1-rank2 model r "
                      f"{r12['model_median_r']:+.3f} "
                      f"[{r12['model_ci95'][0]:+.3f},{r12['model_ci95'][1]:+.3f}]"
                      f"  realised {r12['realised_r']:+.3f}  z {r12['z']:+.2f}"
                      f"  {'IN' if r12['realised_inside_ci95'] else 'OUT'}")
    json.dump(OUT, open(f'{HERE}/p_joint.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p_joint.json')


if __name__ == '__main__':
    main()
