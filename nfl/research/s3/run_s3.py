"""Stage 3 runner: the diagnostic battery on the accepted marginals."""
import json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import joint as J, build_joint as B                            # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', 'p4c'))
import p4c_build as CB                                         # noqa: E402

SEASONS = (2024, 2025)


def main():
    t0 = time.time()
    rows = CB.load_panel(); vol = CB.load_volume(); pa = CB.appearance(rows)
    OUT = {'scope': 'DIAGNOSTIC ONLY -- flags marginals, decides nothing',
           'classes': list(B.CLASSES), 'seasons': list(SEASONS), 'cells': {},
           'flags': []}
    for cls in B.CLASSES:
        for ev in SEASONS:
            jd = B.build(rows, vol, pa, cls, ev)
            if jd is None:
                continue
            d = J.diagnose(jd, purpose='diagnostic')
            OUT['cells'][f'{cls}/{ev}'] = d
            a_pre, a_post = (d['accounting_coherence']['pre'],
                             d['accounting_coherence']['post'])
            m_pre, m_post = (d['marginal_calibration']['pre'],
                             d['marginal_calibration']['post'])
            j_pre, j_post = (d['joint_dependence']['pre'],
                             d['joint_dependence']['post'])
            print(f'\n== {cls} {ev}  n={d["n"]} G={d["G"]} mode={d["mode"]} ==')
            print('  ACCOUNTING COHERENCE           pre        post')
            for k in ('impossible_share_gt_cap', 'team_group_sum_gt_cap_rate',
                      'modelled_mass_mean', 'over_allocation_pct',
                      'team_accounting_error_mean_abs'):
                print(f'    {k:32s} {a_pre[k]:9.4f}  {a_post[k]:9.4f}')
            print(f"    {'team_sum coverage_90':32s} "
                  f"{a_pre['team_sum_distribution']['coverage_90']:9.4f}  "
                  f"{a_post['team_sum_distribution']['coverage_90']:9.4f}")
            print('  MARGINAL CALIBRATION           pre        post')
            for k in ('crps', 'mae', 'bias'):
                print(f'    {k:32s} {m_pre[k]:9.4f}  {m_post[k]:9.4f}')
            print(f"    {'randomised PIT chi2':32s} "
                  f"{m_pre['randomised_pit']['chi2']:9.1f}  "
                  f"{m_post['randomised_pit']['chi2']:9.1f}   (crit 27.877)")
            for lvl in ('90', '99'):
                print(f"    {'coverage@'+lvl:32s} "
                      f"{m_pre['coverage'][lvl]['coverage']:9.4f}  "
                      f"{m_post['coverage'][lvl]['coverage']:9.4f}")
            print(f"    {'exceed p99 rate (nominal .01)':32s} "
                  f"{m_pre['tail']['exceed_p99_rate']:9.4f}  "
                  f"{m_post['tail']['exceed_p99_rate']:9.4f}")
            print('  JOINT DEPENDENCE  (model median r [95% PI] vs realised)')
            for lbl in sorted(j_post['pairs']):
                a, b = j_pre['pairs'].get(lbl, {}), j_post['pairs'][lbl]
                if b.get('state') != 'PASS':
                    print(f'    {lbl:16s} NOT_APPLICABLE')
                    continue
                pa_ = (f"{a['model_median_r']:+.3f}" if a.get('state') == 'PASS'
                       else '   n/a')
                print(f"    {lbl:16s} pre {pa_}   post {b['model_median_r']:+.3f} "
                      f"[{b['model_ci95'][0]:+.3f},{b['model_ci95'][1]:+.3f}]  "
                      f"real {b['realised_r']:+.3f}  z {b['z']:+.2f}  "
                      f"{'IN' if b['realised_inside_ci95'] else 'OUT'}"
                      f"{'  '+b.get('kind','') if b.get('kind') else ''}")
            print(f"    concentration HHI  sim pre {j_pre['concentration']['hhi_sim']:.3f} "
                  f"post {j_post['concentration']['hhi_sim']:.3f}  "
                  f"realised {j_post['concentration']['hhi_realised']:.3f}")
            # FLAGS -- the scaffold may flag, never reject or promote
            if m_post['randomised_pit']['chi2'] > 27.877:
                OUT['flags'].append({
                    'cell': f'{cls}/{ev}', 'kind': 'MARGINAL_CALIBRATION',
                    'detail': f"post-reconciliation randomised PIT chi2 "
                              f"{m_post['randomised_pit']['chi2']:.1f} exceeds "
                              f"27.877",
                    'action': 'FLAGGED FOR RE-EXAMINATION -- not rejected here'})
            for lbl, b in j_post['pairs'].items():
                if b.get('state') == 'PASS' and not b['realised_inside_ci95']:
                    OUT['flags'].append({
                        'cell': f'{cls}/{ev}', 'kind': 'JOINT_DEPENDENCE',
                        'detail': f"{lbl}: realised r {b['realised_r']:+.3f} "
                                  f"outside the model's 95% band "
                                  f"[{b['model_ci95'][0]:+.3f},"
                                  f"{b['model_ci95'][1]:+.3f}], z {b['z']:+.2f}",
                        'action': 'FLAGGED FOR RE-EXAMINATION -- not rejected here'})
            for stg, aa in (('pre', a_pre), ('post', a_post)):
                if aa['team_group_sum_gt_cap_rate'] > 0.01:
                    OUT['flags'].append({
                        'cell': f'{cls}/{ev}', 'kind': 'ACCOUNTING_COHERENCE',
                        'detail': (
                            f"{stg}-reconciliation team group sum exceeds the "
                            f"physical maximum of {aa['team_group_sum_physical_cap']:.1f} "
                            f"in {aa['team_group_sum_gt_cap_rate']:.2%} of draws, "
                            f"peaking at {aa['team_group_sum_max']:.3f} "
                            f"({aa['team_group_sum_max_over_cap_ratio']:.2f}x). "
                            f"The realised maximum is "
                            f"{aa['realised_group_sum_max']:.3f}."),
                        'action': 'FLAGGED FOR RE-EXAMINATION -- not rejected here'})
            if a_post['impossible_share_gt_cap'] > 0:
                OUT['flags'].append({
                    'cell': f'{cls}/{ev}', 'kind': 'ACCOUNTING_COHERENCE',
                    'detail': f"impossible share rate "
                              f"{a_post['impossible_share_gt_cap']:.4f}",
                    'action': 'FLAGGED FOR RE-EXAMINATION -- not rejected here'})
    print(f'\n== flags raised: {len(OUT["flags"])} ==')
    for f in OUT['flags']:
        print(f"  {f['kind']:22s} {f['cell']:14s} {f['detail']}")
    json.dump(OUT, open(f'{HERE}/s3_results.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> s3_results.json')


if __name__ == '__main__':
    main()
