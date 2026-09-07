"""P2 §6 role-change detection and §7 vacated-opportunity redistribution.

§6 asks the harder question: not "can we label a role change afterwards" but
"can we see elevated role-change probability BEFORE kickoff". Every feature here
is prior-game or same-week-pregame (injury designations, chronology-enforced).

§7 says do not assume one redistribution mechanism serves every opportunity
type. Six rules are tested against six opportunity classes separately.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_a as A

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = A.EVAL


def role_features(r):
    f = [1.0]
    for k, d in (('f_prev_snap', 0.0), ('f_snap_ewma', 0.0),
                 ('f_rate_ewma', 0.0)):
        v = r.get(k); f.append(d if v is None else float(v))
        f.append(1.0 if v is None else 0.0)
    f.append(float(r.get('f_swing') or 0.0))
    f.append(min(r.get('f_n_prior') or 0, 20) / 20.0)
    f.append(1.0 if (r.get('f_n_prior') or 0) < 4 else 0.0)
    f.append(min(r.get('f_consec_missed') or 0, 5) / 5.0)
    f.append(float(r.get('f_team_change') or 0))
    f.append(float(r.get('f_teammate_out') or 0.0))
    f.append(float(r.get('f_teammate_returning') or 0.0))
    s = r.get('f_inj_status')
    for L in ('Questionable', 'Doubtful', 'Out'):
        f.append(1.0 if s == L else 0.0)
    f.append(1.0 if s is None else 0.0)
    d_ = r.get('f_depth')
    f.append(min(d_ or 4, 4) / 4.0); f.append(1.0 if d_ is None else 0.0)
    for p in ('WR', 'TE', 'RB'):
        f.append(1.0 if r.get('position') == p else 0.0)
    return f


def main():
    kick = A.kickoffs(); inj, _ = A.injuries(kick); dep = A.depth()
    rows = A.build(kick, inj, dep)
    POS = ('WR', 'TE', 'RB')

    by_tw = collections.defaultdict(list)
    for r in rows:
        by_tw[(r['team'], r['ord'])].append(r)

    # ---- teammate-availability features, all pregame ----------------------
    for (tm, o), rs in by_tw.items():
        prev = None
        for r in rs:
            pass
    team_ords = collections.defaultdict(list)
    for (tm, o) in by_tw:
        team_ords[tm].append(o)
    for tm in team_ords:
        team_ords[tm].sort()
    for tm, ords in team_ords.items():
        for i, o in enumerate(ords):
            cur = by_tw[(tm, o)]
            prev = by_tw[(tm, ords[i - 1])] if i else []
            prev_by = {x['gsis_id']: x for x in prev}
            # a teammate at the same position who played last week and is
            # designated Out this week -> opportunity is likely to move
            out_now = set()
            for x in cur:
                if x.get('f_inj_status') in ('Out', 'Doubtful'):
                    out_now.add(x['gsis_id'])
            for r in cur:
                same_pos_prev = [x for x in prev
                                 if x['position'] == r['position']
                                 and x['gsis_id'] != r['gsis_id']
                                 and x['appeared']]
                vac = sum((x.get('snap_share') or 0) for x in same_pos_prev
                          if x['gsis_id'] in out_now)
                r['f_teammate_out'] = vac
                back = [x for x in cur
                        if x['position'] == r['position']
                        and x['gsis_id'] != r['gsis_id']
                        and x['gsis_id'] not in prev_by]
                r['f_teammate_returning'] = float(len(back)) / 5.0
                pv = [x.get('snap_share') for x in r.get('_hist', [])] \
                    if '_hist' in r else None
    # swing feature: |snap(t-1) - mean(t-2..t-4)|, prior-only
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        h = [v for v in hist[r['gsis_id']] if v is not None]
        r['f_swing'] = (abs(h[-1] - float(np.mean(h[-4:-1])))
                        if len(h) >= 4 else 0.0)
        hist[r['gsis_id']].append(r.get('snap_share'))

    # THE LABEL P1 USED IS NOT A FORECASTING TARGET, AND THE FIRST RUN OF THIS
    # SCRIPT PROVED IT BY RETURNING AUC = 0.9999.
    #
    # P1's role_change is |snap(t-1) - mean(t-2..t-4)| > 0.20 -- a function of
    # PRIOR games only. It says a role has ALREADY moved, and it is therefore
    # perfectly knowable before kickoff by construction. Asking "can we predict
    # it pregame" is asking whether a pregame quantity can be computed from
    # pregame quantities, and my f_swing feature was literally that expression
    # unthresholded. Not a leak of the future; a tautology, and worthless.
    #
    # The question the directive actually asks is whether a role change IN GAME
    # t can be anticipated. That target has to include game t:
    #     role_change_next = |snap(t) - mean(t-1..t-3)| > 0.20
    # which is not knowable pregame and is what is modelled below. P1's flag
    # survives as a FEATURE (f_swing), which is its honest role.
    hist2 = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        h = [v for v in hist2[r['gsis_id']] if v is not None]
        ss = r.get('snap_share')
        if len(h) >= 3 and ss is not None:
            r['role_change_next'] = (
                1 if abs(ss - float(np.mean(h[-3:]))) > 0.20 else 0)
        else:
            r['role_change_next'] = None
        hist2[r['gsis_id']].append(ss)

    cand = [r for r in rows if r['position'] in POS
            and r.get('role_change_next') is not None
            and (r.get('f_n_prior') or 0) >= 4]
    print(f'role-change-NEXT population: {len(cand)} player-games, '
          f'base rate {np.mean([r["role_change_next"] for r in cand]):.4f}')

    res = {}
    for ev in EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500 or len(te) < 200:
            continue
        ytr = [r['role_change_next'] for r in tr]
        yte = [r['role_change_next'] for r in te]
        base = float(np.mean(ytr))
        m = A.fit_logistic([role_features(r) for r in tr], ytr)
        p = A.predict(m, [role_features(r) for r in te])
        pb = np.full(len(te), base)
        # decision table at the threshold that matches the base rate, so the
        # model is asked to make as many positive calls as there are events.
        k = int(round(base * len(te)))
        thr = float(np.sort(p)[::-1][k - 1]) if k >= 1 else 1.0
        pred = (p >= thr).astype(int)
        y = np.array(yte)
        tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
        res[ev] = {
            'n': len(te), 'base_rate': float(np.mean(yte)),
            'brier_base': A.brier(yte, pb), 'brier_model': A.brier(yte, p),
            'auc': A.auc(yte, p), 'logloss_model': A.logloss(yte, p),
            'logloss_base': A.logloss(yte, pb),
            'threshold': thr, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / (tp + fn) if tp + fn else None,
            'calibration': A.calibration(yte, p),
        }
        print(f' {ev} n={len(te):5d} base={np.mean(yte):.3f} '
              f'brier {A.brier(yte,pb):.4f}->{A.brier(yte,p):.4f} '
              f'AUC={A.auc(yte,p):.4f} | at base-rate threshold: '
              f'TP={tp} FP={fp} FN={fn} '
              f'precision={tp/(tp+fp) if tp+fp else 0:.3f} '
              f'recall={tp/(tp+fn) if tp+fn else 0:.3f}')
    json.dump(res, open(f'{HERE}/role_change_results.json', 'w'), indent=1,
              default=float)
    return rows, by_tw, team_ords


if __name__ == '__main__':
    main()
