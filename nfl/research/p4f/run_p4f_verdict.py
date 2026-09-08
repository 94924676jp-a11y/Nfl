"""P4F sections 9 and 12: the matched competition criterion, then the verdict.

There is no promotion decision in P4F. The only two admissible conclusions are
REJECT and RETAIN AS PROSPECTIVE CANDIDATE, and both are reached against
criteria fixed in predeclaration_p4f.md before any of these numbers existed.
"""
import hashlib, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4f_common as K                                         # noqa: E402
import p4e_build as B                                          # noqa: E402

EV = ('2022', '2023', '2024', '2025')
PAIRS = ('RB1-RB2', 'RB1-RB3', 'RB2-RB3', 'top1-remainder')


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for c in iter(lambda: fh.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def rule5(res, name):
    """Section 9, applied verbatim. Both legs, per pair."""
    out = {}
    for pair in PAIRS:
        ctl = [res['seasons'][e]['P4C']['joint_matched'][pair] for e in EV]
        cnd = [res['seasons'][e][name]['joint_matched'][pair] for e in EV]
        if any(x.get('state') != 'PASS' for x in ctl + cnd):
            out[pair] = {'state': 'NOT_APPLICABLE',
                         'why': 'the matched construction was not computable '
                                'for every season; no substitute was invented'}
            continue
        zc = [abs(x['z']) for x in ctl]
        zk = [abs(x['z']) for x in cnd]
        leg1 = sum(1 for a, b in zip(zk, zc) if a <= b)
        inc = sum(1 for x in ctl if x['realised_inside_ci95'])
        ink = sum(1 for x in cnd if x['realised_inside_ci95'])
        out[pair] = {
            'state': 'PASS' if (leg1 >= 3 and ink >= inc) else 'FAIL',
            'seasons_abs_z_no_worse': leg1, 'required': 3,
            'candidate_inside_ci95': ink, 'control_inside_ci95': inc,
            'candidate_abs_z': [round(v, 3) for v in zk],
            'control_abs_z': [round(v, 3) for v in zc],
            'candidate_model_median_r': [round(x['model_median_r'], 4) for x in cnd],
            'realised_r': [round(x['realised_r'], 4) for x in cnd]}
    return out


def main():
    t0 = time.time()
    res = json.load(open(f'{HERE}/p4f_results.json'))
    orc = json.load(open(f'{HERE}/p4f_oracle.json'))
    adv = json.load(open(f'{HERE}/p4f_adversarial.json'))
    dia = json.load(open(f'{HERE}/p4f_diagnostics.json'))
    OUT = {'sample_label': res['sample_label'], 'rule5': {}, 'verdict': {}}

    print('== section 9: matched-estimand competition criterion ==')
    for name in K.SYSTEMS:
        if name == 'P4C':
            continue
        OUT['rule5'][name] = rule5(res, name)
        r = OUT['rule5'][name]['RB1-RB2']
        print(f"  {name:9s} RB1-RB2  {r['state']:4s}  |z| no worse in "
              f"{r['seasons_abs_z_no_worse']}/4 (need 3)  inside CI "
              f"{r['candidate_inside_ci95']} vs control "
              f"{r['control_inside_ci95']}")
        print(f"  {'':9s}          candidate |z| {r['candidate_abs_z']}  "
              f"control |z| {r['control_abs_z']}")

    # ---- the verdict ----------------------------------------------------
    print('\n== verdict ==')
    adv_fail = sum(1 for p in adv['probes'] if p['state'] == 'FAIL')
    gd = adv['guard_deletion_proofs_firing']
    for name in ('MPR_ONLY', 'ABC_MPR'):
        p = res['pooled'][name]
        solver = [res['seasons'][e][name]['solver_report'] for e in EV]
        pit = [res['seasons'][e][name]['scores']['randomised_pit']['chi2']
               for e in EV]
        pit_ctl = [res['seasons'][e]['P4C']['scores']['randomised_pit']['chi2']
                   for e in EV]
        em = dia['sub_populations'][name]['true_emerging']
        em_c = dia['sub_populations']['P4C']['true_emerging']
        flattens = (em['crps'] > em_c['crps']) and (abs(em['bias']) >= abs(em_c['bias']))
        mech = {'solver_state': [s['state'] for s in solver],
                'max_abs_centre_error': max(s['max_abs_centre_error_float64']
                                            for s in solver),
                'infeasible_rows': sum(s['rows_infeasible'] for s in solver),
                'degenerate_rows': sum(s['rows_degenerate_solution_set']
                                       for s in solver)}
        r5 = OUT['rule5'][name]['RB1-RB2']['state']
        v = {
            'pooled_crps': p['pooled_crps'], 'delta_vs_P4C': p['delta_vs_P4C'],
            'seasons_better': p['seasons_better'],
            'mechanism': mech,
            'mechanism_achieved': (all(s['state'].startswith('PASS')
                                       for s in solver)
                                   and mech['max_abs_centre_error'] <= 1e-9),
            'randomised_pit': pit, 'randomised_pit_control': pit_ctl,
            'pit_exceeds_critical_27_877': [x > 27.877 for x in pit],
            'rule5_RB1_RB2': r5,
            'adversarial_fail': adv_fail,
            'guard_deletion_proofs_firing': gd,
            'true_emerging_bias': em['bias'], 'true_emerging_crps': em['crps'],
            'true_emerging_bias_control': em_c['bias'],
            'true_emerging_crps_control': em_c['crps'],
            'flattens_genuine_emerging_backs': bool(flattens),
            'residual_allocation_ceiling_pct_of_P4C':
                orc['pooled'][name]['residual_allocation_ceiling_pct_of_P4C'],
        }
        reasons = []
        if not v['mechanism_achieved']:
            reasons.append('the mechanism was not achieved within tolerance')
        if flattens:
            reasons.append('it flattens genuine emerging backs -- '
                           'predeclaration section 13 names this as a negative '
                           'result, and the band average must not be presented '
                           'as the answer instead')
        if r5 == 'FAIL':
            reasons.append('it worsens competition realism on the matched '
                           'criterion of section 9')
        if adv_fail:
            reasons.append('an adversarial probe FAILED')
        if any(x > 27.877 for x in pit):
            reasons.append('randomised PIT exceeds the 27.877 critical value in '
                           'at least one season')
        v['decision'] = 'REJECT' if reasons else 'RETAIN AS PROSPECTIVE CANDIDATE'
        v['reasons'] = reasons
        v['not_promoted'] = True
        OUT['verdict'][name] = v
        print(f'  {name}: {v["decision"]}')
        for rr in reasons:
            print(f'    - {rr}')
        if not reasons:
            print(f'    mechanism achieved (max |mean-C| '
                  f'{mech["max_abs_centre_error"]:.1e}), rule 5 PASS, '
                  f'0 adversarial FAIL, PIT max {max(pit):.1f} < 27.877')
        print(f'    NOT PROMOTED. P4C system C remains the accepted architecture.')

    # ---- section 12: the freeze -----------------------------------------
    keep = [n for n, v in OUT['verdict'].items()
            if v['decision'] == 'RETAIN AS PROSPECTIVE CANDIDATE']
    if keep:
        P4C = os.path.abspath(os.path.join(HERE, '..', 'p4c'))
        P4E = os.path.abspath(os.path.join(HERE, '..', 'p4e'))
        P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))
        files = {}
        for d, ns in ((HERE, ['p4f_mpr.py', 'p4f_common.py', 'run_p4f.py']),
                      (P4E, ['p4e_build.py', 'p4e_fit.py']),
                      (P4C, ['p4c_build.py', 'p4c_lib.py', 'p4c_results.json'])):
            for n in ns:
                files[n] = sha(os.path.join(d, n))
        inputs = {}
        for n in ('panel_enriched.pkl', 'volume_store.npy'):
            fp = os.path.join(P4B, n)
            inputs[n] = {'sha256': sha(fp), 'path': fp,
                         'in_repository': False,
                         'note': 'not committed; a prospective run must verify '
                                 'this hash before it can claim to be the same '
                                 'experiment'}
        OUT['freeze'] = {
            'candidates': keep,
            'statement': 'Candidate frozen for prospective evaluation; NOT '
                         'promoted.',
            'algorithm': ('P4C system C reconciliation, unchanged, applied to a '
                          'pre-reconciliation weight whose centre is a ridge fit '
                          'on prior-only features and whose draws are shifted by '
                          'a deterministic mean-preserving rectification.'),
            'feature_set': {'base': B.BASE_FEATS,
                            'blocks': {b: B.BLOCKS[b] for b in K.BLOCKS_ABC}},
            'solver': {'method': 'bisection on the IVT bracket',
                       'bracket_lo': 'C + min_m eps - (hi - lo)',
                       'bracket_hi': 'C + max_m eps',
                       'iterations': 80, 'dtype': 'float64',
                       'tolerance_abs': 1e-9,
                       'degenerate_flag': 'DEGENERATE_SOLUTION_SET at C in {0,1}',
                       'infeasible_flag': 'INFEASIBLE_ROW, never silently altered'},
            'residual_construction': (
                'out-of-fold, expanding-window replay inside the training block; '
                'residual pool resampled per position with the same generator '
                'seed as the control, so candidate and control share a draw '
                'sequence'),
            'seeds': {'M_DRAWS': 1000, 'base_seed': 20260907,
                      'weights': 'SEED + 3034', 'mass': 'SEED + 5002',
                      'appearance': 'SEED + 1009', 'scoring': 'SEED + 31'},
            'ridge': {'lambda_grid': [0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0],
                      'selection': 'inner validation on the last training '
                                   'season, never the evaluation season'},
            'source_sha256': files,
            'input_artifacts': inputs,
            'eligibility_rules': [
                'evaluation seasons 2022-2025 are development data and can '
                'never promote this candidate',
                'promotion requires prospective evidence under a separately '
                'pre-declared rule',
                'the appearance model, team-volume draw and reconciliation are '
                'frozen imports and may not change without re-freezing',
                'no market data, no observed weather, no weekly_rosters.status, '
                'no present-week depth-chart state, no 2026 outcomes',
                'the accepted P4C production and research architecture is not '
                'modified by this freeze'],
        }
        print(f'\n== section 12: freeze ==\n  {", ".join(keep)}')
        print('  Candidate frozen for prospective evaluation; NOT promoted.')
    else:
        OUT['freeze'] = {'candidates': [], 'statement': 'no candidate survived; '
                                                        'nothing is frozen'}
    json.dump(OUT, open(f'{HERE}/p4f_verdict.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> p4f_verdict.json')


if __name__ == '__main__':
    main()
