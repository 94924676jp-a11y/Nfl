"""R1 Block 0: chronology audit, then simple persistence and shrinkage.

No context features. The question at this stage is only whether next-game target
rate persists at all, and whether shrinkage beats raw recency.
"""
import collections, copy, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for p in ('p4c', 'p4e', 's2'):
    sys.path.insert(0, os.path.join(HERE, '..', p))
import r1_lib as L                                             # noqa: E402
import p4c_build as CB                                         # noqa: E402

OUTCOME_FIELDS = ('s_pass_snaps', 'y_pass_snaps', 'pass_snaps', 's_targets',
                  'y_targets', 'targets', 'target_share', 's_snaps', 'y_snaps',
                  'offense_snaps', 'offense_pct', 'appeared', 'did_not_appear',
                  'P_star', 'W_star', 'R_star', 'R_defined')
SHRINK_GRID = (0.5, 1, 2, 3, 5, 8, 12, 20, 35, 60, 100)


def fit_shrink(sub, ev, basis):
    """Empirical-Bayes constant k, fitted on seasons < ev ONLY."""
    tr = [r for r in sub if r['season'] < ev and L.eligible(r)
          and r.get(basis) is not None and r.get('h_pos_mean') is not None]
    if len(tr) < 500:
        return 5.0, 'insufficient prior rows; k defaulted to 5.0'
    best, bk = None, SHRINK_GRID[0]
    for k in SHRINK_GRID:
        e = 0.0
        for r in tr:
            n = r['h_eff_n']
            p = (n * r[basis] + k * r['h_pos_mean']) / (n + k)
            e += (p - r['R_star']) ** 2
        if best is None or e < best:
            best, bk = e, k
    return bk, f'fitted on {len(tr)} rows from seasons < {ev}'


def shrunk(r, basis, k):
    b = r.get(basis)
    pr = r.get('h_pos_mean')
    if pr is None:
        return None
    if b is None:
        return pr
    n = r['h_eff_n']
    return (n * b + k * pr) / (n + k)


BASE = {
    'pos_mean':        lambda r, K: r.get('h_pos_mean'),
    'pos_mean_w':      lambda r, K: r.get('h_pos_mean_w'),
    'last_obs':        lambda r, K: r.get('h_last'),
    'expanding':       lambda r, K: r.get('h_expanding'),
    'expanding_w':     lambda r, K: r.get('h_expanding_w'),
    'ewma_hl2':        lambda r, K: r.get('h_ewma2'),
    'ewma_hl3':        lambda r, K: r.get('h_ewma3'),
    'ewma_hl5':        lambda r, K: r.get('h_ewma5'),
    'ewma_hl8':        lambda r, K: r.get('h_ewma8'),
    'ewma_hl2_w':      lambda r, K: r.get('h_ewma2_w'),
    'ewma_hl3_w':      lambda r, K: r.get('h_ewma3_w'),
    'ewma_hl5_w':      lambda r, K: r.get('h_ewma5_w'),
    'ewma_hl8_w':      lambda r, K: r.get('h_ewma8_w'),
    'prev_season':     lambda r, K: r.get('h_prev_season'),
    'prev_season_w':   lambda r, K: r.get('h_prev_season_w'),
    'eb_shrink_ewma3': lambda r, K: shrunk(r, 'h_ewma3', K['ewma3']),
    'eb_shrink_ewma3_w': lambda r, K: shrunk(r, 'h_ewma3_w', K['ewma3_w']),
    'career_shrink':   lambda r, K: shrunk(r, 'h_expanding', K['expanding']),
    'career_shrink_w': lambda r, K: shrunk(r, 'h_expanding_w', K['expanding_w']),
}


def predict(name, r, K):
    v = BASE[name](r, K)
    if v is None:
        v = r.get('h_pos_mean')          # declared fallback, never a silent 0
    return None if v is None else float(min(max(v, 0.0), 2.0))


def main():
    t0 = time.time()
    rows, sub = L.load()
    L.attach(sub, rows)
    OUT = {'estimand': 'R_star = W_star / P_star, Stage 4 definition unchanged',
           'P_note': ('pass-snap participation, an UPPER BOUND on route '
                      'participation; never routes run')}

    # ---- chronology masking audit ---------------------------------------
    print('== chronology masking audit ==')
    HF = sorted({k for r in sub for k in r if k.startswith('h_')})
    ords = sorted({r['ord'] for r in sub})
    probes = [ords[len(ords) // 4], ords[len(ords) // 2],
              ords[3 * len(ords) // 4], ords[-3]]
    allbad = collections.Counter()
    OUT['masking'] = {}
    for k in probes:
        masked = copy.deepcopy(sub)
        nb = 0
        for r in masked:
            if r['ord'] >= k:
                for f in OUTCOME_FIELDS:
                    if f not in r:
                        continue
                    if f in ('appeared', 'did_not_appear', 'R_defined'):
                        r[f] = 0 if f != 'R_defined' else False
                    elif f.startswith('s_') or f in ('offense_pct',
                                                     'target_share', 'P_star',
                                                     'R_star'):
                        r[f] = None
                    else:
                        r[f] = 0
                nb += 1
            for g in [g for g in r if g.startswith('h_')]:
                del r[g]
        L.attach(masked, rows)
        mm = {(r['team'], r['gsis_id']): r for r in masked if r['ord'] == k}
        bad = collections.Counter()
        n_cmp = 0
        for r in [x for x in sub if x['ord'] == k]:
            m = mm.get((r['team'], r['gsis_id']))
            if m is None:
                continue
            for f in HF:
                a, b = r.get(f), m.get(f)
                n_cmp += 1
                if a is None and b is None:
                    continue
                if isinstance(a, str) or isinstance(b, str):
                    if a != b:
                        bad[f] += 1
                    continue
                if a is None or b is None or abs(float(a) - float(b)) > 1e-12:
                    bad[f] += 1
        allbad.update(bad)
        OUT['masking'][str(k)] = {'rows_blanked': nb, 'values_compared': n_cmp,
                                  'leaking': dict(bad)}
        print(f'  ord >= {k}: {nb} blanked, {n_cmp} compared, '
              f'{"CLEAN" if not bad else "LEAKING " + str(dict(bad))}')
    OUT['chronology'] = 'PASS' if not allbad else f'FAIL {dict(allbad)}'
    print(f'  verdict: {OUT["chronology"]}')
    if allbad:
        print('\nSTOP: DATA_BLOCKED -- chronology audit is not clean.')
        json.dump(OUT, open(f'{HERE}/r1_block0.json', 'w'), indent=1)
        sys.exit(2)

    # ---- shrinkage constants, fitted on prior seasons only ---------------
    Kf = {}
    for ev in L.EVAL:
        Kf[ev] = {}
        for basis in ('h_ewma3', 'h_ewma3_w', 'h_expanding', 'h_expanding_w'):
            k, note = fit_shrink(sub, ev, basis)
            Kf[ev][basis.replace('h_', '')] = k
        Kf[ev]['_note'] = note
    OUT['shrinkage_constants'] = {str(e): Kf[e] for e in L.EVAL}
    print(f'\n== empirical-Bayes k, fitted on prior seasons only ==')
    for ev in L.EVAL:
        print(f'  {ev}: ' + '  '.join(f'{a}={Kf[ev][a]}' for a in
                                      ('ewma3', 'ewma3_w', 'expanding',
                                       'expanding_w')))

    # ---- Block 0 evaluation ---------------------------------------------
    per = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(lambda: ([], []))))
    pool = collections.defaultdict(lambda: collections.defaultdict(
        lambda: ([], [])))
    n_elig = collections.Counter()
    for ev in L.EVAL:
        K = Kf[ev]
        for r in sub:
            if not L.eligible(r, ev):
                continue
            n_elig[(ev, r['position'])] += 1
            y = float(r['R_star'])
            for b in BASE:
                p = predict(b, r, K)
                if p is None:
                    continue
                per[b][r['position']][ev][0].append(p)
                per[b][r['position']][ev][1].append(y)
                pool[b][r['position']][0].append(p)
                pool[b][r['position']][1].append(y)
                pool[b]['ALL'][0].append(p)
                pool[b]['ALL'][1].append(y)
    OUT['eligible'] = {f'{e}/{p}': n for (e, p), n in sorted(n_elig.items())}
    print(f'\n== Block 0: next-game target rate conditional on participation ==')
    for pos in ('WR', 'TE', 'RB', 'ALL'):
        print(f'\n  --- {pos} ---')
        print(f"    {'method':20s} {'MAE':>7s} {'RMSE':>7s} {'r':>7s} {'R2':>7s} "
              f"{'sdrat':>7s} {'bias':>8s}   per-season MAE")
        for b in BASE:
            p, y = pool[b][pos]
            if not y:
                continue
            m = L.metrics(p, y)
            seas = []
            for ev in L.EVAL:
                if pos == 'ALL':
                    pp = sum((per[b][q][ev][0] for q in L.POS), [])
                    yy = sum((per[b][q][ev][1] for q in L.POS), [])
                else:
                    pp, yy = per[b][pos][ev]
                seas.append(L.metrics(pp, yy)['mae'] if yy else float('nan'))
            OUT.setdefault('block0', {}).setdefault(pos, {})[b] = {
                'pooled': m, 'per_season_mae': {str(e): s
                                                for e, s in zip(L.EVAL, seas)}}
            print(f"    {b:20s} {m['mae']:7.4f} {m['rmse']:7.4f} "
                  f"{(m['r'] or float('nan')):7.3f} {(m['r2'] or float('nan')):7.3f} "
                  f"{(m['sd_ratio'] or float('nan')):7.3f} {m['bias']:+8.4f}   "
                  + ' '.join(f'{s:.4f}' for s in seas))
    best = {}
    for pos in ('WR', 'TE', 'RB'):
        cand = {b: OUT['block0'][pos][b]['pooled']['mae']
                for b in OUT['block0'][pos]}
        best[pos] = min(cand, key=cand.get)
    cand = {b: OUT['block0']['ALL'][b]['pooled']['mae'] for b in OUT['block0']['ALL']}
    best['ALL'] = min(cand, key=cand.get)
    OUT['best_block0'] = best
    print(f'\n  best by pooled MAE: {best}')
    json.dump(OUT, open(f'{HERE}/r1_block0.json', 'w'), indent=1)
    print(f'\ndone in {time.time()-t0:.0f}s -> r1_block0.json')


if __name__ == '__main__':
    main()
