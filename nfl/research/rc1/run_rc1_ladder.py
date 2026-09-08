"""RC1 sections 5 and 7: the predeclared recoverability ladder, then the
mandatory composition test.

THE LADDER IS CLOSED. Exactly four rungs, fixed in the pre-registration:

    L0  pooled positional empirical value      (no player information)
    L1  chronology-safe shrinkage to the pool  (the baseline's own rule)
    L2  EWMA recency, half-life 2              (inherited from Stage 2)
    L3  shrinkage applied to the EWMA

No feature search. No hyperparameter tuning. Half-life 2 and K = 4 are both
inherited constants, not choices made here.

COMPOSITION IS MANDATORY, per section 7 and per R1: a candidate that improves
its own primitive is NOT a result until it survives substitution into the
receiving-yard simulation with the target machinery held fixed. R1 already
showed a better isolated primitive making the composed simulator worse.

EXPLORATORY. 2022-2025 are heavily mined. Nothing here may be promoted.
"""
import collections, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rc1_lib as L                                            # noqa: E402
import rc1_sim as S                                            # noqa: E402

RUNGS = ('L0', 'L1', 'L2', 'L3')
HL = 2.0


def ewma(vals, hl=HL):
    lam = 0.5 ** (1.0 / hl)
    num = den = 0.0
    w = 1.0
    for v in reversed(vals):
        num += w * v
        den += w
        w *= lam
    return num / den if den > 0 else None


def attach_game_rates(sub):
    """Prior-only, game-level conversion histories. Strict ordinal prefix cut."""
    import bisect
    hist = collections.defaultdict(list)
    hord = collections.defaultdict(list)
    for r in sorted(sub, key=lambda x: (x['ord'], x['team'], x['gsis_id'])):
        pid = r['gsis_id']
        k = bisect.bisect_left(hord[pid], r['ord'])
        past = [x for x in hist[pid][:k] if x['appeared']]
        r['hC_games'] = [x['R'] / x['T'] for x in past if x['T'] > 0]
        r['hV_games'] = [x['Y'] / x['R'] for x in past if x['R'] > 0]
        r['hC_ewma'] = ewma(r['hC_games'])
        r['hV_ewma'] = ewma(r['hV_games'])
        hist[pid].append(r)
        hord[pid].append(r['ord'])
    return sub


def estimator(rung, comp):
    """Return fn(r, pool_value, w) -> estimate. Prior-only by construction."""
    def f(r, pool, w):
        if rung == 'L0':
            return pool
        if comp == 'C':
            own = (r['h_rec'] / r['h_tgt']) if r['h_tgt'] > 0 else None
            ew = r.get('hC_ewma')
        else:
            own = (r['h_yds'] / r['h_rec']) if r['h_rec'] > 0 else None
            ew = r.get('hV_ewma')
        if rung == 'L1':
            return w * own + (1 - w) * pool if own is not None else pool
        if rung == 'L2':
            return ew if ew is not None else pool
        if rung == 'L3':
            return w * ew + (1 - w) * pool if ew is not None else pool
        raise ValueError(rung)
    return f


def main():
    rows, sub = L.load()
    L.attach_prior(sub)
    attach_game_rates(sub)
    OUT = {'label': 'EXPLORATORY -- 2022-2025 are heavily mined; '
                    'diagnosis and recoverability only, never confirmation',
           'rungs': list(RUNGS), 'halflife': HL, 'K_shrink': L.K_SHRINK,
           'primitive': {}, 'composition': {}}

    # ---- primitive level -------------------------------------------------
    print('== primitive level: can conversion be predicted at all? ==')
    for comp in ('C', 'V'):
        OUT['primitive'][comp] = {}
        acc = {rg: {'e': [], 'w': []} for rg in RUNGS}
        for ev in L.EVAL:
            pT, pV, prate = S.pools(sub, ev)
            for r in sub:
                if not L.eligible(r, ev):
                    continue
                if comp == 'C':
                    if r['T'] == 0:
                        continue          # C undefined with no targets
                    truth, wt = r['R'] / r['T'], r['T']
                    pool = prate.get(r['position'], 0.0)
                else:
                    if r['R'] == 0:
                        continue          # V undefined with no receptions
                    truth, wt = r['Y'] / r['R'], r['R']
                    pv = pV.get(r['position'])
                    pool = float(pv.mean()) if pv is not None and len(pv) else 0.0
                w = r['h_n'] / (r['h_n'] + L.K_SHRINK)
                for rg in RUNGS:
                    acc[rg]['e'].append(estimator(rg, comp)(r, pool, w) - truth)
                    acc[rg]['w'].append(wt)
        for rg in RUNGS:
            e = np.array(acc[rg]['e'], float)
            wt = np.array(acc[rg]['w'], float)
            OUT['primitive'][comp][rg] = {
                'n': int(len(e)),
                'mae': float(np.abs(e).mean()),
                'rmse': float(np.sqrt((e * e).mean())),
                'wmae': float((np.abs(e) * wt).sum() / wt.sum()),
                'bias': float(e.mean())}
        b = OUT['primitive'][comp]
        best = min(RUNGS, key=lambda k: b[k]['wmae'])
        OUT['primitive'][comp]['best'] = best
        OUT['primitive'][comp]['gain_vs_L0_pct'] = (
            100.0 * (b['L0']['wmae'] - b[best]['wmae']) / b['L0']['wmae'])
        print(f'  {comp}: n={b["L0"]["n"]}')
        for rg in RUNGS:
            print(f'     {rg}  wMAE {b[rg]["wmae"]:.5f}  MAE {b[rg]["mae"]:.5f}  '
                  f'RMSE {b[rg]["rmse"]:.5f}  bias {b[rg]["bias"]:+.5f}')
        print(f'     best {best}, {OUT["primitive"][comp]["gain_vs_L0_pct"]:+.3f}% '
              f'weighted-MAE against L0')

    # ---- composition -----------------------------------------------------
    print('\n== composition: does a primitive gain survive the simulator? ==')
    print('   target machinery held fixed; substitution is draw-preserving')
    Y, base_c, cand_c = [], [], {}
    bC, bV = OUT['primitive']['C']['best'], OUT['primitive']['V']['best']
    # ('L1','L1') is the CALIBRATION arm: L1 is the baseline's own rule, so
    # routing it through the candidate machinery must land near the baseline.
    # If it does not, the substitution machinery is moving the answer and no
    # other row in this table means anything.
    combos = list(dict.fromkeys(
        [('L1', 'L1'), ('L0', 'L0'), (bC, 'L1'), ('L1', bV), (bC, bV)]))
    for cc, vv in combos:
        cand_c[(cc, vv)] = []
    for ev in L.EVAL:
        rs = [r for r in sub if L.eligible(r, ev)]
        y = np.array([r['Y'] for r in rs], float)
        Y.append(y)
        base_c.append(L.crps_matrix(S.simulate(rs, ev, sub), y))
        for cc, vv in combos:
            cand = {'C': estimator(cc, 'C'), 'V': estimator(vv, 'V')}
            D = S.simulate(rs, ev, sub, candidate=cand)
            cand_c[(cc, vv)].append(L.crps_matrix(D, y))
    Y = np.concatenate(Y)
    base = float(np.concatenate(base_c).mean())
    OUT['composition']['baseline_crps'] = base
    print(f'   accepted baseline CRPS {base:.4f}')
    for cc, vv in combos:
        c = float(np.concatenate(cand_c[(cc, vv)]).mean())
        rel = 100.0 * (base - c) / base
        OUT['composition'][f'C={cc},V={vv}'] = {
            'crps': c, 'rel_pct_vs_baseline': rel,
            'improves': bool(c < base)}
        print(f'   C={cc} V={vv:<3}  CRPS {c:.4f}   {rel:+.4f}% vs baseline'
              f'   {"improves" if c < base else "WORSE"}')
    json.dump(OUT, open(f'{HERE}/rc1_ladder.json', 'w'), indent=1, default=str)
    print('\nwrote rc1_ladder.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
