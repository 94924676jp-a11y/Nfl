"""P2 §8 cold starts, §11 ablations, §12 leakage negative tests."""
import collections, json, os, random, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_a as A

HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS = {
    'history_rates': list(range(1, 13)),        # prev_appeared..snap_ewma pairs
    'sample_size': [13, 14],                    # n_prior, low-history flag
    'absence': [15, 16],                        # weeks since, consecutive missed
    'team_change': [17],
    'position': [18, 19, 20, 21],
    'injury': [22, 23, 24, 25],                 # only present when use_injury
}


def ablate(X, idx):
    X = np.asarray(X, float).copy()
    for i in idx:
        if i < X.shape[1]:
            X[:, i] = 0.0
    return X


def main():
    kick = A.kickoffs(); inj, _ = A.injuries(kick); dep = A.depth()
    rows = A.build(kick, inj, dep)
    POS = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POS
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y'] = 1 if r['appeared'] else 0
    out = {}

    # ---------------- §11 Stage A ablations --------------------------------
    print('=== §11 Stage A ablations (Brier / AUC, injury seasons only)')
    abl = {}
    for ev in [2022, 2023, 2024]:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        Xtr = [A.featurise(r, True) for r in tr]
        Xte = [A.featurise(r, True) for r in te]
        ytr = [r['y'] for r in tr]; yte = [r['y'] for r in te]
        m = A.fit_logistic(Xtr, ytr); p = A.predict(m, Xte)
        full = {'brier': A.brier(yte, p), 'auc': A.auc(yte, p)}
        row = {'full': full}
        for g, idx in GROUPS.items():
            ma = A.fit_logistic(ablate(Xtr, idx), ytr)
            pa = A.predict(ma, ablate(Xte, idx))
            row[g] = {'brier': A.brier(yte, pa), 'auc': A.auc(yte, pa),
                      'd_brier': A.brier(yte, pa) - full['brier'],
                      'd_auc': A.auc(yte, pa) - full['auc']}
        abl[ev] = row
        line = '  '.join(f'{g}:{row[g]["d_brier"]:+.4f}' for g in GROUPS)
        print(f' {ev} full brier={full["brier"]:.4f} auc={full["auc"]:.4f} | '
              f'removing each group changes brier by: {line}')
    out['stage_a_ablation'] = abl

    # ---------------- §8 cold starts ---------------------------------------
    print('\n=== §8 cold starts: players with < 4 prior games')
    cold = {}
    for ev in A.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev
              and (r.get('f_n_prior') or 0) < 4
              and r.get('snap_share') is not None]
        if len(te) < 60:
            continue
        pos_prior = {}
        tp_prior = {}
        dep_prior = {}
        prev_season = {}
        for r in tr:
            ss = r.get('snap_share')
            if ss is None:
                continue
            pos_prior.setdefault(r['position'], []).append(ss)
            tp_prior.setdefault((r['team'], r['position']), []).append(ss)
            d = r.get('f_depth')
            if d is not None:
                dep_prior.setdefault((r['position'], min(d, 4)), []).append(ss)
            prev_season.setdefault((r['gsis_id'], r['season']), []).append(ss)
        pos_m = {k: float(np.mean(v)) for k, v in pos_prior.items()}
        tp_m = {k: float(np.mean(v)) for k, v in tp_prior.items() if len(v) >= 20}
        dep_m = {k: float(np.mean(v)) for k, v in dep_prior.items() if len(v) >= 20}
        ps_m = {}
        for (pid, s), v in prev_season.items():
            ps_m.setdefault(pid, {})[s] = float(np.mean(v))
        gl = float(np.mean([x for v in pos_prior.values() for x in v]))
        errs = collections.defaultdict(list)
        for r in te:
            y = r['snap_share']
            hist = [x for x in (r.get('_hist') or [])] if False else None
            own = r.get('f_snap_ewma')
            pp = pos_m.get(r['position'], gl)
            tpp = tp_m.get((r['team'], r['position']), pp)
            d = r.get('f_depth')
            dp = dep_m.get((r['position'], min(d, 4)), pp) if d is not None else pp
            prev = ps_m.get(r['gsis_id'], {})
            ls = max([s for s in prev if s < r['season']], default=None)
            psp = prev[ls] if ls is not None else pp
            n = r.get('f_n_prior') or 0
            errs['own_rate_unshrunk'].append(abs(y - (own if own is not None else pp)))
            errs['position_prior'].append(abs(y - pp))
            errs['team_position_prior'].append(abs(y - tpp))
            errs['depth_chart_prior'].append(abs(y - dp))
            errs['prev_season_player'].append(abs(y - psp))
            for k in (2, 4):
                sh = ((n * own + k * pp) / (n + k)) if own is not None else pp
                errs[f'shrink_to_position_k{k}'].append(abs(y - sh))
            shd = ((n * own + 4 * dp) / (n + 4)) if own is not None else dp
            errs['shrink_to_depth_k4'].append(abs(y - shd))
        cold[ev] = {'n': len(te),
                    'mae': {k: float(np.mean(v)) for k, v in errs.items()}}
        best = min(cold[ev]['mae'], key=cold[ev]['mae'].get)
        cold[ev]['best'] = best
        line = '  '.join(f'{k}={v:.4f}' for k, v in
                         sorted(cold[ev]['mae'].items(), key=lambda x: x[1]))
        print(f' {ev} n={len(te):4d} best={best}\n      {line}')
    out['cold_start'] = cold

    # ---------------- §12 leakage negative tests ---------------------------
    print('\n=== §12 leakage negative tests')
    lk = {}
    ev = 2024
    tr = [r for r in cand if r['season'] < ev]
    te = [r for r in cand if r['season'] == ev]
    ytr = [r['y'] for r in tr]; yte = [r['y'] for r in te]
    m = A.fit_logistic([A.featurise(r, True) for r in tr], ytr)
    p = A.predict(m, [A.featurise(r, True) for r in te])
    honest = {'brier': A.brier(yte, p), 'auc': A.auc(yte, p)}
    print(f'  honest Stage A            brier={honest["brier"]:.4f} '
          f'auc={honest["auc"]:.4f}')

    def with_extra(getter, label):
        Xtr = [A.featurise(r, True) + [getter(r)] for r in tr]
        Xte = [A.featurise(r, True) + [getter(r)] for r in te]
        mm = A.fit_logistic(Xtr, ytr); pp = A.predict(mm, Xte)
        d = {'brier': A.brier(yte, pp), 'auc': A.auc(yte, pp),
             'd_brier': A.brier(yte, pp) - honest['brier'],
             'd_auc': A.auc(yte, pp) - honest['auc']}
        flag = 'LEAK DETECTED' if d['d_auc'] > 0.02 else 'no material gain'
        print(f'  + {label:<24} brier={d["brier"]:.4f} auc={d["auc"]:.4f} '
              f'({d["d_auc"]:+.4f}) {flag}')
        lk[label] = d
        return d

    # Deliberate positives: these SHOULD light up, proving the probe works.
    with_extra(lambda r: float(r['appeared']), 'SAME-GAME appeared [seeded]')
    with_extra(lambda r: float(r.get('snap_share') or 0.0),
               'SAME-GAME snap_share [seeded]')
    # Deliberate negatives: pregame quantities, should not light up.
    with_extra(lambda r: float(r.get('f_prev_snap') or 0.0),
               'prev-game snap (pregame)')
    with_extra(lambda r: float(r['week']) / 18.0, 'week number (pregame)')
    out['leakage'] = {'honest': honest, 'probes': lk}

    json.dump(out, open(f'{HERE}/ablation_coldstart_leakage.json', 'w'),
              indent=1, default=float)


if __name__ == '__main__':
    main()
