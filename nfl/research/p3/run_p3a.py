"""P3 Track A: does better availability information improve Stage A? (Q1)

Panel is the IDENTIFIER-REPAIRED one. Every arm is trained on prior seasons and
tested chronologically. Ablation removes a feature BLOCK rather than zeroing a
column, so a removed group cannot leave its intercept behind.
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_features as F
import stage_a as A
import model as M

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.environ.get('P3_PANEL', 'panel_p3.csv')


def load_enriched():
    M.SP = os.path.abspath(os.path.join(HERE, '..', 'p1'))
    import csv
    rows = []
    for r in csv.DictReader(open(f'{M.SP}/{PANEL}')):
        r['season'] = int(r['season']); r['week'] = int(r['week'])
        for k in ('targets', 'carries', 'rz_targets', 'rz_carries',
                  'gl_carries', 'third_targets', 'pass_snaps', 'team_plays',
                  'team_dropbacks', 'team_pass_att', 'team_rush_att',
                  'team_rz_rush', 'team_gl_rush', 'team_dropbacks_part',
                  'dropbacks_as_passer', 'pass_att_as_passer'):
            r[k] = int(float(r.get(k) or 0))
        for k in ('scrambles', 'designed_rushes'):
            r[k] = int(float(r.get(k) or 0))
        r['offense_pct'] = float(r['offense_pct']) if r['offense_pct'] else None
        r['ord'] = r['season'] * 100 + r['week']
        rows.append(r)
    rows, _ = M.extend_with_zeros(rows)
    rows = M.add_shares(rows)
    rows = M.role_flag(rows)
    kick = A.kickoffs(); inj, st = A.injuries(kick); dep = A.depth()
    # reuse P2's per-row feature build
    hist = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: x['ord']):
        pid = r['gsis_id']; past = hist[pid]
        r['appeared'] = 1 if (r.get('did_not_appear') == 0) else 0
        ap = [x['appeared'] for x in past]
        sh = [x.get('snap_share') for x in past]
        r['f_prev_appeared'] = ap[-1] if ap else None
        r['f_rate3'] = float(np.mean(ap[-3:])) if ap else None
        r['f_rate5'] = float(np.mean(ap[-5:])) if ap else None
        w = 0.5 ** (1 / 3)
        def ew(v):
            if not v:
                return None
            n = d = 0.0; ww = 1.0
            for x in reversed(v):
                n += ww * x; d += ww; ww *= w
            return n / d
        r['f_rate_ewma'] = ew(ap)
        r['f_n_prior'] = len(past)
        r['f_weeks_since_appear'] = next(
            (i + 1 for i, x in enumerate(reversed(past)) if x['appeared']), None)
        pv = [x for x in sh if x is not None]
        r['f_prev_snap'] = pv[-1] if pv else None
        r['f_snap_ewma'] = ew(pv)
        r['f_team_change'] = 1 if past and past[-1]['team'] != r['team'] else 0
        r['f_consec_missed'] = 0
        for x in reversed(past):
            if x['appeared']:
                break
            r['f_consec_missed'] += 1
        d_ = inj.get((r['season'], r['week'], r['team'], pid))
        r['f_inj_status'] = d_['report_status'] if d_ else None
        r['f_inj_practice'] = d_['practice_status'] if d_ else None
        r['f_inj_available'] = 1 if d_ is not None else 0
        r['f_depth'] = dep.get((r['season'], r['week'], r['team'], pid))
        hist[pid].append(r)
    rows = F.enrich(rows, inj)
    return rows, st


def main():
    rows, st = load_enriched()
    POS = ('WR', 'TE', 'RB', 'QB')
    cand = [r for r in rows if r['position'] in POS
            and (r.get('f_n_prior') or 0) >= 1]
    for r in cand:
        r['y'] = 1 if r['appeared'] else 0
    print(f'panel={PANEL}  candidates={len(cand)}  '
          f'base={np.mean([r["y"] for r in cand]):.4f}')
    iq = collections.Counter(r['info_quality'] for r in cand)
    print('information quality:', dict(iq))

    ALL = set(F.FEATURE_GROUPS) - {'p2_base'}
    out = {'info_quality_counts': dict(iq), 'seasons': {}}
    for ev in A.EVAL:
        tr = [r for r in cand if r['season'] < ev]
        te = [r for r in cand if r['season'] == ev]
        if len(tr) < 500:
            continue
        ui = ev <= 2024
        ytr = [r['y'] for r in tr]; yte = [r['y'] for r in te]
        res = {}
        # P2 baseline
        m = A.fit_logistic([A.featurise(r, ui) for r in tr], ytr)
        p = A.predict(m, [A.featurise(r, ui) for r in te])
        res['P2_baseline'] = {'brier': A.brier(yte, p), 'auc': A.auc(yte, p),
                              'logloss': A.logloss(yte, p)}
        # P3 full
        mf = A.fit_logistic([F.featurise_p3(r, ui, ALL) for r in tr], ytr)
        pf = A.predict(mf, [F.featurise_p3(r, ui, ALL) for r in te])
        res['P3_full'] = {'brier': A.brier(yte, pf), 'auc': A.auc(yte, pf),
                          'logloss': A.logloss(yte, pf)}
        # leave-one-group-out
        for g in sorted(ALL):
            keep = ALL - {g}
            mg = A.fit_logistic([F.featurise_p3(r, ui, keep) for r in tr], ytr)
            pg = A.predict(mg, [F.featurise_p3(r, ui, keep) for r in te])
            res[f'minus_{g}'] = {
                'brier': A.brier(yte, pg), 'auc': A.auc(yte, pg),
                'd_brier': A.brier(yte, pg) - res['P3_full']['brier'],
                'd_auc': A.auc(yte, pg) - res['P3_full']['auc']}
        # stratified by information quality
        strat = {}
        for q in ('HIGH', 'MEDIUM', 'LOW'):
            idx = [i for i, r in enumerate(te) if r['info_quality'] == q]
            if len(idx) >= 100:
                yq = [yte[i] for i in idx]
                strat[q] = {'n': len(idx),
                            'P2_brier': A.brier(yq, [p[i] for i in idx]),
                            'P3_brier': A.brier(yq, [pf[i] for i in idx]),
                            'P3_auc': A.auc(yq, [pf[i] for i in idx])}
        res['by_info_quality'] = strat
        res['calibration_P3'] = A.calibration(yte, pf)
        res['n'] = len(te)
        out['seasons'][ev] = res
        print(f' {ev} n={len(te):6d} inj={ui} '
              f'P2 brier={res["P2_baseline"]["brier"]:.4f}/auc={res["P2_baseline"]["auc"]:.4f} '
              f'-> P3 brier={res["P3_full"]["brier"]:.4f}/auc={res["P3_full"]["auc"]:.4f}')
        print('      leave-one-out d_brier: ' + '  '.join(
            f'{g}:{res[f"minus_{g}"]["d_brier"]:+.4f}' for g in sorted(ALL)))
        if strat:
            print('      by info quality: ' + '  '.join(
                f'{q}(n={v["n"]}) {v["P2_brier"]:.4f}->{v["P3_brier"]:.4f}'
                for q, v in strat.items()))
    json.dump(out, open(f'{HERE}/p3_stage_a.json', 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
