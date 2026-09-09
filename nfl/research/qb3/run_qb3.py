"""QB3 walk-forward evaluation. Scoring fixed in predeclaration_qb3.md s.7."""
import collections, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qb3_lib as Q

PREREG = 'be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e'


def main():
    t0 = time.time()
    rows = Q.load_qb_panel()
    depth = Q.load_depth()
    frame = Q.build_frame(rows, depth)
    by_tg = collections.defaultdict(list)
    for r in frame:
        by_tg[(r['team'], r['ord'])].append(r)
    OUT = {'artifact': 'QB3_RESULTS', 'prereg_sha256': PREREG,
           'label': 'EXPLORATORY -- 2022-2025 are development data. '
                    'Nothing is promoted.',
           'frame_rows': len(frame), 'team_games': len(by_tg),
           'estimand': 's_dropbacks (QB share of team dropbacks)',
           'seasons': {}}
    pooled = collections.defaultdict(list)
    pooled_cl = []
    ran, skipped = [], []
    for ev in Q.EVAL:
        par = Q.fit(frame, ev)
        te = [k for k in by_tg if k[1] // 100 == ev]
        if not te:
            # AN EMPTY FOLD IS NOT A FOLD. Reported as skipped with its cause,
            # never averaged in as a nan. The depth-chart leaves committed to
            # this repository stop at 2024; nflverse changed to daily snapshots
            # with a different schema for 2025 and stage_a.depth() declines to
            # half-adapt it. That is a DATA boundary, not a result.
            skipped.append({'season': ev,
                            'cause': 'NO_DEPTH_CHART_LEAF_FOR_SEASON',
                            'detail': 'nfl/research/inputs/dc_%d.csv.gz does '
                                      'not exist; committed leaves cover '
                                      '2020-2024' % ev})
            print(f'{ev}: SKIPPED -- NO_DEPTH_CHART_LEAF_FOR_SEASON', flush=True)
            continue
        ran.append(ev)
        sc = collections.defaultdict(list)
        clos = collections.defaultdict(list)
        cl = []
        for k in sorted(te):
            v = by_tg[k]
            qbs = [(r['pid'], r['rank'], r['was_prev_primary']) for r in v]
            S = Q.allocate(par, qbs, m=Q.M_DRAWS, seed=Q.SEED,
                           ordinal=k[1], team=k[0])
            y = np.array([r['share'] for r in v])
            # QB3
            for i, r in enumerate(v):
                sc['QB3'].append(Q.crps_sample(S[i], y[i]))
                cl.append(f'{k[0]}_{k[1]}')
            clos['QB3'].append(float(np.abs(S.sum(0) - 1.0).max()))
            # baselines: point forecasts, so CRPS = |f - y|
            b0 = np.array([float(r['was_prev_primary']) for r in v])
            b1 = np.array([float(r['rank'] == 1) for r in v])
            b2 = np.ones(len(v))
            for nm, b in (('B0_incumbent', b0), ('B1_depth_chart', b1),
                          ('B2_current_production', b2)):
                sc[nm].extend(np.abs(b - y).tolist())
                clos[nm].append(float(abs(b.sum() - 1.0)))
        row = {'n_qb_games': len(sc['QB3']), 'n_team_games': len(te)}
        for nm in ('QB3', 'B0_incumbent', 'B1_depth_chart',
                   'B2_current_production'):
            row[nm] = {'crps': float(np.mean(sc[nm])),
                       'closure_error_mean': float(np.mean(clos[nm])),
                       'closure_violation_rate': float(
                           np.mean(np.asarray(clos[nm]) > 1e-6))}
            pooled[nm].extend(sc[nm])
        pooled_cl.extend(cl)
        OUT['seasons'][str(ev)] = row
        print(f'{ev}: n={row["n_qb_games"]:5d} ' + '  '.join(
            f'{nm.split("_")[0]} {row[nm]["crps"]:.4f}'
            for nm in ('QB3', 'B0_incumbent', 'B1_depth_chart',
                       'B2_current_production')), flush=True)
    OUT['evaluation_seasons_run'] = ran
    OUT['evaluation_seasons_skipped'] = skipped
    if not ran:
        raise SystemExit('NO_EVALUATION_FOLD_RAN: refusing to emit a result')
    OUT['pooled'] = {nm: float(np.mean(v)) for nm, v in pooled.items()}
    q3 = np.asarray(pooled['QB3'])
    OUT['contrasts'] = {}
    for nm in ('B0_incumbent', 'B1_depth_chart', 'B2_current_production'):
        d = q3 - np.asarray(pooled[nm])            # negative = QB3 better
        lo, hi = Q.clustered_ci(d, pooled_cl)
        cons = sum(1 for ev in ran
                   if OUT['seasons'][str(ev)]['QB3']['crps']
                   < OUT['seasons'][str(ev)][nm]['crps'])
        OUT['contrasts'][f'QB3_minus_{nm}'] = {
            'mean_crps_diff': float(d.mean()),
            'team_game_clustered_ci95': [lo, hi],
            'ci_excludes_zero': bool(hi < 0 or lo > 0),
            'seasons_QB3_better': f'{cons} of {len(ran)} folds that ran',
            'meets_predeclared_rule': bool(d.mean() < 0 and hi < 0 and cons >= 3),
            'rule_note': 'the predeclared rule asked for consistency in at '
                         'least 3 of 4 evaluation seasons. Only %d folds could '
                         'run -- see evaluation_seasons_skipped -- so "3 of 4" '
                         'is not claimed and the count is stated against the '
                         'folds that exist.' % len(ran),
        }
    OUT['runtime_s'] = round(time.time() - t0, 1)
    json.dump(OUT, open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     'qb3_results.json'), 'w'), indent=1)
    print('\npooled CRPS:', {k: round(v, 5) for k, v in OUT['pooled'].items()})
    print('\ncontrasts (negative = QB3 better):')
    for k, v in OUT['contrasts'].items():
        print(f'  {k}: {v["mean_crps_diff"]:+.5f} '
              f'CI [{v["team_game_clustered_ci95"][0]:+.5f}, '
              f'{v["team_game_clustered_ci95"][1]:+.5f}] '
              f'{v["seasons_QB3_better"]} seasons  '
              f'RULE {"MET" if v["meets_predeclared_rule"] else "NOT MET"}')
    print('\nclosure (fraction of team-games whose shares do not sum to 1):')
    for nm in ('QB3', 'B0_incumbent', 'B1_depth_chart', 'B2_current_production'):
        r = np.mean([OUT['seasons'][str(e)][nm]['closure_violation_rate']
                     for e in ran])
        print(f'  {nm:24s} {r:.4f}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
