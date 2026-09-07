"""P4E: the eight-rule promotion standard, applied verbatim.

The rules and their thresholds were fixed in predeclaration_p4e.md section 12
before any candidate number existed. This scores them. Nothing here is a
judgement call except rule 5, whose margin the pre-declaration did not fix --
that gap is reported as a debt rather than filled in now.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4e_build as B                                          # noqa: E402
import p4e_fit as F                                            # noqa: E402
import p4c_lib as CL                                           # noqa: E402
import run_p4e as R                                            # noqa: E402
import run_p4e_mech as M                                       # noqa: E402
import p4c_build as CB                                         # noqa: E402

CAND = {'E_ABC': ['A', 'B', 'C']}


def pooled_pit(pit_all):
    u = np.concatenate(pit_all)
    return CL.pit_stats(u)


def main():
    t0 = time.time()
    res = json.load(open(f'{HERE}/p4e_results.json'))
    adv = json.load(open(f'{HERE}/p4e_adversarial.json'))
    mech = json.load(open(f'{HERE}/p4e_mechanism.json'))
    rows, vol, pa, sub, D = B.load_all()
    B.attach_features(sub)
    seasons = sorted({r['season'] for r in sub})

    pit = collections.defaultdict(list)
    lowb = collections.defaultdict(list)
    print('== pooled randomised PIT and low-history bias (recomputed) ==')
    for ev in B.EVAL:
        c = B.cell(rows, vol, pa, sub, ev)
        pc = np.array([r.get('g_car_career') or 0.0 for r in c['te']])
        lo = pc < 25
        par = c['par']
        pos = [r['position'] for r in c['te']]
        sysW = {'P4C': c['W_ctrl']}
        for name, blocks in CAND.items():
            fit, pool, _ = F.fit_centre(sub, ev, blocks, seasons)
            sysW[name], mu = F.weights(c, fit, pool, blocks,
                                       np.random.default_rng(CL.SEED + 3034))
            eps2 = CB._resample(pool, pos, c['n'], CL.M_DRAWS,
                                np.random.default_rng(CL.SEED + 3034),
                                np.concatenate(list(pool.values())))
            sysW['X_ABC_mpr'], _ = M.mean_preserving(mu, eps2)
        for name, W in sysW.items():
            Y, _S = B.counts_from_weights(c, W)
            pit[name].append(CL.rpit(Y, c['y'],
                                     np.random.default_rng(CL.SEED + 31)))
            pred = Y.mean(1)
            lowb[name].append((float((pred[lo] - c['y'][lo]).sum()),
                               float(lo.sum()), float(c['y'][lo].sum())))
            del Y, _S
    P = {k: pooled_pit(v) for k, v in pit.items()}
    LB = {k: {'bias': sum(a for a, _n, _y in v) / sum(n for _a, n, _y in v),
              'pred_mean': (sum(a for a, _n, _y in v) + sum(y for _a, _n, y in v))
                           / sum(n for _a, n, _y in v),
              'real_mean': sum(y for _a, _n, y in v) / sum(n for _a, n, _y in v),
              'n': int(sum(n for _a, n, _y in v))}
          for k, v in lowb.items()}
    for k in P:
        print(f"  {k:11s} pooled rPIT chi2 {P[k]['chi2']:7.1f} (crit 27.877)  "
              f"low-history bias {LB[k]['bias']:+.4f} on n={LB[k]['n']} "
              f"(pred {LB[k]['pred_mean']:.3f} vs real {LB[k]['real_mean']:.3f})")

    # ---- the eight rules ------------------------------------------------
    out = {}
    for name in ('E_ABC', 'X_ABC_mpr'):
        src = res['pooled'] if name in res['pooled'] else mech['exploratory_pooled']
        p = src[name]
        base_pit = P['P4C']['chi2']
        cand_pit = P[name]['chi2']
        # rule 5: RB1-RB2 dependence gap to the realised value, per season
        gaps = {}
        if name in res['pooled']:
            for ev in ('2022', '2023', '2024', '2025'):
                for who in ('P4C', name):
                    j = res['seasons'][ev][who]['joint']['RB1-RB2']
                    gaps.setdefault(who, []).append(
                        abs(j['sim_share_corr_within_teamgame']
                            - j['realised_share_corr_across_teamgames']))
        else:
            for ev in ('2022', '2023', '2024', '2025'):
                for who in ('P4C', name):
                    j = mech['exploratory'][who][ev]['joint']['RB1-RB2']
                    gaps.setdefault(who, []).append(
                        abs(j['sim_share_corr_within_teamgame']
                            - j['realised_share_corr_across_teamgames']))
        r5_better = sum(1 for a, b in zip(gaps[name], gaps['P4C']) if a < b)
        rules = {
            '1_pooled_crps_beats_P4C': {
                'pass': p['delta_vs_P4C'] < 0,
                'value': round(p['delta_vs_P4C'], 5)},
            '2_majority_of_seasons': {
                'pass': p.get('seasons_better_than_P4C',
                              p.get('seasons_better')) >= 3,
                'value': p.get('seasons_better_than_P4C', p.get('seasons_better'))},
            '3_pit_not_damaged': {
                'pass': bool(cand_pit <= 1.25 * base_pit and cand_pit < 27.877),
                'value': {'candidate_chi2': round(cand_pit, 2),
                          'control_chi2': round(base_pit, 2),
                          'relative': round(cand_pit / base_pit - 1, 4)}},
            '4_low_history_over_allocation_materially_improved': {
                'pass': abs(LB[name]['bias']) < 0.5 * abs(LB['P4C']['bias']),
                'value': {'candidate_bias': round(LB[name]['bias'], 4),
                          'control_bias': round(LB['P4C']['bias'], 4)}},
            '5_competition_realism_not_worsened': {
                'pass': r5_better >= 2,
                'value': {'seasons_closer_to_realised_RB1_RB2': r5_better,
                          'candidate_gap': [round(g, 4) for g in gaps[name]],
                          'control_gap': [round(g, 4) for g in gaps['P4C']],
                          'caveat': 'the pre-declaration fixed no margin for '
                                    'this rule; "at minimum does not worsen" is '
                                    'scored here as at least half the seasons '
                                    'no further from the realised value, and '
                                    'that reading is a debt, not a pre-declared '
                                    'threshold'}},
            '6_survives_role_change_cohorts': None,
            '7_survives_adversarial': {
                'pass': all(x['state'] != 'FAIL' for x in adv['probes']),
                'value': {'fail': sum(1 for x in adv['probes']
                                      if x['state'] == 'FAIL'),
                          'unresolved': sum(1 for x in adv['probes']
                                            if x['state'] == 'UNRESOLVED'),
                          'guard_deletion_proofs_firing': sum(
                              1 for x in adv['probes']
                              if x['probe'].startswith('GD') and x['state'] == 'PASS')}},
            '8_recovers_5pct_of_allocation_shapley': {
                'pass': p['shapley_fraction_recovered'] >= 0.05,
                'value': round(100 * p['shapley_fraction_recovered'], 2)},
        }
        if name in res['pooled']:
            rc = {}
            for ev in ('2022', '2023', '2024', '2025'):
                a = res['seasons'][ev][name]['cohorts']['role']
                b = res['seasons'][ev]['P4C']['cohorts']['role']
                for lvl in a:
                    rc.setdefault(lvl, []).append(a[lvl]['crps'] - b[lvl]['crps'])
            rules['6_survives_role_change_cohorts'] = {
                'pass': all(np.mean(v) <= 0 for v in rc.values()),
                'value': {k: [round(x, 4) for x in v] for k, v in rc.items()}}
        else:
            rules['6_survives_role_change_cohorts'] = {
                'pass': None,
                'value': 'not computed for the exploratory rung'}
        npass = sum(1 for v in rules.values() if v['pass'] is True)
        out[name] = {'rules': rules, 'rules_passed': npass,
                     'promoted': npass == 8,
                     'eligible': name in res['pooled']}
        print(f'\n== {name} ==')
        for k, v in rules.items():
            mark = {True: 'PASS', False: 'FAIL', None: 'N/A '}[v['pass']]
            print(f'  {mark}  {k}  {v["value"]}')
        print(f'  -> {npass}/8; promoted = {out[name]["promoted"]}'
              + ('' if name in res['pooled'] else
                 '   (EXPLORATORY -- not on the pre-declared ladder, so not '
                 'promotable under this pre-declaration whatever it scores)'))

    out['decision'] = ('NO PROMOTION. P4C system C is retained. P4E is reported '
                       'as negative research under predeclaration_p4e.md '
                       'section 12.')
    out['pooled_pit'] = {k: v for k, v in P.items()}
    out['low_history_pooled'] = LB
    json.dump(out, open(f'{HERE}/p4e_promotion.json', 'w'), indent=1)
    print(f'\n{out["decision"]}')
    print(f'done in {time.time()-t0:.0f}s -> p4e_promotion.json')


if __name__ == '__main__':
    main()
